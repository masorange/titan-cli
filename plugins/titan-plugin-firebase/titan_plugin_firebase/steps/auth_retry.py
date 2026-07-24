"""Shared Firebase authentication retry helpers."""

from __future__ import annotations

from titan_cli.engine import Error, WorkflowContext

from ..exceptions import FirebaseAuthRejectedError
from .login_step import prompt_for_firebase_auth


def reauthenticate_after_rejected_token(
    ctx: WorkflowContext,
    exc: FirebaseAuthRejectedError,
) -> Error | None:
    """Invalidate a rejected token source and prompt for fresh auth."""
    invalidated = False
    invalidator = getattr(ctx.firebase, "invalidate_access_token_source", None)
    if callable(invalidator):
        invalidated = bool(invalidator(exc.auth_source))

    if ctx.textual:
        if invalidated:
            ctx.textual.warning_text("Saved Firebase auth was rejected.")
        else:
            ctx.textual.warning_text("Firebase auth was rejected.")

    auth_available, auth_error, _oauth_attempted = prompt_for_firebase_auth(ctx)
    if auth_error:
        return auth_error
    if not auth_available:
        return Error(
            "Firebase auth was rejected and no replacement credential was provided.",
            exception=exc,
            recoverable=True,
        )
    return None
