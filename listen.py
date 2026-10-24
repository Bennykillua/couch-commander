import argparse
import queue
import sys
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Callable

import mlx_whisper
import numpy as np
import sounddevice as sd
import webrtcvad
from openwakeword.model import Model
from openwakeword.utils import download_models

import controls
from brain import parse


SAMPLE_RATE = 16_000
FRAME_SAMPLES = 1_280
VAD_FRAME_SAMPLES = 320
VAD_FRAME_SECONDS = VAD_FRAME_SAMPLES / SAMPLE_RATE
SILENCE_SECONDS = 0.7
MIN_SPEECH_SECONDS = 0.5
SPEECH_START_TIMEOUT = 2.5
MAX_SPEECH_SECONDS = 5.0
PRE_ROLL_FRAMES = 5
WHISPER_WARMUP_SECONDS = 4
WAKE_THRESHOLD = 0.3
COOLDOWN_SECONDS = 2
DEBUG_UPDATE_SECONDS = 0.2
WHISPER_MODEL = "mlx-community/whisper-small.en-mlx"
ASSET_DIR = Path(__file__).parent / "couch-commander-assets"


def play_wav(path: Path, wait: bool = True) -> None:
    with wave.open(str(path), "rb") as audio_file:
        channels = audio_file.getnchannels()
        sample_width = audio_file.getsampwidth()
        sample_rate = audio_file.getframerate()
        frames = audio_file.readframes(audio_file.getnframes())

    if sample_width != 2:
        raise ValueError(f"Expected 16-bit PCM audio in {path}")
    samples = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels)
    sd.play(samples, samplerate=sample_rate)
    if wait:
        sd.wait()


