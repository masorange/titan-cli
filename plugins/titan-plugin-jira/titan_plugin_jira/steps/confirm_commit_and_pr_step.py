"""
Confirm git commit and PR creation in a single step.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def confirm_commit_and_pr_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show git status and ask user to confirm commit and PR creation.
    Also prompts for PR label selection from available labels.

    Inputs (from ctx.data):
        fix_version (str): Version name for commit message

    Outputs (saved to ctx.data):
        confirmed_commit (bool): User confirmed commit
        confirmed_pr (bool): User wants to create PR
        pr_label (str): Selected label for PR

    Returns:
        Success: User confirmed, proceed with commit and PR
        Error: User cancelled, halt workflow

    Example usage in workflow:
        ```yaml
        - id: confirm_commit_and_pr
          plugin: jira
          step: confirm_commit_and_pr
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
        import subprocess

        # Show header
        ctx.textual.text("")
        ctx.textual.text("🔍 Cambios a Commitear y Crear PR", markup="bold cyan")
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

        # Ask for commit confirmation
        confirmed_commit = ctx.textual.ask_confirm(
            question="¿Confirmar commit y crear PR?",
            default=True
        )

        if not confirmed_commit:
            return Error("Commit y PR cancelados por el usuario")

        # Get available labels from GitHub
        ctx.textual.text("")
        ctx.textual.text("📋 Obteniendo labels disponibles...", markup="cyan")

        try:
            result = subprocess.run(
                ["gh", "label", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            labels_output = result.stdout.strip()

            # Parse labels (format: "name\tdescription\tcolor")
            labels = []
            for line in labels_output.split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if parts:
                        labels.append(parts[0])  # Just the name

            if not labels:
                return Error("No se encontraron labels en el repositorio")

            # Show info about available labels
            ctx.textual.text("")
            ctx.textual.text(f"Found {len(labels)} labels in repository", markup="dim")
            ctx.textual.text("")

            # Ask user to select a label (interactive menu)
            pr_label = ctx.textual.ask_choice(
                question="Select label for PR",
                choices=labels
            )

            if not pr_label:
                return Error("Label selection cancelled by user")

        except subprocess.CalledProcessError as e:
            return Error(f"Error al obtener labels: {e}")
        except Exception as e:
            return Error(f"Error inesperado: {e}")

        return Success(
            "Commit y PR confirmados",
            metadata={
                "confirmed_commit": True,
                "confirmed_pr": True,
                "pr_label": pr_label,
                "branch": current_branch
            }
        )

    # Rich UI (legacy)
    if ctx.views:
        import subprocess

        ctx.views.step_header(
            name="Confirm Commit and PR",
            step_type="plugin",
            step_detail="jira.confirm_commit_and_pr"
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

    # Ask for commit and PR confirmation
    confirmed = ctx.views.prompts.ask_confirm(
        question="¿Confirmar commit y crear PR?",
        default=True
    )

    if not confirmed:
        return Error("Commit y PR cancelados por el usuario")

    # Get available labels
    try:
        result = subprocess.run(
            ["gh", "label", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        labels_output = result.stdout.strip()

        # Parse labels
        labels = []
        for line in labels_output.split('\n'):
            if line.strip():
                parts = line.split('\t')
                if parts:
                    labels.append(parts[0])

        if not labels:
            return Error("No se encontraron labels en el repositorio")

        # Show info about available labels
        if ctx.ui:
            ctx.ui.text.subtitle(f"Select from {len(labels)} labels in repository")
            ctx.ui.spacer.small()

        # Ask for label selection (interactive menu)
        pr_label = ctx.views.prompts.ask_choice(
            question="Select label for PR",
            choices=labels
        )

        if not pr_label:
            return Error("Label selection cancelled by user")

    except subprocess.CalledProcessError as e:
        return Error(f"Error al obtener labels: {e}")
    except Exception as e:
        return Error(f"Error inesperado: {e}")

    return Success(
        "Commit y PR confirmados",
        metadata={
            "confirmed_commit": True,
            "confirmed_pr": True,
            "pr_label": pr_label,
            "branch": current_branch
        }
    )


__all__ = ["confirm_commit_and_pr_step"]
