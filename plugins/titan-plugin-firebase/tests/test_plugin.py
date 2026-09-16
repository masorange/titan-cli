"""Plugin contract: registration, config parsing, and no I/O on initialize."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from titan_plugin_firebase.exceptions import FirebaseConfigurationError, FirebaseError
from titan_plugin_firebase.plugin import FirebasePlugin

EXPECTED_STEPS = {
    "firebase_auth_check",
    "firebase_select_target",
    "firebase_remoteconfig_get",
    "firebase_remoteconfig_conditions",
    "firebase_remoteconfig_select_key",
    "firebase_remoteconfig_set_value",
    "firebase_remoteconfig_diff",
    "firebase_remoteconfig_publish",
    "firebase_select_targets",
    "firebase_remoteconfig_fanout_plan",
    "firebase_remoteconfig_fanout_publish",
}


def _config(plugin_config: dict | None = None):
    plugins = {}
    if plugin_config is not None:
        plugins["firebase"] = SimpleNamespace(config=plugin_config)
    return SimpleNamespace(config=SimpleNamespace(plugins=plugins))


def test_plugin_identity():
    plugin = FirebasePlugin()
    assert plugin.name == "firebase"
    assert plugin.dependencies == []


def test_initialize_reads_project_config():
    plugin = FirebasePlugin()
    plugin.initialize(
        _config({"default_project": "mm-firebase-dev", "request_timeout": 5}),
        MagicMock(),
    )

    assert plugin.is_available()
    assert plugin.get_client().config.default_project == "mm-firebase-dev"
    assert plugin.get_client().config.request_timeout == 5


def test_initialize_without_plugin_section_uses_defaults():
    plugin = FirebasePlugin()
    plugin.initialize(_config(None), MagicMock())

    assert plugin.get_client().config.api_base_url.startswith("https://")


def test_initialize_never_touches_the_secret_broker():
    # Authentication is ADC, so the plugin holds no credential: a broker call
    # here would mean something is storing one.
    plugin = FirebasePlugin()
    broker = MagicMock()
    plugin.initialize(_config({}), broker)

    assert broker.method_calls == []


def test_initialize_rejects_invalid_config():
    plugin = FirebasePlugin()
    with pytest.raises(FirebaseConfigurationError):
        plugin.initialize(_config({"api_base_url": "ftp://nope"}), MagicMock())


def test_get_client_before_initialize_is_an_error():
    with pytest.raises(FirebaseError):
        FirebasePlugin().get_client()


def test_registered_steps():
    assert set(FirebasePlugin().get_steps()) == EXPECTED_STEPS


def test_workflows_directory_ships_the_read_and_write_workflows():
    path = FirebasePlugin().workflows_path
    assert path is not None
    assert {file.name for file in path.glob("*.yaml")} == {
        "read-remoteconfig.yaml",
        "set-remoteconfig-value.yaml",
        "set-remoteconfig-value-multiproject.yaml",
    }


def test_config_schema_only_advertises_the_default_project():
    schema = FirebasePlugin().get_config_schema()
    assert list(schema["properties"]) == ["default_project"]


def test_config_schema_declares_no_credential_field():
    # A credential field would be a design regression: ADC means there is
    # nothing to ask the user for or store.
    properties = FirebasePlugin().get_config_schema()["properties"]
    assert not [
        name
        for name in properties
        if any(word in name for word in ("token", "secret", "password", "client_id"))
    ]


def test_config_schema_declares_no_brand_vocabulary():
    # The wizard walks this schema. A generic plugin must not interrogate the
    # user about brands or a project naming scheme; a repository that has one
    # keeps it in its own plugin and passes project IDs in.
    properties = FirebasePlugin().get_config_schema()["properties"]
    assert not [
        name
        for name in properties
        if any(word in name for word in ("brand", "pattern", "environment"))
    ]
