import time

from brain import parse


MODELS = ("gemma4:e2b", "gemma3:4b")
PHRASES = (
    ("Pause the video", "play_pause", None, "unseen"),
    ("hold on", "play_pause", None, "seen"),
    ("wait", "play_pause", None, "seen"),
    ("abeg pause am", "play_pause", None, "unseen"),
    ("abeg go back small", "rewind", 15, "seen"),
    ("I no hear wetin she talk", "rewind", 10, "seen"),
    ("rewind 30 seconds", "rewind", 30, "unseen"),
    ("make we go back two minutes", "rewind", 120, "unseen"),
    ("jump one minute", "forward", 60, "seen"),
    ("skip ahead 20 seconds", "forward", 20, "unseen"),
    ("move forward 15 seconds", "forward", 15, "unseen"),
    ("make am louder", "volume_up", None, "seen"),
    ("turn the volume down", "volume_down", None, "unseen"),
    ("reduce the sound small", "volume_down", None, "unseen"),
    ("skip this one", "next_video", None, "seen"),
    ("go to the next video", "next_video", None, "unseen"),
    ("make this full screen", "fullscreen_toggle", None, "unseen"),
    ("what's for dinner", "none", None, "seen"),
    ("tell me a joke", "none", None, "unseen"),
    ("do that thing", "none", None, "unseen"),
    ("abeg stop am", "play_pause", None, "unseen"),
    ("carry am go front small", "forward", 10, "unseen"),
    ("I wan hear am well well", "volume_up", None, "unseen"),
    ("na wetin she talk?", "rewind", 10, "unseen"),
    ("pause this gist for me", "play_pause", None, "unseen"),
    ("make the sound soft", "volume_down", None, "unseen"),
    ("take am back by twenty seconds", "rewind", 20, "unseen"),
    ("move the film go front 45 seconds", "forward", 45, "unseen"),
    ("abeg play the next one", "next_video", None, "unseen"),
    ("show me full screen", "fullscreen_toggle", None, "unseen"),
)


def _format_answer(command: str, value: int | float | None) -> str:
    if value is None:
        return command
    return f"{command} ({value:g}s)"


def _is_correct(
    result: dict[str, object], expected_command: str, expected_value: int | None
) -> bool:
    if result.get("command") != expected_command:
        return False
    actual_value = result.get("value")
    if expected_value is None:
        return actual_value is None
    return isinstance(actual_value, (int, float)) and not isinstance(
        actual_value, bool
    ) and actual_value == expected_value


def run_benchmark() -> None:
    outcomes: dict[str, list[tuple[dict[str, object], float]]] = {}

    for model in MODELS:
        parse("Pause the video", model=model)
        model_outcomes = []
        for phrase, _, _, _ in PHRASES:
            started = time.perf_counter()
            answer = parse(phrase, model=model)
            elapsed_ms = (time.perf_counter() - started) * 1000
            model_outcomes.append((answer, elapsed_ms))
        outcomes[model] = model_outcomes

    print(
        f"{'Phrase':<34} {'Expected':<22} "
        f"{MODELS[0] + ' answer / ms':<30} {MODELS[1] + ' answer / ms':<30}"
    )
    print("-" * 119)

    for phrase_index, (phrase, expected_command, expected_value, _) in enumerate(PHRASES):
        expected = _format_answer(expected_command, expected_value)
        cells = []
        for model in MODELS:
            answer, elapsed_ms = outcomes[model][phrase_index]
            answer_text = _format_answer(
                str(answer.get("command", "none")), answer.get("value")
            )
            cells.append(f"{answer_text} ({elapsed_ms:.1f})")
        print(f"{phrase:<34} {expected:<22} {cells[0]:<30} {cells[1]:<30}")

    print("\nSummary")
    print(
        f"{'Model':<16} {'Seen accuracy':>15} {'Unseen accuracy':>17} "
        f"{'Overall':>12} {'Average ms':>14}"
    )
    for model in MODELS:
        model_outcomes = outcomes[model]
        group_results = {"seen": [], "unseen": []}
        for (answer, _), (_, expected_command, expected_value, group) in zip(
            model_outcomes, PHRASES
        ):
            group_results[group].append(
                _is_correct(answer, expected_command, expected_value)
            )
        seen_correct = sum(group_results["seen"])
        unseen_correct = sum(group_results["unseen"])
        correct = seen_correct + unseen_correct
        average_ms = sum(elapsed_ms for _, elapsed_ms in model_outcomes) / len(
            model_outcomes
        )
        seen_total = len(group_results["seen"])
        unseen_total = len(group_results["unseen"])
        total = len(PHRASES)
        print(
            f"{model:<16} {seen_correct:>2}/{seen_total} ({seen_correct / seen_total:>5.1%}) "
            f"{unseen_correct:>2}/{unseen_total} ({unseen_correct / unseen_total:>5.1%}) "
            f"{correct:>2}/{total} ({correct / total:>5.1%}) {average_ms:>13.1f}"
        )


if __name__ == "__main__":
    run_benchmark()