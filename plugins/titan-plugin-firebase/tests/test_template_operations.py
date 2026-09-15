"""Read-modify-write over a whole template payload."""

import pytest

from titan_plugin_firebase.models.values import (
    RemoteConfigValueError,
    RemoteConfigValueType as T,
)
from titan_plugin_firebase.operations.template_operations import (
    TemplateEditError,
    apply_change,
    build_change,
    condition_names,
    current_raw_value,
    effective_value_type_for,
)


def test_condition_names(template_payload):
    assert condition_names(template_payload) == ["android_prod"]


def test_condition_names_tolerates_a_template_without_conditions():
    assert condition_names({"parameters": {}}) == []


def test_effective_value_type_prefers_the_declared_one(template_payload):
    assert effective_value_type_for(template_payload, "feature_enabled") == T.BOOLEAN


def test_effective_value_type_falls_back_to_inference(template_payload):
    assert effective_value_type_for(template_payload, "legacy_untyped") == T.JSON


def test_current_value_default_and_condition(template_payload):
    assert current_raw_value(template_payload, "feature_enabled") == ("false", False)
    assert current_raw_value(template_payload, "feature_enabled", "android_prod") == (
        "true",
        False,
    )


def test_current_value_reports_inheritance(template_payload):
    # welcome_text has no conditional value, so the condition shows the default
    # and says so: the difference matters when deciding what a write creates.
    value, inherited = current_raw_value(
        template_payload, "welcome_text", "android_prod"
    )
    assert (value, inherited) == ("hola", True)


def test_build_change_normalizes_the_value(template_payload):
    change = build_change(template_payload, "feature_enabled", "TRUE")
    assert change.new_raw_value == "true"
    assert change.old_raw_value == "false"
    assert change.value_type == T.BOOLEAN
    assert change.is_noop is False


def test_build_change_detects_a_noop(template_payload):
    change = build_change(template_payload, "feature_enabled", "false")
    assert change.is_noop is True


def test_build_change_flags_a_new_conditional_value(template_payload):
    change = build_change(template_payload, "welcome_text", "adiós", "android_prod")
    assert change.inherited_from_default is True
    assert change.old_raw_value is None
    assert change.creates_conditional_value is True


def test_build_change_rejects_an_unknown_parameter(template_payload):
    with pytest.raises(TemplateEditError) as exc:
        build_change(template_payload, "nope", "x")
    assert "nope" in str(exc.value)


def test_build_change_rejects_an_unknown_condition(template_payload):
    # Writing a conditionalValue for a condition the template does not declare
    # is rejected client-side; Firebase would answer 400.
    with pytest.raises(TemplateEditError) as exc:
        build_change(template_payload, "feature_enabled", "true", "ios_beta")
    assert "ios_beta" in str(exc.value)


def test_build_change_rejects_a_value_of_the_wrong_type(template_payload):
    with pytest.raises(RemoteConfigValueError):
        build_change(template_payload, "feature_enabled", "quizá")


def test_apply_change_touches_only_the_target_value(template_payload):
    change = build_change(template_payload, "feature_enabled", "true")
    updated = apply_change(template_payload, change)

    assert updated["parameters"]["feature_enabled"]["defaultValue"]["value"] == "true"
    # Everything else survives, because the publish replaces the whole template.
    assert (
        updated["parameters"]["feature_enabled"]["conditionalValues"]["android_prod"][
            "value"
        ]
        == "true"
    )
    assert updated["parameters"]["feature_enabled"]["valueType"] == "BOOLEAN"
    assert updated["parameters"]["feature_enabled"]["description"] == "Kill switch"
    assert (
        updated["parameters"]["welcome_text"]
        == template_payload["parameters"]["welcome_text"]
    )
    assert updated["conditions"] == template_payload["conditions"]
    assert updated["parameterGroups"] == template_payload["parameterGroups"]


def test_apply_change_does_not_mutate_the_source(template_payload):
    change = build_change(template_payload, "feature_enabled", "true")
    apply_change(template_payload, change)
    assert (
        template_payload["parameters"]["feature_enabled"]["defaultValue"]["value"]
        == "false"
    )


def test_apply_change_writes_a_conditional_value(template_payload):
    change = build_change(template_payload, "welcome_text", "adiós", "android_prod")
    updated = apply_change(template_payload, change)

    parameter = updated["parameters"]["welcome_text"]
    assert parameter["conditionalValues"]["android_prod"]["value"] == "adiós"
    # The default is left alone: only the condition was targeted.
    assert parameter["defaultValue"]["value"] == "hola"


def test_apply_change_clears_use_in_app_default():
    payload = {
        "parameters": {"k": {"defaultValue": {"useInAppDefault": True}}},
    }
    change = build_change(payload, "k", "hola")
    updated = apply_change(payload, change)

    # Firebase keeps ignoring an explicit value while useInAppDefault stands.
    assert updated["parameters"]["k"]["defaultValue"] == {"value": "hola"}


def test_apply_change_replaces_version_with_only_a_description(template_payload):
    change = build_change(template_payload, "feature_enabled", "true")
    updated = apply_change(template_payload, change)

    # Version numbers and authors are assigned by Firebase; echoing the old
    # ones back would be meaningless. The description is ours to set, and it
    # is what the version history shows next to the author.
    assert set(updated["version"]) == {"description"}
    assert "feature_enabled" in updated["version"]["description"]
    assert "false -> true" in updated["version"]["description"]


def test_apply_change_accepts_an_explicit_description(template_payload):
    change = build_change(template_payload, "feature_enabled", "true")
    updated = apply_change(template_payload, change, version_description="mi nota")
    assert updated["version"]["description"] == "mi nota"


def test_apply_change_preserves_unmodelled_fields(template_payload):
    template_payload["experiments"] = [{"name": "keep_me"}]
    change = build_change(template_payload, "feature_enabled", "true")
    updated = apply_change(template_payload, change)
    assert updated["experiments"] == [{"name": "keep_me"}]


def test_apply_change_fails_if_the_condition_disappeared(template_payload):
    change = build_change(template_payload, "welcome_text", "x", "android_prod")
    template_payload["conditions"] = []
    with pytest.raises(TemplateEditError):
        apply_change(template_payload, change)


def test_change_description_truncates_long_values(template_payload):
    change = build_change(template_payload, "welcome_text", "x" * 300)
    description = change.describe()
    assert description.endswith("…")
    assert len(description) < 250


def test_json_change_is_stored_compacted(template_payload):
    change = build_change(template_payload, "legacy_untyped", '{ "b" : 2 }')
    updated = apply_change(template_payload, change)
    assert updated["parameters"]["legacy_untyped"]["defaultValue"]["value"] == '{"b":2}'
