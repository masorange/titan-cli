"""Creating Remote Config keys across selected projects."""

from unittest.mock import MagicMock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success
from titan_cli.engine.context import WorkflowContext

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.targets import FirebaseProjectTarget
from titan_plugin_firebase.models.values import RemoteConfigValueType as T
from titan_plugin_firebase.models.view import (
    UIRemoteConfigKeyCreatePlanEntry,
    UIRemoteConfigKeyCreateRequest,
    UIRemoteConfigKeyCreateResult,
    UIRemoteConfigVersion,
)
from titan_plugin_firebase.steps.create_key_publish_step import (
    execute_firebase_remoteconfig_create_key_publish_step,
)
from titan_plugin_firebase.steps.create_key_step import (
    execute_firebase_remoteconfig_create_key_plan_step,
)


def _ctx() -> WorkflowContext:
    ctx = WorkflowContext()
    ctx.textual = MagicMock()
    ctx.firebase = MagicMock()
    ctx.firebase.config = FirebasePluginConfig()
    return ctx


def _target(
    label: str,
    project_id: str,
    *,
    environment: str | None = "pro",
) -> FirebaseProjectTarget:
    return FirebaseProjectTarget(
        project_id=project_id,
        label=label,
        environment=environment,
    )


def _create_ctx(**data) -> WorkflowContext:
    ctx = _ctx()
    ctx.data["firebase_targets"] = [
        _target("Yoigo", "mm-firebase-yoigo"),
        _target("Lebara", "mm-firebase-lebara"),
    ]
    ctx.data["firebase_remoteconfig_key_profiles"] = {
        "new_flag": {
            "present_projects": ["mm-firebase-yoigo"],
            "missing_projects": ["mm-firebase-lebara"],
            "conflict_projects": [],
        },
        "common_flag": {
            "present_projects": [
                "mm-firebase-yoigo",
                "mm-firebase-lebara",
            ],
            "missing_projects": [],
            "conflict_projects": [],
        },
    }
    ctx.data["firebase_remoteconfig_project_conditions"] = {
        "mm-firebase-yoigo": [{"name": "android_prod"}],
        "mm-firebase-lebara": [{"name": "android_prod"}],
    }
    ctx.data["firebase_remoteconfig_failed_projects"] = {}
    ctx.data.update(data)
    return ctx


def _request(**overrides) -> UIRemoteConfigKeyCreateRequest:
    fields = {
        "key": "new_flag",
        "value_type": T.BOOLEAN,
        "default_raw_value": "true",
        "conditional_raw_values": {},
        "description": None,
    }
    fields.update(overrides)
    return UIRemoteConfigKeyCreateRequest(**fields)


def _create_result(**overrides) -> UIRemoteConfigKeyCreateResult:
    fields = {
        "project_id": "mm-firebase-lebara",
        "key": "new_flag",
        "value_type": T.BOOLEAN,
        "validated_only": False,
        "etag": "e2",
        "version": UIRemoteConfigVersion(
            version_number="43",
            update_time="2026-09-15T09:00:00Z",
            update_user_email="alex@example.com",
            update_origin="REST_API",
            update_type="INCREMENTAL_UPDATE",
            description="Titan: created Remote Config key new_flag",
        ),
        "retried_after_conflict": False,
    }
    fields.update(overrides)
    return UIRemoteConfigKeyCreateResult(**fields)


def test_create_key_plan_validates_only_missing_selected_projects():
    ctx = _create_ctx(
        key="new_flag",
        value_type="bool",
        default_value="TRUE",
        conditional_values={},
        target_project_ids="mm-firebase-lebara",
    )
    ctx.firebase.create_remote_config_key.return_value = ClientSuccess(
        data=_create_result(validated_only=True)
    )

    result = execute_firebase_remoteconfig_create_key_plan_step(ctx)

    assert isinstance(result, Success)
    plan = result.metadata["firebase_create_key_plan"]
    assert len(plan) == 1
    assert plan[0].target.project_id == "mm-firebase-lebara"
    assert plan[0].request.key == "new_flag"
    assert plan[0].request.value_type == T.BOOLEAN
    assert result.metadata["firebase_value_type"] == "BOOLEAN"
    ctx.firebase.create_remote_config_key.assert_called_once()
    assert (
        ctx.firebase.create_remote_config_key.call_args.kwargs["validate_only"] is True
    )
    ctx.textual.ask_multiselect.assert_not_called()


def test_create_key_plan_exits_when_the_key_exists_everywhere():
    ctx = _create_ctx(key="common_flag")

    result = execute_firebase_remoteconfig_create_key_plan_step(ctx)

    assert isinstance(result, Exit)
    assert "ya existe" in result.message
    ctx.firebase.create_remote_config_key.assert_not_called()


