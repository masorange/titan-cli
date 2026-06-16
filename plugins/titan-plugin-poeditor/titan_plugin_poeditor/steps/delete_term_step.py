"""Delete a term from a PoEditor project step."""

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..messages import msg


def delete_term_step(ctx: WorkflowContext) -> WorkflowResult:
    """Delete a term from a PoEditor project.

    Inputs (from ctx.data):
        selected_project_id (str): PoEditor project ID
        term_key (str): The term key to delete

    Outputs (saved to ctx.data):
        deleted_term_key (str): The term key that was deleted

    Returns:
        Success: If the term was deleted successfully
        Error: If deletion failed or required data is missing
    """
    if not ctx.textual:
        return Error("Textual UI context is not available")

    if not ctx.poeditor:
        return Error("PoEditor client is not available")

    # Begin step container
    ctx.textual.begin_step("Delete Term from PoEditor")

    # Get required data from context
    selected_project_id = ctx.get("selected_project_id")
    term_key = ctx.get("term_key")

    # Validate inputs
    if not selected_project_id:
        ctx.textual.error_text(msg("no_project_selected"))
        ctx.textual.text("")
        ctx.textual.dim_text("Please select a project first using select_project_step")
        ctx.textual.end_step("error")
        return Error("No project selected")

    if not term_key:
        ctx.textual.error_text("No term_key found in context")
        ctx.textual.text("")
        ctx.textual.dim_text("term_key must be set to the key you want to delete")
        ctx.textual.end_step("error")
        return Error("No term_key found in context")

    # Display deletion info
    ctx.textual.text(f"Project ID: {selected_project_id}")
    ctx.textual.text(f"Term key to delete: {term_key}")
    ctx.textual.text("")

    # Ask for confirmation
    ctx.textual.warning_text("⚠️  This action cannot be undone!")
    ctx.textual.text("")

    confirmation = ctx.textual.ask_text(
        "Type 'DELETE' to confirm deletion:",
        default=""
    )

    if confirmation.strip() != "DELETE":
        ctx.textual.text("")
        ctx.textual.dim_text("Deletion cancelled")
        ctx.textual.end_step("success")
        return Success("Deletion cancelled by user")

    ctx.textual.text("")
    ctx.textual.text("Deleting term from PoEditor...")

    # Delete the term
    result = ctx.poeditor.delete_term(
        project_id=selected_project_id,
        term_key=term_key
    )

    match result:
        case ClientSuccess(data=delete_result):
            ctx.textual.text("")
            ctx.textual.success_text(
                f"✓ Successfully deleted term: {term_key}"
            )

            deleted_count = delete_result.get("deleted", 0)
            if deleted_count > 0:
                ctx.textual.dim_text(f"Terms deleted: {deleted_count}")

            ctx.textual.end_step("success")
            return Success(
                f"Deleted term '{term_key}' from PoEditor",
                metadata={
                    "deleted_term_key": term_key,
                    "deleted_count": deleted_count
                }
            )

        case ClientError(error_message=err, error_code=code):
            ctx.textual.text("")
            ctx.textual.error_text(f"✗ Deletion failed: {err}")
            if code:
                ctx.textual.dim_text(f"Error code: {code}")

            # Provide helpful message for common errors
            if code == "TERM_NOT_FOUND":
                ctx.textual.text("")
                ctx.textual.dim_text(f"The term '{term_key}' does not exist in the project")

            ctx.textual.end_step("error")
            return Error(f"Deletion failed: {err}")


__all__ = ["delete_term_step"]
