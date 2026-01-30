"""
Confirm PR creation before proceeding.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def confirm_create_pr_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Ask user if they want to create a Pull Request with AI.

    Returns:
        Success: User confirmed, proceed with PR creation
        Error: User cancelled, skip PR creation

    Example usage in workflow:
        ```yaml
        - id: confirm_pr
          plugin: jira
          step: confirm_create_pr
          requires:
            - fix_version
        ```
    """
    # Get data from context
    fix_version = ctx.get("fix_version")

    # Textual TUI (new UI)
    if ctx.textual:
        from titan_cli.ui.tui.widgets import Panel

        # Show header
        ctx.textual.text("")
        ctx.textual.text("🚀 Crear Pull Request", markup="bold cyan")
        ctx.textual.text("")

        # Show info
        ctx.textual.mount(
            Panel(
                f"Release notes para {fix_version} commiteadas correctamente.\n\n"
                "¿Quieres crear un Pull Request con IA ahora?",
                panel_type="info"
            )
        )
        ctx.textual.text("")

        # Ask for confirmation
        confirmed = ctx.textual.ask_confirm(
            question="¿Crear Pull Request con IA?",
            default=True
        )

        if not confirmed:
            return Error("Creación de PR cancelada por el usuario")

        return Success(
            "Usuario confirmó creación de PR",
            metadata={"confirmed": True}
        )

    # Rich UI (legacy)
    if ctx.views:
        ctx.views.step_header(
            name="Confirm PR Creation",
            step_type="plugin",
            step_detail="jira.confirm_create_pr"
        )

    if not ctx.views:
        return Error("Views not available in context (neither Textual nor Rich UI)")

    # Show info
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.panel.print(
            f"Release notes para {fix_version} commiteadas correctamente.\n\n"
            "¿Quieres crear un Pull Request con IA ahora?",
            panel_type="info",
            title="🚀 Crear Pull Request"
        )
        ctx.ui.spacer.small()

    # Ask for confirmation
    confirmed = ctx.views.prompts.ask_confirm(
        question="¿Crear Pull Request con IA?",
        default=True
    )

    if not confirmed:
        return Error("Creación de PR cancelada por el usuario")

    return Success(
        "Usuario confirmó creación de PR",
        metadata={"confirmed": True}
    )


__all__ = ["confirm_create_pr_step"]
