from unittest.mock import MagicMock

from titan_plugin_firebase.client import FirebaseClient
from titan_plugin_firebase.plugin import FirebasePlugin


def test_firebase_plugin_basic_properties() -> None:
    plugin = FirebasePlugin()

    assert plugin.name == "firebase"
    assert plugin.version == "0.1.0"
    assert plugin.dependencies == []
    assert "Firebase" in plugin.description


def test_firebase_plugin_exposes_public_steps() -> None:
    plugin = FirebasePlugin()

    assert set(plugin.get_steps()) == {
        "firebase_login",
        "firebase_status",
        "firebase_remoteconfig_get",
    }


def test_firebase_plugin_exposes_config_schema() -> None:
    plugin = FirebasePlugin()

    schema = plugin.get_config_schema()

    assert "default_project" in schema["properties"]
    assert "api_base_url" in schema["properties"]
    assert "brand_projects" in schema["properties"]


def test_firebase_plugin_initialize_builds_client() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.config.plugins = {
        "firebase": MagicMock(config={"default_project": "demo-project"})
    }

    plugin.initialize(config, MagicMock())

    client = plugin.get_client()
    assert isinstance(client, FirebaseClient)
    assert client.config.default_project == "demo-project"


def test_firebase_plugin_is_available_delegates_to_client(monkeypatch) -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.config.plugins = {"firebase": MagicMock(config={})}
    plugin.initialize(config, MagicMock())
    monkeypatch.setattr(plugin.get_client(), "is_available", MagicMock(return_value=True))

    assert plugin.is_available() is True
