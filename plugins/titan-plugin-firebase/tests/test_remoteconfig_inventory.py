import pytest

from titan_plugin_firebase.client import RemoteConfigTemplate
from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.exceptions import FirebaseClientError
from titan_plugin_firebase.models import RemoteConfigValueType
from titan_plugin_firebase.operations.remoteconfig_inventory import (
    build_remote_config_inventory,
    resolve_project_targets,
)


class FakeInventoryClient:
    def __init__(
        self,
        templates: dict[str, RemoteConfigTemplate],
        failures: dict[str, str] | None = None,
    ):
        self.templates = templates
        self.failures = failures or {}

    def get_remote_config(self, project_id: str) -> RemoteConfigTemplate:
        if project_id in self.failures:
            raise FirebaseClientError(self.failures[project_id])
        return self.templates[project_id]


def test_resolve_project_targets_from_environment_brand_mapping() -> None:
    config = FirebasePluginConfig(
        brand_projects={
            "prod": {
                "yoigo": "yoigo-prod",
                "masmovil": {"project_id": "masmovil-prod", "platform": "ios"},
            }
        }
    )

    targets = resolve_project_targets(config)

    assert [target.project_id for target in targets] == [
        "yoigo-prod",
        "masmovil-prod",
    ]
    assert targets[1].brand == "masmovil"
    assert targets[0].environment == "prod"
    assert targets[1].platform == "ios"


def test_resolve_project_targets_from_brand_environment_mapping() -> None:
    config = FirebasePluginConfig(
        brand_projects_layout="brand_environment",
        brand_projects={"yoigo": {"pre": "yoigo-pre", "prod": "yoigo-prod"}},
    )

    targets = resolve_project_targets(config, environments="prod")

    assert len(targets) == 1
    assert targets[0].brand == "yoigo"
    assert targets[0].environment == "prod"
    assert targets[0].project_id == "yoigo-prod"


def test_resolve_project_targets_filters_environment_aliases() -> None:
    config = FirebasePluginConfig(
        environments=[
            {"name": "production", "aliases": ["prod", "live"]},
            {"name": "staging", "aliases": ["pre"]},
        ],
        brand_projects={
            "production": {"yoigo": "yoigo-prod"},
            "staging": {"yoigo": "yoigo-pre"},
        },
    )

    targets = resolve_project_targets(config, environments="prod")

    assert len(targets) == 1
    assert targets[0].environment == "production"
    assert targets[0].project_id == "yoigo-prod"
    assert targets[0].label == "production/yoigo"


def test_resolve_project_targets_normalizes_target_environment_aliases() -> None:
    config = FirebasePluginConfig(
        environments=[
            {"name": "production", "aliases": ["prod"]},
        ],
        projects=[
            {
                "brand": "yoigo",
                "environment": "prod",
                "project_id": "yoigo-prod",
            },
        ],
    )

    targets = resolve_project_targets(config)

    assert len(targets) == 1
    assert targets[0].environment == "production"
    assert targets[0].label == "production/yoigo"


def test_build_remote_config_inventory_aggregates_keys_and_types() -> None:
    target_config = FirebasePluginConfig(
        projects=[
            {"brand": "yoigo", "environment": "prod", "project_id": "yoigo-prod"},
            {
                "brand": "masmovil",
                "environment": "prod",
                "project_id": "masmovil-prod",
            },
        ]
    )
    targets = resolve_project_targets(target_config)
    client = FakeInventoryClient(
        {
            "yoigo-prod": RemoteConfigTemplate(
                project_id="yoigo-prod",
                etag="etag-a",
                template={
                    "version": {"versionNumber": "11"},
                    "parameters": {
                        "feature_enabled": {
                            "valueType": "BOOLEAN",
                            "defaultValue": {"value": "true"},
                        },
                        "welcome_text": {"defaultValue": {"value": "hola"}},
                    },
                },
            ),
            "masmovil-prod": RemoteConfigTemplate(
                project_id="masmovil-prod",
                etag="etag-b",
                template={
                    "version": {"versionNumber": "22"},
                    "parameters": {
                        "feature_enabled": {
                            "valueType": "JSON",
                            "defaultValue": {"value": '{"enabled": true}'},
                        },
                    },
                },
            ),
        }
    )

    inventory = build_remote_config_inventory(client, targets)
    keys = {key.key: key for key in inventory.keys}

    assert inventory.project_count == 2
    assert inventory.key_count == 2
    assert keys["feature_enabled"].has_type_mismatch is True
    assert keys["feature_enabled"].observed_types == [
        RemoteConfigValueType.BOOLEAN,
        RemoteConfigValueType.JSON,
    ]
    assert keys["welcome_text"].projects_missing == ["prod/masmovil (masmovil-prod)"]


def test_build_remote_config_inventory_collects_failures() -> None:
    target_config = FirebasePluginConfig(
        projects=[
            {"brand": "yoigo", "environment": "prod", "project_id": "yoigo-prod"},
            {
                "brand": "masmovil",
                "environment": "prod",
                "project_id": "masmovil-prod",
            },
        ]
    )
    targets = resolve_project_targets(target_config)
    client = FakeInventoryClient(
        {
            "yoigo-prod": RemoteConfigTemplate(
                project_id="yoigo-prod",
                etag="etag-a",
                template={"parameters": {"feature_enabled": {}}},
            )
        },
        failures={"masmovil-prod": "permission denied"},
    )

    inventory = build_remote_config_inventory(client, targets)

    assert inventory.project_count == 1
    assert len(inventory.failures) == 1
    assert inventory.failures[0].target.project_id == "masmovil-prod"


def test_build_remote_config_inventory_collects_template_normalization_failures() -> None:
    target_config = FirebasePluginConfig(
        projects=[
            {"brand": "yoigo", "environment": "prod", "project_id": "yoigo-prod"},
            {
                "brand": "masmovil",
                "environment": "prod",
                "project_id": "masmovil-prod",
            },
        ]
    )
    targets = resolve_project_targets(target_config)
    client = FakeInventoryClient(
        {
            "yoigo-prod": RemoteConfigTemplate(
                project_id="yoigo-prod",
                etag="etag-a",
                template={"parameters": {"feature_enabled": {}}},
            ),
            "masmovil-prod": RemoteConfigTemplate(
                project_id="masmovil-prod",
                etag="etag-b",
                template={
                    "parameters": {
                        "broken_parameter": {
                            "defaultValue": ["not", "an", "object"],
                        },
                    },
                },
            ),
        }
    )

    inventory = build_remote_config_inventory(client, targets)

    assert inventory.project_count == 1
    assert len(inventory.failures) == 1
    assert inventory.failures[0].target.project_id == "masmovil-prod"
    assert "broken_parameter" in inventory.failures[0].message
    assert "could not be normalized" in inventory.failures[0].message


def test_build_remote_config_inventory_raises_template_normalization_failure() -> None:
    target_config = FirebasePluginConfig(
        projects=[
            {
                "brand": "masmovil",
                "environment": "prod",
                "project_id": "masmovil-prod",
            },
        ]
    )
    targets = resolve_project_targets(target_config)
    client = FakeInventoryClient(
        {
            "masmovil-prod": RemoteConfigTemplate(
                project_id="masmovil-prod",
                etag="etag-b",
                template={"parameters": ["not", "an", "object"]},
            ),
        }
    )

    with pytest.raises(FirebaseClientError, match="parameters must be"):
        build_remote_config_inventory(client, targets, continue_on_error=False)
