"""The plugin's configuration surface, which is deliberately small."""

import pytest

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.plugin import FirebasePlugin


def test_defaults_need_no_configuration():
    config = FirebasePluginConfig()
    assert config.default_project is None
    assert config.default_project_set is None
    assert config.default_environment is None
    assert config.default_condition_group is None
    assert config.condition_groups == {}
    assert config.project_sets == {}
    assert config.api_base_url.startswith("https://")
    assert config.request_timeout == 30
    assert config.oauth_scopes == ["https://www.googleapis.com/auth/cloud-platform"]


def test_the_configurable_surface_stays_generic():
    # This plugin is generic: it speaks about Firebase projects, reusable sets,
    # labels, groups and repo-owned metadata. It still knows nothing about
    # naming patterns or business-specific environment semantics.
    assert set(FirebasePluginConfig.model_fields) == {
        "default_project",
        "default_project_set",
        "default_environment",
        "default_condition_group",
        "condition_groups",
        "project_sets",
        "quota_project_id",
        "api_base_url",
        "request_timeout",
        "oauth_scopes",
    }


def test_project_sets_parse_labels_groups_brand_and_environment():
    config = FirebasePluginConfig(
        default_project_set="ragnarok_ios",
        default_environment=" PRO ",
        project_sets={
            "ragnarok_ios": {
                "description": "Ragnarok iOS Remote Config",
                "default_environment": " DEV ",
                "projects": [
                    {
                        "project_id": "mm-firebase-lebara",
                        "label": "Lebara",
                        "brand": "Lebara",
                        "environment": " DEV ",
                        "groups": ["Prepago", "prepago"],
                    }
                ],
            }
        },
    )

    assert config.default_project_set == "ragnarok_ios"
    assert config.default_environment == "pro"
    assert config.project_sets["ragnarok_ios"].default_environment == "dev"
    project = config.project_sets["ragnarok_ios"].projects[0]
    assert project.project_id == "mm-firebase-lebara"
    assert project.label == "Lebara"
    assert project.brand == "Lebara"
    assert project.environment == "dev"
    assert project.groups == ["prepago"]


def test_condition_groups_parse_value_views():
    config = FirebasePluginConfig(
        default_condition_group=" Android ",
        condition_groups={
            " Android ": {
                "label": "Android",
                "include_default": True,
                "conditions": [" Android - Dev ", "Android - Dev"],
                "condition_prefixes": "Android - ",
                "condition_contains": [" android "],
            }
        },
    )

    assert config.default_condition_group == "android"
    assert list(config.condition_groups) == ["android"]
    group = config.condition_groups["android"]
    assert group.label == "Android"
    assert group.include_default is True
    assert group.conditions == ["Android - Dev"]
    assert group.condition_prefixes == ["Android -"]
    assert group.condition_contains == ["android"]


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


def test_project_fields_are_asked_before_transport_defaults():
    # The configuration wizard walks the schema, so order is UX: project-local
    # target choices come before transport tuning.
    properties = FirebasePlugin().get_config_schema()["properties"]
    assert list(properties)[:5] == [
        "default_project",
        "default_project_set",
        "default_environment",
        "default_condition_group",
        "condition_groups",
    ]
    assert list(properties)[5:7] == [
        "project_sets",
        "quota_project_id",
    ]
    assert len(properties) == 10


def test_api_base_url_must_be_http():
    with pytest.raises(ValueError):
        FirebasePluginConfig(api_base_url="ftp://nope")


def test_blank_optional_values_normalize_to_none():
    config = FirebasePluginConfig(
        default_project="  ",
        default_project_set=" ",
        default_environment="",
        default_condition_group="",
        quota_project_id="",
    )
    assert config.default_project is None
    assert config.default_project_set is None
    assert config.default_environment is None
    assert config.default_condition_group is None
    assert config.quota_project_id is None


def test_a_single_scope_may_be_given_as_a_string():
    config = FirebasePluginConfig(oauth_scopes="https://example.com/scope")
    assert config.oauth_scopes == ["https://example.com/scope"]
