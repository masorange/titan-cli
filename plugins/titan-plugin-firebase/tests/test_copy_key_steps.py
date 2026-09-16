"""Copy missing Remote Config keys across projects."""

from dataclasses import replace
from unittest.mock import MagicMock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success
from titan_cli.engine.context import WorkflowContext

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.targets import FirebaseProjectTarget
from titan_plugin_firebase.models.values import RemoteConfigValueType as T
from titan_plugin_firebase.models.view import (
    UIRemoteConfigKeyCopyPlanEntry,
    UIRemoteConfigKeyCopyResult,
    UIRemoteConfigVersion,
)
from titan_plugin_firebase.operations.key_inventory_operations import (
    build_key_inventory,
    key_profiles_to_metadata,
)
from titan_plugin_firebase.steps.copy_key_step import (
    execute_firebase_remoteconfig_copy_key_step,
)
from titan_plugin_firebase.steps.sync_plan_step import (
    execute_firebase_remoteconfig_sync_plan_step,
)
from titan_plugin_firebase.steps.sync_publish_step import (
    execute_firebase_remoteconfig_sync_publish_step,
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
    environment: str | None = None,
) -> FirebaseProjectTarget:
    return FirebaseProjectTarget(
        project_id=project_id,
        label=label,
        environment=environment,
    )


def _template_without_legacy(ui_template):
    return replace(
        ui_template,
        project_id="mm-firebase-lebara",
        parameters=[
            parameter
            for parameter in ui_template.parameters
            if parameter.key != "legacy_untyped"
        ],
    )


def _copy_inventory(ui_template):
    inventory = build_key_inventory(
        {
            "mm-firebase-yoigo": ui_template,
            "mm-firebase-lebara": _template_without_legacy(ui_template),
        }
    )
    return key_profiles_to_metadata(inventory.key_profiles)


def _copy_ctx(ui_template, **data) -> WorkflowContext:
    ctx = _ctx()
    ctx.data["firebase_targets"] = [
        _target("Yoigo", "mm-firebase-yoigo"),
        _target("Lebara", "mm-firebase-lebara"),
    ]
    ctx.data["firebase_remoteconfig_key_profiles"] = _copy_inventory(ui_template)
    ctx.data["firebase_remoteconfig_failed_projects"] = {}
    ctx.data.update(data)
    return ctx


def _copy_result(**overrides) -> UIRemoteConfigKeyCopyResult:
    fields = {
        "source_project_id": "mm-firebase-yoigo",
        "project_id": "mm-firebase-lebara",
        "key": "legacy_untyped",
        "value_type": T.JSON,
        "validated_only": False,
        "etag": "e2",
        "version": UIRemoteConfigVersion(
            version_number="43",
            update_time="2026-09-15T09:00:00Z",
            update_user_email="alex@example.com",
            update_origin="REST_API",
            update_type="INCREMENTAL_UPDATE",
            description="Titan: copied Remote Config key legacy_untyped",
        ),
        "retried_after_conflict": False,
    }
    fields.update(overrides)
    return UIRemoteConfigKeyCopyResult(**fields)


def test_copy_key_step_plans_explicit_missing_destinations(ui_template):
    ctx = _copy_ctx(
        ui_template,
        key="legacy_untyped",
        target_project_ids="mm-firebase-lebara",
    )

    result = execute_firebase_remoteconfig_copy_key_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_key"] == "legacy_untyped"
    assert result.metadata["firebase_copy_source_project_id"] == "mm-firebase-yoigo"
    plan = result.metadata["firebase_copy_plan"]
    assert len(plan) == 1
    assert plan[0].key == "legacy_untyped"
    assert plan[0].source.project_id == "mm-firebase-yoigo"
    assert plan[0].target.project_id == "mm-firebase-lebara"
    assert plan[0].value_type == T.JSON
    ctx.textual.ask_option.assert_not_called()
    ctx.textual.ask_multiselect.assert_not_called()


