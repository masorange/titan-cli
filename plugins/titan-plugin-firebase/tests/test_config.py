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


def test_only_one_field_is_asked_before_the_defaults():
    # The configuration wizard walks the schema, so field count is UX: a
    # generic plugin should not interrogate the user about a naming scheme.
    properties = FirebasePlugin().get_config_schema()["properties"]
    assert list(properties)[:2] == ["default_project", "quota_project_id"]
    assert len(properties) == 5


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
