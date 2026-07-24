from unittest.mock import MagicMock

from titan_cli.engine.builder import WorkflowContextBuilder
from titan_plugin_firebase.plugin import FirebasePlugin


def test_with_firebase_loads_client_from_plugin_registry() -> None:
    plugin_registry = MagicMock()
    firebase_plugin = MagicMock()
    firebase_client = MagicMock()

    plugin_registry.get_plugin.return_value = firebase_plugin
    firebase_plugin.is_available.return_value = True
    firebase_plugin.get_client.return_value = firebase_client

    ctx = (
        WorkflowContextBuilder(
            plugin_registry=plugin_registry,
            secrets=MagicMock(),
            ai_config=None,
        )
        .with_firebase()
        .build()
    )

    assert ctx.firebase is firebase_client


def test_with_firebase_uses_explicit_client() -> None:
    plugin_registry = MagicMock()
    firebase_client = MagicMock()

    ctx = (
        WorkflowContextBuilder(
            plugin_registry=plugin_registry,
            secrets=MagicMock(),
            ai_config=None,
        )
        .with_firebase(firebase_client)
        .build()
    )

    assert ctx.firebase is firebase_client


def test_with_firebase_injects_initialized_plugin_client_without_auth(
    monkeypatch,
) -> None:
    plugin_registry = MagicMock()
    firebase_plugin = FirebasePlugin()
    config = MagicMock()
    config.config.plugins = {"firebase": MagicMock(config={})}
    firebase_plugin.initialize(config, MagicMock())
    monkeypatch.setattr(
        firebase_plugin.get_client(),
        "is_available",
        MagicMock(return_value=False),
    )
    plugin_registry.get_plugin.return_value = firebase_plugin

    ctx = (
        WorkflowContextBuilder(
            plugin_registry=plugin_registry,
            secrets=MagicMock(),
            ai_config=None,
        )
        .with_firebase()
        .build()
    )

    assert ctx.firebase is firebase_plugin.get_client()
