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

On naming the account: Titan does not try to resolve the signed-in user's
email. An ADC session minted for `cloud-platform` does not necessarily carry
the `userinfo.email` scope, so the obvious probe answers 401 — and when the
credential has a quota project the probe answers 403 instead, because the
userinfo endpoint rejects `x-goog-user-project` from a caller without
`serviceusage.services.use` on it. Both were observed live. The identity that
actually matters is the one Firebase records on the published version, which is
reported after a publish, so the auth check reports the credential *kind* —
the part that decides whether the audit trail names a person at all — and a
service account's own email, which is available locally.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional, Sequence

from ...exceptions import FirebaseAuthUnavailableError
from ...models.view import UIAdcIdentity

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


def resolve_credentials(
    scopes: Optional[Sequence[str]] = None,
    *,
    quota_project_id: Optional[str] = None,
):
    """
    Resolve Application Default Credentials.

    A configured `quota_project_id` is applied to the credential itself, not
    just to a request header: `google.auth` overwrites `x-goog-user-project`
    with the credential's quota project on every request (see
    `google.auth.credentials.Credentials.apply`), so a header alone would be
    silently ignored whenever the ADC session carries one of its own.

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

    if quota_project_id and hasattr(credentials, "with_quota_project"):
        credentials = credentials.with_quota_project(quota_project_id)
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


def describe_identity(credentials) -> UIAdcIdentity:
    """
    Describe the credential, without a network call.

    Everything reported here is available locally: the kind of credential, a
    service account's own email, and the quota project. See the module
    docstring for why the signed-in user's email is not resolved.
    """
    kind = _credential_kind(credentials)
    account = getattr(credentials, "service_account_email", None)
    return UIAdcIdentity(
        account=account if isinstance(account, str) and account else None,
        credential_kind=kind,
        quota_project_id=getattr(credentials, "quota_project_id", None),
        scopes=tuple(getattr(credentials, "scopes", None) or ()),
    )


def service_account_env_var_set() -> bool:
    """Whether GOOGLE_APPLICATION_CREDENTIALS would shadow user credentials."""
    value = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    return bool(value and value.strip())


def create_adc_session(
    scopes: Optional[Sequence[str]] = None,
    *,
    quota_project_id: Optional[str] = None,
) -> AdcSession:
    """Resolve ADC, verify it can mint a token, and describe the identity."""
    credentials = resolve_credentials(scopes, quota_project_id=quota_project_id)
    refresh_credentials(credentials)
    return AdcSession(
        session=build_session(credentials),
        identity=describe_identity(credentials),
    )
