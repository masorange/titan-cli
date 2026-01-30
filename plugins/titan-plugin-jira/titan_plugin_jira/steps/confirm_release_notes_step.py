"""
Confirm release notes before proceeding with file operations.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def confirm_release_notes_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Display generated release notes and ask user to confirm before proceeding.

    Inputs (from ctx.data):
        release_notes (str): Generated markdown release notes
        fix_version (str): Version name
        total_issues (int): Number of issues processed
        brand_counts (dict): Issues per brand

    Returns:
        Success: User confirmed, continue with file operations
        Error: User cancelled, halt workflow

    Example usage in workflow:
        ```yaml
        - id: confirm_notes
          plugin: jira
          step: confirm_release_notes
          requires:
            - release_notes
            - fix_version
        ```
    """
    # Get data from context
    release_notes = ctx.get("release_notes")
    fix_version = ctx.get("fix_version")
    total_issues = ctx.get("total_issues", 0)
    brand_counts = ctx.get("brand_counts", {})

    if not release_notes:
        return Error("No release notes available. Run generate_release_notes step first.")

    # Textual TUI (new UI)
    if ctx.textual:
        from titan_cli.ui.tui.widgets import Panel

        # Show header
        ctx.textual.text("")
        ctx.textual.text("📋 Release Notes Preview", markup="bold cyan")
        ctx.textual.text("")

        # Show version info
        ctx.textual.text(f"Version: {fix_version}", markup="bold")
        ctx.textual.text(f"Total issues: {total_issues}", markup="dim")
        ctx.textual.text(f"Brands: {len(brand_counts)}", markup="dim")
        ctx.textual.text("")

        # Show release notes in panel
        ctx.textual.mount(
            Panel(release_notes, panel_type="info")
        )
        ctx.textual.text("")

        # Ask for confirmation
        confirmed = ctx.textual.ask_confirm(
            question="¿Continuar con la creación de archivos?",
            default=True
        )

        if not confirmed:
            return Error("Operación cancelada por el usuario")

        return Success(
            f"Release notes confirmadas para {fix_version}",
            metadata={"confirmed": True}
        )

    # Rich UI (legacy)
    if ctx.views:
        ctx.views.step_header(
            name="Confirm Release Notes",
            step_type="plugin",
            step_detail="jira.confirm_release_notes"
        )

    if not ctx.views:
        return Error("Views not available in context (neither Textual nor Rich UI)")

    # Show release notes
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle(f"Version: {fix_version}")
        ctx.ui.text.body(f"Total issues: {total_issues}")
        ctx.ui.text.body(f"Brands: {len(brand_counts)}")
        ctx.ui.spacer.small()

        ctx.ui.panel.print(
            release_notes,
            panel_type="info",
            title=f"Release Notes - {fix_version}"
        )
        ctx.ui.spacer.small()

    # Ask for confirmation
    confirmed = ctx.views.prompts.ask_confirm(
        question="¿Continuar con la creación de archivos?",
        default=True
    )

    if not confirmed:
        return Error("Operación cancelada por el usuario")

    return Success(
        f"Release notes confirmadas para {fix_version}",
        metadata={"confirmed": True}
    )


__all__ = ["confirm_release_notes_step"]