def test_create_key_plan_rejects_target_where_key_already_exists():
    ctx = _create_ctx(
        key="new_flag",
        value_type="BOOLEAN",
        default_value="true",
        target_project_ids="mm-firebase-yoigo",
    )

    result = execute_firebase_remoteconfig_create_key_plan_step(ctx)

    assert isinstance(result, Error)
    assert "no son proyectos donde falte" in result.message
    ctx.firebase.create_remote_config_key.assert_not_called()


def test_create_key_plan_rejects_condition_not_common_to_targets():
    ctx = _create_ctx(
        key="new_flag",
        value_type="BOOLEAN",
        default_value="true",
        conditional_values={"ios_beta": "false"},
        target_project_ids="mm-firebase-lebara",
    )

    result = execute_firebase_remoteconfig_create_key_plan_step(ctx)

    assert isinstance(result, Error)
    assert "condiciones no existen" in result.message
    ctx.firebase.create_remote_config_key.assert_not_called()


def test_create_key_plan_keeps_validation_errors_per_project():
    ctx = _create_ctx(
        key="brand_new",
        value_type="STRING",
        default_value="hola",
        conditional_values={},
        target_project_ids="mm-firebase-yoigo mm-firebase-lebara",
    )
    ctx.firebase.create_remote_config_key.side_effect = [
        ClientSuccess(data=_create_result(project_id="mm-firebase-yoigo")),
        ClientError(
            error_message="sin permiso",
            error_code="PERMISSION_DENIED",
        ),
    ]

    result = execute_firebase_remoteconfig_create_key_plan_step(ctx)

    assert isinstance(result, Success)
    assert [
        entry.target.project_id for entry in result.metadata["firebase_create_key_plan"]
    ] == ["mm-firebase-yoigo"]
    rejected = result.metadata["firebase_create_key_rejected"]
    assert rejected[0].target.project_id == "mm-firebase-lebara"
    assert rejected[0].error == "sin permiso"


def test_create_key_plan_allows_mixed_known_environments():
    ctx = _create_ctx(
        key="brand_new",
        value_type="STRING",
        default_value="hola",
        conditional_values={},
        target_project_ids="mm-firebase-yoigo mm-firebase-lebara",
    )
    ctx.data["firebase_targets"] = [
        _target("Yoigo DEV", "mm-firebase-yoigo", environment="dev"),
        _target("Lebara PRO", "mm-firebase-lebara", environment="pro"),
    ]
    ctx.firebase.create_remote_config_key.side_effect = [
        ClientSuccess(data=_create_result(project_id="mm-firebase-yoigo")),
        ClientSuccess(data=_create_result(project_id="mm-firebase-lebara")),
    ]

    result = execute_firebase_remoteconfig_create_key_plan_step(ctx)

    assert isinstance(result, Success)
    assert [
        entry.target.environment
        for entry in result.metadata["firebase_create_key_plan"]
    ] == ["dev", "pro"]


def _publish_ctx(**data) -> WorkflowContext:
    ctx = _ctx()
    ctx.data["firebase_create_key_plan"] = [
        UIRemoteConfigKeyCreatePlanEntry(
            target=_target("Lebara", "mm-firebase-lebara"),
            request=_request(),
        )
    ]
    ctx.data.update(data)
    return ctx


def test_create_key_publish_validates_before_publishing():
    ctx = _publish_ctx()
    ctx.firebase.create_remote_config_key.side_effect = [
        ClientSuccess(data=_create_result(validated_only=True)),
        ClientSuccess(data=_create_result(), message="Clave publicada"),
    ]

    result = execute_firebase_remoteconfig_create_key_publish_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_create_key_published"] == 1
    flags = [
        call.kwargs["validate_only"]
        for call in ctx.firebase.create_remote_config_key.call_args_list
    ]
    assert flags == [True, False]


def test_create_key_publish_dry_run_only_validates():
    ctx = _publish_ctx(dry_run=True)
    ctx.firebase.create_remote_config_key.return_value = ClientSuccess(
        data=_create_result(validated_only=True)
    )

    result = execute_firebase_remoteconfig_create_key_publish_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_create_key_published"] == 1
    assert ctx.firebase.create_remote_config_key.call_count == 1
    assert (
        ctx.firebase.create_remote_config_key.call_args.kwargs["validate_only"] is True
    )


def test_create_key_publish_skips_publish_when_validation_fails():
    ctx = _publish_ctx()
    ctx.firebase.create_remote_config_key.return_value = ClientError(
        error_message="ya existe",
        error_code="TEMPLATE_EDIT_ERROR",
    )

    result = execute_firebase_remoteconfig_create_key_publish_step(ctx)

    assert isinstance(result, Error)
    assert "0 proyectos" in result.message
    assert ctx.firebase.create_remote_config_key.call_count == 1
