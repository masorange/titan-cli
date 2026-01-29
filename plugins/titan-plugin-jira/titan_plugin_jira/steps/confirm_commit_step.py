"""
Confirm git commit before executing.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def confirm_commit_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show git status/diff and ask user to confirm commit before proceeding.

    Inputs (from ctx.data):
        fix_version (str): Version name for commit message

    Returns:
        Success: User confirmed, proceed with commit
        Error: User cancelled, halt workflow

    Example usage in workflow:
        ```yaml
        - id: confirm_commit
          plugin: jira
          step: confirm_commit
          requires:
            - fix_version
        ```
    """
    # Get data from context
    fix_version = ctx.get("fix_version")

    if not ctx.git:
        return Error("GitClient not available in context")

    # Get git status
    try:
        status = ctx.git.get_status()
        current_branch = ctx.git.get_current_branch()
    except Exception as e:
        return Error(f"Error getting git status: {e}")

    # Textual TUI (new UI)
    if ctx.textual:
        from titan_cli.ui.tui.widgets import Panel

        # Show header
        ctx.textual.text("")
        ctx.textual.text("🔍 Cambios a Commitear", markup="bold cyan")
        ctx.textual.text("")

        # Show branch info
        ctx.textual.text(f"Branch: {current_branch}", markup="bold")
        ctx.textual.text("")

        # Show modified files
        if status.modified_files:
            ctx.textual.text("📝 Archivos modificados:", markup="yellow")
            for file in status.modified_files:
                ctx.textual.text(f"  - {file}", markup="dim")
            ctx.textual.text("")

        # Show untracked files
        if status.untracked_files:
            ctx.textual.text("📄 Archivos nuevos:", markup="green")
            for file in status.untracked_files:
                ctx.textual.text(f"  - {file}", markup="dim")
            ctx.textual.text("")

        # Show commit message preview
        commit_msg = f"docs: Add release notes for {fix_version}"
        ctx.textual.text("Commit Preview:", markup="bold")
        ctx.textual.mount(
            Panel(
                f"Mensaje del commit:\n{commit_msg}",
                panel_type="info"
            )
        )
        ctx.textual.text("")

        # Ask for confirmation
        confirmed = ctx.textual.ask_confirm(
            question="¿Confirmar commit de estos cambios?",
            default=True
        )

        if not confirmed:
            return Error("Commit cancelado por el usuario")

        return Success(
            "Commit confirmado",
            metadata={"confirmed": True, "branch": current_branch}
        )

    # Rich UI (legacy)
    if ctx.views:
        ctx.views.step_header(
            name="Confirm Commit",
            step_type="plugin",
            step_detail="jira.confirm_commit"
        )

    if not ctx.views:
        return Error("Views not available in context (neither Textual nor Rich UI)")

    # Show git status
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle(f"Branch: {current_branch}")
        ctx.ui.spacer.small()

        if status.modified_files:
            ctx.ui.text.warning("📝 Archivos modificados:")
            for file in status.modified_files:
                ctx.ui.text.body(f"  - {file}")

        if status.untracked_files:
            ctx.ui.text.success("📄 Archivos nuevos:")
            for file in status.untracked_files:
                ctx.ui.text.body(f"  - {file}")

        ctx.ui.spacer.small()

        commit_msg = f"docs: Add release notes for {fix_version}"
        ctx.ui.panel.print(
            f"Mensaje del commit:\n{commit_msg}",
            panel_type="info",
            title="Commit Preview"
        )
        ctx.ui.spacer.small()

    # Ask for confirmation
    confirmed = ctx.views.prompts.ask_confirm(
        question="¿Confirmar commit de estos cambios?",
        default=True
    )

    if not confirmed:
        return Error("Commit cancelado por el usuario")

    return Success(
        "Commit confirmado",
        metadata={"confirmed": True, "branch": current_branch}
    )


__all__ = ["confirm_commit_step"]
