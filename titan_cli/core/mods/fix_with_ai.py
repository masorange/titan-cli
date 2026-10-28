"""The "✦ Fix with AI" button for a mod's error card: opens the user's AI CLI with the error pasted in."""

from .elements import Button

# The workflow Titan ships that does it; a project can extend it under another name and `run` resolves that.
FIX_WORKFLOW = "fix-with-ai"


def fix_with_ai_button(m, error: str, context: str = "", label: str = "✦ Fix with AI") -> Button:
    """
    A button for `error_card(actions=[...])` that hands `error` to an interactive AI CLI.

    The `fix-with-ai` workflow opens it, after asking, in the project; which CLI is the one set in
    AI Configuration. `context` is whatever helps place the error (a log excerpt, the branch) and
    goes after it. The error is never shortened, so pass what the CLI should read.
    """
    text = error if not context else f"{error}\n\n{context}"
    return Button(label, lambda: m.workflows.run(FIX_WORKFLOW, {"fix_error": text}))
