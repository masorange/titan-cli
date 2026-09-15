"""Step behaviour: UI orchestration, metadata contracts, and error paths."""

from unittest.mock import MagicMock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success
from titan_cli.engine.context import WorkflowContext

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.view import UIAdcIdentity
from titan_plugin_firebase.steps.auth_check_step import (
    execute_firebase_auth_check_step,
)
from titan_plugin_firebase.steps.conditions_step import (
    execute_firebase_remoteconfig_conditions_step,
)
from titan_plugin_firebase.steps.remoteconfig_get_step import (
    execute_firebase_remoteconfig_get_step,
)
from titan_plugin_firebase.steps.select_key_step import (
    execute_firebase_remoteconfig_select_key_step,
)
from titan_plugin_firebase.steps.select_target_step import (
    execute_firebase_select_target_step,
)



def _ctx(config=None) -> WorkflowContext:
    ctx = WorkflowContext()
    ctx.textual = MagicMock()
    ctx.firebase = MagicMock()
    ctx.firebase.config = config or FirebasePluginConfig(
        brands=["yoigo", "guuk"],
        project_id_pattern="mm-firebase-{brand}",
        brand_project_overrides={"guuk": "mm-guuk-firebase-prod"},
    )
    return ctx


# --- auth check -------------------------------------------------------------


def test_auth_check_publishes_the_identity():
    ctx = _ctx()
    ctx.firebase.check_auth.return_value = ClientSuccess(
        data=UIAdcIdentity(
            account="alex@example.com",
            credential_kind="user",
            quota_project_id="mm-ragnarok-dev",
        )
    )

    result = execute_firebase_auth_check_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_account"] == "alex@example.com"
    assert result.metadata["firebase_credential_is_user"] is True


def test_auth_check_warns_when_a_service_account_would_own_the_changes():
    ctx = _ctx()
    ctx.firebase.check_auth.return_value = ClientSuccess(
        data=UIAdcIdentity(
            account="ci@project.iam.gserviceaccount.com",
            credential_kind="service_account",
            quota_project_id=None,
        )
    )
    ctx.firebase.uses_service_account_env_var.return_value = True

    result = execute_firebase_auth_check_step(ctx)

    # It still works, but the Firebase version history would name the service
    # account for every publish, which defeats the audit trail.
    assert isinstance(result, Success)
    assert result.metadata["firebase_credential_is_user"] is False
    ctx.textual.warning_text.assert_called_once()


def test_auth_check_errors_without_credentials():
    ctx = _ctx()
    ctx.firebase.check_auth.return_value = ClientError(
        error_message="sin credenciales",
        error_code="ADC_UNAVAILABLE",
    )

    result = execute_firebase_auth_check_step(ctx)

    assert isinstance(result, Error)
    assert "sin credenciales" in result.message


def test_auth_check_errors_without_plugin():
    ctx = _ctx()
    ctx.firebase = None

    assert isinstance(execute_firebase_auth_check_step(ctx), Error)


# --- select target ----------------------------------------------------------


def test_select_target_uses_explicit_project_without_prompting():
    ctx = _ctx()
    ctx.data["project_id"] = "mm-firebase-other"

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_id"] == "mm-firebase-other"
    ctx.textual.ask_option.assert_not_called()


def test_select_target_resolves_the_chosen_brand():
    ctx = _ctx()
    ctx.textual.ask_option.return_value = "guuk"

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_id"] == "mm-guuk-firebase-prod"
    assert result.metadata["firebase_brand"] == "guuk"


def test_select_target_asks_for_the_environment_when_ambiguous():
    config = FirebasePluginConfig(
        brand_projects={
            "pre": {"yoigo": "y-pre"},
            "pro": {"yoigo": "y-pro"},
        }
    )
    ctx = _ctx(config)
    ctx.textual.ask_option.side_effect = ["pro", "yoigo"]

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_id"] == "y-pro"
    assert result.metadata["firebase_environment"] == "pro"


