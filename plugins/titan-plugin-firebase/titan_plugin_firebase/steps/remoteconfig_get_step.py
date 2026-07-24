"""Firebase Remote Config read workflow step."""

from __future__ import annotations

from contextlib import nullcontext

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..exceptions import FirebaseClientError


def execute_firebase_remoteconfig_get_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Read a Firebase Remote Config template for one project.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        project_id (str, optional): Firebase project ID to read.
        firebase_project_id (str, optional): Alternate project ID key from a previous step.

    Outputs (saved to ctx.data):
        firebase_project_id (str): Firebase project ID used for the request.
        firebase_remoteconfig_template (dict): Remote Config template JSON payload.
        firebase_remoteconfig_etag (Optional[str]): ETag returned by Firebase for later publishing.
        firebase_remoteconfig_version (Optional[dict]): Remote Config template version payload.

    Returns:
        Success: If the Remote Config template is read successfully.
        Error: If Firebase is unavailable, no project ID is provided, or the API request fails.
    """
    if ctx.textual:
        ctx.textual.begin_step("Get Firebase Remote Config")

    if not ctx.firebase:
        message = "Firebase client not available"
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    project_id = (
        ctx.get("project_id")
        or ctx.get("firebase_project_id")
        or ctx.firebase.config.default_project
    )
    if not project_id:
        message = (
            "Firebase project_id is required. Pass project_id or configure "
            "plugins.firebase.config.default_project."
        )
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    loading = (
        ctx.textual.loading(f"Reading Remote Config for {project_id}...")
        if ctx.textual
        else nullcontext()
    )
    try:
        with loading:
            remote_config = ctx.firebase.get_remote_config(str(project_id))
    except FirebaseClientError as exc:
        message = str(exc)
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message, exception=exc)

    if ctx.textual:
        version = remote_config.version or {}
        version_number = version.get("versionNumber") if isinstance(version, dict) else None
        suffix = f" version {version_number}" if version_number else ""
        ctx.textual.success_text(
            f"Remote Config template loaded for {remote_config.project_id}{suffix}"
        )
        ctx.textual.end_step("success")

    return Success(
        "Firebase Remote Config template loaded",
        metadata={
            "firebase_project_id": remote_config.project_id,
            "firebase_remoteconfig_template": remote_config.template,
            "firebase_remoteconfig_etag": remote_config.etag,
            "firebase_remoteconfig_version": remote_config.version,
        },
    )
