"""Ask the user's routed AI in the background and show its answer: the state, the button, the box and the chip."""
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Union

from .bus import AIAnswer
from .elements import Box, Button, Text
from .error_card import error_card

WHO = "ai:who"


@dataclass(frozen=True)
class AIResult:
    """
    One asked question under a key: still running, answered or failed.

    `text` is what the model said; `value` is anything else the mod's `work` made of it
    (several answers parsed into rows, say), kept so the mod can draw it its own way.
    """

    status: str  # "running", "done" or "error"
    text: str = ""
    model: Optional[str] = None
    error: Optional[str] = None
    value: Any = None


Work = Callable[[Any], Union[AIAnswer, AIResult]]


def _slot(key: str) -> str:
    return f"ai:{key}"


def ai_result(m, key: str) -> Optional[AIResult]:
    """What `key` holds now, or None when it was never asked."""
    return m.state.get(_slot(key))


def ask_ai(m, key: str, work: Work) -> bool:
    """
    Run `work(m)` on a background thread and keep its outcome under `key`; False when `key`
    is already running, so a second press while one is in flight starts nothing.

    `work` makes the AI calls (`m.ai.complete`) and returns their `AIAnswer`, or an `AIResult`
    when it has more to hand back than text; raising turns into an error. Reserving the key
    happens in `m.state`, not in what the last repaint showed, so two quick presses cannot both
    start. Call it from a button: only a state update and a thread start run on the UI thread.
    """
    claimed: List[bool] = []

    def claim(current):
        if current is not None and current.status == "running":
            return current
        claimed.append(True)
        return AIResult("running", model=m.state.get(WHO))

    m.state.update(_slot(key), claim)
    if not claimed:
        return False

    def run() -> None:
        try:
            outcome = work(m)
            if isinstance(outcome, AIAnswer):
                outcome = AIResult("done", outcome.text, outcome.model) if outcome.ok else AIResult("error", error=outcome.error)
            if outcome.status == "error":
                # `work` returned the failure instead of raising it; log it the same way.
                m.log.warning("mod_ask_ai_failed", key=key, error=(outcome.error or "")[:500])
        except Exception as e:
            m.log.warning("mod_ask_ai_failed", key=key, exc_info=True)
            outcome = AIResult("error", error=str(e))
        m.state.set(_slot(key), outcome)

    m.run(run)
    return True


def ai_ask_button(
    m,
    key: str,
    work: Work,
    label: str = "✦ Ask AI",
    again_label: str = "✦ Ask again",
    running_label: str = "… asking",
) -> Button:
    """The button that runs `ask_ai`; its label follows the state: ask, who is answering, ask again."""
    current = ai_result(m, key)
    running = current is not None and current.status == "running"
    if running:
        return Button(f"{running_label} {current.model or 'AI'}", lambda: None, dim=True)
    return Button(again_label if current is not None and current.status == "done" else label, lambda: ask_ai(m, key, work))


def _lines(text: str) -> List[Text]:
    """The model answers in Markdown and the pane has none: headings become bold, `**` goes, the rest wraps."""
    lines: List[Text] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            lines.append(Text(line.lstrip("# ").strip(), bold=True, color="info", wrap=True))
        else:
            lines.append(Text(line.replace("**", ""), wrap=True))
    return lines


def ai_answer_box(
    m,
    key: str,
    title: str = "✦ Answer",
    render: Optional[Callable[[Any], Union[Box, List[Any]]]] = None,
) -> Optional[Box]:
    """
    What `key` answered: its text (or what `render(value)` draws instead) with a copy button,
    or an error card; nothing while it is running or was never asked.
    """
    current = ai_result(m, key)
    if current is None or current.status == "running":
        return None
    if current.status == "error":
        return error_card(current.error or "no answer", copy=m.ui.copy, title="Could not ask AI")
    body = render(current.value) if render is not None else _lines(current.text)
    return Box(
        Text(Text(title, bold=True, color="accent"), Text(f" · {current.model or 'AI'}", dim=True)),
        body,
        current.text and Button("⧉ Copy", lambda: m.ui.copy(current.text, "answer"), dim=True),
    )


def refresh_ai_chip(m) -> None:
    """Read who answers now into state for `ai_chip`; resolving may probe, so call it off the UI thread (`m.run`)."""
    m.state.set(WHO, m.ai.describe())


def ai_chip(m, title: str) -> Button:
    """
    The "⟳ who answers" line: pressing it opens the pickers for this mod's task, and the label
    follows what the user picks. Fill it once at start with `m.run(lambda: refresh_ai_chip(m))`.
    """
    return Button(
        f"⟳ {m.state.get(WHO) or 'AI routing'}",
        lambda: m.ai.configure(title, on_done=lambda: m.run(lambda: refresh_ai_chip(m))),
        dim=True,
    )
