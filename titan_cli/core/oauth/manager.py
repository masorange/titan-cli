"""Async-ready OAuth credential manager."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Protocol

from titan_cli.core.secrets import ScopeType, SecretManager

from .events import NullOAuthEventSink, OAuthEvent, OAuthEventSink
from .exceptions import (
    OAuthAuthenticationRequired,
    OAuthAuthorizationError,
    OAuthError,
    OAuthProviderNotFound,
    OAuthTokenInvalidError,
    OAuthTokenRefreshError,
)
from .locks import OAuthLockManager
from .models import (
    OAuthCredential,
    OAuthRequest,
    OAuthTokenSet,
    build_oauth_credential_key,
)
from .storage import OAuthTokenStore


class OAuthProvider(Protocol):
    """Provider adapter used by OAuthManager for refresh/login flows."""

    async def refresh(
        self,
        request: OAuthRequest,
        token_set: OAuthTokenSet,
        sink: OAuthEventSink,
    ) -> OAuthTokenSet:
        """Refresh a stored token set."""

    async def authorize(
        self,
        request: OAuthRequest,
        sink: OAuthEventSink,
    ) -> OAuthTokenSet:
        """Run an interactive authorization flow."""


class OAuthManager:
    """Resolves OAuth credentials through env, storage, legacy keys, and providers."""

    def __init__(
        self,
        secrets: SecretManager,
        *,
        providers: dict[str, OAuthProvider] | None = None,
        token_store: OAuthTokenStore | None = None,
        lock_manager: OAuthLockManager | None = None,
        refresh_margin_seconds: int = 300,
    ) -> None:
        self.secrets = secrets
        self.providers = providers or {}
        self.token_store = token_store or OAuthTokenStore(secrets)
        self.lock_manager = lock_manager or OAuthLockManager()
        self.refresh_margin_seconds = refresh_margin_seconds

    async def get_credential(
        self,
        request: OAuthRequest,
        *,
        sink: OAuthEventSink | None = None,
    ) -> OAuthCredential:
        """Resolve a credential without blocking the event loop while waiting."""
        event_sink = sink or NullOAuthEventSink()
        operation_id = uuid.uuid4().hex
        credential_key = build_oauth_credential_key(request)

        self._emit(
            event_sink,
            "oauth.resolve.started",
            operation_id,
            request,
            credential_key,
            "Resolving OAuth credential.",
        )

        credential = self._resolve_without_provider(
            request,
            credential_key,
            include_legacy=False,
        )
        if credential:
            self._emit_resolved(event_sink, operation_id, request, credential)
            return credential

        stored_token_set = self.token_store.read_with_scope(request)
        provider = self.providers.get(request.provider)
        if not provider:
            legacy_credential = self._credential_from_legacy_secret(
                request,
                credential_key,
            )
            if legacy_credential:
                self._emit_resolved(
                    event_sink,
                    operation_id,
                    request,
                    legacy_credential,
                )
                return legacy_credential

            if stored_token_set and stored_token_set.token_set.refresh_token:
                self._emit(
                    event_sink,
                    "oauth.provider.missing",
                    operation_id,
                    request,
                    credential_key,
                    "OAuth refresh provider is not registered.",
                )
                raise OAuthProviderNotFound(
                    f"OAuth provider '{request.provider}' is not registered."
                )
            if request.interactive:
                self._emit(
                    event_sink,
                    "oauth.provider.missing",
                    operation_id,
                    request,
                    credential_key,
                    "OAuth authorization provider is not registered.",
                )
                raise OAuthProviderNotFound(
                    f"OAuth provider '{request.provider}' is not registered."
                )

            self._emit(
                event_sink,
                "oauth.resolve.auth_required",
                operation_id,
                request,
                credential_key,
                "OAuth authentication is required.",
            )
            raise OAuthAuthenticationRequired(
                f"OAuth credential for '{request.connection_id}' is not available."
            )

        async with self.lock_manager.lock(credential_key):
            self._emit(
                event_sink,
                "oauth.lock.acquired",
                operation_id,
                request,
                credential_key,
                "OAuth credential lock acquired.",
            )

            credential = self._resolve_without_provider(
                request,
                credential_key,
                include_legacy=False,
            )
            if credential:
                self._emit_resolved(event_sink, operation_id, request, credential)
                return credential

            stored_token_set = self.token_store.read_with_scope(request)
            reauthorize_storage_scope: ScopeType = "user"
            if stored_token_set and stored_token_set.token_set.refresh_token:
                storage_scope = stored_token_set.scope
                self._emit(
                    event_sink,
                    "oauth.refresh.started",
                    operation_id,
                    request,
                    credential_key,
                    "Refreshing OAuth credential.",
                )
                try:
                    refreshed = await provider.refresh(
                        request,
                        stored_token_set.token_set,
                        event_sink,
                    )
                except OAuthTokenInvalidError:
                    self._emit(
                        event_sink,
                        "oauth.refresh.failed",
                        operation_id,
                        request,
                        credential_key,
                        "OAuth refresh failed.",
                    )
                    if not request.interactive:
                        raise
                    self.token_store.delete(request, scope=storage_scope)
                    reauthorize_storage_scope = storage_scope
                    self._emit(
                        event_sink,
                        "oauth.refresh.stale_deleted",
                        operation_id,
                        request,
                        credential_key,
                        "Deleted stale OAuth credential after refresh failure.",
                    )
                except OAuthError:
                    self._emit(
                        event_sink,
                        "oauth.refresh.failed",
                        operation_id,
                        request,
                        credential_key,
                        "OAuth refresh failed.",
                    )
                    if not request.interactive:
                        raise
                    reauthorize_storage_scope = storage_scope
                except Exception as exc:
                    self._emit(
                        event_sink,
                        "oauth.refresh.failed",
                        operation_id,
                        request,
                        credential_key,
                        "OAuth refresh failed.",
                    )
                    if not request.interactive:
                        raise OAuthTokenRefreshError(str(exc)) from exc
                    reauthorize_storage_scope = storage_scope
                else:
                    self.token_store.write(request, refreshed, scope=storage_scope)
                    credential = self._credential_from_token_set(
                        request,
                        credential_key,
                        refreshed,
                        source="oauth-refresh",
                    )
                    self._emit_resolved(event_sink, operation_id, request, credential)
                    return credential

            if request.interactive:
                self._emit(
                    event_sink,
                    "oauth.authorize.started",
                    operation_id,
                    request,
                    credential_key,
                    "Starting OAuth authorization.",
                )
                try:
                    token_set = await provider.authorize(request, event_sink)
                except OAuthError:
                    self._emit(
                        event_sink,
                        "oauth.authorize.failed",
                        operation_id,
                        request,
                        credential_key,
                        "OAuth authorization failed.",
                    )
                    raise
                except Exception as exc:
                    self._emit(
                        event_sink,
                        "oauth.authorize.failed",
                        operation_id,
                        request,
                        credential_key,
                        "OAuth authorization failed.",
                    )
                    raise OAuthAuthorizationError(str(exc)) from exc
                self.token_store.write(
                    request,
                    token_set,
                    scope=reauthorize_storage_scope,
                )
                credential = self._credential_from_token_set(
                    request,
                    credential_key,
                    token_set,
                    source="oauth-login",
                )
                self._emit_resolved(event_sink, operation_id, request, credential)
                return credential

            legacy_credential = self._credential_from_legacy_secret(
                request,
                credential_key,
            )
            if legacy_credential:
                self._emit_resolved(
                    event_sink,
                    operation_id,
                    request,
                    legacy_credential,
                )
                return legacy_credential

            self._emit(
                event_sink,
                "oauth.resolve.auth_required",
                operation_id,
                request,
                credential_key,
                "OAuth authentication is required.",
            )
            raise OAuthAuthenticationRequired(
                f"OAuth credential for '{request.connection_id}' is not available."
            )

    def get_credential_blocking(
        self,
        request: OAuthRequest,
        *,
        sink: OAuthEventSink | None = None,
    ) -> OAuthCredential:
        """Resolve a credential from synchronous code."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.get_credential(request, sink=sink))

        raise OAuthError(
            "get_credential_blocking cannot run inside an active event loop. "
            "Use await get_credential(...) instead."
        )

    async def save_token_set(
        self,
        request: OAuthRequest,
        token_set: OAuthTokenSet,
        *,
        scope: ScopeType = "user",
        sink: OAuthEventSink | None = None,
    ) -> str:
        """Persist a token set under the request's credential lock."""
        event_sink = sink or NullOAuthEventSink()
        operation_id = uuid.uuid4().hex
        credential_key = build_oauth_credential_key(request)

        async with self.lock_manager.lock(credential_key):
            secret_key = self.token_store.write(request, token_set, scope=scope)

        self._emit(
            event_sink,
            "oauth.storage.saved",
            operation_id,
            request,
            credential_key,
            "OAuth credential saved.",
            metadata={"secret_key": secret_key},
        )
        return secret_key

    def save_token_set_blocking(
        self,
        request: OAuthRequest,
        token_set: OAuthTokenSet,
        *,
        scope: ScopeType = "user",
        sink: OAuthEventSink | None = None,
    ) -> str:
        """Persist a token set from synchronous code."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.save_token_set(
                    request,
                    token_set,
                    scope=scope,
                    sink=sink,
                )
            )

        raise OAuthError(
            "save_token_set_blocking cannot run inside an active event loop. "
            "Use await save_token_set(...) instead."
        )

    def _resolve_without_provider(
        self,
        request: OAuthRequest,
        credential_key: str,
        *,
        include_legacy: bool = True,
    ) -> OAuthCredential | None:
        env_credential = self._credential_from_env(request, credential_key)
        if env_credential:
            return env_credential

        stored_token_set = self.token_store.read(request)
        if stored_token_set and stored_token_set.is_valid(
            refresh_margin_seconds=self.refresh_margin_seconds,
        ):
            return self._credential_from_token_set(
                request,
                credential_key,
                stored_token_set,
                source="oauth-cache",
            )

        if include_legacy:
            return self._credential_from_legacy_secret(request, credential_key)
        return None

    def _credential_from_env(
        self,
        request: OAuthRequest,
        credential_key: str,
    ) -> OAuthCredential | None:
        if not request.access_token_env_var:
            return None
        token = os.environ.get(request.access_token_env_var, "").strip()
        if not token:
            return None
        return OAuthCredential(
            access_token=token,
            token_type="Bearer",
            scopes=request.scopes,
            provider=request.provider,
            connection_id=request.connection_id,
            credential_key=credential_key,
            source=request.access_token_env_var,
        )

    def _credential_from_legacy_secret(
        self,
        request: OAuthRequest,
        credential_key: str,
    ) -> OAuthCredential | None:
        for secret_key in request.legacy_secret_keys:
            token = self.secrets.get(secret_key)
            if token and token.strip():
                return OAuthCredential(
                    access_token=token.strip(),
                    token_type="Bearer",
                    scopes=request.scopes,
                    provider=request.provider,
                    connection_id=request.connection_id,
                    credential_key=credential_key,
                    source=f"keyring:{secret_key}",
                )
        return None

    def _credential_from_token_set(
        self,
        request: OAuthRequest,
        credential_key: str,
        token_set: OAuthTokenSet,
        *,
        source: str,
    ) -> OAuthCredential:
        return OAuthCredential(
            access_token=token_set.access_token,
            token_type=token_set.token_type,
            expires_at=token_set.expires_at,
            scopes=token_set.scopes or request.scopes,
            provider=request.provider,
            connection_id=request.connection_id,
            credential_key=credential_key,
            source=source,
        )

    def _emit_resolved(
        self,
        sink: OAuthEventSink,
        operation_id: str,
        request: OAuthRequest,
        credential: OAuthCredential,
    ) -> None:
        self._emit(
            sink,
            "oauth.resolve.succeeded",
            operation_id,
            request,
            credential.credential_key,
            "OAuth credential resolved.",
            metadata={"source": credential.source},
        )

    def _emit(
        self,
        sink: OAuthEventSink,
        event_type: str,
        operation_id: str,
        request: OAuthRequest,
        credential_key: str,
        message: str,
        *,
        metadata: dict | None = None,
    ) -> None:
        sink.emit(
            OAuthEvent(
                type=event_type,
                operation_id=operation_id,
                credential_key=credential_key,
                provider=request.provider,
                connection_id=request.connection_id,
                message=message,
                metadata=self._safe_metadata(metadata or {}),
            )
        )

    def _safe_metadata(self, metadata: dict) -> dict:
        safe_metadata = {}
        for key, value in metadata.items():
            if "token" in str(key).lower():
                safe_metadata[key] = "<redacted>"
            else:
                safe_metadata[key] = value
        return safe_metadata
