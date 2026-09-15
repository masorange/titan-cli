"""Write steps: value entry, the diff gate, and publishing."""

from unittest.mock import MagicMock


from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success
from titan_cli.engine.context import WorkflowContext

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.values import RemoteConfigValueType as T
from titan_plugin_firebase.models.view import (
    UIRemoteConfigChange,
    UIRemoteConfigPublishResult,
    UIRemoteConfigVersion,
)
from titan_plugin_firebase.steps.diff_step import (
    execute_firebase_remoteconfig_diff_step,
)
from titan_plugin_firebase.steps.publish_step import (
    execute_firebase_remoteconfig_publish_step,
)
from titan_plugin_firebase.steps.set_value_step import (
    execute_firebase_remoteconfig_set_value_step,
)


def _ctx() -> WorkflowContext:
    ctx = WorkflowContext()
    ctx.textual = MagicMock()
    ctx.firebase = MagicMock()
    ctx.firebase.config = FirebasePluginConfig(default_project="mm-firebase-yoigo")
    ctx.data["firebase_project_id"] = "mm-firebase-yoigo"
    return ctx


def _change(**overrides) -> UIRemoteConfigChange:
    fields = {
        "key": "feature_enabled",
        "condition": None,
        "value_type": T.BOOLEAN,
        "old_raw_value": "false",
        "new_raw_value": "true",
        "inherited_from_default": False,
    }
    fields.update(overrides)
    return UIRemoteConfigChange(**fields)


def _publish_result(**overrides) -> UIRemoteConfigPublishResult:
    fields = {
        "project_id": "mm-firebase-yoigo",
        "validated_only": False,
        "etag": "e2",
        "version": UIRemoteConfigVersion(
            version_number="43",
            update_time="2026-09-15T09:00:00Z",
            update_user_email="alex@example.com",
            update_origin="REST_API",
            update_type="INCREMENTAL_UPDATE",
            description="Titan: feature_enabled [valor por defecto] false -> true",
        ),
        "change": _change(),
        "retried_after_conflict": False,
    }
    fields.update(overrides)
    return UIRemoteConfigPublishResult(**fields)


# --- set value --------------------------------------------------------------


def test_set_value_asks_with_buttons_for_a_boolean():
    ctx = _ctx()
    ctx.data.update(
        {
            "firebase_key": "feature_enabled",
            "firebase_value_type": "BOOLEAN",
            "firebase_current_value": "false",
        }
    )
    ctx.textual.ask_choice.return_value = "true"
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change()
    )

    result = execute_firebase_remoteconfig_set_value_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_new_value"] == "true"
    ctx.textual.ask_choice.assert_called_once()
    ctx.textual.ask_text.assert_not_called()


def test_set_value_uses_a_multiline_prompt_for_json():
    ctx = _ctx()
    ctx.data.update(
        {
            "firebase_key": "config_blob",
            "firebase_value_type": "JSON",
            "firebase_current_value": '{"a":1}',
        }
    )
    ctx.textual.ask_multiline.return_value = '{"a": 2}'
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change(key="config_blob", value_type=T.JSON, new_raw_value='{"a":2}')
    )

    result = execute_firebase_remoteconfig_set_value_step(ctx)

    assert isinstance(result, Success)
    # JSON is routinely multi-line; a single-line input would be unusable.
    ctx.textual.ask_multiline.assert_called_once()


def test_set_value_accepts_a_preset_value_without_prompting():
    ctx = _ctx()
    ctx.data.update(
        {"firebase_key": "feature_enabled", "firebase_value_type": "BOOLEAN", "value": "true"}
    )
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change()
    )

    result = execute_firebase_remoteconfig_set_value_step(ctx)

    assert isinstance(result, Success)
    ctx.textual.ask_choice.assert_not_called()


def test_set_value_passes_the_condition_through():
    ctx = _ctx()
    ctx.data.update(
        {
            "firebase_key": "welcome_text",
            "firebase_value_type": "STRING",
            "firebase_condition": "android_prod",
            "value": "adiós",
        }
    )
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change(
            key="welcome_text",
            condition="android_prod",
            value_type=T.STRING,
            old_raw_value=None,
            new_raw_value="adiós",
            inherited_from_default=True,
        )
    )

    result = execute_firebase_remoteconfig_set_value_step(ctx)

    assert isinstance(result, Success)
    ctx.firebase.validate_remote_config_change.assert_called_once_with(
        "mm-firebase-yoigo", "welcome_text", "adiós", "android_prod"
    )


def test_set_value_reports_an_invalid_value():
    ctx = _ctx()
    ctx.data.update(
        {"firebase_key": "feature_enabled", "firebase_value_type": "BOOLEAN", "value": "quizá"}
    )
    ctx.firebase.validate_remote_config_change.return_value = ClientError(
        error_message="'quizá' no es un booleano. Usa true o false.",
        error_code="INVALID_VALUE",
    )

    result = execute_firebase_remoteconfig_set_value_step(ctx)

    assert isinstance(result, Error)
    assert "booleano" in result.message


