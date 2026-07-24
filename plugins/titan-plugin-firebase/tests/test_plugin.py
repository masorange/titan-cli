import importlib
import sys
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
        "firebase_remoteconfig_inventory",
    }


def test_firebase_steps_package_exports_are_lazy() -> None:
    for module_name in list(sys.modules):
        if module_name.startswith("titan_plugin_firebase.steps"):
            sys.modules.pop(module_name)

    steps_package = importlib.import_module("titan_plugin_firebase.steps")

    assert "titan_plugin_firebase.steps.login_step" not in sys.modules
    assert callable(steps_package.execute_firebase_login_step)
    assert "titan_plugin_firebase.steps.login_step" in sys.modules


def test_firebase_plugin_exposes_config_schema() -> None:
    plugin = FirebasePlugin()

    schema = plugin.get_config_schema()

    assert "access_token" in schema["properties"]
    assert "default_project" in schema["properties"]
    assert "projects" in schema["properties"]
    assert "default_environment" in schema["properties"]
    assert "api_base_url" in schema["properties"]
    assert "oauth_client_id" in schema["properties"]
    assert "oauth_client_secret" in schema["properties"]
    assert "oauth_redirect_port" in schema["properties"]
    assert "oauth_timeout" in schema["properties"]
    assert "oauth_scopes" in schema["properties"]
    assert "brand_projects" in schema["properties"]
    assert "access_token" not in schema.get("required", [])
    assert list(schema["properties"])[0] == "oauth_client_id"
    assert list(schema["properties"])[1] == "oauth_client_secret"
    assert schema["properties"]["oauth_client_secret"]["format"] == "password"
    assert schema["properties"]["access_token"]["ui_hidden"] is True


def test_firebase_plugin_exposes_workflows_path() -> None:
    plugin = FirebasePlugin()

    assert plugin.workflows_path is not None
    assert plugin.workflows_path.name == "workflows"


def test_firebase_plugin_initialize_builds_client() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {
        "firebase": MagicMock(config={"default_project": "demo-project"})
    }
    secrets = MagicMock()

    plugin.initialize(config, secrets)

    client = plugin.get_client()
    assert isinstance(client, FirebaseClient)
    assert client.config.default_project == "demo-project"
    assert client.secrets == secrets
    assert client.project_name == "demo"
    assert client.oauth_manager is not None


def test_firebase_plugin_initialize_registers_google_oauth_provider() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {
        "firebase": MagicMock(
            config={
                "oauth_client_id": "google-client-id",
                "oauth_client_secret": "google-client-secret",
                "oauth_redirect_port": 8766,
                "oauth_timeout": 60,
            }
        )
    }
    secrets = MagicMock()

    plugin.initialize(config, secrets)

    client = plugin.get_client()
    assert "google" in client.oauth_manager.providers
    assert client.oauth_manager.providers["google"].flow.client_secret == (
        "google-client-secret"
    )


def test_firebase_plugin_initialize_uses_saved_oauth_client_id() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {"firebase": MagicMock(config={})}
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "demo_firebase_oauth_client_id": "saved-google-client-id",
        "demo_firebase_oauth_client_secret": "saved-google-client-secret",
    }.get(key)

    plugin.initialize(config, secrets)

    client = plugin.get_client()
    assert client.config.oauth_client_id == "saved-google-client-id"
    assert client.config.oauth_client_secret == "saved-google-client-secret"
    assert "google" in client.oauth_manager.providers


def test_firebase_plugin_project_saved_oauth_client_id_overrides_config_value() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {
        "firebase": MagicMock(
            config={
                "oauth_client_id": "old-config-client-id",
                "oauth_client_secret": "old-config-client-secret",
            }
        )
    }
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "demo_firebase_oauth_client_id": "saved-google-client-id",
        "demo_firebase_oauth_client_secret": "saved-google-client-secret",
    }.get(key)

    plugin.initialize(config, secrets)

    assert plugin.get_client().config.oauth_client_id == "saved-google-client-id"
    assert plugin.get_client().config.oauth_client_secret == (
        "saved-google-client-secret"
    )


def test_firebase_plugin_does_not_mix_project_saved_id_with_config_secret() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {
        "firebase": MagicMock(
            config={
                "oauth_client_id": "config-client-id",
                "oauth_client_secret": "config-client-secret",
            }
        )
    }
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "demo_firebase_oauth_client_id": "saved-google-client-id",
    }.get(key)

    plugin.initialize(config, secrets)

    assert plugin.get_client().config.oauth_client_id == "saved-google-client-id"
    assert plugin.get_client().config.oauth_client_secret is None


def test_firebase_plugin_pairs_config_id_with_project_secret_from_wizard() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {
        "firebase": MagicMock(config={"oauth_client_id": "config-client-id"})
    }
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "demo_firebase_oauth_client_secret": "wizard-client-secret",
    }.get(key)

    plugin.initialize(config, secrets)

    assert plugin.get_client().config.oauth_client_id == "config-client-id"
    assert plugin.get_client().config.oauth_client_secret == "wizard-client-secret"


def test_firebase_plugin_config_oauth_client_id_overrides_generic_saved_value() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {
        "firebase": MagicMock(
            config={
                "oauth_client_id": "config-client-id",
                "oauth_client_secret": "config-client-secret",
            }
        )
    }
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "firebase_oauth_client_id": "generic-saved-client-id",
        "firebase_oauth_client_secret": "generic-saved-client-secret",
    }.get(key)

    plugin.initialize(config, secrets)

    assert plugin.get_client().config.oauth_client_id == "config-client-id"
    assert plugin.get_client().config.oauth_client_secret == "config-client-secret"


def test_firebase_plugin_does_not_mix_config_id_with_different_generic_secret() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {
        "firebase": MagicMock(config={"oauth_client_id": "config-client-id"})
    }
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "firebase_oauth_client_id": "generic-saved-client-id",
        "firebase_oauth_client_secret": "generic-saved-client-secret",
    }.get(key)

    plugin.initialize(config, secrets)

    assert plugin.get_client().config.oauth_client_id == "config-client-id"
    assert plugin.get_client().config.oauth_client_secret is None


def test_firebase_plugin_reuses_generic_secret_only_for_same_config_id() -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.get_project_name.return_value = "demo"
    config.config.plugins = {
        "firebase": MagicMock(config={"oauth_client_id": "same-client-id"})
    }
    secrets = MagicMock()
    secrets.get.side_effect = lambda key: {
        "firebase_oauth_client_id": "same-client-id",
        "firebase_oauth_client_secret": "generic-saved-client-secret",
    }.get(key)

    plugin.initialize(config, secrets)

    assert plugin.get_client().config.oauth_client_id == "same-client-id"
    assert plugin.get_client().config.oauth_client_secret == (
        "generic-saved-client-secret"
    )


def test_firebase_plugin_is_available_delegates_to_client(monkeypatch) -> None:
    plugin = FirebasePlugin()
    config = MagicMock()
    config.config.plugins = {"firebase": MagicMock(config={})}
    plugin.initialize(config, MagicMock())
    monkeypatch.setattr(
        plugin.get_client(),
        "is_available",
        MagicMock(return_value=True),
    )

    assert plugin.is_available() is True
