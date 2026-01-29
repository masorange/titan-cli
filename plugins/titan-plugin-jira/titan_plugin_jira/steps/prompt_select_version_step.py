"""
Prompt user to select a version from available versions
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def prompt_select_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompt user to select a version from available versions.

    Inputs (from ctx.data):
        versions (list): List of version names from list_versions step

    Outputs (saved to ctx.data):
        fix_version (str): Selected version name

    Returns:
        Success: Version selected
        Error: No versions available or selection cancelled

    Example usage in workflow:
        ```yaml
        - id: select_version
          plugin: jira
          step: prompt_select_version
          requires:
            - versions
        ```
    """
    # Get versions from previous step
    versions = ctx.get("versions")
    if not versions:
        return Error("No versions available. Run list_versions step first.")

    if len(versions) == 0:
        return Error("No versions found in project")

    # Limit choices to first 20 versions (to avoid overwhelming the user)
    display_versions = versions[:20]

    # Textual TUI (new UI)
    if ctx.textual:
        from titan_cli.ui.tui.widgets import Panel

        # Show info
        ctx.textual.text(f"Found {len(versions)} unreleased versions", markup="dim")
        ctx.textual.text("")

        # Prompt for version selection
        selected_version = ctx.textual.ask_choice(
            question="Select fixVersion",
            choices=display_versions
        )

        if not selected_version:
            return Error("Version selection cancelled")

        # Show confirmation
        ctx.textual.mount(
            Panel(f"Selected version: {selected_version}", panel_type="info")
        )

        return Success(
            f"Version selected: {selected_version}",
            metadata={
                "fix_version": selected_version
            }
        )

    # Rich UI (legacy)
    if ctx.views:
        ctx.views.step_header(
            name="Select Version",
            step_type="plugin",
            step_detail="jira.prompt_select_version"
        )

    if not ctx.views:
        return Error("Views not available in context (neither Textual nor Rich UI)")

    # Show info
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle(f"Select from {len(versions)} unreleased versions")
        ctx.ui.spacer.small()

    # Prompt for version selection (ask_choice shows numbered menu: 1, 2, 3...)
    selected_version = ctx.views.prompts.ask_choice(
        question="Select fixVersion",
        choices=display_versions
    )

    if not selected_version:
        return Error("Version selection cancelled")

    # Show confirmation
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.panel.print(
            f"Selected version: {selected_version}",
            panel_type="info"
        )
        ctx.ui.spacer.small()

    return Success(
        f"Version selected: {selected_version}",
        metadata={
            "fix_version": selected_version
        }
    )


__all__ = ["prompt_select_version_step"]