def test_set_value_requires_a_key():
    ctx = _ctx()
    ctx.data["value"] = "true"

    result = execute_firebase_remoteconfig_set_value_step(ctx)

    assert isinstance(result, Error)
    assert "key" in result.message


# --- diff -------------------------------------------------------------------


def test_diff_requires_confirmation_before_publishing():
    ctx = _ctx()
    ctx.data["firebase_change"] = _change()
    ctx.textual.ask_confirm.return_value = True

    result = execute_firebase_remoteconfig_diff_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_change_confirmed"] is True
    # The confirmation must default to "no": this is the irreversible step.
    assert ctx.textual.ask_confirm.call_args.kwargs["default"] is False


def test_diff_exits_when_the_user_declines():
    ctx = _ctx()
    ctx.data["firebase_change"] = _change()
    ctx.textual.ask_confirm.return_value = False

    result = execute_firebase_remoteconfig_diff_step(ctx)

    assert isinstance(result, Exit)


def test_diff_exits_on_a_noop_without_asking():
    ctx = _ctx()
    ctx.data["firebase_change"] = _change(old_raw_value="true", new_raw_value="true")

    result = execute_firebase_remoteconfig_diff_step(ctx)

    assert isinstance(result, Exit)
    assert "nada que publicar" in result.message
    ctx.textual.ask_confirm.assert_not_called()


def test_diff_without_a_change_is_an_error():
    result = execute_firebase_remoteconfig_diff_step(_ctx())

    assert isinstance(result, Error)
    assert "firebase_remoteconfig_set_value" in result.message


# --- publish ----------------------------------------------------------------


def test_publish_validates_before_publishing():
    ctx = _ctx()
    ctx.data.update(
        {"firebase_change": _change(), "firebase_change_confirmed": True}
    )
    ctx.firebase.publish_remote_config_change.side_effect = [
        ClientSuccess(data=_publish_result(validated_only=True)),
        ClientSuccess(data=_publish_result(), message="Publicada la versión 43"),
    ]

    result = execute_firebase_remoteconfig_publish_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_published_version"] == "43"
    assert result.metadata["firebase_published_author"] == "alex@example.com"
    validate_only_flags = [
        call.kwargs["validate_only"]
        for call in ctx.firebase.publish_remote_config_change.call_args_list
    ]
    assert validate_only_flags == [True, False]


def test_publish_stops_when_validation_fails():
    ctx = _ctx()
    ctx.data.update(
        {"firebase_change": _change(), "firebase_change_confirmed": True}
    )
    ctx.firebase.publish_remote_config_change.return_value = ClientError(
        error_message="Param count too large",
        error_code="BAD_REQUEST",
    )

    result = execute_firebase_remoteconfig_publish_step(ctx)

    assert isinstance(result, Error)
    assert "Param count too large" in result.message
    # Only the validation ran; nothing was published.
    assert ctx.firebase.publish_remote_config_change.call_count == 1


def test_publish_refuses_an_unconfirmed_change():
    ctx = _ctx()
    ctx.data["firebase_change"] = _change()

    result = execute_firebase_remoteconfig_publish_step(ctx)

    assert isinstance(result, Error)
    assert "firebase_remoteconfig_diff" in result.message
    ctx.firebase.publish_remote_config_change.assert_not_called()


def test_dry_run_validates_without_confirmation_and_publishes_nothing():
    ctx = _ctx()
    ctx.data.update({"firebase_change": _change(), "dry_run": True})
    ctx.firebase.publish_remote_config_change.return_value = ClientSuccess(
        data=_publish_result(validated_only=True, version=None)
    )

    result = execute_firebase_remoteconfig_publish_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_published_version"] is None
    assert ctx.firebase.publish_remote_config_change.call_count == 1
    assert (
        ctx.firebase.publish_remote_config_change.call_args.kwargs["validate_only"]
        is True
    )


def test_publish_surfaces_a_conflict_retry():
    ctx = _ctx()
    ctx.data.update(
        {"firebase_change": _change(), "firebase_change_confirmed": True}
    )
    ctx.firebase.publish_remote_config_change.side_effect = [
        ClientSuccess(data=_publish_result(validated_only=True)),
        ClientSuccess(
            data=_publish_result(retried_after_conflict=True),
            message="Publicada la versión 43 (tras reintentar por ETag)",
        ),
    ]

    result = execute_firebase_remoteconfig_publish_step(ctx)

    assert isinstance(result, Success)
    ctx.textual.warning_text.assert_called_once()


def test_publish_reports_an_api_failure():
    ctx = _ctx()
    ctx.data.update(
        {"firebase_change": _change(), "firebase_change_confirmed": True}
    )
    ctx.firebase.publish_remote_config_change.side_effect = [
        ClientSuccess(data=_publish_result(validated_only=True)),
        ClientError(error_message="permiso denegado", error_code="PERMISSION_DENIED"),
    ]

    result = execute_firebase_remoteconfig_publish_step(ctx)

    assert isinstance(result, Error)
    assert "permiso denegado" in result.message
