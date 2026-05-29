"""Import translations to PoEditor project step."""

from pathlib import Path

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..messages import msg


def import_translations_step(ctx: WorkflowContext) -> WorkflowResult:
    """Upload translation file to PoEditor project.

    Parameters (from workflow):
        project_id (str): PoEditor project ID
        file_path (str): Path to translation file
        language_code (str): Language code (e.g., "en", "es", "fr")
        updating (str, optional): What to update - "terms", "terms_translations", or "translations"

    Returns:
        Success: File uploaded successfully
        Error: Failed to upload file
    """
    if not ctx.textual:
        return Error("Textual UI context is not available")

    # Begin step container
    ctx.textual.begin_step("Import Translations")

    # Check client availability
    if not ctx.poeditor:
        ctx.textual.error_text(msg("no_client"))
        ctx.textual.end_step("error")
        return Error(msg("no_client"))

    # Get parameters
    project_id = ctx.get("project_id")
    file_path = ctx.get("file_path")
    language_code = ctx.get("language_code", "en")
    updating = ctx.get("updating", "terms_translations")

    # Validate parameters
    if not project_id:
        ctx.textual.error_text("Project ID is required")
        ctx.textual.end_step("error")
        return Error("Project ID is required")

    if not file_path:
        ctx.textual.error_text("File path is required")
        ctx.textual.end_step("error")
        return Error("File path is required")

    # Validate file exists
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        ctx.textual.error_text(msg("file_not_found", file_path=file_path))
        ctx.textual.end_step("error")
        return Error(msg("file_not_found", file_path=file_path))

    if not file_path_obj.is_file():
        ctx.textual.error_text(f"Path is not a file: {file_path}")
        ctx.textual.end_step("error")
        return Error(f"Path is not a file: {file_path}")

    # Display upload details
    ctx.textual.text(f"Project ID: {project_id}")
    ctx.textual.text(f"File: {file_path}")
    ctx.textual.text(f"Language: {language_code}")
    ctx.textual.text(f"Updating: {updating}")
    ctx.textual.text("")

    # Upload file with loading indicator
    with ctx.textual.loading(f"Uploading {file_path_obj.name}..."):
        result = ctx.poeditor.upload_file(
            project_id=project_id,
            file_path=file_path,
            language_code=language_code,
            updating=updating,
        )

    # Pattern match on Result
    match result:
        case ClientSuccess(data=upload_stats):
            # Show success
            ctx.textual.success_text(
                msg(
                    "upload_success",
                    added=upload_stats.added,
                    updated=upload_stats.updated,
                    deleted=upload_stats.deleted,
                )
            )
            ctx.textual.text("")
            ctx.textual.text(f"✓ {upload_stats.added} new terms added")
            ctx.textual.text(f"✓ {upload_stats.updated} terms updated")
            if upload_stats.deleted > 0:
                ctx.textual.text(f"✓ {upload_stats.deleted} terms deleted")

            ctx.textual.end_step("success")

            # Return success with upload statistics
            return Success(
                msg(
                    "upload_success",
                    added=upload_stats.added,
                    updated=upload_stats.updated,
                    deleted=upload_stats.deleted,
                ),
                metadata={
                    "upload_stats": {
                        "added": upload_stats.added,
                        "updated": upload_stats.updated,
                        "deleted": upload_stats.deleted,
                    }
                },
            )

        case ClientError(error_message=err, error_code=code):
            # Handle error with code
            if code == "FILE_NOT_FOUND":
                error_msg = msg("file_not_found", file_path=file_path)
            elif code == "AUTH_ERROR":
                error_msg = "Authentication failed - check your API token"
            else:
                error_msg = msg("upload_failed", error=err)

            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


__all__ = ["import_translations_step"]
