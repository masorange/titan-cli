import asyncio
import json
import time

import pytest

from titan_cli.core.oauth import (
    CollectingOAuthEventSink,
    OAuthAuthenticationRequired,
    OAuthAuthorizationError,
    OAuthEvent,
    OAuthLockManager,
    OAuthManager,
    OAuthRequest,
    OAuthTokenSet,
    OAuthTokenStore,
    QueuedOAuthEventSink,
)


class FakeSecretManager:
    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self.values = dict(initial or {})
        self.set_calls: list[tuple[str, str, str]] = []

    def get(self, key: str, namespace: str = "titan") -> str | None:
        return self.values.get(key)

    def set(
        self,
        key: str,
        value: str,
        namespace: str = "titan",
        scope: str = "user",
    ) -> None:
        self.values[key] = value
        self.set_calls.append((key, value, scope))

    def delete(self, key: str, namespace: str = "titan", scope: str = "user") -> None:
        self.values.pop(key, None)


def _manager(
    secrets: FakeSecretManager,
    tmp_path,
    *,
    providers=None,
) -> OAuthManager:
    return OAuthManager(
        secrets,
        providers=providers,
        lock_manager=OAuthLockManager(
            lock_dir=tmp_path,
            enable_file_locks=False,
        ),
    )


def _request(**overrides) -> OAuthRequest:
    defaults = {
        "provider": "google",
        "connection_id": "firebase:demo",
        "scopes": ["https://www.googleapis.com/auth/firebase.remoteconfig"],
        "legacy_secret_keys": ["demo_firebase_access_token"],
        "access_token_env_var": "FIREBASE_ACCESS_TOKEN",
        "subject": "demo",
    }
    defaults.update(overrides)
    return OAuthRequest(**defaults)


def test_oauth_manager_prefers_environment_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FIREBASE_ACCESS_TOKEN", "env-token")
    manager = _manager(
        FakeSecretManager({"demo_firebase_access_token": "legacy-token"}),
        tmp_path,
    )
    sink = CollectingOAuthEventSink()

    credential = asyncio.run(manager.get_credential(_request(), sink=sink))

    assert credential.access_token == "env-token"
    assert credential.source == "FIREBASE_ACCESS_TOKEN"
    assert sink.events[-1].type == "oauth.resolve.succeeded"
    assert sink.events[-1].metadata == {"source": "FIREBASE_ACCESS_TOKEN"}


def test_oauth_manager_uses_stored_oauth_blob(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)
    secrets = FakeSecretManager()
    request = _request()
    store = OAuthTokenStore(secrets)
    store.write(
        request,
        OAuthTokenSet(
            access_token="stored-token",
            expires_at=int(time.time()) + 3600,
        ),
    )
    manager = OAuthManager(
        secrets,
        token_store=store,
        lock_manager=OAuthLockManager(lock_dir=tmp_path, enable_file_locks=False),
    )

    credential = asyncio.run(manager.get_credential(request))

    assert credential.access_token == "stored-token"
    assert credential.source == "oauth-cache"


def test_oauth_manager_refreshes_token_inside_expiry_margin(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)
    secrets = FakeSecretManager()
    request = _request()
    store = OAuthTokenStore(secrets)
    store.write(
        request,
        OAuthTokenSet(
            access_token="almost-expired-token",
            refresh_token="refresh-token",
            expires_at=int(time.time()) + 120,
        ),
    )

    class RefreshProvider:
        async def refresh(self, request, token_set, sink):
            return OAuthTokenSet(
                access_token="fresh-token",
                refresh_token=token_set.refresh_token,
                expires_at=int(time.time()) + 3600,
            )

        async def authorize(self, request, sink):
            raise AssertionError("authorize should not run")

    manager = OAuthManager(
        secrets,
        providers={"google": RefreshProvider()},
        token_store=store,
        lock_manager=OAuthLockManager(lock_dir=tmp_path, enable_file_locks=False),
        refresh_margin_seconds=300,
    )

    credential = asyncio.run(manager.get_credential(request))

    assert credential.access_token == "fresh-token"
    assert credential.source == "oauth-refresh"


def test_oauth_manager_refreshes_before_legacy_secret(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)
    secrets = FakeSecretManager({"demo_firebase_access_token": "legacy-token"})
    request = _request()
    store = OAuthTokenStore(secrets)
    store.write(
        request,
        OAuthTokenSet(
            access_token="expired-oauth-token",
            refresh_token="refresh-token",
            expires_at=1,
        ),
    )

    class RefreshProvider:
        async def refresh(self, request, token_set, sink):
            return OAuthTokenSet(
                access_token="fresh-token",
                refresh_token=token_set.refresh_token,
                expires_at=int(time.time()) + 3600,
            )

        async def authorize(self, request, sink):
            raise AssertionError("authorize should not run")

    manager = OAuthManager(
        secrets,
        providers={"google": RefreshProvider()},
        token_store=store,
        lock_manager=OAuthLockManager(lock_dir=tmp_path, enable_file_locks=False),
    )

    credential = asyncio.run(manager.get_credential(request))

    assert credential.access_token == "fresh-token"
    assert credential.source == "oauth-refresh"


