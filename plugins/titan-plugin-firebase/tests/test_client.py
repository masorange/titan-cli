from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from titan_plugin_firebase.client import FirebaseClient
from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.exceptions import FirebaseClientError


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


def _client() -> FirebaseClient:
    return FirebaseClient(FirebasePluginConfig())


def test_config_defaults_and_overrides() -> None:
    default = FirebasePluginConfig()
    overridden = FirebasePluginConfig(
        default_project=" demo ",
        api_base_url="https://example.com/firebase/",
        request_timeout=5,
        brand_projects={"android": {"orange": "orange-app"}},
    )

    assert default.default_project is None
    assert default.request_timeout == 30
    assert overridden.default_project == "demo"
    assert overridden.api_base_url == "https://example.com/firebase"
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
        "https://firebaseremoteconfig.googleapis.com/v1/projects/demo-project/remoteConfig",
        headers={"Authorization": "Bearer token"},
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


def test_get_remote_config_wraps_request_errors(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(client, "get_adc_access_token", MagicMock(return_value="token"))
    monkeypatch.setattr(
        "titan_plugin_firebase.client.requests.get",
        MagicMock(side_effect=requests.Timeout("slow")),
    )

    with pytest.raises(FirebaseClientError, match="request failed"):
        client.get_remote_config("demo-project")
