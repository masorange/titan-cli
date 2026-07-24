"""Firebase Remote Config read workflow step."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from typing import Any

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..exceptions import FirebaseAuthRejectedError, FirebaseClientError
from .auth_retry import reauthenticate_after_rejected_token


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
        Error: If Firebase is unavailable, no project ID is provided, the API request fails, or the template payload is malformed.
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

    loading_message = f"Reading Remote Config for {project_id}..."
    try:
        with _loading(ctx, loading_message):
            remote_config = ctx.firebase.get_remote_config(str(project_id))
    except FirebaseAuthRejectedError as exc:
        retry_error = reauthenticate_after_rejected_token(ctx, exc)
        if retry_error:
            if ctx.textual:
                ctx.textual.error_text(retry_error.message)
                ctx.textual.end_step("error")
            return retry_error

        try:
            with _loading(ctx, loading_message):
                remote_config = ctx.firebase.get_remote_config(str(project_id))
        except FirebaseClientError as retry_exc:
            message = str(retry_exc)
            if ctx.textual:
                ctx.textual.error_text(message)
                ctx.textual.end_step("error")
            return Error(message, exception=retry_exc)
    except FirebaseClientError as exc:
        message = str(exc)
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message, exception=exc)

    try:
        template, version, version_number = _validate_remote_config_template(
            remote_config.template
        )
    except FirebaseClientError as exc:
        message = str(exc)
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message, exception=exc)

    if ctx.textual:
        suffix = f" version {version_number}" if version_number else ""
        ctx.textual.success_text(
            f"Remote Config template loaded for {remote_config.project_id}{suffix}"
        )
        ctx.textual.end_step("success")

    return Success(
        "Firebase Remote Config template loaded",
        metadata={
            "firebase_project_id": remote_config.project_id,
            "firebase_remoteconfig_template": template,
            "firebase_remoteconfig_etag": remote_config.etag,
            "firebase_remoteconfig_version": version,
        },
    )


def _loading(ctx: WorkflowContext, message: str) -> AbstractContextManager[object]:
    """Return a fresh loading context for each request attempt."""
    if ctx.textual:
        return ctx.textual.loading(message)
    return nullcontext()


def _validate_remote_config_template(
    template: Any,
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    """Validate the Remote Config template shape before rendering metadata."""
    if not isinstance(template, dict):
        raise FirebaseClientError(
            "Firebase Remote Config template payload was malformed: "
            "template must be a JSON object."
        )

    version = template.get("version")
    if version is not None and not isinstance(version, dict):
        raise FirebaseClientError(
            "Firebase Remote Config template payload was malformed: "
            "version must be a JSON object when present."
        )

    version_number = None
    if version:
        raw_version_number = version.get("versionNumber")
        if raw_version_number is not None:
            if isinstance(raw_version_number, bool) or not isinstance(
                raw_version_number,
                (int, str),
            ):
                raise FirebaseClientError(
                    "Firebase Remote Config template payload was malformed: "
                    "version.versionNumber must be a string or integer when present."
                )
            version_number = str(raw_version_number)

    return template, version, version_number