def test_oauth_manager_reads_legacy_secret_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)
    manager = _manager(
        FakeSecretManager({"demo_firebase_access_token": " legacy-token "}),
        tmp_path,
    )

    credential = asyncio.run(manager.get_credential(_request()))

    assert credential.access_token == "legacy-token"
    assert credential.source == "keyring:demo_firebase_access_token"


def test_oauth_manager_raises_when_no_credential(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)
    manager = _manager(FakeSecretManager(), tmp_path)

    with pytest.raises(OAuthAuthenticationRequired):
        asyncio.run(manager.get_credential(_request()))


def test_oauth_manager_wraps_authorization_errors(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)

    class BrokenProvider:
        async def refresh(self, request, token_set, sink):
            raise AssertionError("refresh should not run")

        async def authorize(self, request, sink):
            raise RuntimeError("browser failed")

    manager = _manager(
        FakeSecretManager(),
        tmp_path,
        providers={"google": BrokenProvider()},
    )
    request = _request(interactive=True)

    with pytest.raises(OAuthAuthorizationError, match="browser failed"):
        asyncio.run(manager.get_credential(request))


def test_oauth_manager_refreshes_only_once_under_concurrency(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)
    secrets = FakeSecretManager()
    request = _request()
    store = OAuthTokenStore(secrets)
    store.write(
        request,
        OAuthTokenSet(
            access_token="expired-token",
            refresh_token="refresh-token",
            expires_at=1,
        ),
    )

    class RefreshProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def refresh(self, request, token_set, sink):
            self.calls += 1
            await asyncio.sleep(0.02)
            return OAuthTokenSet(
                access_token=f"fresh-token-{self.calls}",
                refresh_token=token_set.refresh_token,
                expires_at=int(time.time()) + 3600,
            )

        async def authorize(self, request, sink):
            raise AssertionError("authorize should not run")

    provider = RefreshProvider()
    manager = OAuthManager(
        secrets,
        providers={"google": provider},
        token_store=store,
        lock_manager=OAuthLockManager(lock_dir=tmp_path, enable_file_locks=False),
    )

    async def resolve_many():
        return await asyncio.gather(
            *(manager.get_credential(request) for _ in range(8))
        )

    credentials = asyncio.run(resolve_many())

    assert provider.calls == 1
    assert {credential.access_token for credential in credentials} == {
        "fresh-token-1"
    }


def test_oauth_manager_interactive_authorizes_after_refresh_failure(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)
    secrets = FakeSecretManager()
    request = _request(interactive=True)
    store = OAuthTokenStore(secrets)
    old_secret_key = store.write(
        request,
        OAuthTokenSet(
            access_token="expired-token",
            refresh_token="old-refresh-token",
            expires_at=1,
        ),
    )

    class ReauthorizingProvider:
        def __init__(self) -> None:
            self.refresh_calls = 0
            self.authorize_calls = 0

        async def refresh(self, request, token_set, sink):
            self.refresh_calls += 1
            raise RuntimeError("refresh token revoked")

        async def authorize(self, request, sink):
            self.authorize_calls += 1
            return OAuthTokenSet(
                access_token="new-login-token",
                refresh_token="new-refresh-token",
                expires_at=int(time.time()) + 3600,
            )

    provider = ReauthorizingProvider()
    sink = CollectingOAuthEventSink()
    manager = OAuthManager(
        secrets,
        providers={"google": provider},
        token_store=store,
        lock_manager=OAuthLockManager(lock_dir=tmp_path, enable_file_locks=False),
    )

    credential = asyncio.run(manager.get_credential(request, sink=sink))

    assert credential.access_token == "new-login-token"
    assert credential.source == "oauth-login"
    assert provider.refresh_calls == 1
    assert provider.authorize_calls == 1
    stored_payload = json.loads(secrets.values[old_secret_key])
    assert stored_payload["refresh_token"] == "new-refresh-token"
    assert "oauth.refresh.stale_deleted" in [event.type for event in sink.events]


def test_oauth_manager_saves_one_json_blob(tmp_path) -> None:
    secrets = FakeSecretManager()
    manager = _manager(secrets, tmp_path)
    request = _request()

    secret_key = manager.save_token_set_blocking(
        request,
        OAuthTokenSet(access_token="manual-token"),
    )

    assert secret_key.startswith("oauth_google_")
    stored_payload = json.loads(secrets.values[secret_key])
    assert stored_payload["access_token"] == "manual-token"
    assert [call[0] for call in secrets.set_calls] == [secret_key]


def test_queued_oauth_event_sink_drains_events() -> None:
    sink = QueuedOAuthEventSink()

    sink.emit(OAuthEvent(type="oauth.resolve.started", operation_id="op-1"))
    sink.emit(OAuthEvent(type="oauth.resolve.succeeded", operation_id="op-1"))

    assert [event.type for event in sink.drain()] == [
        "oauth.resolve.started",
        "oauth.resolve.succeeded",
    ]
    assert sink.get(block=False) is None
