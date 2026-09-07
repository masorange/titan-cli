"""OAuth token storage backed by Titan's security boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, cast

from titan_cli.core.security.oauth_tokens import (
    OAuthSecretOrigin,
    OAuthSecretStoreProtocol,
    OAuthStorageScope,
    ResolvedOAuthSecret,
    coerce_oauth_secret_store,
)

from .exceptions import OAuthStorageError
from .models import OAuthRequest, OAuthTokenSet, build_oauth_credential_key

_VALID_STORAGE_SCOPES: Final[frozenset[str]] = frozenset({"project", "user"})


@dataclass(frozen=True)
class StoredOAuthTokenSet:
    """Stored OAuth token set with source and writable scope metadata."""

    token_set: OAuthTokenSet
    origin: OAuthSecretOrigin
    storage_scope: OAuthStorageScope | None

    @property
    def scope(self) -> OAuthStorageScope | None:
        """Writable storage scope retained for older call sites."""
        return self.storage_scope


class OAuthTokenStore:
    """Stores one JSON token-set blob per OAuth credential."""

    def __init__(
        self,
        secrets: object | None = None,
        *,
        namespace: str | None = None,
        secret_prefix: str = "oauth",
    ) -> None:
        self.secret_store: OAuthSecretStoreProtocol = coerce_oauth_secret_store(secrets)
        # Backward-compatible attribute for tests/callers that inspect the
        # injected store, without re-opening any legacy get/set path.
        self.secrets = self.secret_store
        default_namespace = getattr(self.secret_store, "namespace", "titan")
        if (
            namespace is not None
            and getattr(self.secret_store, "namespace_locked", False)
            and namespace != default_namespace
        ):
            raise ValueError(
                "OAuth token store namespace is derived from SecretBroker "
                "and cannot be overridden."
            )
        self.namespace = (
            namespace
            if namespace is not None
            else default_namespace
            if isinstance(default_namespace, str)
            else "titan"
        )
        self.secret_prefix = secret_prefix

    def build_secret_key(self, request: OAuthRequest) -> str:
        """Return the SecretManager key for an OAuth request."""
        return f"{self.secret_prefix}_{build_oauth_credential_key(request)}"

    def read(self, request: OAuthRequest) -> OAuthTokenSet | None:
        """Read a stored token set, if present."""
        stored_token_set = self.read_with_scope(request)
        return stored_token_set.token_set if stored_token_set else None

    def read_with_scope(self, request: OAuthRequest) -> StoredOAuthTokenSet | None:
        """Read a stored token set with the scope that supplied it."""
        secret_key = self.build_secret_key(request)
        resolved_secret = self._get_secret_with_scope(secret_key)
        if not resolved_secret or not resolved_secret.value:
            return None

        try:
            payload = json.loads(resolved_secret.value)
            if not isinstance(payload, dict):
                raise ValueError("OAuth token payload is not an object.")
            return StoredOAuthTokenSet(
                token_set=OAuthTokenSet.from_dict(payload),
                origin=resolved_secret.origin,
                storage_scope=resolved_secret.storage_scope,
            )
        except Exception as exc:
            raise OAuthStorageError(
                f"Stored OAuth credential '{secret_key}' is not valid."
            ) from exc

    def write(
        self,
        request: OAuthRequest,
        token_set: OAuthTokenSet,
        *,
        scope: OAuthStorageScope = "user",
    ) -> str:
        """Write a token set and return the SecretManager key used."""
        secret_key = self.build_secret_key(request)
        try:
            scope = _validate_scope(scope)
            payload = json.dumps(
                token_set.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
            )
            self._set_secret(secret_key, payload, scope=scope)
        except Exception as exc:
            raise OAuthStorageError(
                f"OAuth credential '{secret_key}' could not be written."
            ) from exc
        return secret_key

    def delete(
        self,
        request: OAuthRequest,
        *,
        scope: OAuthStorageScope = "user",
    ) -> None:
        """Delete a stored token set."""
        secret_key = self.build_secret_key(request)
        try:
            scope = _validate_scope(scope)
            self._delete_secret(secret_key, scope=scope)
            self._verify_secret_deleted(secret_key, scope=scope)
        except OAuthStorageError:
            raise
        except Exception as exc:
            raise OAuthStorageError(
                f"OAuth credential '{secret_key}' could not be deleted."
            ) from exc

    def read_env_secret(self, key: str) -> str | None:
        """Read an explicit access-token environment variable."""
        return self.secret_store.resolve_env(key)

    def read_legacy_secret(self, key: str) -> ResolvedOAuthSecret | None:
        """Read a configured legacy single-token secret."""
        return self._get_secret_with_scope(key)

    def _get_secret_with_scope(self, key: str) -> ResolvedOAuthSecret | None:
        return self.secret_store.resolve(key, namespace=self.namespace)

    def _set_secret(
        self,
        key: str,
        value: str,
        *,
        scope: OAuthStorageScope,
    ) -> None:
        self.secret_store.set(
            key,
            value,
            namespace=self.namespace,
            scope=scope,
        )

    def _delete_secret(self, key: str, *, scope: OAuthStorageScope) -> None:
        self.secret_store.delete(key, namespace=self.namespace, scope=scope)

    def _verify_secret_deleted(self, key: str, *, scope: OAuthStorageScope) -> None:
        """Verify that a scoped credential is gone after deletion."""
        scoped_value = self._get_secret_from_scope(key, scope=scope)
        if scoped_value is not None:
            raise OAuthStorageError(
                f"OAuth credential '{key}' was not deleted from {scope} storage."
            )

    def _get_secret_from_scope(
        self,
        key: str,
        *,
        scope: OAuthStorageScope,
    ) -> str | None:
        return self.secret_store.get_from_scope(
            key,
            namespace=self.namespace,
            scope=scope,
        )


def _validate_scope(scope: object) -> OAuthStorageScope:
    """Validate runtime storage scopes before delegating to SecretManager."""
    if scope not in _VALID_STORAGE_SCOPES:
        allowed = ", ".join(sorted(_VALID_STORAGE_SCOPES))
        raise ValueError(f"OAuth storage scope must be one of: {allowed}.")
    return cast(OAuthStorageScope, scope)