def test_copy_key_step_prompts_for_the_missing_key_and_destinations(ui_template):
    ctx = _copy_ctx(ui_template)
    ctx.textual.ask_option.return_value = "legacy_untyped"
    ctx.textual.ask_multiselect.return_value = ["mm-firebase-lebara"]

    result = execute_firebase_remoteconfig_copy_key_step(ctx)

    assert isinstance(result, Success)
    key_options = ctx.textual.ask_option.call_args.args[1]
    assert [option.value for option in key_options] == ["legacy_untyped"]
    destination_options = ctx.textual.ask_multiselect.call_args.args[1]
    assert [option.value for option in destination_options] == ["mm-firebase-lebara"]


def test_copy_key_step_exits_when_key_is_already_common(ui_template):
    ctx = _copy_ctx(ui_template, key="welcome_text")

    result = execute_firebase_remoteconfig_copy_key_step(ctx)

    assert isinstance(result, Exit)
    assert "ya existe" in result.message


def test_copy_key_step_rejects_partial_inventory(ui_template):
    ctx = _copy_ctx(ui_template, key="legacy_untyped")
    ctx.data["firebase_remoteconfig_failed_projects"] = {"mm-firebase-lebara": "403"}

    result = execute_firebase_remoteconfig_copy_key_step(ctx)

    assert isinstance(result, Error)
    assert "no pudo leer todos los proyectos" in result.message


def test_copy_key_step_rejects_unknown_source_type(ui_template):
    ctx = _copy_ctx(ui_template, key="legacy_untyped")
    profile = ctx.data["firebase_remoteconfig_key_profiles"]["legacy_untyped"]
    profile["observations"]["mm-firebase-yoigo"]["effective_type"] = T.UNKNOWN.value

    result = execute_firebase_remoteconfig_copy_key_step(ctx)

    assert isinstance(result, Error)
    assert "tipo determinista" in result.message


def test_copy_key_step_rejects_firebase_managed_source_values(ui_template):
    ctx = _copy_ctx(ui_template, key="legacy_untyped")
    profile = ctx.data["firebase_remoteconfig_key_profiles"]["legacy_untyped"]
    profile["observations"]["mm-firebase-yoigo"]["unsupported_value_count"] = 1
    profile["observations"]["mm-firebase-yoigo"]["unsupported_value_sources"] = [
        "experimentValue"
    ]

    result = execute_firebase_remoteconfig_copy_key_step(ctx)

    assert isinstance(result, Error)
    assert "gestionados por Firebase" in result.message


def test_copy_key_step_allows_mixed_known_environments(ui_template):
    ctx = _copy_ctx(
        ui_template,
        key="legacy_untyped",
        target_project_ids="mm-firebase-lebara",
    )
    ctx.data["firebase_targets"] = [
        _target("Yoigo DEV", "mm-firebase-yoigo", environment="dev"),
        _target("Lebara PRO", "mm-firebase-lebara", environment="pro"),
    ]

    result = execute_firebase_remoteconfig_copy_key_step(ctx)

    assert isinstance(result, Success)
    assert [
        entry.target.environment for entry in result.metadata["firebase_copy_plan"]
    ] == ["pro"]


def test_sync_plan_builds_copy_entries_for_explicit_keys(ui_template):
    ctx = _copy_ctx(
        ui_template,
        keys="legacy_untyped",
        target_project_ids="mm-firebase-lebara",
    )

    result = execute_firebase_remoteconfig_sync_plan_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_sync_keys"] == ["legacy_untyped"]
    assert result.metadata["firebase_sync_rejected_keys"] == {}
    plan = result.metadata["firebase_copy_plan"]
    assert len(plan) == 1
    assert plan[0].source.project_id == "mm-firebase-yoigo"
    assert plan[0].target.project_id == "mm-firebase-lebara"


def test_sync_plan_rejects_keys_without_deterministic_source(ui_template):
    ctx = _copy_ctx(
        ui_template,
        keys="welcome_text",
        target_project_ids="mm-firebase-lebara",
    )

    result = execute_firebase_remoteconfig_sync_plan_step(ctx)

    assert isinstance(result, Error)
    assert "no son sincronizables" in result.message


