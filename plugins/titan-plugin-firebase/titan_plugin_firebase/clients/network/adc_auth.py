"""
Application Default Credentials for the Firebase Remote Config API.

Titan does not implement an OAuth client here, and deliberately holds no
credential of its own: `gcloud auth application-default login` already ran the
OAuth flow, and `google.auth` reads those credentials and refreshes them.

Two consequences matter beyond convenience:

- There is no secret for Titan to custody, so nothing in this plugin needs the
  secret broker. The access token is minted and refreshed inside
  `AuthorizedSession`, which sets the Authorization header itself — this module
  never copies the token into a variable of its own, and registers it for
  redaction so it cannot surface in a log or an echoed command.
- The publish is attributed by Firebase to whoever the token belongs to. With
  user credentials that is the real person, which is the audit trail the
  version history shows. A service account would attribute every publish to
  itself, so `describe_identity` reports the credential kind and callers warn
  before writing.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional, Sequence

from ...exceptions import FirebaseAuthUnavailableError
from ...models.view import UIAdcIdentity

USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
DEFAULT_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/cloud-platform",
)
ADC_LOGIN_HINT = "gcloud auth application-default login"


@dataclass(frozen=True)
class AdcSession:
    """An authorized HTTP session plus the identity behind it."""

    session: object
    identity: UIAdcIdentity


def _credential_kind(credentials: object) -> str:
    """Classify a credential object without importing every provider module."""
    module = type(credentials).__module__
    if "service_account" in module:
        return "service_account"
    if "impersonated" in module:
        return "impersonated"
    if "compute_engine" in module:
        return "compute_engine"
    if "external_account" in module:
        return "external_account"
    if module.startswith("google.oauth2.credentials"):
        return "user"
    return type(credentials).__name__


def resolve_credentials(scopes: Optional[Sequence[str]] = None):
    """
    Resolve Application Default Credentials.

    Raises:
        FirebaseAuthUnavailableError: If no ADC session exists, with the exact
            command that creates one.
    """
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    requested_scopes = list(scopes or DEFAULT_SCOPES)
    try:
        credentials, _project_id = google.auth.default(scopes=requested_scopes)
    except DefaultCredentialsError as exc:
        raise FirebaseAuthUnavailableError(
            "No se encontraron credenciales de Google (ADC). Ejecuta: "
            f"{ADC_LOGIN_HINT}"
        ) from exc
    return credentials


def refresh_credentials(credentials) -> None:
    """
    Mint an access token so an expired ADC session fails here, not mid-write.

    The token is registered for redaction and never returned.
    """
    from google.auth.exceptions import RefreshError, TransportError
    from google.auth.transport.requests import Request

    try:
        credentials.refresh(Request())
    except (RefreshError, TransportError) as exc:
        raise FirebaseAuthUnavailableError(
            "Las credenciales de Google (ADC) no se pudieron renovar. "
            f"Vuelve a ejecutar: {ADC_LOGIN_HINT}. Detalle: {exc}"
        ) from exc

    token = getattr(credentials, "token", None)
    if isinstance(token, str) and token:
        from titan_cli.core.security import register_secret

        register_secret(token)


def build_session(credentials):
    """Build an AuthorizedSession that manages the bearer token itself."""
    from google.auth.transport.requests import AuthorizedSession

    return AuthorizedSession(credentials)


def describe_identity(
    credentials,
    session,
    *,
    timeout: int = 10,
) -> UIAdcIdentity:
    """
    Describe who the credentials belong to.

    The account is read through the authorized session so the token stays
    inside `google.auth`. A failure here is not fatal: the identity is
    informational, and Firebase attributes the publish from the token itself.
    """
    kind = _credential_kind(credentials)
    account = getattr(credentials, "service_account_email", None)

    if account is None:
        try:
            response = session.get(USERINFO_URL, timeout=timeout)
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, dict):
                    account = payload.get("email")
        except Exception:
            account = None

    scopes = getattr(credentials, "scopes", None) or ()
    return UIAdcIdentity(
        account=account if isinstance(account, str) and account else None,
        credential_kind=kind,
        quota_project_id=getattr(credentials, "quota_project_id", None),
        scopes=tuple(scopes),
    )


def service_account_env_var_set() -> bool:
    """Whether GOOGLE_APPLICATION_CREDENTIALS would shadow user credentials."""
    value = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    return bool(value and value.strip())


def create_adc_session(scopes: Optional[Sequence[str]] = None) -> AdcSession:
    """Resolve ADC, verify it can mint a token, and describe the identity."""
    credentials = resolve_credentials(scopes)
    refresh_credentials(credentials)
    session = build_session(credentials)
    return AdcSession(
        session=session,
        identity=describe_identity(credentials, session),
    )
