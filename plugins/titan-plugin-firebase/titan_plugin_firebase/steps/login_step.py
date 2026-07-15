"""Firebase ADC authentication workflow steps."""

from __future__ import annotations

from titan_cli.engine import Error, Skip, Success, WorkflowContext, WorkflowResult


def _begin(ctx: WorkflowContext, title: str) -> None:
    if ctx.textual:
        ctx.textual.begin_step(title)


def _end(ctx: WorkflowContext, status: str) -> None:
    if ctx.textual:
        ctx.textual.end_step(status)


def _success(ctx: WorkflowContext, message: str) -> None:
    if ctx.textual:
        ctx.textual.success_text(message)


def _warning(ctx: WorkflowContext, message: str) -> None:
    if ctx.textual:
        ctx.textual.warning_text(message)


def _error(ctx: WorkflowContext, message: str) -> None:
    if ctx.textual:
        ctx.textual.error_text(message)


def _check_adc(ctx: WorkflowContext, title: str) -> WorkflowResult:
    """Shared implementation for Firebase ADC login/status checks."""
    _begin(ctx, title)

    if not ctx.firebase:
        message = "Firebase client not available"
        _error(ctx, message)
        _end(ctx, "error")
        return Error(message)

    account = ctx.firebase.get_active_account()
    login_command = ctx.firebase.get_login_command()

    if ctx.firebase.is_available():
        account_label = account or "unknown gcloud account"
        _success(ctx, f"Firebase ADC session available for {account_label}")
        _end(ctx, "success")
        return Success(
            "Firebase ADC session available",
            metadata={
                "firebase_account": account,
                "firebase_login_command": login_command,
            },
        )

    message = (
        "Firebase ADC session not available. Run: "
        f"{login_command}"
    )
    fail_on_missing_auth = ctx.get("fail_on_missing_auth", True)
    if fail_on_missing_auth:
        _error(ctx, message)
        _end(ctx, "error")
        return Error(message, recoverable=True)

    _warning(ctx, message)
    _end(ctx, "skip")
    return Skip(
        message,
        metadata={
            "firebase_account": account,
            "firebase_login_command": login_command,
        },
    )


def execute_firebase_login_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Validate that the current user has a Firebase ADC session.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        fail_on_missing_auth (bool, optional): Return Error when ADC is missing. Defaults to True.

    Outputs (saved to ctx.data):
        firebase_account (Optional[str]): Active gcloud account reported by `gcloud auth list`.
        firebase_login_command (str): Command the user can run to create an ADC session.

    Returns:
        Success: If gcloud ADC is available.
        Error: If Firebase client or ADC auth is missing and fail_on_missing_auth is True.
        Skip: If ADC auth is missing and fail_on_missing_auth is False.
    """
    return _check_adc(ctx, "Firebase ADC Login")


def execute_firebase_status_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Report the current Firebase ADC authentication status.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        fail_on_missing_auth (bool, optional): Return Error when ADC is missing. Defaults to True.

    Outputs (saved to ctx.data):
        firebase_account (Optional[str]): Active gcloud account reported by `gcloud auth list`.
        firebase_login_command (str): Command the user can run to create an ADC session.

    Returns:
        Success: If gcloud ADC is available.
        Error: If Firebase client or ADC auth is missing and fail_on_missing_auth is True.
        Skip: If ADC auth is missing and fail_on_missing_auth is False.
    """
    return _check_adc(ctx, "Firebase ADC Status")
