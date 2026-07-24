import json
import time
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from titan_cli.core.oauth import OAuthLockManager, OAuthManager, OAuthTokenSet
from titan_plugin_firebase.client import (
    FirebaseClient,
    OAUTH_CLIENT_ID_SECRET_KEY,
    OAUTH_CLIENT_SECRET_KEY,
)
from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.exceptions import (
    FirebaseAuthRejectedError,
    FirebaseClientError,
)


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        text: str = "",
    ):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.fixture(autouse=True)
def _clear_env_token(monkeypatch) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)


def _client(
    secrets: MagicMock | None = None,
    project_name: str | None = None,
    oauth_manager: OAuthManager | None = None,
) -> FirebaseClient:
    return FirebaseClient(
        FirebasePluginConfig(),
        secrets=secrets,
        project_name=project_name,
        oauth_manager=oauth_manager,
    )


def test_config_defaults_and_overrides() -> None:
    default = FirebasePluginConfig()
    overridden = FirebasePluginConfig(
        default_project=" demo ",
        default_environment=" prod ",
        api_base_url="https://example.com/firebase/",
        request_timeout=5,
        oauth_client_id=" google-client-id ",
        oauth_client_secret=" google-client-secret ",
        oauth_redirect_port=8766,
        oauth_timeout=90,
        projects=[{"brand": "orange", "project_id": "orange-prod"}],
        brand_projects={"android": {"orange": "orange-app"}},
    )

    assert default.default_project is None
    assert default.access_token is None
    assert default.request_timeout == 30
    assert default.access_token_env_var == "FIREBASE_ACCESS_TOKEN"
    assert default.oauth_client_id is None
    assert default.oauth_redirect_port == 0
    assert default.oauth_timeout == 180
    assert default.oauth_scopes == [
        "https://www.googleapis.com/auth/cloud-platform"
    ]
    assert overridden.default_project == "demo"
    assert overridden.default_environment == "prod"
    assert overridden.api_base_url == "https://example.com/firebase"
    assert overridden.request_timeout == 5
    assert overridden.oauth_client_id == "google-client-id"
    assert overridden.oauth_client_secret == "google-client-secret"
    assert overridden.oauth_redirect_port == 8766
    assert overridden.oauth_timeout == 90
    assert overridden.projects[0].project_id == "orange-prod"
    assert overridden.brand_projects["android"]["orange"] == "orange-app"


