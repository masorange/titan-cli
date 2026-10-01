"""Step behaviour: UI orchestration, metadata contracts, and error paths."""

from unittest.mock import MagicMock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success
from titan_cli.engine.context import WorkflowContext

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.view import UIAdcIdentity
from titan_plugin_firebase.models.view import UIFirebaseProject
from titan_plugin_firebase.steps.auth_check_step import (
    execute_firebase_auth_check_step,
)
from titan_plugin_firebase.steps.conditions_step import (
    execute_firebase_remoteconfig_conditions_step,
)
from titan_plugin_firebase.steps.list_keys_step import (
    execute_firebase_remoteconfig_list_keys_step,
)
from titan_plugin_firebase.steps.list_projects_step import (
    execute_firebase_projects_list_step,
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
        default_project="mm-firebase-dev"
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
    ctx.textual.ask_text.assert_not_called()


def test_select_target_keeps_a_caller_supplied_label():
    ctx = _ctx()
    ctx.data["project_id"] = "mm-firebase-yoigo"
    ctx.data["project_label"] = "yoigo"

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_target_label"] == "yoigo (mm-firebase-yoigo)"


def test_select_target_falls_back_to_the_configured_default():
    ctx = _ctx()

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_id"] == "mm-firebase-dev"
    # Nothing is asked: this plugin does not own a project catalogue.
    ctx.textual.ask_option.assert_not_called()
    ctx.textual.ask_text.assert_not_called()


def test_select_target_recovers_metadata_from_configured_project_set():
    ctx = _ctx(
        FirebasePluginConfig(
            default_project="mm-firebase-yoigo-pro",
            default_project_set="ragnarok_ios",
            project_sets={
                "ragnarok_ios": {
                    "projects": [
                        {
                            "project_id": "mm-firebase-yoigo-pro",
                            "label": "Yoigo PRO",
                            "brand": "Yoigo",
                            "environment": "PRO",
                        }
                    ]
                }
            },
        )
    )

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_id"] == "mm-firebase-yoigo-pro"
    assert result.metadata["firebase_target_label"] == (
        "Yoigo PRO (mm-firebase-yoigo-pro)"
    )
    assert result.metadata["firebase_environment"] == "pro"
    assert result.metadata["firebase_project_brand"] == "Yoigo"


def test_select_target_prompts_for_project_when_tui_has_no_default():
    ctx = _ctx(FirebasePluginConfig())
    ctx.textual.ask_text.return_value = "mm-firebase-yoigo"

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_id"] == "mm-firebase-yoigo"
    ctx.textual.ask_text.assert_called_once_with(
        "Project ID de Firebase:",
        default="",
    )


def test_select_target_lists_available_projects_before_manual_prompt():
    ctx = _ctx(FirebasePluginConfig())
    ctx.firebase.list_projects.return_value = ClientSuccess(
        data=[
            UIFirebaseProject(
                project_id="mm-firebase-yoigo",
                display_name="Yoigo",
                name="projects/mm-firebase-yoigo",
                project_number="111",
            )
        ]
    )
    ctx.textual.ask_option.return_value = "mm-firebase-yoigo"

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_id"] == "mm-firebase-yoigo"
    ctx.textual.ask_option.assert_called_once()
    ctx.textual.ask_text.assert_not_called()


def test_select_target_errors_when_tui_project_prompt_is_empty():
    ctx = _ctx(FirebasePluginConfig())
    ctx.textual.ask_text.return_value = ""

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Error)
    assert "project_id" in result.message


def test_select_target_errors_when_nothing_names_a_project_without_tui():
    ctx = _ctx(FirebasePluginConfig())
    ctx.textual = None

    result = execute_firebase_select_target_step(ctx)

    assert isinstance(result, Error)
    assert "default_project" in result.message


# --- list projects ----------------------------------------------------------


def test_list_projects_publishes_available_firebase_projects():
    ctx = _ctx()
    ctx.firebase.list_projects.return_value = ClientSuccess(
        data=[
            UIFirebaseProject(
                project_id="mm-firebase-yoigo",
                display_name="Yoigo",
                name="projects/mm-firebase-yoigo",
                project_number="111",
            )
        ]
    )

    result = execute_firebase_projects_list_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == ["mm-firebase-yoigo"]
    assert result.metadata["firebase_projects"][0].display_name == "Yoigo"
    ctx.textual.table.assert_called_once()


def test_list_projects_recovers_configured_project_metadata():
    ctx = _ctx(
        FirebasePluginConfig(
            project_sets={
                "ragnarok_ios": {
                    "default_environment": "PRO",
                    "projects": [
                        {
                            "project_id": "mm-firebase-yoigo",
                            "label": "Yoigo",
                            "brand": "Yoigo",
                            "groups": ["national"],
                        }
                    ],
                }
            }
        )
    )
    ctx.firebase.list_projects.return_value = ClientSuccess(
        data=[
            UIFirebaseProject(
                project_id="mm-firebase-yoigo",
                display_name="Firebase Yoigo",
                name="projects/mm-firebase-yoigo",
                project_number="111",
            )
        ]
    )

    result = execute_firebase_projects_list_step(ctx)

    assert isinstance(result, Success)
    project = result.metadata["firebase_projects"][0]
    assert project.configured_label == "Yoigo"
    assert project.environment == "pro"
    assert project.brand == "Yoigo"
    assert project.groups == ("national",)
    assert result.metadata["firebase_project_labels"] == {
        "mm-firebase-yoigo": "Yoigo"
    }
    assert result.metadata["firebase_project_environments"] == {
        "mm-firebase-yoigo": "pro"
    }
    assert result.metadata["firebase_project_brands"] == {
        "mm-firebase-yoigo": "Yoigo"
    }
    assert result.metadata["firebase_project_group_map"] == {
        "mm-firebase-yoigo": ["national"]
    }
    rows = ctx.textual.table.call_args.kwargs["rows"]
    assert rows == [
        [
            "mm-firebase-yoigo",
            "Firebase Yoigo",
            "Yoigo",
            "PRO",
            "Yoigo",
            "national",
            "111",
        ]
    ]


