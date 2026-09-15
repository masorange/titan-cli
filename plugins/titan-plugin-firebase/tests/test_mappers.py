"""Network template payloads to UI models."""

from titan_plugin_firebase.models.mappers import map_template
from titan_plugin_firebase.models.network.rest import NetworkRemoteConfigTemplate
from titan_plugin_firebase.models.values import RemoteConfigValueType as T


def test_parameters_are_sorted_by_key(ui_template):
    assert [p.key for p in ui_template.parameters] == [
        "feature_enabled",
        "legacy_untyped",
        "welcome_text",
    ]


def test_declared_value_type_wins(ui_template):
    parameter = ui_template.parameter("feature_enabled")
    assert parameter.declared_value_type == T.BOOLEAN
    assert parameter.value_type == T.BOOLEAN
    assert parameter.default_value.parsed_value is False
    assert parameter.conditional_values["android_prod"].parsed_value is True


def test_untyped_parameter_type_is_inferred(ui_template):
    # Parameters created before valueType existed carry none, so the type has
    # to come from the value itself.
    parameter = ui_template.parameter("legacy_untyped")
    assert parameter.declared_value_type == T.UNKNOWN
    assert parameter.value_type == T.JSON
    assert parameter.default_value.parsed_value == {"a": 1}


def test_conditions_and_groups_are_exposed(ui_template):
    assert [c.name for c in ui_template.conditions] == ["android_prod"]
    assert ui_template.conditions[0].display_expression == "app.id == '1:1:android:1'"
    assert ui_template.parameter_group_names == ["onboarding"]


def test_version_metadata_carries_the_author(ui_template):
    version = ui_template.version
    assert version.version_number == "42"
    assert version.update_user_email == "someone@example.com"
    assert version.update_origin == "CONSOLE"


def test_value_for_returns_default_or_condition(ui_template):
    parameter = ui_template.parameter("feature_enabled")
    assert parameter.value_for(None).raw_value == "false"
    assert parameter.value_for("android_prod").raw_value == "true"
    assert parameter.value_for("missing_condition") is None


def test_round_trip_preserves_unmodelled_fields(template_payload):
    template_payload["experiments"] = [{"name": "future_field"}]
    network = NetworkRemoteConfigTemplate.model_validate(template_payload)
    payload = network.to_payload()
    # Publishing replaces the whole template, so anything Titan does not model
    # has to survive a read-modify-write.
    assert payload["experiments"] == [{"name": "future_field"}]
    assert payload["parameterGroups"] == template_payload["parameterGroups"]


def test_in_app_default_is_rendered_explicitly():
    network = NetworkRemoteConfigTemplate.model_validate(
        {"parameters": {"k": {"defaultValue": {"useInAppDefault": True}}}}
    )
    parameter = map_template("mm-firebase-yoigo", network, None).parameter("k")
    assert parameter.default_value.use_in_app_default is True
    assert parameter.default_value.display_value == "(in-app default)"
