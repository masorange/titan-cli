"""Resolving brands and environments to Firebase projects."""

import pytest

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.operations.target_operations import (
    TargetResolutionError,
    available_brands,
    available_environments,
    project_id_for_brand,
    resolve_target,
    resolve_targets,
)


def test_pattern_resolves_brand(plugin_config):
    assert project_id_for_brand(plugin_config, "yoigo") == "mm-firebase-yoigo"


def test_override_wins_over_pattern(plugin_config):
    # The Android brands follow mm-firebase-{brand} except for the ones that
    # do not; the override is the whole point of the pattern being a default.
    assert project_id_for_brand(plugin_config, "guuk") == "mm-guuk-firebase-prod"


def test_explicit_mapping_wins_over_pattern():
    config = FirebasePluginConfig(
        project_id_pattern="mm-firebase-{brand}",
        brand_projects={"pre": {"yoigo": "mm-firebase-yoigo-pre"}},
        default_environment="pre",
    )
    assert project_id_for_brand(config, "yoigo", "pre") == "mm-firebase-yoigo-pre"


def test_brand_without_any_source_is_rejected():
    config = FirebasePluginConfig(brands=["yoigo"])
    with pytest.raises(TargetResolutionError):
        project_id_for_brand(config, "yoigo")


def test_ambiguous_environment_is_rejected():
    config = FirebasePluginConfig(
        brand_projects={
            "pre": {"yoigo": "a-pre"},
            "pro": {"yoigo": "a-pro"},
        }
    )
    with pytest.raises(TargetResolutionError) as exc:
        project_id_for_brand(config, "yoigo")
    assert "default_environment" in str(exc.value)


def test_single_environment_needs_no_selection():
    config = FirebasePluginConfig(brand_projects={"pro": {"yoigo": "a-pro"}})
    assert project_id_for_brand(config, "yoigo") == "a-pro"


def test_brand_environment_layout():
    config = FirebasePluginConfig(
        brand_projects={"yoigo": {"pre": "y-pre", "pro": "y-pro"}},
        brand_projects_layout="brand_environment",
    )
    assert project_id_for_brand(config, "yoigo", "pro") == "y-pro"
    assert available_environments(config) == ["pre", "pro"]


def test_available_brands_keeps_configured_order(plugin_config):
    assert available_brands(plugin_config) == ["yoigo", "masmovil", "guuk"]


def test_available_brands_from_mapping_when_unconfigured():
    config = FirebasePluginConfig(brand_projects={"pro": {"b": "x", "a": "y"}})
    assert available_brands(config) == ["a", "b"]


def test_resolve_target_prefers_explicit_project(plugin_config):
    target = resolve_target(plugin_config, project_id="mm-firebase-other")
    assert target.project_id == "mm-firebase-other"


def test_resolve_target_falls_back_to_default_project():
    config = FirebasePluginConfig(default_project="mm-firebase-dev")
    target = resolve_target(config)
    assert target.project_id == "mm-firebase-dev"
    assert target.brand is None


def test_resolve_target_without_anything_is_rejected():
    with pytest.raises(TargetResolutionError):
        resolve_target(FirebasePluginConfig())


def test_target_label_and_reference(plugin_config):
    target = resolve_target(plugin_config, brand="yoigo", environment="pro")
    assert target.label == "yoigo/pro"
    assert target.reference() == "yoigo/pro (mm-firebase-yoigo)"


def test_resolve_targets_reports_failures_without_aborting(plugin_config):
    targets, failures = resolve_targets(
        plugin_config, ["yoigo", "guuk", "unknown-brand"]
    )
    # A fan-out over ten brands must not lose nine because of the tenth; the
    # pattern makes "unknown-brand" resolvable, so the failure map is empty
    # here and every brand comes back.
    assert [t.project_id for t in targets] == [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
        "mm-firebase-unknown-brand",
    ]
    assert failures == {}


def test_resolve_targets_collects_unresolvable_brands():
    config = FirebasePluginConfig(
        brand_projects={"pro": {"yoigo": "y-pro"}},
    )
    targets, failures = resolve_targets(config, ["yoigo", "lebara"])
    assert [t.project_id for t in targets] == ["y-pro"]
    assert set(failures) == {"lebara"}
