"""
Select CLI Step

Asks user which headless AI CLI to use for PR analysis (Claude, Gemini, or Codex).
Saves the choice to ctx.data["cli_preference"] for subsequent steps.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success
from titan_cli.ports.protocol import InteractionOption


def select_cli_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Ask user to explicitly choose which AI CLI to use for PR analysis.

    Offers Claude, Gemini, or Codex (no Auto, since user must decide).
    Stores the choice in ctx.data["cli_preference"].

    Returns:
        Success with the chosen CLI name stored in ctx.data
    """
    ui = getattr(ctx, "interaction", None) or getattr(ctx, "textual", None)
    if not ui:
        return Success("No interaction context available")

    ui.begin_step("Select AI CLI")

    options = [
        InteractionOption(
            id="claude",
            value="claude",
            label="Claude",
            description="Anthropic's Claude AI",
        ),
        InteractionOption(
            id="gemini",
            value="gemini",
            label="Gemini",
            description="Google's Gemini AI",
        ),
        InteractionOption(
            id="codex",
            value="codex",
            label="Codex",
            description="OpenAI's Codex",
        ),
    ]

    try:
        choice = ui.option_list(
            interaction_id="select-cli",
            message="Which AI CLI do you want to use for this PR review?",
            options=options,
        )
    except KeyboardInterrupt:
        ui.end_step("skip")
        return Success("Cancelled CLI selection")

    if not choice:
        ui.end_step("skip")
        return Success("No CLI selected")

    ctx.data["cli_preference"] = choice
    ui.success_text(f"Using {choice.capitalize()} for analysis")
    ui.end_step("success")
    return Success(f"Selected CLI: {choice}")
