"""Firebase authentication workflow steps."""

from __future__ import annotations

import getpass
import sys
from typing import Optional

from titan_cli.core.oauth import OAuthEvent
from titan_cli.engine import Error, Skip, Success, WorkflowContext, WorkflowResult

from ..exceptions import FirebaseClientError

_TRUE_BOOLEAN_STRINGS = {"1", "true", "yes", "y", "on"}
_FALSE_BOOLEAN_STRINGS = {"0", "false", "no", "n", "off"}


class _WorkflowOAuthSink:
    """Adapts provider-neutral OAuth events to the current workflow context."""

    def __init__(self, ctx: WorkflowContext) -> None:
        self.ctx = ctx

    def emit(self, event: OAuthEvent) -> None:
        """Render only user-relevant OAuth events."""
        if not self.ctx.textual:
            return

        if event.type in {"oauth.refresh.started", "oauth.authorize.started"}:
            self.ctx.textual.dim_text(event.message)
        elif event.type == "oauth.storage.saved":
            self.ctx.textual.dim_text("OAuth credential saved in Titan OAuth store")


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


def _get_workflow_bool(
    ctx: WorkflowContext,
    key: str,
    *,
    default: bool,
) -> bool:
    """Return a strict workflow boolean from ctx.data."""
    if not ctx.has(key):
        return default

    value = ctx.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_BOOLEAN_STRINGS:
            return True
        if normalized in _FALSE_BOOLEAN_STRINGS:
            return False
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)

    raise ValueError(
        f"{key} must be a boolean or one of: true/false, yes/no, on/off, 1/0."
    )


def _get_auth_source_label(ctx: WorkflowContext) -> Optional[str]:
    """Return a safe label for the current Firebase auth source."""
    source_getter = getattr(ctx.firebase, "get_access_token_source_label", None)
    source_label = source_getter() if callable(source_getter) else None
    if isinstance(source_label, str) and source_label.strip():
        return source_label
    return None


def _is_available(ctx: WorkflowContext, sink: _WorkflowOAuthSink) -> bool:
    """Return auth availability while supporting older Firebase client doubles."""
    try:
        return bool(ctx.firebase.is_available(sink=sink))
    except TypeError:
        return bool(ctx.firebase.is_available())


def _auth_success(
    ctx: WorkflowContext,
    *,
    login_command: str,
    token_saved: bool = False,
    oauth_login_completed: bool = False,
) -> Success:
    """Render and return a successful Firebase auth result."""
    auth_source_label = _get_auth_source_label(ctx) or "configured Firebase auth"
    _success(ctx, f"Firebase auth available via {auth_source_label}")
    _end(ctx, "success")
    return Success(
        "Firebase auth available",
        metadata={
            "firebase_account": None,
            "firebase_auth_source": auth_source_label,
            "firebase_login_command": login_command,
            "firebase_access_token_saved": token_saved,
            "firebase_oauth_login_completed": oauth_login_completed,
        },
    )


def _ask_for_access_token(ctx: WorkflowContext) -> Optional[str]:
    """Ask the user for a Firebase OAuth access token in an interactive session."""
    question = "Firebase access token (saved to Titan OAuth store)"
    try:
        if ctx.textual and hasattr(ctx.textual, "ask_password"):
            token = ctx.textual.ask_password(question)
        elif sys.stdin.isatty():
            token = getpass.getpass(f"{question}: ")
        else:
            return None
    except (EOFError, KeyboardInterrupt):
        return None

    if not isinstance(token, str):
        return None
    normalized = token.strip()
    return normalized or None


def _ask_for_oauth_client_id(ctx: WorkflowContext) -> Optional[str]:
    """Ask the user for a Google OAuth client ID in an interactive session."""
    question = (
        "Google OAuth Desktop app client ID for Titan Firebase login "
        "(saved to Titan keyring)"
    )
    try:
        if ctx.textual and hasattr(ctx.textual, "ask_text"):
            client_id = ctx.textual.ask_text(question, default="")
        elif sys.stdin.isatty():
            client_id = input(f"{question}: ")
        else:
            return None
    except (EOFError, KeyboardInterrupt):
        return None

    if not isinstance(client_id, str):
        return None
    normalized = client_id.strip()
    return normalized or None


def _ask_for_oauth_client_secret(ctx: WorkflowContext) -> Optional[str]:
    """Ask the user for a Google OAuth client secret in an interactive session."""
    question = (
        "Google OAuth Desktop app client secret for Titan Firebase login "
        "(saved to Titan keyring)"
    )
    try:
        if ctx.textual and hasattr(ctx.textual, "ask_password"):
            client_secret = ctx.textual.ask_password(question)
        elif sys.stdin.isatty():
            client_secret = getpass.getpass(f"{question}: ")
        else:
            return None
    except (EOFError, KeyboardInterrupt):
        return None

    if not isinstance(client_secret, str):
        return None
    normalized = client_secret.strip()
    return normalized or None


