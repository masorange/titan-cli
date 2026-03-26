"""
Select CLI Step

Asks user which headless AI CLI to use for PR analysis (Claude or Gemini).
Saves the choice to ctx.data["cli_preference"] for subsequent steps.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success
from titan_cli.ui.tui.widgets import ChoiceOption


def select_cli_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Ask user to explicitly choose which AI CLI to use for PR analysis.

    Only offers Claude or Gemini (no Auto, since user must decide).
    Stores the choice in ctx.data["cli_preference"].

    Returns:
        Success with the chosen CLI name stored in ctx.data
    """
    ctx.textual.begin_step("Select AI CLI for Review")

    options = [
        ChoiceOption(value="claude", label="Claude", variant="primary"),
        ChoiceOption(value="gemini", label="Gemini", variant="default"),
    ]

    try:
        choice = ctx.textual.ask_choice(
            "Which AI CLI do you want to use for this PR review?",
            options=options,
        )
    except KeyboardInterrupt:
        ctx.textual.end_step("skip")
        return Success("Cancelled CLI selection")

    if not choice:
        ctx.textual.end_step("skip")
        return Success("No CLI selected")

    ctx.data["cli_preference"] = choice
    ctx.textual.success_text(f"Using {choice.capitalize()} for analysis")
    ctx.textual.end_step("success")
    return Success(f"Selected CLI: {choice}")