def test_is_available_requires_gcloud_and_adc(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(
        "titan_plugin_firebase.client.auth.is_gcloud_installed",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        "titan_plugin_firebase.client.auth.get_adc_access_token",
        MagicMock(return_value="token"),
    )

    assert client.is_available() is True


def test_is_available_returns_false_without_adc(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(
        "titan_plugin_firebase.client.auth.is_gcloud_installed",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        "titan_plugin_firebase.client.auth.get_adc_access_token",
        MagicMock(return_value=None),
    )

    assert client.is_available() is False


def test_is_available_accepts_env_access_token(monkeypatch) -> None:
    client = _client()
    monkeypatch.setenv("FIREBASE_ACCESS_TOKEN", "env-token")
    monkeypatch.setattr(
        "titan_plugin_firebase.client.auth.get_adc_access_token",
        MagicMock(return_value=None),
    )

    assert client.is_available() is True
    assert client.get_access_token() == "env-token"


def test_is_available_accepts_keyring_access_token(monkeypatch) -> None:
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "demo_firebase_access_token": " saved-token ",
    }.get(key)
    client = _client(secrets=secrets, project_name="demo")
    monkeypatch.setattr(
        "titan_plugin_firebase.client.auth.get_adc_access_token",
        MagicMock(return_value=None),
    )

    assert client.is_available() is True
    assert client.get_access_token() == "saved-token"
    assert (
        client.get_access_token_source_label()
        == "keyring:demo_firebase_access_token"
    )


def test_is_available_returns_false_when_refresh_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FIREBASE_ACCESS_TOKEN", raising=False)
    secrets = MagicMock()
    secrets.get.return_value = None

    class BrokenRefreshProvider:
        async def refresh(self, request, token_set, sink):
            raise RuntimeError("refresh token revoked")

        async def authorize(self, request, sink):
            return OAuthTokenSet(
                access_token="fresh-token",
                refresh_token="fresh-refresh-token",
                expires_at=int(time.time()) + 3600,
            )

    oauth_manager = OAuthManager(
        secrets,
        providers={"google": BrokenRefreshProvider()},
        lock_manager=OAuthLockManager(lock_dir=tmp_path, enable_file_locks=False),
    )
    client = _client(
        secrets=secrets,
        project_name="demo",
        oauth_manager=oauth_manager,
    )
    oauth_manager.token_store.write(
        client.build_oauth_request(),
        OAuthTokenSet(
            access_token="expired-token",
            refresh_token="revoked-refresh-token",
            expires_at=1,
        ),
    )

    assert client.is_available() is False
    assert client.get_access_token(interactive=True) == "fresh-token"


def test_get_access_token_prefers_env_over_keyring(monkeypatch) -> None:
    secrets = MagicMock()
    secrets.get.return_value = "saved-token"
    client = _client(secrets=secrets, project_name="demo")
    monkeypatch.setenv("FIREBASE_ACCESS_TOKEN", "env-token")

    assert client.get_access_token() == "env-token"
    assert client.get_access_token_source_label() == "FIREBASE_ACCESS_TOKEN"


def test_save_access_token_uses_oauth_token_store_blob(tmp_path) -> None:
    secrets = MagicMock()
    oauth_manager = OAuthManager(
        secrets,
        lock_manager=OAuthLockManager(lock_dir=tmp_path, enable_file_locks=False),
    )
    client = _client(
        secrets=secrets,
        project_name="demo",
        oauth_manager=oauth_manager,
    )
    expected_key = client.oauth_manager.token_store.build_secret_key(
        client.build_oauth_request()
    )

    client.save_access_token(" token-value ")

    secrets.set.assert_called_once()
    secret_key, secret_value = secrets.set.call_args.args
    assert secret_key == expected_key
    assert json.loads(secret_value)["access_token"] == "token-value"
    assert secrets.set.call_args.kwargs == {"scope": "user"}


def test_save_oauth_client_id_persists_and_configures_google_provider() -> None:
    secrets = MagicMock()
    client = _client(secrets=secrets, project_name="demo")

    client.save_oauth_client_id(
        " google-client-id ",
        client_secret=" google-client-secret ",
    )

    assert client.config.oauth_client_id == "google-client-id"
    assert client.config.oauth_client_secret == "google-client-secret"
    assert "google" in client.oauth_manager.providers
    assert secrets.set.call_args_list[0].args == (
        f"demo_{OAUTH_CLIENT_ID_SECRET_KEY}",
        "google-client-id",
    )
    assert secrets.set.call_args_list[1].args == (
        OAUTH_CLIENT_ID_SECRET_KEY,
        "google-client-id",
    )
    assert secrets.set.call_args_list[2].args == (
        f"demo_{OAUTH_CLIENT_SECRET_KEY}",
        "google-client-secret",
    )
    assert secrets.set.call_args_list[3].args == (
        OAUTH_CLIENT_SECRET_KEY,
        "google-client-secret",
    )


def test_configure_google_oauth_clears_stale_secret_when_client_id_changes() -> None:
    secrets = MagicMock()
    client = _client(secrets=secrets, project_name="demo")
    client.config = client.config.model_copy(
        update={
            "oauth_client_id": "old-client-id",
            "oauth_client_secret": "old-client-secret",
        }
    )

    client.configure_google_oauth("new-client-id")

    assert client.config.oauth_client_id == "new-client-id"
    assert client.config.oauth_client_secret is None
    assert client.oauth_manager.providers["google"].flow.client_secret is None


def test_save_oauth_client_id_without_secret_deletes_stale_secret_keys() -> None:
    secrets = MagicMock()
    client = _client(secrets=secrets, project_name="demo")
    client.config = client.config.model_copy(
        update={
            "oauth_client_id": "old-client-id",
            "oauth_client_secret": "old-client-secret",
        }
    )

    client.save_oauth_client_id("new-client-id")

    assert client.config.oauth_client_id == "new-client-id"
    assert client.config.oauth_client_secret is None
    assert secrets.delete.call_args_list[0].args == (
        f"demo_{OAUTH_CLIENT_SECRET_KEY}",
    )
    assert secrets.delete.call_args_list[1].args == (OAUTH_CLIENT_SECRET_KEY,)


def test_delete_oauth_client_id_clears_keyring_and_runtime_provider() -> None:
    secrets = MagicMock()
    client = _client(secrets=secrets, project_name="demo")
    client.save_oauth_client_id("google-client-id", client_secret="google-secret")

    assert client.delete_oauth_client_id() is True

    assert client.config.oauth_client_id is None
    assert client.config.oauth_client_secret is None
    assert "google" not in client.oauth_manager.providers
    assert secrets.delete.call_args_list[0].args == (
        f"demo_{OAUTH_CLIENT_ID_SECRET_KEY}",
    )
    assert secrets.delete.call_args_list[1].args == (OAUTH_CLIENT_ID_SECRET_KEY,)
    assert secrets.delete.call_args_list[2].args == (
        f"demo_{OAUTH_CLIENT_SECRET_KEY}",
    )
    assert secrets.delete.call_args_list[3].args == (OAUTH_CLIENT_SECRET_KEY,)
    assert secrets.delete.call_args_list[0].kwargs == {"scope": "user"}


def test_get_remote_config_success(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(client, "get_adc_access_token", MagicMock(return_value="token"))
    response = FakeResponse(
        200,
        payload={"parameters": {}, "version": {"versionNumber": "12"}},
        headers={"ETag": "etag-123"},
    )
    get = MagicMock(return_value=response)
    monkeypatch.setattr("titan_plugin_firebase.client.requests.get", get)

    template = client.get_remote_config("demo-project")

    assert template.project_id == "demo-project"
    assert template.etag == "etag-123"
    assert template.version == {"versionNumber": "12"}
    get.assert_called_once_with(
        "https://firebaseremoteconfig.googleapis.com/v1/projects/"
        "demo-project/remoteConfig",
        headers={
            "Authorization": "Bearer token",
            "x-goog-user-project": "demo-project",
        },
        timeout=30,
    )


def test_get_remote_config_requires_adc(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(client, "get_adc_access_token", MagicMock(return_value=None))

    with pytest.raises(FirebaseClientError, match="application-default login"):
        client.get_remote_config("demo-project")


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, "rejected or expired"),
        (403, "permission denied"),
        (404, "not found"),
    ],
)
def test_get_remote_config_maps_common_http_errors(
    monkeypatch,
    status_code: int,
    expected: str,
) -> None:
    client = _client()
    monkeypatch.setattr(client, "get_adc_access_token", MagicMock(return_value="token"))
    monkeypatch.setattr(
        "titan_plugin_firebase.client.requests.get",
        MagicMock(
            return_value=FakeResponse(
                status_code,
                payload={"error": {"message": "firebase said no"}},
            )
        ),
    )

    with pytest.raises(FirebaseClientError, match=expected):
        client.get_remote_config("demo-project")