def _prompt_and_configure_oauth_client_id(ctx: WorkflowContext) -> Optional[Error]:
    """Prompt for and save the Google OAuth client ID when missing."""
    _warning(
        ctx,
        "Firebase browser OAuth is not configured. Enter a Google OAuth "
        "Desktop app client ID and client secret for Titan CLI to open Google "
        "login, or leave the Client ID blank to paste a temporary access token.",
    )
    client_id = _ask_for_oauth_client_id(ctx)
    if not client_id:
        return None

    client_secret = _ask_for_oauth_client_secret(ctx)
    if not client_secret:
        _warning(
            ctx,
            "Google may reject the token exchange without the Desktop app "
            "client secret.",
        )

    saver = getattr(ctx.firebase, "save_oauth_client_id", None)
    configurer = getattr(ctx.firebase, "configure_google_oauth", None)
    try:
        if callable(saver):
            saver(client_id, client_secret=client_secret)
        elif callable(configurer):
            configurer(client_id, client_secret=client_secret)
        else:
            return Error(
                "Firebase client cannot configure Google OAuth dynamically.",
                recoverable=True,
            )
    except FirebaseClientError as exc:
        return Error(str(exc), exception=exc, recoverable=True)
    except Exception as exc:
        return Error(
            f"Could not configure Firebase browser OAuth: {exc}",
            exception=exc,
            recoverable=True,
        )

    _success(ctx, "Firebase browser OAuth configured")
    return None


def _prompt_and_save_access_token(ctx: WorkflowContext) -> Optional[Error]:
    """Prompt for a token and save it to Titan's OAuth token store."""
    _warning(
        ctx,
        "Firebase browser OAuth is not configured or did not complete. Paste an "
        "OAuth access token to continue.",
    )
    token = _ask_for_access_token(ctx)
    if not token:
        return None

    try:
        ctx.firebase.save_access_token(token)
    except FirebaseClientError as exc:
        return Error(str(exc), exception=exc, recoverable=True)
    except Exception as exc:
        return Error(
            f"Could not save Firebase access token: {exc}",
            exception=exc,
            recoverable=True,
        )

    _success(ctx, "Firebase access token saved in Titan OAuth store")
    return None


def _is_oauth_client_secret_error(exc: Exception) -> bool:
    """Return whether Google rejected the OAuth client secret at token exchange."""
    message = str(exc).lower()
    mentions_secret = "client_secret" in message or "client secret" in message
    return mentions_secret and ("missing" in message or "invalid" in message)


def _try_interactive_oauth(
    ctx: WorkflowContext,
    sink: _WorkflowOAuthSink,
) -> tuple[bool, Optional[Error], bool]:
    """Run browser OAuth when the Firebase client is configured for it."""
    oauth_client_id = getattr(ctx.firebase.config, "oauth_client_id", None)
    if not oauth_client_id:
        return False, None, False

    _warning(ctx, "Firebase auth not available. Opening browser for Google login.")
    token_getter = getattr(ctx.firebase, "get_access_token", None)
    if not callable(token_getter):
        return False, None, False

    try:
        token_getter(sink=sink, interactive=True)
    except FirebaseClientError as exc:
        if _is_oauth_client_secret_error(exc):
            _warning(
                ctx,
                "Google accepted the browser login, but rejected the token "
                "exchange because the OAuth client secret is missing or invalid. "
                "Enter the Client ID and Client Secret from the same Desktop "
                "app OAuth client.",
            )
            return True, None, True
        _warning(
            ctx,
            f"Firebase browser OAuth did not complete: {exc}. "
            "You can paste a temporary access token instead.",
        )
        return True, None, False
    except Exception as exc:
        return (
            True,
            Error(
                f"Firebase Google OAuth login failed: {exc}",
                exception=exc,
                recoverable=True,
            ),
            False,
        )

    return True, None, False


def prompt_for_firebase_auth(
    ctx: WorkflowContext,
) -> tuple[bool, Optional[Error], bool]:
    """Prompt for browser OAuth or a manual token and return auth status."""
    oauth_sink = _WorkflowOAuthSink(ctx)

    for _attempt in range(3):
        oauth_attempted, oauth_error, client_id_rejected = _try_interactive_oauth(
            ctx,
            oauth_sink,
        )
        if oauth_error:
            return False, oauth_error, False

        if (
            oauth_attempted
            and not client_id_rejected
            and _is_available(
                ctx,
                oauth_sink,
            )
        ):
            return True, None, True

        oauth_client_id = getattr(ctx.firebase.config, "oauth_client_id", None)
        if oauth_client_id and not client_id_rejected:
            break

        oauth_config_error = _prompt_and_configure_oauth_client_id(ctx)
        if oauth_config_error:
            return False, oauth_config_error, False
        if not getattr(ctx.firebase.config, "oauth_client_id", None):
            break

    prompt_error = _prompt_and_save_access_token(ctx)
    if prompt_error:
        return False, prompt_error, False

    return _is_available(ctx, oauth_sink), None, False


