import json
import math
from urllib.request import Request, urlopen


MODEL = "gemma4:e2b"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
COMMANDS = (
    "play_pause",
    "rewind",
    "forward",
    "volume_up",
    "volume_down",
    "next_video",
    "fullscreen_toggle",
    "none",
)

SYSTEM_PROMPT = '''You classify a user's sentence as a command for controlling YouTube playback.
Return exactly one JSON object with the keys "command" and "value". The command must be one of: play_pause, rewind, forward, volume_up, volume_down, next_video, fullscreen_toggle, none. Use a number of seconds for value only for rewind and forward; otherwise use null. If unclear or not a playback command, use {"command":"none","value":null}.

Examples:
"abeg go back small" -> {"command":"rewind","value":15}
"I no hear wetin she talk" -> {"command":"rewind","value":10}
"make am louder" -> {"command":"volume_up","value":null}
"skip this one" -> {"command":"next_video","value":null}
"hold on" -> {"command":"play_pause","value":null}
"wait" -> {"command":"play_pause","value":null}
"jump one minute" -> {"command":"forward","value":60}
"what's for dinner" -> {"command":"none","value":null}'''

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "enum": COMMANDS},
        "value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
    },
    "required": ["command", "value"],
    "additionalProperties": False,
}


def _none_result() -> dict[str, str | None]:
    return {"command": "none", "value": None}


def _validate_result(value: object) -> dict[str, str | int | float | None]:
    if not isinstance(value, dict) or set(value) != {"command", "value"}:
        return _none_result()

    command = value["command"]
    seconds = value["value"]
    if command not in COMMANDS:
        return _none_result()

    if command in {"rewind", "forward"}:
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds)
            or seconds < 0
        ):
            return _none_result()
    elif seconds is not None:
        return _none_result()

    return {"command": command, "value": seconds}


def parse(text: str, model: str = MODEL) -> dict[str, str | int | float | None]:
    """Classify a playback sentence using the local Ollama chat API."""
    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "stream": False,
        "think": False,
        "format": RESPONSE_SCHEMA,
        "options": {"temperature": 0},
    }
    request = Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        content = response_data["message"]["content"]
        parsed = json.loads(content)
    except (OSError, TimeoutError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return _none_result()

    return _validate_result(parsed)