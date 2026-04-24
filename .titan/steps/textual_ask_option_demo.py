from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Success, WorkflowResult
from titan_cli.ui.tui.widgets import OptionItem


def textual_ask_option_demo(ctx: WorkflowContext) -> WorkflowResult:
    """Show ctx.textual.ask_option for documentation screenshots."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("ask_option()")

    selected = ctx.textual.ask_option(
        "Select a plugin docs workflow:",
        [
            OptionItem(
                value="sync-plugin-docs",
                title="Sync Plugin Docs",
                description="Generate machine-readable step inventories for plugin docs.",
            ),
            OptionItem(
                value="validate-plugin-docs",
                title="Validate Plugin Docs",
                description="Check docstring conventions, grouping metadata, and generated outputs.",
            ),
            OptionItem(
                value="deploy-docs",
                title="Deploy Docs",
                description="Validate docs and publish the MkDocs site.",
            ),
        ],
    )

    ctx.textual.success_text(f"Selected option: {selected}")
    ctx.textual.end_step("success")
    return Success("Rendered ask_option() demo")
