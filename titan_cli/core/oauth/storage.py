"""SecretManager-backed OAuth token storage."""

from __future__ import annotations

import json

from titan_cli.core.secrets import ScopeType, SecretManager

from .exceptions import OAuthStorageError
from .models import OAuthRequest, OAuthTokenSet, build_oauth_credential_key


class OAuthTokenStore:
    """Stores one JSON token-set blob per OAuth credential."""

    def __init__(
        self,
        secrets: SecretManager,
        *,
        namespace: str = "titan",
        secret_prefix: str = "oauth",
    ) -> None:
        self.secrets = secrets
        self.namespace = namespace
        self.secret_prefix = secret_prefix

    def build_secret_key(self, request: OAuthRequest) -> str:
        """Return the SecretManager key for an OAuth request."""
        return f"{self.secret_prefix}_{build_oauth_credential_key(request)}"

    def read(self, request: OAuthRequest) -> OAuthTokenSet | None:
        """Read a stored token set, if present."""
        secret_key = self.build_secret_key(request)
        raw_value = self._get_secret(secret_key)
        if not raw_value:
            return None

        try:
            payload = json.loads(raw_value)
            if not isinstance(payload, dict):
                raise ValueError("OAuth token payload is not an object.")
            return OAuthTokenSet.from_dict(payload)
        except Exception as exc:
            raise OAuthStorageError(
                f"Stored OAuth credential '{secret_key}' is not valid."
            ) from exc

    def write(
        self,
        request: OAuthRequest,
        token_set: OAuthTokenSet,
        *,
        scope: ScopeType = "user",
    ) -> str:
        """Write a token set and return the SecretManager key used."""
        secret_key = self.build_secret_key(request)
        payload = json.dumps(
            token_set.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
        self._set_secret(secret_key, payload, scope=scope)
        return secret_key

    def delete(self, request: OAuthRequest, *, scope: ScopeType = "user") -> None:
        """Delete a stored token set."""
        self._delete_secret(self.build_secret_key(request), scope=scope)

    def _get_secret(self, key: str) -> str | None:
        if self.namespace == "titan":
            return self.secrets.get(key)
        return self.secrets.get(key, namespace=self.namespace)

    def _set_secret(self, key: str, value: str, *, scope: ScopeType) -> None:
        if self.namespace == "titan":
            self.secrets.set(key, value, scope=scope)
            return
        self.secrets.set(key, value, namespace=self.namespace, scope=scope)

    def _delete_secret(self, key: str, *, scope: ScopeType) -> None:
        if self.namespace == "titan":
            self.secrets.delete(key, scope=scope)
            return
        self.secrets.delete(key, namespace=self.namespace, scope=scope)