def test_get_remote_config_401_keeps_rejected_auth_source(monkeypatch) -> None:
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "demo_firebase_access_token": " saved-token ",
    }.get(key)
    client = _client(secrets=secrets, project_name="demo")
    monkeypatch.setattr(client, "get_adc_access_token", MagicMock(return_value=None))
    monkeypatch.setattr(
        "titan_plugin_firebase.client.requests.get",
        MagicMock(
            return_value=FakeResponse(
                401,
                payload={"error": {"message": "invalid credentials"}},
            )
        ),
    )

    with pytest.raises(FirebaseAuthRejectedError) as raised:
        client.get_remote_config("demo-project")

    assert raised.value.auth_source == "keyring:demo_firebase_access_token"


def test_invalidate_access_token_source_deletes_legacy_keyring_token() -> None:
    secrets = MagicMock()
    client = _client(secrets=secrets, project_name="demo")

    assert (
        client.invalidate_access_token_source(
            "keyring:demo_firebase_access_token",
        )
        is True
    )

    secrets.delete.assert_called_once_with(
        "demo_firebase_access_token",
        scope="user",
    )
    assert "demo_firebase_access_token" not in (
        client.build_oauth_request().legacy_secret_keys
    )


def test_get_remote_config_wraps_request_errors(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(client, "get_adc_access_token", MagicMock(return_value="token"))
    monkeypatch.setattr(
        "titan_plugin_firebase.client.requests.get",
        MagicMock(side_effect=requests.Timeout("slow")),
    )

    with pytest.raises(FirebaseClientError, match="request failed"):
        client.get_remote_config("demo-project")
