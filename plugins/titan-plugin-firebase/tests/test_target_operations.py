"""Resolving which Firebase project(s) a workflow acts on."""

import pytest

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.operations.target_operations import (
    TargetResolutionError,
    filter_targets_by_environment,
    parse_environment_names,
    parse_group_names,
    parse_project_ids,
    resolve_project_set,
    resolve_target,
    resolve_targets,
    target_environments,
)


def test_explicit_project_wins_over_the_default():
    config = FirebasePluginConfig(default_project="mm-firebase-dev")
    assert resolve_target(config, project_id="other-project").project_id == (
        "other-project"
    )


def test_default_project_is_used_when_nothing_is_passed():
    config = FirebasePluginConfig(default_project="mm-firebase-dev")
    assert resolve_target(config).project_id == "mm-firebase-dev"


def test_blank_project_falls_back_to_the_default():
    config = FirebasePluginConfig(default_project="mm-firebase-dev")
    assert resolve_target(config, project_id="   ").project_id == "mm-firebase-dev"


def test_no_project_anywhere_is_rejected_with_both_ways_out():
    with pytest.raises(TargetResolutionError) as exc:
        resolve_target(FirebasePluginConfig())
    assert "project_id" in str(exc.value)
    assert "default_project" in str(exc.value)


def test_a_label_is_kept_for_display_and_defaults_to_the_id():
    labelled = resolve_target(
        FirebasePluginConfig(), project_id="mm-firebase-yoigo", label="yoigo"
    )
    assert labelled.reference() == "yoigo (mm-firebase-yoigo)"

    plain = resolve_target(FirebasePluginConfig(), project_id="mm-firebase-yoigo")
    assert plain.reference() == "mm-firebase-yoigo"


def test_resolve_target_recovers_configured_metadata():
    config = FirebasePluginConfig(
        default_project="mm-firebase-yoigo",
        default_project_set="ragnarok_ios",
        project_sets={
            "ragnarok_ios": {
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo",
                        "label": "Yoigo PRO",
                        "brand": "Yoigo",
                        "environment": "PRO",
                        "groups": ["National"],
                    }
                ]
            }
        },
    )

    target = resolve_target(config)

    assert target.reference() == "Yoigo PRO (mm-firebase-yoigo)"
    assert target.brand == "Yoigo"
    assert target.environment == "pro"
    assert target.groups == ["national"]


@pytest.mark.parametrize(
    "value,expected",
    [
        (["a", "b"], ["a", "b"]),
        ("a,b", ["a", "b"]),
        ("a, b  c", ["a", "b", "c"]),
        ("  ", []),
        (None, []),
        (42, []),
        # Publishing to the same project twice in one fan-out is never intended.
        (["a", "b", "a"], ["a", "b"]),
    ],
)
def test_parse_project_ids(value, expected):
    assert parse_project_ids(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (["Prepago", "national"], ["prepago", "national"]),
        ("Prepago, National", ["prepago", "national"]),
        ("  ", []),
        (None, []),
        (42, []),
        (["prepago", "Prepago"], ["prepago"]),
    ],
)
def test_parse_group_names(value, expected):
    assert parse_group_names(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (["PRO", "dev"], ["pro", "dev"]),
        ("PRO, DEV", ["pro", "dev"]),
        ("  ", []),
        (None, []),
        (42, []),
        (["pro", "PRO"], ["pro"]),
    ],
)
def test_parse_environment_names(value, expected):
    assert parse_environment_names(value) == expected


def test_resolve_project_set_uses_default_set_and_labels():
    config = FirebasePluginConfig(
        default_project_set="ragnarok_ios",
        project_sets={
            "ragnarok_ios": {
                "projects": [
                    {
                        "project_id": "mm-firebase-lebara",
                        "label": "Lebara",
                        "brand": "Lebara",
                        "environment": "dev",
                        "groups": ["prepago"],
                    },
                    {
                        "project_id": "mm-firebase-yoigo",
                        "label": "Yoigo",
                        "brand": "Yoigo",
                        "environment": "dev",
                        "groups": ["national"],
                    },
                ]
            }
        },
    )

    resolution = resolve_project_set(config)

    assert resolution is not None
    assert resolution.name == "ragnarok_ios"
    assert resolution.groups == []
    assert resolution.environments == []
    assert [target.reference() for target in resolution.targets] == [
        "Lebara (mm-firebase-lebara)",
        "Yoigo (mm-firebase-yoigo)",
    ]
    assert [target.environment for target in resolution.targets] == ["dev", "dev"]


def test_resolve_project_set_can_filter_by_group():
    config = FirebasePluginConfig(
        default_project_set="ragnarok_ios",
        project_sets={
            "ragnarok_ios": {
                "projects": [
                    {
                        "project_id": "mm-firebase-lebara",
                        "label": "Lebara",
                        "groups": ["prepago"],
                    },
                    {
                        "project_id": "mm-firebase-yoigo",
                        "label": "Yoigo",
                        "groups": ["national"],
                    },
                ]
            }
        },
    )

    resolution = resolve_project_set(config, groups="National")

    assert resolution is not None
    assert resolution.groups == ["national"]
    assert [target.project_id for target in resolution.targets] == ["mm-firebase-yoigo"]