def _check_auth(
    ctx: WorkflowContext,
    title: str,
    *,
    prompt_for_missing_auth_default: bool,
) -> WorkflowResult:
    """Shared implementation for Firebase login/status checks."""
    _begin(ctx, title)

    if not ctx.firebase:
        message = "Firebase client not available"
        _error(ctx, message)
        _end(ctx, "error")
        return Error(message)

    login_command = ctx.firebase.get_login_command()
    oauth_sink = _WorkflowOAuthSink(ctx)
    try:
        prompt_for_missing_auth = _get_workflow_bool(
            ctx,
            "prompt_for_missing_auth",
            default=prompt_for_missing_auth_default,
        )
        fail_on_missing_auth = _get_workflow_bool(
            ctx,
            "fail_on_missing_auth",
            default=True,
        )
    except ValueError as exc:
        message = str(exc)
        _error(ctx, message)
        _end(ctx, "error")
        return Error(message, recoverable=True)

    if _is_available(ctx, oauth_sink):
        return _auth_success(
            ctx,
            login_command=login_command,
        )

    if prompt_for_missing_auth:
        auth_available, auth_error, oauth_login_completed = prompt_for_firebase_auth(
            ctx
        )
        if auth_error:
            _error(ctx, auth_error.message)
            _end(ctx, "error")
            return auth_error

        if auth_available:
            return _auth_success(
                ctx,
                login_command=login_command,
                token_saved=True,
                oauth_login_completed=oauth_login_completed,
            )

    message = (
        "Firebase auth not available. Configure Firebase oauth_client_id, set "
        f"{ctx.firebase.config.access_token_env_var}, or run: {login_command}"
    )
    if fail_on_missing_auth:
        _error(ctx, message)
        _end(ctx, "error")
        return Error(message, recoverable=True)

    _warning(ctx, message)
    _end(ctx, "skip")
    return Skip(
        message,
        metadata={
            "firebase_account": None,
            "firebase_auth_source": None,
            "firebase_login_command": login_command,
            "firebase_access_token_saved": False,
            "firebase_oauth_login_completed": False,
        },
    )


def execute_firebase_login_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Validate that the current user has Firebase OAuth authentication.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        fail_on_missing_auth (bool, optional): Return Error when auth is missing. Defaults to True.
        prompt_for_missing_auth (bool, optional): Prompt for Google OAuth setup/login when auth is missing. Defaults to True.

    Outputs (saved to ctx.data):
        firebase_account (Optional[str]): Reserved until Firebase token identity can be resolved; currently None.
        firebase_auth_source (Optional[str]): Safe source label for the token Titan will use.
        firebase_login_command (str): Command the user can run to create an ADC session.
        firebase_access_token_saved (bool): Whether this step saved a token to Titan's OAuth token store.
        firebase_oauth_login_completed (bool): Whether this step completed browser OAuth login.

    Returns:
        Success: If Firebase OAuth auth is available.
        Error: If Firebase client or auth is missing and fail_on_missing_auth is True.
        Skip: If auth is missing and fail_on_missing_auth is False.
    """
    return _check_auth(
        ctx,
        "Firebase Login",
        prompt_for_missing_auth_default=True,
    )


def execute_firebase_status_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Report the current Firebase OAuth authentication status.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        fail_on_missing_auth (bool, optional): Return Error when auth is missing. Defaults to True.
        prompt_for_missing_auth (bool, optional): Prompt for Google OAuth setup/login when auth is missing. Defaults to False.

    Outputs (saved to ctx.data):
        firebase_account (Optional[str]): Reserved until Firebase token identity can be resolved; currently None.
        firebase_auth_source (Optional[str]): Safe source label for the token Titan will use.
        firebase_login_command (str): Command the user can run to create an ADC session.
        firebase_access_token_saved (bool): Whether this step saved a token to Titan's OAuth token store.
        firebase_oauth_login_completed (bool): Whether this step completed browser OAuth login.

    Returns:
        Success: If Firebase OAuth auth is available.
        Error: If Firebase client or auth is missing and fail_on_missing_auth is True.
        Skip: If auth is missing and fail_on_missing_auth is False.
    """
    return _check_auth(
        ctx,
        "Firebase Auth Status",
        prompt_for_missing_auth_default=False,
    )
