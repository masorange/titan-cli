"""OAuth token storage bridge inside Titan's secret trust boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ._vault import OriginType, ScopeType, SecretManager
from .broker import SecretBroker
from .redaction import register_secret

OAuthSecretOrigin = OriginType
OAuthStorageScope = ScopeType


@dataclass(frozen=True)
class ResolvedOAuthSecret:
    """Secret value plus its origin and writable storage scope, when any."""

    value: str
    origin: OAuthSecretOrigin
    storage_scope: OAuthStorageScope | None

    @property
    def scope(self) -> str:
        """Backward-compatible label for callers migrating from SecretManager."""
        return "user" if self.origin == "keyring" else self.origin


class OAuthSecretStoreProtocol(Protocol):
    """Methods OAuth storage may use to cross the secret boundary."""

    def resolve(
        self,
        key: str,
        *,
        namespace: str = "titan",
    ) -> ResolvedOAuthSecret | None:
        """Resolve a secret through the configured cascade."""

    def resolve_env(self, key: str) -> str | None:
        """Resolve one explicit environment variable."""

    def set(
        self,
        key: str,
        value: str,
        *,
        namespace: str = "titan",
        scope: OAuthStorageScope = "user",
    ) -> None:
        """Store a secret in one writable scope."""

    def delete(
        self,
        key: str,
        *,
        namespace: str = "titan",
        scope: OAuthStorageScope = "user",
    ) -> None:
        """Delete a secret from one writable scope."""

    def get_from_scope(
        self,
        key: str,
        *,
        namespace: str = "titan",
        scope: OAuthStorageScope = "user",
    ) -> str | None:
        """Read one writable scope without cascade fallback."""


class OAuthSecretStore:
    """Secret-boundary adapter for OAuth token blobs and legacy credentials."""

    def __init__(
        self,
        *,
        project_path: Path | None = None,
        vault: SecretManager | None = None,
        namespace: str = "titan",
        namespace_locked: bool = False,
    ) -> None:
        self._vault = vault or SecretManager(project_path=project_path)
        self._namespace = namespace
        self._namespace_locked = namespace_locked

    @property
    def namespace(self) -> str:
        """Default namespace used when callers do not override one."""
        return self._namespace

    @property
    def namespace_locked(self) -> bool:
        """Whether this store's namespace came from a broker boundary."""
        return self._namespace_locked

    def resolve(
        self,
        key: str,
        *,
        namespace: str | None = None,
    ) -> ResolvedOAuthSecret | None:
        """Resolve a secret through the vault cascade."""
        value, origin = self._vault.resolve(
            key,
            namespace=namespace or self._namespace,
        )
        if not value or not value.strip() or origin is None:
            return None
        register_secret(value)
        return ResolvedOAuthSecret(
            value=value,
            origin=origin,
            storage_scope=_storage_scope_for_origin(origin),
        )

    def resolve_env(self, key: str) -> str | None:
        """Resolve an explicit environment variable by name."""
        return self._vault.resolve_env(key)

    def set(
        self,
        key: str,
        value: str,
        *,
        namespace: str | None = None,
        scope: OAuthStorageScope = "user",
    ) -> None:
        """Store an OAuth secret in a writable vault scope."""
        self._vault.set(
            key,
            value,
            namespace=namespace or self._namespace,
            scope=scope,
        )

    def delete(
        self,
        key: str,
        *,
        namespace: str | None = None,
        scope: OAuthStorageScope = "user",
    ) -> None:
        """Delete an OAuth secret from a writable vault scope."""
        self._vault.delete(
            key,
            namespace=namespace or self._namespace,
            scope=scope,
        )

    def get_from_scope(
        self,
        key: str,
        *,
        namespace: str | None = None,
        scope: OAuthStorageScope = "user",
    ) -> str | None:
        """Read one writable scope for delete-postcondition checks."""
        return self._vault.get_from_scope(
            key,
            namespace=namespace or self._namespace,
            scope=scope,
        )


def create_oauth_secret_store(
    project_path: Path | None = None,
    *,
    namespace: str = "titan",
) -> OAuthSecretStore:
    """Create an OAuth secret store scoped to a project root."""
    if project_path is None:
        from titan_cli.core.utils import find_project_root

        project_path = find_project_root()
    return OAuthSecretStore(project_path=project_path, namespace=namespace)


def create_oauth_secret_store_from_broker(broker: SecretBroker) -> OAuthSecretStore:
    """Create an OAuth secret store backed by a scoped broker's vault."""
    return OAuthSecretStore(
        vault=broker._vault,
        namespace=broker.namespace,
        namespace_locked=True,
    )


def coerce_oauth_secret_store(
    source: object | None = None,
    *,
    project_path: Path | None = None,
) -> OAuthSecretStoreProtocol:
    """Return the OAuth boundary adapter for supported secret sources."""
    if source is None:
        return create_oauth_secret_store(project_path=project_path)
    if isinstance(source, OAuthSecretStore):
        return source
    if isinstance(source, SecretBroker):
        return create_oauth_secret_store_from_broker(source)
    if isinstance(source, SecretManager):
        return OAuthSecretStore(vault=source)
    raise TypeError(
        "OAuth token storage requires OAuthSecretStore, SecretBroker, "
        "SecretManager, or None."
    )


def _storage_scope_for_origin(origin: OAuthSecretOrigin) -> OAuthStorageScope | None:
    if origin == "project":
        return "project"
    if origin == "keyring":
        return "user"
    return None
