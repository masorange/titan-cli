"""List all PoEditor projects step."""

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..messages import msg


def list_projects_step(ctx: WorkflowContext) -> WorkflowResult:
    """List all PoEditor projects.

    Outputs (saved to ctx.data):
        poeditor_projects (List[UIPoEditorProject]): All accessible projects

    Returns:
        Success: Projects retrieved
        Error: Failed to list projects
    """
    if not ctx.textual:
        return Error("Textual UI context is not available")

    # Begin step container
    ctx.textual.begin_step("List PoEditor Projects")

    # Check client availability
    if not ctx.poeditor:
        ctx.textual.error_text(msg("no_client"))
        ctx.textual.end_step("error")
        return Error(msg("no_client"))

    # Show loading indicator while fetching
    with ctx.textual.loading("Fetching projects..."):
        result = ctx.poeditor.list_projects()

    # Pattern match on Result
    match result:
        case ClientSuccess(data=projects):
            if not projects:
                ctx.textual.warning_text(msg("no_projects"))
                ctx.textual.end_step("success")
                return Success(msg("no_projects"), metadata={"poeditor_projects": []})

            # Show success
            ctx.textual.success_text(
                msg("list_projects_success", count=len(projects))
            )
            ctx.textual.text("")

            # Display projects in table format
            for i, project in enumerate(projects, 1):
                ctx.textual.primary_text(
                    f"{i}. {project.progress_icon} {project.name} (ID: {project.id})"
                )
                ctx.textual.text(
                    f"   Description: {project.description} | Terms: {project.terms_count} | Language: {project.reference_language}"
                )
                ctx.textual.text(
                    f"   Updated: {project.formatted_updated_at} | Public: {'Yes' if project.is_public else 'No'}"
                )
                ctx.textual.text("")

            ctx.textual.end_step("success")

            # Return success with projects in metadata for next steps
            return Success(
                msg("list_projects_success", count=len(projects)),
                metadata={"poeditor_projects": projects},
            )

        case ClientError(error_message=err, error_code=code):
            # Handle error with code
            if code == "AUTH_ERROR":
                error_msg = "Authentication failed - check your API token"
            else:
                error_msg = f"Failed to list projects: {err}"

            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


__all__ = ["list_projects_step"]