def test_list_projects_can_filter_the_project_catalogue():
    ctx = _ctx()
    ctx.data["project_filter"] = "Prepago, National"
    ctx.firebase.list_projects.return_value = ClientSuccess(
        data=[
            UIFirebaseProject(
                project_id="mm-firebase-lebara",
                display_name="- Prepago - Lebara",
                name="projects/mm-firebase-lebara",
                project_number="111",
            ),
            UIFirebaseProject(
                project_id="mm-firebase-yoigo",
                display_name="- National Telco - Yoigo",
                name="projects/mm-firebase-yoigo",
                project_number="222",
            ),
            UIFirebaseProject(
                project_id="mm-firebase-energy",
                display_name="- Energia - MasOrange",
                name="projects/mm-firebase-energy",
                project_number="333",
            ),
        ]
    )

    result = execute_firebase_projects_list_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == [
        "mm-firebase-lebara",
        "mm-firebase-yoigo",
    ]
    assert result.metadata["firebase_project_catalog_count"] == 3
    assert result.metadata["firebase_project_filter_terms"] == [
        "prepago",
        "national",
    ]
    assert len(ctx.textual.table.call_args.kwargs["rows"]) == 2


def test_list_projects_propagates_api_errors():
    ctx = _ctx()
    ctx.firebase.list_projects.return_value = ClientError(
        error_message="permiso denegado",
        error_code="PERMISSION_DENIED",
    )

    result = execute_firebase_projects_list_step(ctx)

    assert isinstance(result, Error)
    assert "permiso denegado" in result.message


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


# --- list keys --------------------------------------------------------------


def test_list_keys_publishes_the_complete_key_inventory(ui_template):
    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = ui_template

    result = execute_firebase_remoteconfig_list_keys_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_keys"] == [
        "feature_enabled",
        "legacy_untyped",
        "welcome_text",
    ]
    assert result.metadata["firebase_remoteconfig_key_count"] == 3
    assert result.metadata["firebase_remoteconfig_key_values"]["feature_enabled"] == {
        "key": "feature_enabled",
        "value_type": "BOOLEAN",
        "type_label": "Bool",
        "default_value": {
            "raw_value": "false",
            "display_value": "false",
            "value_type": "BOOLEAN",
            "type_label": "Bool",
            "use_in_app_default": False,
            "value_source": "value",
            "source_label": "Literal",
            "editable": True,
        },
        "conditional_values": {
            "android_prod": {
                "raw_value": "true",
                "display_value": "true",
                "value_type": "BOOLEAN",
                "type_label": "Bool",
                "use_in_app_default": False,
                "value_source": "value",
                "source_label": "Literal",
                "editable": True,
            }
        },
    }
    ctx.textual.table.assert_called_once()
    assert ctx.textual.table.call_args.kwargs["headers"] == [
        "Clave",
        "Tipo",
        "Valor por defecto",
        "Entornos/condiciones",
    ]
    assert ctx.textual.table.call_args.kwargs["rows"][0] == [
        "feature_enabled",
        "Bool",
        "false",
        "android_prod=true",
    ]


def test_list_keys_works_without_tui(ui_template):
    ctx = _ctx()
    ctx.textual = None
    ctx.data["firebase_remoteconfig_template"] = ui_template

    result = execute_firebase_remoteconfig_list_keys_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_key_count"] == 3


def test_list_keys_allows_empty_templates(ui_template):
    from dataclasses import replace

    ctx = _ctx()
    ctx.data["firebase_remoteconfig_template"] = replace(ui_template, parameters=[])

    result = execute_firebase_remoteconfig_list_keys_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_keys"] == []
    assert result.metadata["firebase_remoteconfig_key_count"] == 0
    ctx.textual.dim_text.assert_called_once()
    ctx.textual.table.assert_not_called()


def test_list_keys_without_a_template_is_an_error():
    ctx = _ctx()

    result = execute_firebase_remoteconfig_list_keys_step(ctx)

    assert isinstance(result, Error)
    assert "firebase_remoteconfig_get" in result.message


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
    assert (
        result.metadata["firebase_parameter_values"]["default_value"]["display_value"]
        == "false"
    )
    assert (
        result.metadata["firebase_parameter_values"]["conditional_values"][
            "android_prod"
        ]["display_value"]
        == "true"
    )
    assert ctx.textual.table.call_args.kwargs["headers"] == [
        "Clave",
        "Tipo",
        "Valor por defecto",
        "Entornos/condiciones",
        "Valor (android_prod)",
    ]


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
