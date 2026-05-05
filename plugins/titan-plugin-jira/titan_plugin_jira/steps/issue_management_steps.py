"""Reusable Jira steps for issue state and version management."""

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..messages import msg
from ..operations import issue_has_fix_version


def get_transitions_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch available transitions for a Jira issue.

    Returns:
        Success: If transitions are fetched successfully.
        Error: If required context is missing or the Jira call fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Get Jira Transitions")

    if not ctx.jira:
        ctx.textual.error_text(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)
        ctx.textual.end_step("error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    issue_key = ctx.get("jira_issue_key")
    if not issue_key:
        ctx.textual.error_text(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)

    with ctx.textual.loading(f"Fetching transitions for {issue_key}..."):
        result = ctx.jira.get_transitions(issue_key)

    match result:
        case ClientSuccess(data=transitions):
            success_msg = msg.Steps.Transitions.GET_SUCCESS.format(
                count=len(transitions), issue_key=issue_key
            )
            ctx.textual.success_text(success_msg)
            ctx.textual.end_step("success")
            return Success(success_msg, metadata={"jira_transitions": transitions})
        case ClientError(error_message=err):
            error_msg = msg.Steps.Transitions.GET_FAILED.format(e=err)
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


def transition_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Transition a Jira issue to a target status.

    Returns:
        Success: If the issue transitions successfully.
        Error: If required context is missing or the Jira call fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Transition Jira Issue")

    if not ctx.jira:
        ctx.textual.error_text(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)
        ctx.textual.end_step("error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    issue_key = ctx.get("jira_issue_key")
    target_status = ctx.get("target_status")
    comment = ctx.get("transition_comment")
    fields = ctx.get("transition_fields", ctx.get("fields"))
    update = ctx.get("transition_update", ctx.get("update"))

    if not issue_key:
        ctx.textual.error_text(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
    if not target_status:
        ctx.textual.error_text(msg.Steps.Transitions.TARGET_STATUS_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Transitions.TARGET_STATUS_REQUIRED)

    with ctx.textual.loading(f"Transitioning {issue_key} to {target_status}..."):
        result = ctx.jira.transition_issue(
            issue_key,
            target_status,
            comment=comment,
            fields=fields,
            update=update,
        )

    match result:
        case ClientSuccess():
            success_msg = msg.Steps.Transitions.TRANSITION_SUCCESS.format(
                issue_key=issue_key, status=target_status
            )
            ctx.textual.success_text(success_msg)
            ctx.textual.end_step("success")
            return Success(success_msg, metadata={"transition_target_status": target_status})
        case ClientError(error_message=err):
            error_msg = msg.Steps.Transitions.TRANSITION_FAILED.format(e=err)
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


def verify_issue_state_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Verify that a Jira issue is currently in the expected status.

    Returns:
        Success: If the issue is in the expected status.
        Error: If required context is missing, verification fails, or the Jira call fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Verify Jira Issue State")

    if not ctx.jira:
        ctx.textual.error_text(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)
        ctx.textual.end_step("error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    issue_key = ctx.get("jira_issue_key")
    expected_status = ctx.get("expected_status")

    if not issue_key:
        ctx.textual.error_text(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
    if not expected_status:
        ctx.textual.error_text(msg.Steps.Transitions.TARGET_STATUS_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Transitions.TARGET_STATUS_REQUIRED)

    with ctx.textual.loading(f"Verifying status for {issue_key}..."):
        result = ctx.jira.get_issue(issue_key)

    match result:
        case ClientSuccess(data=issue):
            if issue.status.lower() != str(expected_status).lower():
                error_msg = msg.Steps.Transitions.VERIFY_FAILED.format(
                    issue_key=issue_key,
                    actual_status=issue.status,
                    expected_status=expected_status,
                )
                ctx.textual.error_text(error_msg)
                ctx.textual.end_step("error")
                return Error(error_msg)

            success_msg = msg.Steps.Transitions.VERIFY_SUCCESS.format(
                issue_key=issue_key,
                status=issue.status,
            )
            ctx.textual.success_text(success_msg)
            ctx.textual.end_step("success")
            return Success(success_msg, metadata={"verified_jira_issue": issue})
        case ClientError(error_message=err):
            error_msg = msg.Steps.GetIssue.GET_FAILED.format(e=err)
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


def create_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create a Jira version.

    Returns:
        Success: If the version is created successfully.
        Error: If required context is missing or the Jira call fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Create Jira Version")

    if not ctx.jira:
        ctx.textual.error_text(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)
        ctx.textual.end_step("error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    version_name = ctx.get("version_name")
    project_key = ctx.get("project_key")
    description = ctx.get("version_description")
    release_date = ctx.get("release_date")

    if not version_name:
        ctx.textual.error_text(msg.Steps.Versions.VERSION_NAME_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Versions.VERSION_NAME_REQUIRED)

    with ctx.textual.loading(f"Creating version {version_name}..."):
        result = ctx.jira.create_version(
            name=version_name,
            project_key=project_key,
            description=description,
            release_date=release_date,
        )

    match result:
        case ClientSuccess(data=version):
            success_msg = msg.Steps.Versions.CREATE_SUCCESS.format(version_name=version.name)
            ctx.textual.success_text(success_msg)
            ctx.textual.end_step("success")
            return Success(
                success_msg,
                metadata={
                    "version": version,
                    "version_id": version.id,
                    "version_name": version.name,
                },
            )
        case ClientError(error_message=err, error_code=code):
            error_msg = msg.Steps.Versions.CREATE_FAILED.format(e=err)
            if code == "MISSING_PROJECT_KEY":
                error_msg = msg.Steps.Versions.LIST_PROJECT_REQUIRED
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


def ensure_version_exists_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Ensure a Jira version exists, creating it if missing.

    Returns:
        Success: If the version already exists or is created successfully.
        Error: If required context is missing or the Jira call fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Ensure Jira Version Exists")

    if not ctx.jira:
        ctx.textual.error_text(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)
        ctx.textual.end_step("error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    version_name = ctx.get("version_name")
    project_key = ctx.get("project_key")
    description = ctx.get("version_description")
    release_date = ctx.get("release_date")

    if not version_name:
        ctx.textual.error_text(msg.Steps.Versions.VERSION_NAME_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Versions.VERSION_NAME_REQUIRED)

    with ctx.textual.loading(f"Ensuring version {version_name} exists..."):
        result = ctx.jira.ensure_version_exists(
            name=version_name,
            project_key=project_key,
            description=description,
            release_date=release_date,
        )

    match result:
        case ClientSuccess(data=version):
            success_msg = msg.Steps.Versions.ENSURE_SUCCESS.format(version_name=version.name)
            ctx.textual.success_text(success_msg)
            ctx.textual.end_step("success")
            return Success(
                success_msg,
                metadata={
                    "version": version,
                    "version_id": version.id,
                    "version_name": version.name,
                },
            )
        case ClientError(error_message=err, error_code=code):
            error_msg = msg.Steps.Versions.CREATE_FAILED.format(e=err)
            if code == "MISSING_PROJECT_KEY":
                error_msg = msg.Steps.Versions.LIST_PROJECT_REQUIRED
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


def assign_fix_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Assign a fixVersion to a Jira issue.

    Returns:
        Success: If the fix version is assigned successfully.
        Error: If required context is missing or the Jira call fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Assign Jira Fix Version")

    if not ctx.jira:
        ctx.textual.error_text(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)
        ctx.textual.end_step("error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    issue_key = ctx.get("jira_issue_key")
    version_id = ctx.get("version_id")
    version_name = ctx.get("version_name")
    project_key = ctx.get("project_key")

    if not issue_key:
        ctx.textual.error_text(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
    if not version_id and not version_name:
        ctx.textual.error_text("version_id or version_name is required")
        ctx.textual.end_step("error")
        return Error("version_id or version_name is required")

    with ctx.textual.loading(f"Assigning fix version to {issue_key}..."):
        result = ctx.jira.assign_fix_version(
            issue_key=issue_key,
            version_id=version_id,
            version_name=version_name,
            project_key=project_key,
        )

    match result:
        case ClientSuccess():
            resolved_name = version_name or version_id
            success_msg = msg.Steps.Versions.ASSIGN_SUCCESS.format(
                version_name=resolved_name,
                issue_key=issue_key,
            )
            ctx.textual.success_text(success_msg)
            ctx.textual.end_step("success")
            return Success(success_msg, metadata={"assigned_fix_version": resolved_name})
        case ClientError(error_message=err):
            error_msg = msg.Steps.Versions.ASSIGN_FAILED.format(e=err)
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


def verify_issue_has_fix_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Verify a Jira issue has the expected fixVersion.

    Returns:
        Success: If the issue has the expected fix version.
        Error: If required context is missing, verification fails, or the Jira call fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Verify Jira Fix Version")

    if not ctx.jira:
        ctx.textual.error_text(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)
        ctx.textual.end_step("error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    issue_key = ctx.get("jira_issue_key")
    version_name = ctx.get("expected_fix_version") or ctx.get("version_name")

    if not issue_key:
        ctx.textual.error_text(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Transitions.ISSUE_KEY_REQUIRED)
    if not version_name:
        ctx.textual.error_text(msg.Steps.Versions.VERSION_NAME_REQUIRED)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Versions.VERSION_NAME_REQUIRED)

    with ctx.textual.loading(f"Verifying fix version on {issue_key}..."):
        result = ctx.jira.get_issue(issue_key)

    match result:
        case ClientSuccess(data=issue):
            if not issue_has_fix_version(issue, version_name):
                error_msg = msg.Steps.Versions.VERIFY_FAILED.format(
                    issue_key=issue_key,
                    version_name=version_name,
                )
                ctx.textual.error_text(error_msg)
                ctx.textual.end_step("error")
                return Error(error_msg)

            success_msg = msg.Steps.Versions.VERIFY_SUCCESS.format(
                issue_key=issue_key,
                version_name=version_name,
            )
            ctx.textual.success_text(success_msg)
            ctx.textual.end_step("success")
            return Success(success_msg, metadata={"verified_jira_issue": issue})
        case ClientError(error_message=err):
            error_msg = msg.Steps.GetIssue.GET_FAILED.format(e=err)
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


__all__ = [
    "get_transitions_step",
    "transition_issue_step",
    "verify_issue_state_step",
    "create_version_step",
    "ensure_version_exists_step",
    "assign_fix_version_step",
    "verify_issue_has_fix_version_step",
]
