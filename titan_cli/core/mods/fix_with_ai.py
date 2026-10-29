"""The "✦ Fix with AI" button for a mod's error card: opens the user's AI CLI with the error pasted in."""
from titan_cli.core.mods.elements import Button


def fix_with_ai_button(m, error: str, context: str = "", label: str = "✦ Fix with AI", cwd: str = None) -> Button:
    """
    A button for `error_card(actions=[...])` that hands `error` to the interactive AI CLI.

    Pressing it opens that CLI (the one set in AI Configuration) with the error typed in,
    through `m.ai.assist`; there is no workflow in between. `context` is whatever helps
    place the error (a log excerpt, the branch) and goes after it. The error is never
    shortened, so pass what the CLI should read.
    """
    text = error if not context else f"{error}\n\n{context}"
    return Button(label, lambda: m.ai.assist(f"Help me fix this error. Find its cause in the code before changing anything.\n\n{text}", cwd))