def record_command(
    input_device: int,
    stop_event: threading.Event,
) -> np.ndarray | None:
    vad = webrtcvad.Vad(2)
    pre_roll: deque[bytes] = deque(maxlen=PRE_ROLL_FRAMES)
    recorded_frames: list[bytes] = []
    recording_started = time.monotonic()
    speech_started: float | None = None
    silence_started: float | None = None

    with sd.InputStream(
        device=input_device,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=VAD_FRAME_SAMPLES,
    ) as stream:
        while not stop_event.is_set():
            audio, overflowed = stream.read(VAD_FRAME_SAMPLES)
            if overflowed:
                print("Microphone input overflow during command recording.", flush=True)
            frame = audio.reshape(-1).tobytes()
            now = time.monotonic()
            speech_detected = vad.is_speech(frame, SAMPLE_RATE)

            if speech_started is None:
                pre_roll.append(frame)
                if speech_detected:
                    speech_started = now
                    recorded_frames.extend(pre_roll)
                    pre_roll.clear()
                elif now - recording_started >= SPEECH_START_TIMEOUT:
                    return None
                continue

            recorded_frames.append(frame)
            if speech_detected:
                silence_started = None
            elif silence_started is None:
                silence_started = now

            captured_duration = len(recorded_frames) * VAD_FRAME_SECONDS
            if captured_duration >= MAX_SPEECH_SECONDS:
                break
            if (
                silence_started is not None
                and captured_duration >= MIN_SPEECH_SECONDS
                and now - silence_started >= SILENCE_SECONDS
            ):
                break

    if stop_event.is_set() or not recorded_frames:
        return None
    pcm = np.frombuffer(b"".join(recorded_frames), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


def transcribe(recording: np.ndarray) -> str:
    result = mlx_whisper.transcribe(
        recording,
        path_or_hf_repo=WHISPER_MODEL,
        language="en",
        task="transcribe",
        temperature=0.0,
    )
    return result.get("text", "").strip()


def run_command(command: str, value: object) -> bool:
    if command == "play_pause":
        return controls.play_pause()
    if command == "rewind" and isinstance(value, (int, float)):
        return controls.rewind(value)
    if command == "forward" and isinstance(value, (int, float)):
        return controls.forward(value)
    if command == "volume_up":
        return controls.volume_up()
    if command == "volume_down":
        return controls.volume_down()
    if command == "next_video":
        return controls.next_video()
    if command == "fullscreen_toggle":
        return controls.fullscreen_toggle()
    return False


def _notify(on_state: Callable[..., None] | None, state: str, **details: object) -> None:
    if on_state is not None:
        on_state(state, **details)


def _command_title(command: str, value: object) -> str:
    if command == "rewind":
        return f"Rewinding {value:g}s" if isinstance(value, (int, float)) else "Rewinding"
    if command == "forward":
        return f"Forward {value:g}s" if isinstance(value, (int, float)) else "Skipping forward"
    return {
        "play_pause": "Playback toggled",
        "volume_up": "Volume up",
        "volume_down": "Volume down",
        "next_video": "Next video",
        "fullscreen_toggle": "Fullscreen toggled",
    }.get(command, "Command complete")


def handle_wake_word(
    wake_time: float,
    input_device: int,
    stop_event: threading.Event,
    on_state: Callable[..., None] | None = None,
) -> None:
    print(f"Wake word detected (+{time.perf_counter() - wake_time:.2f}s)", flush=True)
    _notify(on_state, "wake")
    play_wav(ASSET_DIR / "listen.wav")

    old_volume = controls.get_video_volume()
    volume_lowered = old_volume is not None and controls.set_video_volume(0.2)
    record_started = time.perf_counter()
    try:
        recording = record_command(input_device, stop_event)
    finally:
        if volume_lowered and old_volume is not None:
            controls.set_video_volume(old_volume)
    print(
        f"Recording ended (+{time.perf_counter() - record_started:.2f}s)",
        flush=True,
    )
    if recording is None:
        print("No speech detected; cancelled quietly.", flush=True)
        _notify(on_state, "cancelled")
        return
    if stop_event.is_set():
        return

    transcription_started = time.perf_counter()
    text = transcribe(recording)
    print(
        f'Transcription: "{text}" '
        f"(+{time.perf_counter() - transcription_started:.2f}s)",
        flush=True,
    )

    parse_started = time.perf_counter()
    result = parse(text)
    command = result.get("command", "none")
    value = result.get("value")
    print(
        f"Parsed command: {command}"
        + (f" ({value}s)" if value is not None else "")
        + f" (+{time.perf_counter() - parse_started:.2f}s)",
        flush=True,
    )

    if command == "none":
        _notify(on_state, "none", text=text)
        return
    if stop_event.is_set():
        return

    command_started = time.perf_counter()
    if run_command(str(command), value):
        command_elapsed = time.perf_counter() - command_started
        _notify(
            on_state,
            "done",
            title=_command_title(str(command), value),
            text=text,
        )
        play_wav(ASSET_DIR / "done.wav", wait=False)
        print(
            f"Done (+{command_elapsed:.2f}s; chime playing)",
            flush=True,
        )


def _input_devices() -> tuple[list[tuple[int, dict]], int]:
    devices = sd.query_devices()
    input_devices = [
        (index, device)
        for index, device in enumerate(devices)
        if device["max_input_channels"] > 0
    ]
    default_input = sd.default.device[0]
    if default_input is None or default_input < 0:
        if not input_devices:
            raise RuntimeError("No microphone input devices are available.")
        default_input = input_devices[0][0]
    return input_devices, int(default_input)


def _wake_input_devices(
    input_devices: list[tuple[int, dict]], default_input: int
) -> list[tuple[int, dict]]:
    selected = [(default_input, device) for index, device in input_devices if index == default_input]
    selected.extend(
        (index, device)
        for index, device in input_devices
        if index != default_input and "iphone" in device["name"].lower()
    )
    return selected


def _print_input_devices(input_devices: list[tuple[int, dict]], selected: int) -> None:
    print("Input devices:")
    for index, device in input_devices:
        marker = " (using)" if index == selected else ""
        print(f"  {index}: {device['name']}{marker}")
    print(
        f"Using input {selected}: {sd.query_devices(selected)['name']} "
        f"at {SAMPLE_RATE} Hz, mono, int16, {FRAME_SAMPLES}-sample chunks.",
        flush=True,
    )


def _print_wake_devices(input_devices: list[tuple[int, dict]]) -> None:
    names = ", ".join(f"{device['name']} ({index})" for index, device in input_devices)
    print(f"Listening for wake word on: {names}", flush=True)


def _print_debug_meter(audio: np.ndarray, score: float) -> None:
    rms = float(np.sqrt(np.mean(np.square(audio.astype(np.float32) / 32768.0))))
    bars = min(10, round(rms * 40))
    meter = "█" * bars + "░" * (10 - bars)
    sys.stdout.write(f"\rmic: {meter} {rms:.2f} | jarvis: {score:.2f}   ")
    sys.stdout.flush()


def listen_forever(
    debug: bool = False,
    stop_event: threading.Event | None = None,
    on_state: Callable[..., None] | None = None,
) -> None:
    stop_event = stop_event or threading.Event()
    input_devices, default_input = _input_devices()
    wake_devices = _wake_input_devices(input_devices, default_input)
    if not wake_devices:
        raise RuntimeError("No microphone input devices are available.")
    _print_input_devices(input_devices, default_input)
    _print_wake_devices(wake_devices)

    download_models()
    wake_models = {
        device_index: Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx",
        )
        for device_index, _ in wake_devices
    }
    whisper_warmup_started = time.perf_counter()
    transcribe(np.zeros(SAMPLE_RATE * WHISPER_WARMUP_SECONDS, dtype=np.float32))
    print(
        f"Ready (models loaded; Whisper warm-up "
        f"{time.perf_counter() - whisper_warmup_started:.2f}s).",
        flush=True,
    )
    print('Listening for "Hey Jarvis". Press Ctrl+C to stop.', flush=True)

    while not stop_event.is_set():
        audio_queue: queue.Queue = queue.Queue(maxsize=8)
        streams = []

        def make_callback(device_index):
            def enqueue_audio(indata, frames, callback_time, status):
                if status:
                    print(f"Microphone {device_index}: {status}", flush=True)
                try:
                    audio_queue.put_nowait((device_index, indata.copy()))
                except queue.Full:
                    try:
                        audio_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        audio_queue.put_nowait((device_index, indata.copy()))
                    except queue.Full:
                        pass
            return enqueue_audio

        try:
            for device_index, _ in wake_devices:
                stream = sd.InputStream(
                    device=device_index,
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="int16",
                    blocksize=FRAME_SAMPLES,
                    callback=make_callback(device_index),
                )
                stream.start()
                streams.append(stream)

            next_meter_update = 0.0
            while not stop_event.is_set():
                try:
                    device_index, audio = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                wake_model = wake_models[device_index]
                scores = wake_model.predict(audio.reshape(-1))
                wake_score = float(scores.get("hey_jarvis", 0.0))
                now = time.monotonic()
                if debug and now >= next_meter_update:
                    _print_debug_meter(audio, wake_score)
                    next_meter_update = now + DEBUG_UPDATE_SECONDS
                if wake_score >= WAKE_THRESHOLD:
                    if debug:
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                    wake_time = time.perf_counter()
                    break
        finally:
            for stream in streams:
                stream.stop()
                stream.close()

        if stop_event.is_set():
            break
        try:
            handle_wake_word(wake_time, device_index, stop_event, on_state)
        except Exception as error:
            print(f"Voice command failed: {error}", flush=True)
        finally:
            for wake_model in wake_models.values():
                wake_model.reset()
        if stop_event.wait(COOLDOWN_SECONDS):
            break


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(description="Couch Commander voice control")
    argument_parser.add_argument(
        "--debug",
        action="store_true",
        help="show microphone level and wake-word score while listening",
    )
    arguments = argument_parser.parse_args()
    try:
        listen_forever(debug=arguments.debug)
    except KeyboardInterrupt:
        print("\nVoice control stopped.", flush=True)