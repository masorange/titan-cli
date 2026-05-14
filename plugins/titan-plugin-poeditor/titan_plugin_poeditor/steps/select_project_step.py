"""Select a PoEditor project step."""

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..messages import msg


def select_project_step(ctx: WorkflowContext) -> WorkflowResult:
    """Prompt user to select a PoEditor project.

    Inputs (from ctx.data):
        poeditor_projects (List[UIPoEditorProject]): List of projects from previous step

    Outputs (saved to ctx.data):
        selected_project_id (str): Selected project ID
        selected_project (UIPoEditorProject): Selected project object

    Returns:
        Success: If the user selects a valid project
        Error: If there are no projects, the selection is invalid, or the prompt is cancelled
    """
    if not ctx.textual:
        return Error("Textual UI context is not available")

    # Begin step container
    ctx.textual.begin_step("Select PoEditor Project")

    # Get projects from previous step
    projects = ctx.get("poeditor_projects")
    if not projects:
        ctx.textual.error_text(msg("no_projects"))
        ctx.textual.end_step("error")
        return Error(msg("no_projects"))

    if len(projects) == 0:
        ctx.textual.error_text(msg("no_projects"))
        ctx.textual.end_step("error")
        return Error(msg("no_projects"))

    # Prompt user to select project
    ctx.textual.text("")

    try:
        # Ask for selection using text input and validate
        response = ctx.textual.ask_text(
            msg("select_project_prompt"), default=""
        )

        if not response or not response.strip():
            ctx.textual.error_text("No project selected")
            ctx.textual.end_step("error")
            return Error("No project selected")

        # Validate it's a number
        try:
            selected_index = int(response.strip())
        except ValueError:
            ctx.textual.error_text(f"Invalid input: '{response}' is not a number")
            ctx.textual.end_step("error")
            return Error(f"Invalid input: '{response}' is not a number")

        # Validate it's in range
        if selected_index < 1 or selected_index > len(projects):
            ctx.textual.error_text(
                f"Invalid selection: must be between 1 and {len(projects)}"
            )
            ctx.textual.end_step("error")
            return Error(f"Invalid selection: must be between 1 and {len(projects)}")

        # Convert to 0-based index
        selected_project = projects[selected_index - 1]

        ctx.textual.text("")
        ctx.textual.success_text(
            f"Selected project: {selected_project.name} (ID: {selected_project.id})"
        )

        ctx.textual.end_step("success")
        return Success(
            f"Selected project: {selected_project.name}",
            metadata={
                "selected_project_id": selected_project.id,
                "selected_project": selected_project,
            },
        )
    except (KeyboardInterrupt, EOFError):
        ctx.textual.error_text("User cancelled project selection")
        ctx.textual.end_step("error")
        return Error("User cancelled project selection")


__all__ = ["select_project_step"]
