import time

from controls import (
    forward,
    fullscreen_toggle,
    next_video,
    play_pause,
    rewind,
    volume_down,
    volume_up,
)


def main() -> None:
    tests = [
        ("play_pause()", play_pause),
        ("rewind(10)", lambda: rewind(10)),
        ("forward(10)", lambda: forward(10)),
        ("volume_up()", volume_up),
        ("volume_down()", volume_down),
        ("next_video()", next_video),
        ("fullscreen_toggle()", fullscreen_toggle),
    ]
    expected_results = [
        "The video pauses or resumes.",
        "Playback moves back 10 seconds.",
        "Playback moves forward 10 seconds.",
        "The video volume increases by 10%.",
        "The video volume decreases by 10%.",
        "YouTube starts the next video, if one is queued.",
        "The video enters or exits fullscreen.",
    ]

    for index, ((name, control), expected) in enumerate(zip(tests, expected_results)):
        print(f"Running {name}: {expected}", flush=True)
        control()
        if index < len(tests) - 1:
            time.sleep(5)


if __name__ == "__main__":
    main()