def test_select_target_errors_when_nothing_is_configured():
    ctx = _ctx(FirebasePluginConfig())
    ctx.textual.ask_option.return_value = None

    assert isinstance(execute_firebase_select_target_step(ctx), Error)


# --- read -------------------------------------------------------------------


def test_get_publishes_etag_and_template(ui_template):
    ctx = _ctx()
    ctx.data["firebase_project_id"] = "mm-firebase-yoigo"
    ctx.firebase.get_remote_config.return_value = ClientSuccess(data=ui_template)

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_etag"] == "etag-1"
    assert result.metadata["firebase_remoteconfig_version"] == "42"
    assert result.metadata["firebase_remoteconfig_template"].parameter_count == 3


def test_get_errors_without_a_project():
    ctx = _ctx(FirebasePluginConfig())

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Error)
    assert "firebase_select_target" in result.message


def test_get_propagates_api_errors():
    ctx = _ctx()
    ctx.data["firebase_project_id"] = "mm-firebase-yoigo"
    ctx.firebase.get_remote_config.return_value = ClientError(
        error_message="permiso denegado",
        error_code="PERMISSION_DENIED",
    )

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Error)
    assert "permiso denegado" in result.message


# --- conditions -------------------------------------------------------------


def test_conditions_lets_the_user_pick_a_condition(ui_template):
    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = ui_template
    ctx.textual.ask_option.return_value = "android_prod"

    result = execute_firebase_remoteconfig_conditions_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_condition"] == "android_prod"


def test_conditions_default_target_is_none(ui_template):
    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = ui_template
    ctx.textual.ask_option.return_value = "__default__"

    result = execute_firebase_remoteconfig_conditions_step(ctx)

    assert result.metadata["firebase_condition"] is None
    assert result.metadata["firebase_condition_label"] == "valor por defecto"


def test_conditions_accepts_a_preselected_condition(ui_template):
    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = ui_template
    ctx.data["condition"] = "android_prod"

    result = execute_firebase_remoteconfig_conditions_step(ctx)

    assert result.metadata["firebase_condition"] == "android_prod"
    ctx.textual.ask_option.assert_not_called()


def test_conditions_rejects_a_condition_that_does_not_exist(ui_template):
    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = ui_template
    ctx.data["condition"] = "does_not_exist"

    result = execute_firebase_remoteconfig_conditions_step(ctx)

    assert isinstance(result, Error)
    assert "does_not_exist" in result.message


def test_conditions_without_a_template_is_an_error():
    ctx = _ctx()

    result = execute_firebase_remoteconfig_conditions_step(ctx)

    assert isinstance(result, Error)
    assert "firebase_remoteconfig_get" in result.message


# --- select key -------------------------------------------------------------


def test_select_key_reports_the_current_value_for_the_target(ui_template):
    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = ui_template
    ctx.data["firebase_condition"] = "android_prod"
    ctx.textual.ask_option.return_value = "feature_enabled"

    result = execute_firebase_remoteconfig_select_key_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_key"] == "feature_enabled"
    assert result.metadata["firebase_value_type"] == "BOOLEAN"
    # The condition overrides the default, so the current value is the
    # conditional one.
    assert result.metadata["firebase_current_value"] == "true"


def test_select_key_reports_none_when_the_condition_has_no_value(ui_template):
    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = ui_template
    ctx.data["firebase_condition"] = "android_prod"
    ctx.data["key"] = "welcome_text"

    result = execute_firebase_remoteconfig_select_key_step(ctx)

    assert result.metadata["firebase_current_value"] is None


def test_select_key_rejects_an_unknown_key(ui_template):
    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = ui_template
    ctx.data["key"] = "nope"

    result = execute_firebase_remoteconfig_select_key_step(ctx)

    assert isinstance(result, Error)
    assert "nope" in result.message
