import math
import subprocess


def _run_osascript(script: str) -> str | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        message = getattr(error, "stderr", "") or str(error)
        print(f"Chrome control failed: {message.strip()}")
        return None
    return result.stdout.strip()


def _execute_youtube_js(javascript: str) -> bool:
    guarded_javascript = (
        "(() => { const host = location.hostname.toLowerCase(); "
        "if (host !== 'youtube.com' && !host.endsWith('.youtube.com') && host !== 'youtu.be') "
        f"return 'NO_YOUTUBE'; return {javascript}; }})()"
    )
    escaped_javascript = guarded_javascript.replace("\\", "\\\\").replace('"', '\\"')
    result = _run_osascript(f'''tell application "Google Chrome"
    activate
    if (count of windows) is 0 then return "NO_CHROME_TAB"
    return execute active tab of front window javascript "{escaped_javascript}"
end tell''')
    if result is None:
        return False
    if result == "NO_CHROME_TAB":
        print("No active Chrome tab found. Open a YouTube video in Chrome and try again.")
        return False
    if result == "NO_YOUTUBE":
        print("The active Chrome tab is not YouTube. Open a YouTube video in Chrome and try again.")
        return False
    if result == "NO_VIDEO":
        print("No video element found in the active YouTube tab.")
        return False
    if result.startswith("ERROR:"):
        print(f"YouTube control failed: {result[6:]}")
        return False
    return result == "OK"


def _video_action(action: str) -> bool:
    return _execute_youtube_js(
        f"(() => {{ const video = document.querySelector('video'); "
        f"if (!video) return 'NO_VIDEO'; {action} return 'OK'; }})()"
    )


def play_pause() -> bool:
    return _video_action("if (video.paused) video.play(); else video.pause();")


def rewind(seconds: float) -> bool:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("seconds must be a non-negative finite number")
    return _video_action(f"video.currentTime = Math.max(0, video.currentTime - {float(seconds)});")


def forward(seconds: float) -> bool:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("seconds must be a non-negative finite number")
    return _video_action(
        f"video.currentTime = Math.min(video.duration || Infinity, video.currentTime + {float(seconds)});"
    )


def volume_up() -> bool:
    return _video_action("video.volume = Math.min(1, video.volume + 0.1);")


def volume_down() -> bool:
    return _video_action("video.volume = Math.max(0, video.volume - 0.1);")


def get_video_volume() -> float | None:
    javascript = (
        "(() => { const host = location.hostname.toLowerCase(); "
        "if (host !== 'youtube.com' && !host.endsWith('.youtube.com') && host !== 'youtu.be') "
        "return 'NO_YOUTUBE'; const video = document.querySelector('video'); "
        "if (!video) return 'NO_VIDEO'; return String(video.volume); })()"
    )
    escaped_javascript = javascript.replace("\\", "\\\\").replace('"', '\\"')
    result = _run_osascript(f'''tell application "Google Chrome"
    activate
    if (count of windows) is 0 then return "NO_CHROME_TAB"
    return execute active tab of front window javascript "{escaped_javascript}"
end tell''')
    try:
        volume = float(result) if result is not None else None
    except ValueError:
        volume = None
    if volume is None or not math.isfinite(volume) or not 0 <= volume <= 1:
        print("Could not read the active YouTube video's volume.")
        return None
    return volume


def set_video_volume(volume: float) -> bool:
    if not math.isfinite(volume):
        raise ValueError("volume must be finite")
    volume = min(1.0, max(0.0, volume))
    javascript = (
        "(() => { const host = location.hostname.toLowerCase(); "
        "if (host !== 'youtube.com' && !host.endsWith('.youtube.com') && host !== 'youtu.be') "
        "return 'NO_YOUTUBE'; const video = document.querySelector('video'); "
        "if (!video) return 'NO_VIDEO'; "
        f"video.volume = {volume}; return 'OK'; }})()"
    )
    escaped_javascript = javascript.replace("\\", "\\\\").replace('"', '\\"')
    result = _run_osascript(f'''tell application "Google Chrome"
    activate
    if (count of windows) is 0 then return "NO_CHROME_TAB"
    return execute active tab of front window javascript "{escaped_javascript}"
end tell''')
    return result == "OK"


def next_video() -> bool:
    return _execute_youtube_js(
        "(() => { const button = document.querySelector('.ytp-next-button'); "
        "if (!button) return 'ERROR:YouTube next-video button is unavailable'; "
        "button.click(); return 'OK'; })()"
    )


def fullscreen_toggle() -> bool:
    script = (
        'tell application "Google Chrome"\n'
        '    activate\n'
        '    if (count of windows) is 0 then return "NO_CHROME_TAB"\n'
        '    set result to execute active tab of front window javascript '
        '"(() => { const host = location.hostname.toLowerCase(); '
        "if (host !== 'youtube.com' && !host.endsWith('.youtube.com') && host !== 'youtu.be') "
        "return 'NO_YOUTUBE'; if (!document.querySelector('video')) return 'NO_VIDEO'; "
        'if (document.activeElement) document.activeElement.blur(); '
        "document.body.focus(); return 'OK'; })()\n"
        '    if result is not "OK" then return result\n'
        'end tell\n'
        'delay 0.2\n'
        'tell application "System Events" to keystroke "f"\n'
        'return "OK"'
    )
    result = _run_osascript(script)
    if result == "NO_CHROME_TAB":
        print("No active Chrome tab found. Open a YouTube video in Chrome and try again.")
        return False
    if result == "NO_YOUTUBE":
        print("The active Chrome tab is not YouTube. Open a YouTube video in Chrome and try again.")
        return False
    if result == "NO_VIDEO":
        print("No video element found in the active YouTube tab.")
        return False
    return result == "OK"