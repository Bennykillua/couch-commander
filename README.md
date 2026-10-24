# Couch Commander 🦥

Control YouTube from the couch with your voice. No remote, no getting up.

Say **"Hey Jarvis"**, wait for the chime, then say what you want, in English or Pidgin:

- "abeg go back small" → rewinds 15s
- "I no hear wetin she talk" → rewinds 10s
- "make am louder" → volume up
- "skip this one" → next video

A little pixel sloth pops up in the corner to show it heard you.



## Why it runs fully on my Mac

An always-on mic in your living room only makes sense if nothing leaves the room. Every piece runs locally:

| Step | Open-source piece |
|---|---|
| Wake word | openWakeWord ("hey jarvis") |
| Knowing when you stopped talking | webrtcvad |
| Speech to text | Whisper (mlx-whisper, small) |
| Understanding the command | Gemma 4 E2B via Ollama |
| Controlling YouTube | AppleScript → Chrome |

No account, no API key, no cloud.

## How well the brain works

I tested 30 phrases (22 the model had never seen as examples), on two local models:

| Model | Unseen phrases | Overall | Avg. time |
|---|---|---|---|
| gemma4:e2b (thinking off) | 20/22 (91%) | 28/30 (93%) | ~190 ms |
| gemma3:4b | 18/22 (82%) | 26/30 (87%) | ~330 ms |

Turning off Gemma 4's thinking mode took it from ~1,490 ms to ~190 ms. When Gemma 4 is unsure, it does nothing. Gemma 3's mistakes were actions, like pausing on "tell me a joke". Full table in `brain_results.txt`.

## Setup (macOS, Apple Silicon)

1. Install [Ollama](https://ollama.com) and run `ollama pull gemma4:e2b`
2. In Chrome: **View → Developer → Allow JavaScript from Apple Events**
3. System Settings → Privacy & Security: give **Terminal** access to **Microphone** and **Accessibility**
4. Then:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Click the sloth in the menu bar → **Start listening**. The first run downloads the Whisper and wake-word models.

## Files

- `app.py`: menu bar app, starts the listener
- `listen.py`: wake word → record → transcribe → parse → act
- `brain.py`: Gemma turns a sentence into one command (or `none`)
- `controls.py`: controls the YouTube player in Chrome
- `overlay.py`: the sloth toast
- `test_brain.py`: the model benchmark

## Limits

- Works with YouTube in Chrome on macOS only.
- Pidgin is harder for the small Whisper model than plain English.
- The movie's own dialogue can occasionally sound like a command. The wake word and the "do nothing when unsure" rule keep this rare.

You can read the [article here: Control YouTube from the couch with your voice. No remote, no getting up](https://dev.to/bennykillua/im-not-getting-up-a-voice-remote-for-youtube-that-runs-fully-offline-and-understands-pidgin-1028)

MIT licensed.
