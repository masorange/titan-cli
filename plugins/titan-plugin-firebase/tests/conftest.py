"""Shared fixtures for the Firebase plugin tests."""

from __future__ import annotations

from typing import Any, Optional

import pytest

from titan_plugin_firebase.clients.network.adc_auth import AdcSession
from titan_plugin_firebase.clients.network.remoteconfig_network import (
    RemoteConfigNetwork,
)
from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.view import UIAdcIdentity


class FakeResponse:
    """Minimal stand-in for a requests.Response."""

    def __init__(
        self,
        status_code: int = 200,
        payload: Optional[dict] = None,
        headers: Optional[dict] = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """Records requests and replays queued responses."""

    def __init__(self, responses: Optional[list[FakeResponse]] = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def _next(self) -> FakeResponse:
        if not self.responses:
            raise AssertionError("FakeSession ran out of queued responses")
        return self.responses.pop(0)

    def get(self, url, headers=None, timeout=None):
        self.calls.append(
            {"method": "GET", "url": url, "headers": headers or {}, "timeout": timeout}
        )
        return self._next()

    def put(self, url, json=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": "PUT",
                "url": url,
                "json": json,
                "headers": headers or {},
                "timeout": timeout,
            }
        )
        return self._next()


@pytest.fixture
def make_response():
    """Factory for fake HTTP responses."""
    return FakeResponse


@pytest.fixture
def identity() -> UIAdcIdentity:
    """A user-credential identity, which is the supported case."""
    return UIAdcIdentity(
        account="alex@example.com",
        credential_kind="user",
        quota_project_id=None,
    )


@pytest.fixture
def plugin_config() -> FirebasePluginConfig:
    """Config shaped like the real multi-brand Android setup."""
    return FirebasePluginConfig(
        brands=["yoigo", "masmovil", "guuk"],
        project_id_pattern="mm-firebase-{brand}",
        brand_project_overrides={"guuk": "mm-guuk-firebase-prod"},
    )


@pytest.fixture
def make_network(identity):
    """Build a network bound to a FakeSession with queued responses."""

    def _make(responses: list[FakeResponse], **kwargs) -> RemoteConfigNetwork:
        session = FakeSession(responses)
        network = RemoteConfigNetwork(
            api_base_url="https://rc.example.com/v1",
            request_timeout=7,
            adc_session=AdcSession(session=session, identity=identity),
            **kwargs,
        )
        network.fake_session = session  # type: ignore[attr-defined]
        return network

    return _make


@pytest.fixture
def template_payload() -> dict:
    """A template shaped like a real Android brand project."""
    import copy

    return copy.deepcopy(_TEMPLATE_PAYLOAD)


@pytest.fixture
def ui_template(template_payload):
    """The same template, mapped to the UI model a step receives."""
    from titan_plugin_firebase.models.mappers import map_template
    from titan_plugin_firebase.models.network.rest import (
        NetworkRemoteConfigTemplate,
    )

    network = NetworkRemoteConfigTemplate.model_validate(template_payload)
    return map_template("mm-firebase-yoigo", network, "etag-1")


_TEMPLATE_PAYLOAD = {
    "conditions": [
        {
            "name": "android_prod",
            "expression": "app.id == '1:1:android:1'",
            "tagColor": "BLUE",
        }
    ],
    "parameters": {
        "feature_enabled": {
            "defaultValue": {"value": "false"},
            "conditionalValues": {"android_prod": {"value": "true"}},
            "valueType": "BOOLEAN",
            "description": "Kill switch",
        },
        "welcome_text": {
            "defaultValue": {"value": "hola"},
            "valueType": "STRING",
        },
        "legacy_untyped": {
            "defaultValue": {"value": "{\"a\": 1}"},
        },
    },
    "parameterGroups": {
        "onboarding": {"parameters": {"welcome_text": {}}},
    },
    "version": {
        "versionNumber": "42",
        "updateTime": "2026-09-01T10:00:00Z",
        "updateUser": {"email": "someone@example.com", "name": "Someone"},
        "updateOrigin": "CONSOLE",
        "updateType": "INCREMENTAL_UPDATE",
        "description": "cambio previo",
    },
}
