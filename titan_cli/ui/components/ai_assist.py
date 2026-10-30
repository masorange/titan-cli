"""The button that hands a text to the user's AI CLI, for a mod to put anywhere."""
from typing import Optional

from titan_cli.ui.elements import Button


def fix_prompt(error: str, context: str = "") -> str:
    """The prompt for "help me fix this error": the error whole, then `context` (a log excerpt, the branch)."""
    text = error if not context else f"{error}\n\n{context}"
    return f"Help me fix this error. Find its cause in the code before changing anything.\n\n{text}"


def ai_assist_button(m, prompt: str, label: str = "✦ Ask AI", cwd: Optional[str] = None) -> Button:
    """
    A button that opens the AI CLI the user set for this mod's help task with `prompt` typed in.

    Which CLI and model is the user's choice in AI Configuration (the mod's `ai_assist_task`),
    through `m.ai.assist`; there is no workflow in between. Fits an `error_card`'s `actions`
    or any other place a `Button` goes. `prompt` is sent whole, so build it with what the CLI
    should read (`fix_prompt` for an error).
    """
    return Button(label, lambda: m.ai.assist(prompt, cwd))