def test_resolve_project_set_can_filter_by_environment():
    config = FirebasePluginConfig(
        default_project_set="ragnarok_ios",
        project_sets={
            "ragnarok_ios": {
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo-dev",
                        "label": "Yoigo DEV",
                        "environment": "dev",
                    },
                    {
                        "project_id": "mm-firebase-yoigo-pro",
                        "label": "Yoigo PRO",
                        "environment": "pro",
                    },
                ]
            }
        },
    )

    resolution = resolve_project_set(config, environments="PRO")

    assert resolution is not None
    assert resolution.environments == ["pro"]
    assert [target.project_id for target in resolution.targets] == [
        "mm-firebase-yoigo-pro"
    ]


def test_project_set_default_environment_is_not_a_silent_filter():
    config = FirebasePluginConfig(
        default_project_set="ragnarok_ios",
        project_sets={
            "ragnarok_ios": {
                "default_environment": "dev",
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo-dev",
                        "environment": "dev",
                    },
                    {
                        "project_id": "mm-firebase-yoigo-pro",
                        "environment": "pro",
                    },
                ],
            }
        },
    )

    resolution = resolve_project_set(config)

    assert resolution is not None
    assert resolution.environments == []
    assert resolution.default_environment == "dev"
    assert [target.project_id for target in resolution.targets] == [
        "mm-firebase-yoigo-dev",
        "mm-firebase-yoigo-pro",
    ]


def test_project_set_default_environment_is_inherited_by_projects_without_one():
    config = FirebasePluginConfig(
        default_project_set="ragnarok_ios",
        project_sets={
            "ragnarok_ios": {
                "default_environment": "pro",
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo",
                        "label": "Yoigo",
                        "groups": ["national"],
                    },
                    {
                        "project_id": "mm-firebase-lebara",
                        "label": "Lebara",
                        "environment": "dev",
                        "groups": ["prepago"],
                    },
                ],
            }
        },
    )

    resolution = resolve_project_set(config)

    assert resolution is not None
    assert resolution.environments == []
    assert resolution.default_environment == "pro"
    assert [target.project_id for target in resolution.targets] == [
        "mm-firebase-yoigo",
        "mm-firebase-lebara",
    ]
    assert resolution.targets[0].environment == "pro"
    assert resolution.targets[1].environment == "dev"


def test_resolve_project_set_returns_none_when_no_set_is_named():
    assert resolve_project_set(FirebasePluginConfig()) is None


def test_resolve_project_set_rejects_unknown_sets():
    config = FirebasePluginConfig(default_project_set="missing")
    with pytest.raises(TargetResolutionError) as exc:
        resolve_project_set(config)
    assert "missing" in str(exc.value)


def test_resolve_targets_applies_caller_supplied_labels():
    targets = resolve_targets(
        ["mm-firebase-yoigo", "mm-guuk-firebase-prod"],
        {"mm-guuk-firebase-prod": "guuk"},
    )
    # The label lets a caller show its own vocabulary without this plugin
    # needing to know what the name means.
    assert [target.reference() for target in targets] == [
        "mm-firebase-yoigo",
        "guuk (mm-guuk-firebase-prod)",
    ]


def test_resolve_targets_enriches_explicit_project_ids_from_config():
    config = FirebasePluginConfig(
        default_project_set="ragnarok_ios",
        project_sets={
            "ragnarok_ios": {
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo-pro",
                        "label": "Yoigo PRO",
                        "brand": "Yoigo",
                        "environment": "pro",
                        "groups": ["national"],
                    }
                ]
            }
        },
    )

    targets = resolve_targets(["mm-firebase-yoigo-pro"], config=config)

    assert targets[0].reference() == "Yoigo PRO (mm-firebase-yoigo-pro)"
    assert targets[0].brand == "Yoigo"
    assert targets[0].environment == "pro"
    assert targets[0].groups == ["national"]


def test_resolve_targets_inherits_the_project_set_default_environment_from_config():
    config = FirebasePluginConfig(
        default_project_set="ragnarok_ios",
        project_sets={
            "ragnarok_ios": {
                "default_environment": "pro",
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo",
                        "label": "Yoigo",
                        "groups": ["national"],
                    }
                ],
            }
        },
    )

    targets = resolve_targets(["mm-firebase-yoigo"], config=config)

    assert targets[0].environment == "pro"


def test_explicit_target_metadata_wins_over_configured_metadata():
    config = FirebasePluginConfig(
        project_sets={
            "apps": {
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo-pro",
                        "label": "Yoigo PRO",
                        "brand": "Yoigo",
                        "environment": "pro",
                    }
                ]
            }
        }
    )

    targets = resolve_targets(
        ["mm-firebase-yoigo-pro"],
        labels={"mm-firebase-yoigo-pro": "Override"},
        brands={"mm-firebase-yoigo-pro": "Other"},
        environments={"mm-firebase-yoigo-pro": "dev"},
        config=config,
    )

    assert targets[0].reference() == "Override (mm-firebase-yoigo-pro)"
    assert targets[0].brand == "Other"
    assert targets[0].environment == "dev"


def test_environment_helpers_filter_and_list_target_environments():
    targets = resolve_targets(
        ["dev-project", "pro-project"],
        environments={"dev-project": "dev", "pro-project": "pro"},
    )

    assert [
        target.project_id for target in filter_targets_by_environment(targets, "DEV")
    ] == ["dev-project"]
    assert target_environments(targets) == ["dev", "pro"]


def test_resolve_targets_preserves_order():
    ids = ["c-project", "a-project", "b-project"]
    assert [t.project_id for t in resolve_targets(ids)] == ids


def test_resolve_targets_rejects_an_empty_list():
    with pytest.raises(TargetResolutionError) as exc:
        resolve_targets([])
    assert "firebase_project_ids" in str(exc.value)
