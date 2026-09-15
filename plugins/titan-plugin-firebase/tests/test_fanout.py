"""Multi-brand fan-out: plan aggregation, per-brand confirmation, publishing."""

from unittest.mock import MagicMock

import pytest

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success
from titan_cli.engine.context import WorkflowContext

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.targets import FirebaseProjectTarget
from titan_plugin_firebase.models.values import RemoteConfigValueType as T
from titan_plugin_firebase.models.view import (
    UIFanoutEntry,
    UIFanoutOutcome,
    UIRemoteConfigChange,
    UIRemoteConfigPublishResult,
    UIRemoteConfigVersion,
)
from titan_plugin_firebase.operations.fanout_operations import (
    describe_plan,
    outcome_summary,
    plan_summary,
    publishable_entries,
    select_entries,
)
from titan_plugin_firebase.steps.fanout_plan_step import (
    execute_firebase_remoteconfig_fanout_plan_step,
)
from titan_plugin_firebase.steps.fanout_publish_step import (
    execute_firebase_remoteconfig_fanout_publish_step,
)
from titan_plugin_firebase.steps.select_targets_step import (
    execute_firebase_select_targets_step,
)

BRAND_CONFIG = FirebasePluginConfig(
    brands=["yoigo", "masmovil", "guuk"],
    project_id_pattern="mm-firebase-{brand}",
    brand_project_overrides={"guuk": "mm-guuk-firebase-prod"},
)


def _ctx(config=BRAND_CONFIG) -> WorkflowContext:
    ctx = WorkflowContext()
    ctx.textual = MagicMock()
    ctx.firebase = MagicMock()
    ctx.firebase.config = config
    return ctx


def _target(brand: str, project_id: str) -> FirebaseProjectTarget:
    return FirebaseProjectTarget(project_id=project_id, brand=brand)


def _change(new_value="true", old_value="false") -> UIRemoteConfigChange:
    return UIRemoteConfigChange(
        key="feature_enabled",
        condition=None,
        value_type=T.BOOLEAN,
        old_raw_value=old_value,
        new_raw_value=new_value,
    )


def _published(version="43", retried=False) -> UIRemoteConfigPublishResult:
    return UIRemoteConfigPublishResult(
        project_id="mm-firebase-yoigo",
        validated_only=False,
        etag="e2",
        version=UIRemoteConfigVersion(
            version_number=version,
            update_time=None,
            update_user_email="alex@example.com",
            update_origin="REST_API",
            update_type="INCREMENTAL_UPDATE",
            description=None,
        ),
        change=_change(),
        retried_after_conflict=retried,
    )


# --- operations -------------------------------------------------------------


def test_plan_summary_counts_by_status():
    entries = [
        UIFanoutEntry(target=_target("yoigo", "mm-firebase-yoigo"), change=_change()),
        UIFanoutEntry(
            target=_target("masmovil", "mm-firebase-masmovil"),
            change=_change(new_value="false"),
        ),
        UIFanoutEntry(
            target=_target("guuk", "mm-guuk-firebase-prod"), error="no existe la clave"
        ),
    ]
    assert plan_summary(entries) == {"ready": 1, "noop": 1, "error": 1}
    assert [entry.target.brand for entry in publishable_entries(entries)] == ["yoigo"]


def test_entry_detail_explains_each_status():
    ready = UIFanoutEntry(
        target=_target("yoigo", "mm-firebase-yoigo"), change=_change()
    )
    noop = UIFanoutEntry(
        target=_target("masmovil", "mm-firebase-masmovil"),
        change=_change(new_value="false"),
    )
    failed = UIFanoutEntry(
        target=_target("guuk", "mm-guuk-firebase-prod"), error="sin permiso"
    )
    assert ready.detail == "false -> true"
    assert noop.detail == "ya vale false"
    assert failed.detail == "sin permiso"


def test_entry_detail_marks_a_value_that_did_not_exist():
    entry = UIFanoutEntry(
        target=_target("yoigo", "mm-firebase-yoigo"),
        change=_change(old_value=None),
    )
    assert entry.detail == "(sin valor) -> true"


def test_select_entries_keeps_plan_order_and_ignores_unknown_ids():
    entries = [
        UIFanoutEntry(target=_target("yoigo", "mm-firebase-yoigo"), change=_change()),
        UIFanoutEntry(target=_target("guuk", "mm-guuk-firebase-prod"), change=_change()),
    ]
    chosen = select_entries(entries, ["mm-guuk-firebase-prod", "mm-firebase-other"])
    assert [entry.target.brand for entry in chosen] == ["guuk"]


