"""Resolving which Firebase project(s) a workflow acts on."""

import pytest

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.operations.target_operations import (
    TargetResolutionError,
    parse_project_ids,
    resolve_target,
    resolve_targets,
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


def test_resolve_targets_preserves_order():
    ids = ["c-project", "a-project", "b-project"]
    assert [t.project_id for t in resolve_targets(ids)] == ids


def test_resolve_targets_rejects_an_empty_list():
    with pytest.raises(TargetResolutionError) as exc:
        resolve_targets([])
    assert "firebase_project_ids" in str(exc.value)
