"""Firebase client for OAuth-backed Remote Config REST operations."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Optional, Sequence

import requests

from titan_cli.core.oauth import (
    OAuthAuthenticationRequired,
    OAuthCredential,
    OAuthError,
    OAuthEventSink,
    OAuthManager,
    OAuthProviderNotFound,
    OAuthRequest,
    OAuthTokenSet,
)
from titan_cli.core.secrets import ScopeType, SecretManager

from . import auth
from .config import FirebasePluginConfig
from .exceptions import FirebaseAuthRejectedError, FirebaseClientError
from .models import FirebaseProjectTarget, RemoteConfigInventory

ACCESS_TOKEN_SECRET_KEY = "firebase_access_token"
OAUTH_CLIENT_ID_SECRET_KEY = "firebase_oauth_client_id"
OAUTH_CLIENT_SECRET_KEY = "firebase_oauth_client_secret"


@dataclass(frozen=True)
class RemoteConfigTemplate:
    """Remote Config template returned by Firebase."""

    project_id: str
    template: dict[str, Any]
    etag: Optional[str]

    @property
    def version(self) -> Any:
        """Return the Remote Config template version payload, when present."""
        return self.template.get("version")


class FirebaseClient:
    """Client facade for Firebase Remote Config operations."""

    def __init__(
        self,
        config: FirebasePluginConfig,
        secrets: Optional[SecretManager] = None,
        project_name: Optional[str] = None,
        oauth_manager: Optional[OAuthManager] = None,
    ):
        """Initialize the Firebase client with validated plugin config."""
        self.config = config
        self.secrets = secrets
        self.project_name = project_name
        self.oauth_manager = oauth_manager or (
            OAuthManager(secrets) if secrets is not None else None
        )
        self._ignored_access_token_sources: set[str] = set()

    def is_gcloud_installed(self) -> bool:
        """Return whether the gcloud CLI is installed."""
        return auth.is_gcloud_installed()

    def get_active_account(self) -> Optional[str]:
        """Return the active gcloud account, if one is configured."""
        return auth.get_active_account()

    def get_adc_access_token(self) -> Optional[str]:
        """Return the current ADC bearer token, if available."""
        return auth.get_adc_access_token()

    def build_oauth_request(self, *, interactive: bool = False) -> OAuthRequest:
        """Build the OAuth request used by Titan's credential manager."""
        connection_suffix = self.project_name or "default"
        access_token_env_var = self.config.access_token_env_var
        if access_token_env_var in self._ignored_access_token_sources:
            access_token_env_var = None

        legacy_secret_keys = [
            key
            for key in self.get_access_token_secret_keys()
            if f"keyring:{key}" not in self._ignored_access_token_sources
        ]
        return OAuthRequest(
            provider="google",
            connection_id=f"firebase:{connection_suffix}",
            scopes=self.config.oauth_scopes,
            interactive=interactive,
            access_token_env_var=access_token_env_var,
            legacy_secret_keys=legacy_secret_keys,
            subject=self.project_name,
        )

    def get_oauth_credential(
        self,
        *,
        sink: Optional[OAuthEventSink] = None,
        interactive: bool = False,
    ) -> Optional[OAuthCredential]:
        """Return a Titan-managed OAuth credential, if one is available."""
        if not self.oauth_manager:
            return None

        try:
            return self.oauth_manager.get_credential_blocking(
                self.build_oauth_request(interactive=interactive),
                sink=sink,
            )
        except (OAuthAuthenticationRequired, OAuthProviderNotFound):
            return None
        except OAuthError as exc:
            raise FirebaseClientError(
                f"Firebase OAuth credential resolution failed: {exc}"
            ) from exc

    def resolve_access_token(
        self,
        *,
        sink: Optional[OAuthEventSink] = None,
        interactive: bool = False,
    ) -> tuple[Optional[str], Optional[str]]:
        """Return the access token and safe source label Titan will use."""
        credential = self.get_oauth_credential(sink=sink, interactive=interactive)
        if credential:
            return credential.access_token, credential.source

        access_token_env_var = self.config.access_token_env_var
        if (
            access_token_env_var
            and access_token_env_var not in self._ignored_access_token_sources
        ):
            env_token = os.environ.get(access_token_env_var)
            if env_token and env_token.strip():
                return env_token.strip(), access_token_env_var

        if (
            self.config.access_token
            and "Firebase plugin access_token" not in self._ignored_access_token_sources
        ):
            return self.config.access_token, "Firebase plugin access_token"

        if "gcloud ADC" not in self._ignored_access_token_sources:
            adc_token = self.get_adc_access_token()
            if adc_token:
                return adc_token, "gcloud ADC"

        return None, None

    def get_access_token(
        self,
        *,
        sink: Optional[OAuthEventSink] = None,
        interactive: bool = False,
    ) -> Optional[str]:
        """Return an OAuth access token via OAuthManager, config, then gcloud ADC."""
        token, _source = self.resolve_access_token(
            sink=sink,
            interactive=interactive,
        )
        return token

    def get_access_token_secret_keys(self) -> list[str]:
        """Return keyring keys checked for saved Firebase access tokens."""
        keys = []
        if self.project_name:
            keys.append(f"{self.project_name}_{ACCESS_TOKEN_SECRET_KEY}")
        keys.append(ACCESS_TOKEN_SECRET_KEY)
        return keys

    def get_oauth_client_id_secret_keys(self) -> list[str]:
        """Return keyring keys checked for saved Google OAuth client IDs."""
        keys = []
        if self.project_name:
            keys.append(f"{self.project_name}_{OAUTH_CLIENT_ID_SECRET_KEY}")
        keys.append(OAUTH_CLIENT_ID_SECRET_KEY)
        return keys

    def get_oauth_client_secret_secret_keys(self) -> list[str]:
        """Return keyring keys checked for saved Google OAuth client secrets."""
        keys = []
        if self.project_name:
            keys.append(f"{self.project_name}_{OAUTH_CLIENT_SECRET_KEY}")
        keys.append(OAUTH_CLIENT_SECRET_KEY)
        return keys

    def configure_google_oauth(
        self,
        client_id: str,
        client_secret: str | None = None,
    ) -> None:
        """Configure browser-based Google OAuth for this client session."""
        normalized = client_id.strip() if client_id else ""
        if not normalized:
            raise FirebaseClientError("Google OAuth client ID is required.")

        current_client_id = self.config.oauth_client_id
        normalized_secret = (
            client_secret.strip()
            if isinstance(client_secret, str) and client_secret.strip()
            else (
                self.config.oauth_client_secret
                if current_client_id == normalized
                else None
            )
        )

        from .oauth import GoogleOAuthFlow, GoogleOAuthProvider

        self.config = self.config.model_copy(
            update={
                "oauth_client_id": normalized,
                "oauth_client_secret": normalized_secret,
            }
        )
        if not self.oauth_manager:
            if not self.secrets:
                raise FirebaseClientError("Titan SecretManager is not available.")
            self.oauth_manager = OAuthManager(self.secrets)

        self.oauth_manager.providers["google"] = GoogleOAuthProvider(
            GoogleOAuthFlow(
                client_id=normalized,
                client_secret=normalized_secret,
                redirect_port=self.config.oauth_redirect_port,
                scopes=self.config.oauth_scopes,
                timeout=self.config.oauth_timeout,
                token_request_timeout=self.config.request_timeout,
            )
        )

    def save_oauth_client_id(
        self,
        client_id: str,
        client_secret: str | None = None,
        scope: ScopeType = "user",
    ) -> None:
        """Persist a Google OAuth client ID and enable browser login."""
        if not self.secrets:
            raise FirebaseClientError("Titan SecretManager is not available.")

        normalized = client_id.strip() if client_id else ""
        if not normalized:
            raise FirebaseClientError("Google OAuth client ID is required.")
        normalized_secret = (
            client_secret.strip()
            if isinstance(client_secret, str) and client_secret.strip()
            else None
        )

        keys = [OAUTH_CLIENT_ID_SECRET_KEY]
        if self.project_name:
            keys.insert(0, f"{self.project_name}_{OAUTH_CLIENT_ID_SECRET_KEY}")

        for key in keys:
            self.secrets.set(key, normalized, scope=scope)
        if normalized_secret:
            secret_keys = [OAUTH_CLIENT_SECRET_KEY]
            if self.project_name:
                secret_keys.insert(0, f"{self.project_name}_{OAUTH_CLIENT_SECRET_KEY}")
            for key in secret_keys:
                self.secrets.set(key, normalized_secret, scope=scope)
        else:
            for key in self.get_oauth_client_secret_secret_keys():
                self.secrets.delete(key, scope=scope)

        self.configure_google_oauth(normalized, client_secret=normalized_secret)

    def delete_oauth_client_id(self, scope: ScopeType = "user") -> bool:
        """Delete saved Google OAuth client IDs and clear runtime OAuth config."""
        deleted = False
        if self.secrets:
            for key in (
                self.get_oauth_client_id_secret_keys()
                + self.get_oauth_client_secret_secret_keys()
            ):
                self.secrets.delete(key, scope=scope)
                deleted = True

        self.config = self.config.model_copy(
            update={"oauth_client_id": None, "oauth_client_secret": None}
        )
        if self.oauth_manager:
            self.oauth_manager.providers.pop("google", None)
        return deleted

    def save_access_token(self, token: str, scope: ScopeType = "user") -> None:
        """Persist a Firebase access token using Titan's OAuth token store."""
        normalized = token.strip() if token else ""
        if not normalized:
            raise FirebaseClientError("Firebase access token is required.")
        if not self.secrets:
            raise FirebaseClientError("Titan SecretManager is not available.")
        if not self.oauth_manager:
            raise FirebaseClientError("Titan OAuthManager is not available.")

        try:
            self.oauth_manager.save_token_set_blocking(
                self.build_oauth_request(),
                OAuthTokenSet(
                    access_token=normalized,
                    scopes=self.config.oauth_scopes,
                    metadata={"provider": "firebase", "kind": "manual_access_token"},
                ),
                scope=scope,
            )
        except OAuthError as exc:
            raise FirebaseClientError(
                f"Could not save Firebase access token: {exc}"
            ) from exc

    def get_access_token_source_label(self) -> Optional[str]:
        """Return a safe label for the currently resolved auth source."""
        _token, source = self.resolve_access_token()
        if source:
            if source == self.config.access_token_env_var:
                return self.config.access_token_env_var
            if source.startswith("keyring:"):
                return source
            if source in {
                "oauth-cache",
                "oauth-refresh",
                "oauth-login",
            }:
                return "Titan OAuth token store"
            return source

        return None

    def get_login_command(self) -> str:
        """Return the command users should run to create an ADC session."""
        return auth.adc_login_hint()

    def is_available(self, *, sink: Optional[OAuthEventSink] = None) -> bool:
        """Return whether an OAuth token is available for Firebase requests."""
        try:
            return bool(self.get_access_token(sink=sink))
        except FirebaseClientError:
            return False

    def invalidate_access_token_source(
        self,
        source: Optional[str],
        *,
        scope: ScopeType = "user",
    ) -> bool:
        """Invalidate one rejected auth source for the current client session."""
        if not source:
            return False

        self._ignored_access_token_sources.add(source)

        if source.startswith("keyring:") and self.secrets:
            key = source.removeprefix("keyring:")
            self.secrets.delete(key, scope=scope)
            return True

        if source in {"oauth-cache", "oauth-refresh", "oauth-login"}:
            if self.oauth_manager:
                try:
                    self.oauth_manager.token_store.delete(
                        self.build_oauth_request(),
                        scope=scope,
                    )
                    return True
                except OAuthError:
                    return False
            return False

        return source in {
            self.config.access_token_env_var,
            "Firebase plugin access_token",
            "gcloud ADC",
        }

    def get_remote_config(self, project_id: str) -> RemoteConfigTemplate:
        """
        Read a Firebase Remote Config template for one project.

        Args:
            project_id: Firebase project ID.

        Returns:
            RemoteConfigTemplate containing the JSON template and ETag.

        Raises:
            FirebaseClientError: If auth is missing or the API request fails.
        """
        normalized_project_id = project_id.strip() if project_id else ""
        if not normalized_project_id:
            raise FirebaseClientError("Firebase project_id is required.")

        token, auth_source = self.resolve_access_token()
        if not token:
            raise FirebaseClientError(
                "Firebase OAuth token not available. Configure Firebase "
                "oauth_client_id, set "
                f"{self.config.access_token_env_var}, paste a temporary access "
                f"token, or run: {self.get_login_command()}"
            )

        url = (
            f"{self.config.api_base_url}/projects/"
            f"{normalized_project_id}/remoteConfig"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": normalized_project_id,
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise FirebaseClientError(
                f"Firebase Remote Config request failed: {exc}"
            ) from exc

        if response.status_code == 200:
            try:
                template = response.json()
            except ValueError as exc:
                raise FirebaseClientError(
                    "Firebase Remote Config response was not valid JSON."
                ) from exc

            return RemoteConfigTemplate(
                project_id=normalized_project_id,
                template=template,
                etag=response.headers.get("ETag"),
            )

        detail = self._extract_error_detail(response)
        if response.status_code == 401:
            raise FirebaseAuthRejectedError(
                "Firebase OAuth token was rejected or expired. Refresh the saved "
                f"token, update {self.config.access_token_env_var}, or run: "
                f"{self.get_login_command()}. {detail}",
                auth_source=auth_source,
            )
        if response.status_code == 403:
            raise FirebaseClientError(
                "Firebase Remote Config permission denied for project "
                f"'{normalized_project_id}'. {detail}"
            )
        if response.status_code == 404:
            raise FirebaseClientError(
                "Firebase Remote Config project or template not found for "
                f"'{normalized_project_id}'. {detail}"
            )

        raise FirebaseClientError(
            "Firebase Remote Config request failed with status "
            f"{response.status_code}. {detail}"
        )

    def get_remote_config_inventory(
        self,
        targets: Sequence[FirebaseProjectTarget],
        *,
        continue_on_error: bool = True,
    ) -> RemoteConfigInventory:
        """
        Build a Remote Config key inventory across Firebase project targets.

        Args:
            targets: Firebase project targets to read.
            continue_on_error: Keep reading later projects when one project fails.

        Returns:
            RemoteConfigInventory with per-project parameters and aggregated keys.

        Raises:
            FirebaseClientError: If no targets are configured or a project read fails
                while continue_on_error is False.
        """
        from .operations.remoteconfig_inventory import build_remote_config_inventory

        return build_remote_config_inventory(
            client=self,
            targets=targets,
            continue_on_error=continue_on_error,
        )

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Extract a concise error detail from a Firebase HTTP response."""
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if message:
                    return str(message)
            if error:
                return str(error)

        text = (response.text or "").strip()
        return text or "No response detail provided."
