"""
Prompt user for JIRA fixVersion
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def prompt_fix_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompt user to enter a JIRA fixVersion.

    Outputs (saved to ctx.data):
        fix_version (str): The fixVersion entered by user (e.g., "26.4.0")

    Returns:
        Success: Version entered
        Error: User cancelled or invalid input

    Example usage in workflow:
        ```yaml
        - id: prompt_version
          plugin: jira
          step: prompt_fix_version
        ```
    """
    if ctx.views:
        ctx.views.step_header(
            name="Enter Fix Version",
            step_type="plugin",
            step_detail="jira.prompt_fix_version"
        )

    if not ctx.views:
        return Error("Views not available in context")

    # Show info about version format
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle("Fix Version Format")
        ctx.ui.text.body("  Format: YY.W.B (Year.Week.Build)", style="dim")
        ctx.ui.text.body("  Example: 26.4.0 (Year 2026, Week 4, Build 0)", style="dim")
        ctx.ui.spacer.small()

    # Prompt for fix version
    fix_version = ctx.views.prompts.ask_text(
        prompt="Enter fixVersion",
        default=""
    )

    if not fix_version:
        return Error("fixVersion is required")

    # Basic validation (YY.W.B format)
    parts = fix_version.split(".")
    if len(parts) != 3:
        error_msg = f"Invalid fixVersion format: {fix_version}. Expected format: YY.W.B (e.g., 26.4.0)"
        if ctx.ui:
            ctx.ui.panel.print(error_msg, panel_type="error")
        return Error(error_msg)

    # Show confirmation
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.panel.print(
            f"Using fixVersion: {fix_version}",
            panel_type="info"
        )
        ctx.ui.spacer.small()

    return Success(
        f"fixVersion set to: {fix_version}",
        metadata={
            "fix_version": fix_version
        }
    )


__all__ = ["prompt_fix_version_step"]
