"""Read-modify-write over a whole template payload."""

import pytest

from titan_plugin_firebase.models.values import (
    RemoteConfigValueError,
    RemoteConfigValueSource,
    RemoteConfigValueType as T,
)
from titan_plugin_firebase.operations.template_operations import (
    TemplateEditError,
    add_parameter_to_payload,
    apply_change,
    blocked_value_sources_for_parameter,
    build_change,
    build_parameter_payload,
    condition_names,
    current_raw_value,
    effective_value_type_for,
    parameter_payload,
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


def test_build_change_rejects_firebase_managed_default_value():
    payload = {
        "parameters": {
            "k": {
                "defaultValue": {"experimentValue": {"experimentId": "exp-1"}},
                "valueType": "STRING",
            }
        }
    }

    with pytest.raises(TemplateEditError, match="Experiment"):
        build_change(payload, "k", "hola")


def test_build_change_rejects_firebase_managed_conditional_value(template_payload):
    template_payload["parameters"]["welcome_text"]["conditionalValues"] = {
        "android_prod": {"rolloutValue": {"rolloutId": "rollout-1"}}
    }

    with pytest.raises(TemplateEditError, match="Rollout"):
        build_change(template_payload, "welcome_text", "hola", "android_prod")


def test_build_change_allows_adding_a_missing_conditional_literal(template_payload):
    template_payload["parameters"]["welcome_text"]["defaultValue"] = {
        "experimentValue": {"experimentId": "exp-1"}
    }

    change = build_change(template_payload, "welcome_text", "hola", "android_prod")

    assert change.creates_conditional_value is True


def test_apply_change_rechecks_managed_values_after_validation(template_payload):
    change = build_change(template_payload, "welcome_text", "hola")
    template_payload["parameters"]["welcome_text"]["defaultValue"] = {
        "personalizationValue": {"personalizationId": "personalization-1"}
    }

    with pytest.raises(TemplateEditError, match="Personalization"):
        apply_change(template_payload, change)


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


def test_parameter_payload_returns_a_copy(template_payload):
    copied = parameter_payload(template_payload, "welcome_text")

    copied["defaultValue"]["value"] = "mutated"

    assert template_payload["parameters"]["welcome_text"]["defaultValue"]["value"] == (
        "hola"
    )


def test_add_parameter_to_payload_copies_a_missing_parameter(template_payload):
    target = {
        "conditions": template_payload["conditions"],
        "parameters": {
            "feature_enabled": template_payload["parameters"]["feature_enabled"],
        },
    }
    source_parameter = parameter_payload(template_payload, "welcome_text")

    updated = add_parameter_to_payload(target, "welcome_text", source_parameter)

    assert updated["parameters"]["welcome_text"] == source_parameter
    assert (
        updated["parameters"]["feature_enabled"]
        == target["parameters"]["feature_enabled"]
    )
    assert "welcome_text" not in target["parameters"]
    assert updated["version"] == {
        "description": "Titan: copied Remote Config key welcome_text"
    }


def test_add_parameter_to_payload_refuses_to_overwrite(template_payload):
    source_parameter = parameter_payload(template_payload, "welcome_text")

    with pytest.raises(TemplateEditError, match="ya existe"):
        add_parameter_to_payload(template_payload, "welcome_text", source_parameter)


def test_add_parameter_to_payload_requires_matching_conditions(template_payload):
    source_parameter = parameter_payload(template_payload, "feature_enabled")
    target_without_conditions = {"parameters": {}}

    with pytest.raises(TemplateEditError, match="android_prod"):
        add_parameter_to_payload(
            target_without_conditions,
            "feature_enabled",
            source_parameter,
        )


def test_add_parameter_to_payload_rejects_firebase_managed_values():
    source_parameter = {
        "defaultValue": {"value": "fallback"},
        "conditionalValues": {
            "android_prod": {"experimentValue": {"experimentId": "exp-1"}}
        },
        "valueType": "STRING",
    }
    target = {
        "conditions": [{"name": "android_prod"}],
        "parameters": {},
    }

    with pytest.raises(TemplateEditError, match="Experiment"):
        add_parameter_to_payload(target, "k", source_parameter)


def test_blocked_value_sources_for_parameter_reports_future_union_fields():
    assert blocked_value_sources_for_parameter(
        {"defaultValue": {"newFirebaseValue": {"id": "future"}}}
    ) == [RemoteConfigValueSource.UNKNOWN]


def test_build_parameter_payload_serializes_typed_values():
    parameter = build_parameter_payload(
        T.JSON,
        '{ "enabled": true }',
        conditional_values={"android_prod": '{ "enabled": false }'},
        description="Feature settings",
    )

    assert parameter == {
        "defaultValue": {"value": '{"enabled":true}'},
        "valueType": "JSON",
        "description": "Feature settings",
        "conditionalValues": {
            "android_prod": {"value": '{"enabled":false}'},
        },
    }


def test_build_parameter_payload_rejects_unknown_types():
    with pytest.raises(TemplateEditError, match="tipo"):
        build_parameter_payload(T.UNKNOWN, "x")


def test_build_parameter_payload_rejects_invalid_values():
    with pytest.raises(RemoteConfigValueError):
        build_parameter_payload(T.BOOLEAN, "quizá")