def test_outcome_summary_and_rows():
    outcomes = [
        UIFanoutOutcome(target=_target("yoigo", "mm-firebase-yoigo"), published=_published()),
        UIFanoutOutcome(target=_target("guuk", "mm-guuk-firebase-prod"), error="403"),
    ]
    assert outcome_summary(outcomes) == {"published": 1, "failed": 1}


def test_outcome_detail_flags_a_conflict_retry():
    outcome = UIFanoutOutcome(
        target=_target("yoigo", "mm-firebase-yoigo"),
        published=_published(retried=True),
    )
    assert outcome.detail == "versión 43 (reintentada por ETag)"


def test_describe_plan_rows():
    entries = [
        UIFanoutEntry(target=_target("yoigo", "mm-firebase-yoigo"), change=_change())
    ]
    assert describe_plan(entries) == [
        ["yoigo", "mm-firebase-yoigo", "ready", "false -> true"]
    ]


# --- select targets ---------------------------------------------------------


def test_select_targets_resolves_the_chosen_brands():
    ctx = _ctx()
    ctx.textual.ask_multiselect.return_value = ["yoigo", "guuk"]

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert [target.project_id for target in result.metadata["firebase_targets"]] == [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
    ]


def test_select_targets_preselects_nothing():
    ctx = _ctx()
    ctx.textual.ask_multiselect.return_value = []

    execute_firebase_select_targets_step(ctx)

    options = ctx.textual.ask_multiselect.call_args.args[1]
    # A fan-out writes to production projects: nothing is checked by default.
    assert all(option.selected is False for option in options)


def test_select_targets_accepts_a_comma_separated_param():
    ctx = _ctx()
    ctx.data["brands"] = "yoigo, guuk"

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert len(result.metadata["firebase_targets"]) == 2
    ctx.textual.ask_multiselect.assert_not_called()


def test_select_targets_reports_brands_it_could_not_resolve():
    ctx = _ctx(FirebasePluginConfig(brand_projects={"pro": {"yoigo": "y-pro"}}))
    ctx.data["brands"] = ["yoigo", "lebara"]

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert [t.project_id for t in result.metadata["firebase_targets"]] == ["y-pro"]
    assert set(result.metadata["firebase_target_failures"]) == {"lebara"}
    ctx.textual.warning_text.assert_called_once()


def test_select_targets_errors_when_no_brand_resolves():
    ctx = _ctx(FirebasePluginConfig())
    ctx.data["brands"] = ["lebara"]

    assert isinstance(execute_firebase_select_targets_step(ctx), Error)


# --- plan -------------------------------------------------------------------


def _plan_ctx(**data) -> WorkflowContext:
    ctx = _ctx()
    ctx.data["firebase_targets"] = [
        _target("yoigo", "mm-firebase-yoigo"),
        _target("guuk", "mm-guuk-firebase-prod"),
    ]
    ctx.data.update({"key": "feature_enabled", "value": "true"})
    ctx.data.update(data)
    return ctx


def test_plan_validates_every_brand_independently():
    ctx = _plan_ctx()
    ctx.firebase.validate_remote_config_change.side_effect = [
        ClientSuccess(data=_change()),
        ClientError(error_message="no existe la clave", error_code="TEMPLATE_EDIT_ERROR"),
    ]
    ctx.textual.ask_multiselect.return_value = ["mm-firebase-yoigo"]

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Success)
    assert [entry.target.brand for entry in result.metadata["firebase_fanout_plan"]] == [
        "yoigo"
    ]
    # The brand that cannot take the change is kept in the report, not dropped.
    assert any(
        entry.status == "error" for entry in result.metadata["firebase_fanout_rejected"]
    )


def test_plan_exits_when_no_brand_needs_the_change():
    ctx = _plan_ctx()
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change(new_value="false")
    )

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Exit)
    ctx.textual.ask_multiselect.assert_not_called()


def test_plan_exits_when_the_user_selects_no_brand():
    ctx = _plan_ctx()
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change()
    )
    ctx.textual.ask_multiselect.return_value = []

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Exit)


def test_plan_requires_targets():
    ctx = _ctx()
    ctx.data.update({"key": "k", "value": "v"})

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Error)
    assert "firebase_select_targets" in result.message


