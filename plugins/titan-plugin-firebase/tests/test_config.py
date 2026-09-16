"""The plugin's configuration surface, which is deliberately small."""

import pytest

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.plugin import FirebasePlugin


def test_defaults_need_no_configuration():
    config = FirebasePluginConfig()
    assert config.default_project is None
    assert config.api_base_url.startswith("https://")
    assert config.request_timeout == 30
    assert config.oauth_scopes == [
        "https://www.googleapis.com/auth/cloud-platform"
    ]


def test_the_configurable_surface_is_five_fields():
    # This plugin is generic: it speaks about Firebase projects and knows
    # nothing about brands, naming patterns or environment maps. A repository
    # that maps its own names to projects keeps that in its own plugin and
    # passes project IDs in, so nothing here should grow a vocabulary.
    assert set(FirebasePluginConfig.model_fields) == {
        "default_project",
        "quota_project_id",
        "api_base_url",
        "request_timeout",
        "oauth_scopes",
    }


def test_no_credential_field():
    # ADC means there is nothing to ask the user for or store.
    fields = FirebasePluginConfig.model_fields
    assert not [
        name
        for name in fields
        if any(
            word in name
            for word in ("token", "secret", "password", "client_id", "credential")
        )
    ]


def test_the_wizard_asks_for_exactly_one_field():
    # The wizard renders every property the schema advertises, so the schema is
    # the UX. Only default_project earns a question; everything else has a
    # working default and would turn "enable Firebase" into an interrogation.
    assert list(FirebasePlugin().get_config_schema()["properties"]) == [
        "default_project"
    ]


def test_the_wizard_never_marks_a_field_required():
    # default_project is optional: a workflow can pass project_id instead.
    assert FirebasePlugin().get_config_schema()["required"] == []


def test_options_left_out_of_the_wizard_still_work_from_the_toml_file():
    # Narrowing the wizard must not narrow the plugin: these are set by hand in
    # .titan/config.toml when someone needs them.
    config = FirebasePluginConfig(
        quota_project_id="mm-ragnarok-dev",
        api_base_url="https://example.test/v1",
        request_timeout=5,
        oauth_scopes=["https://www.googleapis.com/auth/firebase.remoteconfig"],
    )
    assert config.quota_project_id == "mm-ragnarok-dev"
    assert config.api_base_url == "https://example.test/v1"
    assert config.request_timeout == 5
    assert config.oauth_scopes == [
        "https://www.googleapis.com/auth/firebase.remoteconfig"
    ]


def test_api_base_url_must_be_http():
    with pytest.raises(ValueError):
        FirebasePluginConfig(api_base_url="ftp://nope")


def test_blank_optional_values_normalize_to_none():
    config = FirebasePluginConfig(default_project="  ", quota_project_id="")
    assert config.default_project is None
    assert config.quota_project_id is None


def test_a_single_scope_may_be_given_as_a_string():
    config = FirebasePluginConfig(oauth_scopes="https://example.com/scope")
    assert config.oauth_scopes == ["https://example.com/scope"]