def test_sync_plan_rejects_firebase_managed_source_values(ui_template):
    ctx = _copy_ctx(ui_template, keys="legacy_untyped")
    profile = ctx.data["firebase_remoteconfig_key_profiles"]["legacy_untyped"]
    profile["observations"]["mm-firebase-yoigo"]["unsupported_value_count"] = 1
    profile["observations"]["mm-firebase-yoigo"]["unsupported_value_sources"] = [
        "rolloutValue"
    ]

    result = execute_firebase_remoteconfig_sync_plan_step(ctx)

    assert isinstance(result, Error)
    assert "no son sincronizables" in result.message
    assert "origen gestionado por Firebase" in result.message


def test_sync_plan_allows_mixed_known_environments(ui_template):
    ctx = _copy_ctx(
        ui_template,
        keys="legacy_untyped",
        target_project_ids="mm-firebase-lebara",
    )
    ctx.data["firebase_targets"] = [
        _target("Yoigo DEV", "mm-firebase-yoigo", environment="dev"),
        _target("Lebara PRO", "mm-firebase-lebara", environment="pro"),
    ]

    result = execute_firebase_remoteconfig_sync_plan_step(ctx)

    assert isinstance(result, Success)
    assert [
        entry.target.environment for entry in result.metadata["firebase_copy_plan"]
    ] == ["pro"]


def test_sync_plan_prompts_for_syncable_keys(ui_template):
    ctx = _copy_ctx(ui_template)
    ctx.textual.ask_multiselect.side_effect = [
        ["legacy_untyped"],
        ["mm-firebase-lebara"],
    ]

    result = execute_firebase_remoteconfig_sync_plan_step(ctx)

    assert isinstance(result, Success)
    key_options = ctx.textual.ask_multiselect.call_args_list[0].args[1]
    assert [option.value for option in key_options] == ["legacy_untyped"]
    destination_options = ctx.textual.ask_multiselect.call_args_list[1].args[1]
    assert [option.value for option in destination_options] == ["mm-firebase-lebara"]


def _publish_ctx(**data) -> WorkflowContext:
    ctx = _ctx()
    ctx.data["firebase_copy_plan"] = [
        UIRemoteConfigKeyCopyPlanEntry(
            key="legacy_untyped",
            source=_target("Yoigo", "mm-firebase-yoigo"),
            target=_target("Lebara", "mm-firebase-lebara"),
            value_type=T.JSON,
        )
    ]
    ctx.data.update(data)
    return ctx


def test_sync_publish_validates_before_copying():
    ctx = _publish_ctx()
    ctx.firebase.copy_remote_config_key.side_effect = [
        ClientSuccess(data=_copy_result(validated_only=True)),
        ClientSuccess(data=_copy_result(), message="Clave publicada"),
    ]

    result = execute_firebase_remoteconfig_sync_publish_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_copy_published"] == 1
    flags = [
        call.kwargs["validate_only"]
        for call in ctx.firebase.copy_remote_config_key.call_args_list
    ]
    assert flags == [True, False]


def test_sync_publish_dry_run_only_validates():
    ctx = _publish_ctx(dry_run=True)
    ctx.firebase.copy_remote_config_key.return_value = ClientSuccess(
        data=_copy_result(validated_only=True)
    )

    result = execute_firebase_remoteconfig_sync_publish_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_copy_published"] == 1
    assert ctx.firebase.copy_remote_config_key.call_count == 1
    assert ctx.firebase.copy_remote_config_key.call_args.kwargs["validate_only"] is True


def test_sync_publish_skips_publish_when_validation_fails():
    ctx = _publish_ctx()
    ctx.firebase.copy_remote_config_key.return_value = ClientError(
        error_message="ya existe",
        error_code="TEMPLATE_EDIT_ERROR",
    )

    result = execute_firebase_remoteconfig_sync_publish_step(ctx)

    assert isinstance(result, Error)
    assert "0 proyectos" in result.message
    assert ctx.firebase.copy_remote_config_key.call_count == 1
