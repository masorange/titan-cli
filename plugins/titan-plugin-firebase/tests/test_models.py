from titan_plugin_firebase.models import (
    RemoteConfigValueType,
    build_parameter_inventory,
    infer_remote_config_value_type,
)


def test_infer_remote_config_value_types() -> None:
    assert infer_remote_config_value_type("true") == RemoteConfigValueType.BOOLEAN
    assert infer_remote_config_value_type('{"enabled": true}') == RemoteConfigValueType.JSON
    assert infer_remote_config_value_type("[1, 2]") == RemoteConfigValueType.JSON
    assert infer_remote_config_value_type("42") == RemoteConfigValueType.NUMBER
    assert infer_remote_config_value_type("hello") == RemoteConfigValueType.STRING


def test_build_parameter_inventory_uses_declared_json_type() -> None:
    parameter = build_parameter_inventory(
        "feature_payload",
        {
            "description": "Feature payload",
            "valueType": "JSON",
            "defaultValue": {"value": '{"enabled": true}'},
            "conditionalValues": {
                "beta_users": {"value": '{"enabled": false}'},
            },
        },
    )

    assert parameter.value_type == RemoteConfigValueType.JSON
    assert parameter.default_value.parsed_value == {"enabled": True}
    assert parameter.conditional_values["beta_users"].parsed_value == {
        "enabled": False
    }


def test_build_parameter_inventory_infers_boolean_type() -> None:
    parameter = build_parameter_inventory(
        "feature_enabled",
        {"defaultValue": {"value": "false"}},
    )

    assert parameter.declared_value_type == RemoteConfigValueType.UNKNOWN
    assert parameter.inferred_value_type == RemoteConfigValueType.BOOLEAN
    assert parameter.value_type == RemoteConfigValueType.BOOLEAN
    assert parameter.default_value.parsed_value is False
