from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Success, WorkflowResult
from titan_cli.ui.tui.widgets import ChoiceOption


def textual_ask_choice_demo(ctx: WorkflowContext) -> WorkflowResult:
    """Show ctx.textual.ask_choice for documentation screenshots."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("ask_choice()")

    choice = ctx.textual.ask_choice(
        "What would you like to do?",
        options=[
            ChoiceOption(value="send", label="Send", variant="primary"),
            ChoiceOption(value="edit", label="Edit", variant="default"),
            ChoiceOption(value="skip", label="Skip", variant="error"),
        ],
    )

    ctx.textual.success_text(f"Selected choice: {choice}")
    ctx.textual.end_step("success")
    return Success("Rendered ask_choice() demo")