def test_plan_ignores_empty_workflow_params_and_asks(ui_template):
    # The workflow declares key/value/condition with empty defaults, so "" has
    # to mean "ask me", not "write an empty string".
    ctx = _plan_ctx(key="", value="", condition="")
    ctx.firebase.get_remote_config.return_value = ClientSuccess(data=ui_template)
    ctx.textual.ask_option.side_effect = ["__default__", "feature_enabled"]
    ctx.textual.ask_choice.return_value = "true"
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change()
    )
    ctx.textual.ask_multiselect.return_value = [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
    ]

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Success)
    # The first brand's template is the reference the prompts are built from.
    ctx.firebase.get_remote_config.assert_called_once_with("mm-firebase-yoigo")
    assert len(result.metadata["firebase_fanout_plan"]) == 2


def test_plan_fails_when_the_reference_template_cannot_be_read():
    ctx = _plan_ctx(key="", value="")
    ctx.firebase.get_remote_config.return_value = ClientError(
        error_message="403", error_code="PERMISSION_DENIED"
    )

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Error)
    assert "referencia" in result.message


# --- publish ----------------------------------------------------------------


def _publish_ctx(**data) -> WorkflowContext:
    ctx = _ctx()
    ctx.data["firebase_fanout_plan"] = [
        UIFanoutEntry(target=_target("yoigo", "mm-firebase-yoigo"), change=_change()),
        UIFanoutEntry(target=_target("guuk", "mm-guuk-firebase-prod"), change=_change()),
    ]
    ctx.data.update(data)
    return ctx


def test_publish_continues_after_one_brand_fails():
    ctx = _publish_ctx()
    ctx.firebase.publish_remote_config_change.side_effect = [
        ClientSuccess(data=_published()),           # yoigo validation
        ClientSuccess(data=_published()),           # yoigo publish
        ClientSuccess(data=_published()),           # guuk validation
        ClientError(error_message="403", error_code="PERMISSION_DENIED"),
    ]

    result = execute_firebase_remoteconfig_fanout_publish_step(ctx)

    # Nine good publishes must not be lost because the tenth brand denies it.
    assert isinstance(result, Success)
    assert result.metadata["firebase_fanout_published"] == 1
    assert result.metadata["firebase_fanout_failed"] == 1
    outcomes = result.metadata["firebase_fanout_outcomes"]
    assert [outcome.succeeded for outcome in outcomes] == [True, False]


def test_publish_validates_each_brand_before_writing_it():
    ctx = _publish_ctx()
    ctx.firebase.publish_remote_config_change.side_effect = [
        ClientSuccess(data=_published()),
        ClientSuccess(data=_published()),
        ClientSuccess(data=_published()),
        ClientSuccess(data=_published()),
    ]

    execute_firebase_remoteconfig_fanout_publish_step(ctx)

    flags = [
        call.kwargs["validate_only"]
        for call in ctx.firebase.publish_remote_config_change.call_args_list
    ]
    assert flags == [True, False, True, False]


def test_publish_skips_a_brand_whose_validation_fails():
    ctx = _publish_ctx()
    ctx.firebase.publish_remote_config_change.side_effect = [
        ClientError(error_message="Param count too large", error_code="BAD_REQUEST"),
        ClientSuccess(data=_published()),
        ClientSuccess(data=_published()),
    ]

    result = execute_firebase_remoteconfig_fanout_publish_step(ctx)

    assert isinstance(result, Success)
    outcomes = result.metadata["firebase_fanout_outcomes"]
    assert outcomes[0].succeeded is False
    assert "validación" in outcomes[0].error
    # Three calls, not four: the failed brand was never published.
    assert ctx.firebase.publish_remote_config_change.call_count == 3


def test_publish_fails_when_every_brand_fails():
    ctx = _publish_ctx()
    ctx.firebase.publish_remote_config_change.return_value = ClientError(
        error_message="403", error_code="PERMISSION_DENIED"
    )

    result = execute_firebase_remoteconfig_fanout_publish_step(ctx)

    assert isinstance(result, Error)
    assert "0 marcas publicadas" in result.message


def test_dry_run_publishes_nothing():
    ctx = _publish_ctx(dry_run=True)
    ctx.firebase.publish_remote_config_change.return_value = ClientSuccess(
        data=_published()
    )

    result = execute_firebase_remoteconfig_fanout_publish_step(ctx)

    assert isinstance(result, Success)
    assert "validadas" in result.message
    flags = [
        call.kwargs["validate_only"]
        for call in ctx.firebase.publish_remote_config_change.call_args_list
    ]
    assert flags == [True, True]


def test_publish_requires_a_plan():
    result = execute_firebase_remoteconfig_fanout_publish_step(_ctx())

    assert isinstance(result, Error)
    assert "firebase_remoteconfig_fanout_plan" in result.message
