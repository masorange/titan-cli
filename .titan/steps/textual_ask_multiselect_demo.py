from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Success, WorkflowResult
from titan_cli.ui.tui.widgets import SelectionOption


def textual_ask_multiselect_demo(ctx: WorkflowContext) -> WorkflowResult:
    """Show ctx.textual.ask_multiselect for documentation screenshots."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("ask_multiselect()")

    selected = ctx.textual.ask_multiselect(
        "Select which checks to include:",
        [
            SelectionOption(value="lint", label="Run linter", selected=True),
            SelectionOption(value="tests", label="Run tests", selected=True),
            SelectionOption(value="docs", label="Validate docs", selected=False),
        ],
    )

    ctx.textual.success_text(f"Selected items: {selected}")
    ctx.textual.end_step("success")
    return Success("Rendered ask_multiselect() demo")
