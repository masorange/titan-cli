"""Multi-project fan-out: inventory, plan aggregation, confirmation, publishing."""

from dataclasses import replace
from unittest.mock import MagicMock

from rich.text import Text

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success
from titan_cli.engine.context import WorkflowContext
from titan_cli.ui.tui.widgets import Table

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.mappers import map_template
from titan_plugin_firebase.models.network.rest import NetworkRemoteConfigTemplate
from titan_plugin_firebase.models.targets import FirebaseProjectTarget
from titan_plugin_firebase.models.values import RemoteConfigValueType as T
from titan_plugin_firebase.models.view import (
    UIFanoutEntry,
    UIFanoutOutcome,
    UIFirebaseProject,
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
from titan_plugin_firebase.operations.key_inventory_operations import (
    build_key_inventory,
    describe_key_comparison_items,
    describe_key_inventory,
    describe_project_key_value_items,
    describe_project_key_values,
)
from titan_plugin_firebase.steps.fanout_list_keys_step import (
    execute_firebase_remoteconfig_fanout_list_keys_step,
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


def _ctx(config=None) -> WorkflowContext:
    ctx = WorkflowContext()
    ctx.textual = MagicMock()
    ctx.firebase = MagicMock()
    ctx.firebase.config = config or FirebasePluginConfig()
    return ctx


def _target(
    label: str,
    project_id: str,
    *,
    environment: str | None = None,
    brand: str | None = None,
) -> FirebaseProjectTarget:
    return FirebaseProjectTarget(
        project_id=project_id,
        label=label,
        environment=environment,
        brand=brand,
    )


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
    assert [entry.target.label for entry in publishable_entries(entries)] == ["yoigo"]


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
        UIFanoutEntry(
            target=_target("guuk", "mm-guuk-firebase-prod"), change=_change()
        ),
    ]
    chosen = select_entries(entries, ["mm-guuk-firebase-prod", "mm-firebase-other"])
    assert [entry.target.label for entry in chosen] == ["guuk"]


def test_outcome_summary_and_rows():
    outcomes = [
        UIFanoutOutcome(
            target=_target("yoigo", "mm-firebase-yoigo"), published=_published()
        ),
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
        ["yoigo (mm-firebase-yoigo)", "ready", "false -> true"]
    ]


# --- select targets ---------------------------------------------------------


def test_select_targets_takes_the_project_list_from_a_workflow_param():
    ctx = _ctx()
    ctx.data["project_ids"] = "mm-firebase-yoigo, mm-guuk-firebase-prod"

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
    ]


def test_select_targets_takes_the_list_produced_by_an_earlier_step():
    # This is the seam another plugin uses: it resolves its own names to
    # project IDs and publishes them, and this plugin never learns what the
    # names meant.
    ctx = _ctx()
    ctx.data["firebase_project_ids"] = ["mm-firebase-yoigo"]
    ctx.data["firebase_project_labels"] = {"mm-firebase-yoigo": "yoigo"}

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    targets = result.metadata["firebase_targets"]
    assert targets[0].reference() == "yoigo (mm-firebase-yoigo)"


def test_select_targets_uses_the_default_project_set_from_config():
    ctx = _ctx(
        FirebasePluginConfig(
            default_project_set="ragnarok_ios",
            project_sets={
                "ragnarok_ios": {
                    "projects": [
                        {
                            "project_id": "mm-firebase-lebara",
                            "label": "Lebara",
                            "brand": "Lebara",
                            "environment": "pro",
                            "groups": ["prepago"],
                        },
                        {
                            "project_id": "mm-firebase-yoigo",
                            "label": "Yoigo",
                            "brand": "Yoigo",
                            "environment": "pro",
                            "groups": ["national"],
                        },
                    ]
                }
            },
        )
    )

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == [
        "mm-firebase-lebara",
        "mm-firebase-yoigo",
    ]
    assert result.metadata["firebase_project_set"] == "ragnarok_ios"
    assert result.metadata["firebase_environment"] == "pro"
    assert result.metadata["firebase_environments"] == ["pro"]
    assert result.metadata["firebase_project_environments"] == {
        "mm-firebase-lebara": "pro",
        "mm-firebase-yoigo": "pro",
    }
    assert result.metadata["firebase_project_brands"] == {
        "mm-firebase-lebara": "Lebara",
        "mm-firebase-yoigo": "Yoigo",
    }
    ctx.textual.ask_text.assert_not_called()
    ctx.textual.ask_multiselect.assert_not_called()


def test_select_targets_summarizes_visible_targets_by_brand_and_environments():
    ctx = _ctx(
        FirebasePluginConfig(
            default_project_set="ragnarok_ios",
            project_sets={
                "ragnarok_ios": {
                    "projects": [
                        {
                            "project_id": "mm-firebase-yoigo-dev",
                            "label": "Yoigo DEV",
                            "brand": "Yoigo",
                            "environment": "dev",
                            "groups": ["national"],
                        },
                        {
                            "project_id": "mm-firebase-yoigo-pro",
                            "label": "Yoigo PRO",
                            "brand": "Yoigo",
                            "environment": "pro",
                            "groups": ["national"],
                        },
                        {
                            "project_id": "mm-firebase-lebara",
                            "label": "Lebara",
                            "brand": "Lebara",
                            "environment": "pro",
                            "groups": ["prepago"],
                        },
                    ]
                }
            },
        )
    )
    ctx.textual.ask_multiselect.return_value = ["dev", "pro"]

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    table = ctx.textual.table.call_args.kwargs
    assert table["headers"] == ["Marca", "Entornos", "Grupo"]
    assert table["rows"] == [
        ["Yoigo", "DEV, PRO", "national"],
        ["Lebara", "PRO", "prepago"],
    ]
    assert table["flex_column"] == 0


def test_select_targets_filters_the_configured_project_set_by_group():
    ctx = _ctx(
        FirebasePluginConfig(
            default_project_set="ragnarok_ios",
            project_sets={
                "ragnarok_ios": {
                    "projects": [
                        {
                            "project_id": "mm-firebase-lebara",
                            "label": "Lebara",
                            "groups": ["prepago"],
                        },
                        {
                            "project_id": "mm-firebase-yoigo",
                            "label": "Yoigo",
                            "groups": ["national"],
                        },
                    ]
                }
            },
        )
    )
    ctx.data["project_groups"] = "prepago"

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == ["mm-firebase-lebara"]
    assert result.metadata["firebase_project_groups"] == ["prepago"]
    ctx.textual.ask_text.assert_not_called()
    ctx.textual.ask_multiselect.assert_not_called()


def test_select_targets_filters_the_configured_project_set_by_environment():
    ctx = _ctx(
        FirebasePluginConfig(
            default_project_set="ragnarok_ios",
            project_sets={
                "ragnarok_ios": {
                    "projects": [
                        {
                            "project_id": "mm-firebase-yoigo-dev",
                            "label": "Yoigo DEV",
                            "brand": "Yoigo",
                            "environment": "dev",
                        },
                        {
                            "project_id": "mm-firebase-yoigo-pro",
                            "label": "Yoigo PRO",
                            "brand": "Yoigo",
                            "environment": "pro",
                        },
                    ]
                }
            },
        )
    )
    ctx.data["environment"] = "PRO"

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == ["mm-firebase-yoigo-pro"]
    assert result.metadata["firebase_environment"] == "pro"
    assert result.metadata["firebase_environment_filter"] == ["pro"]


def test_select_targets_asks_which_environments_to_include():
    ctx = _ctx(
        FirebasePluginConfig(
            default_project_set="ragnarok_ios",
            project_sets={
                "ragnarok_ios": {
                    "default_environment": "pro",
                    "projects": [
                        {
                            "project_id": "mm-firebase-yoigo-dev",
                            "label": "Yoigo DEV",
                            "brand": "Yoigo",
                            "environment": "dev",
                        },
                        {
                            "project_id": "mm-firebase-yoigo-pro",
                            "label": "Yoigo PRO",
                            "brand": "Yoigo",
                            "environment": "pro",
                        },
                    ]
                }
            },
        )
    )
    ctx.textual.ask_multiselect.return_value = ["pro", "dev"]

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == [
        "mm-firebase-yoigo-dev",
        "mm-firebase-yoigo-pro",
    ]
    assert result.metadata["firebase_environments"] == ["dev", "pro"]
    assert result.metadata["firebase_environment_filter"] == ["pro", "dev"]
    assert "firebase_environment" not in result.metadata
    options = ctx.textual.ask_multiselect.call_args.args[1]
    assert [(option.value, option.selected) for option in options] == [
        ("dev", False),
        ("pro", True),
    ]


def test_select_targets_filters_explicit_project_ids_by_configured_environment():
    ctx = _ctx(
        FirebasePluginConfig(
            default_project_set="ragnarok_ios",
            project_sets={
                "ragnarok_ios": {
                    "projects": [
                        {
                            "project_id": "mm-firebase-yoigo-dev",
                            "label": "Yoigo DEV",
                            "environment": "dev",
                        },
                        {
                            "project_id": "mm-firebase-yoigo-pro",
                            "label": "Yoigo PRO",
                            "environment": "pro",
                        },
                    ]
                }
            },
        )
    )
    ctx.data["project_ids"] = "mm-firebase-yoigo-dev, mm-firebase-yoigo-pro"
    ctx.data["environment"] = "dev"

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == ["mm-firebase-yoigo-dev"]
    assert result.metadata["firebase_environment"] == "dev"


def test_select_targets_does_not_prompt_when_projects_are_supplied():
    # The caller chose the projects; this step only normalizes them.
    ctx = _ctx()
    ctx.data["project_ids"] = ["mm-firebase-yoigo"]

    execute_firebase_select_targets_step(ctx)

    ctx.textual.ask_text.assert_not_called()
    ctx.textual.ask_multiselect.assert_not_called()
    ctx.textual.ask_option.assert_not_called()


def test_select_targets_prompts_for_projects_when_tui_has_no_input():
    ctx = _ctx()
    ctx.textual.ask_text.return_value = "mm-firebase-yoigo, mm-guuk-firebase-prod"

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
    ]
    ctx.textual.ask_text.assert_called_once_with(
        "Project IDs de Firebase (separados por coma):",
        default="",
    )


def test_select_targets_lists_available_projects_for_tui_selection():
    ctx = _ctx()
    ctx.firebase.list_projects.return_value = ClientSuccess(
        data=[
            UIFirebaseProject(
                project_id="mm-firebase-yoigo",
                display_name="Yoigo",
                name="projects/mm-firebase-yoigo",
                project_number="111",
            ),
            UIFirebaseProject(
                project_id="mm-guuk-firebase-prod",
                display_name="Guuk",
                name="projects/mm-guuk-firebase-prod",
                project_number="222",
            ),
        ]
    )
    ctx.textual.ask_multiselect.return_value = [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
    ]

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
    ]
    ctx.textual.ask_multiselect.assert_called_once()
    ctx.textual.ask_text.assert_not_called()


def test_select_targets_recovers_config_metadata_after_catalogue_selection():
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
    ctx.textual.ask_multiselect.return_value = ["mm-firebase-yoigo"]

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    target = result.metadata["firebase_targets"][0]
    assert target.label == "Yoigo"
    assert target.environment == "pro"
    assert target.brand == "Yoigo"
    assert target.groups == ["national"]
    assert result.metadata["firebase_environment"] == "pro"
    assert result.metadata["firebase_project_environments"] == {
        "mm-firebase-yoigo": "pro"
    }


def test_select_targets_filters_the_available_project_catalogue():
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
    ctx.textual.ask_multiselect.return_value = [
        "mm-firebase-lebara",
        "mm-firebase-yoigo",
    ]

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_ids"] == [
        "mm-firebase-lebara",
        "mm-firebase-yoigo",
    ]
    options = ctx.textual.ask_multiselect.call_args.args[1]
    assert [option.value for option in options] == [
        "mm-firebase-lebara",
        "mm-firebase-yoigo",
    ]


def test_select_targets_errors_when_tui_project_prompt_is_empty():
    ctx = _ctx()
    ctx.textual.ask_text.return_value = ""

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Error)
    assert "firebase_project_ids" in result.message


def test_select_targets_errors_without_a_project_list_or_tui():
    ctx = _ctx()
    ctx.textual = None

    result = execute_firebase_select_targets_step(ctx)

    assert isinstance(result, Error)
    assert "firebase_project_ids" in result.message


# --- key inventory ----------------------------------------------------------


def _template_with_feature_as_string(ui_template):
    feature = ui_template.parameter("feature_enabled")
    welcome = ui_template.parameter("welcome_text")
    assert feature is not None
    assert welcome is not None
    return replace(
        ui_template,
        project_id="mm-guuk-firebase-prod",
        parameters=[
            replace(
                feature,
                value_type=T.STRING,
                declared_value_type=T.STRING,
            ),
            welcome,
        ],
    )


def test_key_inventory_finds_missing_keys_and_type_conflicts(ui_template):
    other_template = _template_with_feature_as_string(ui_template)

    inventory = build_key_inventory(
        {
            "mm-firebase-yoigo": ui_template,
            "mm-guuk-firebase-prod": other_template,
        }
    )

    assert inventory.keys == [
        "feature_enabled",
        "legacy_untyped",
        "welcome_text",
    ]
    assert inventory.common_keys == ["feature_enabled", "welcome_text"]
    assert inventory.missing_keys["mm-guuk-firebase-prod"] == ["legacy_untyped"]
    assert inventory.type_conflicts == {
        "feature_enabled": ["BOOLEAN", "STRING"],
    }
    assert inventory.value_types == ["BOOLEAN", "JSON", "STRING"]
    assert inventory.bulk_safe_keys == ["welcome_text"]
    assert inventory.bulk_blocked_keys == {
        "feature_enabled": ["type_conflict"],
        "legacy_untyped": ["missing"],
    }
    assert inventory.key_profiles["welcome_text"].is_bulk_safe is True
    assert inventory.key_profiles["welcome_text"].bulk_value_type == "STRING"
    assert inventory.key_profiles["feature_enabled"].is_bulk_safe is False

    rows = describe_key_inventory(inventory)
    assert rows[0] == [
        "feature_enabled",
        "2/2",
        "Bool / String",
        "type conflict",
    ]
    assert rows[1] == ["legacy_untyped", "1/2", "JSON", "missing in 1"]

    value_rows = describe_project_key_values(
        {
            "mm-firebase-yoigo": ui_template,
            "mm-guuk-firebase-prod": other_template,
        },
        [
            _target("yoigo", "mm-firebase-yoigo", environment="dev"),
            _target("guuk", "mm-guuk-firebase-prod", environment="pro"),
        ],
    )
    assert value_rows[0] == [
        "yoigo",
        "feature_enabled",
        "default, android_prod",
        "Bool · default=false, android_prod=true",
    ]


def test_project_key_value_rows_are_compact_for_table_rendering():
    template = map_template(
        "mm-firebase-yoigo",
        NetworkRemoteConfigTemplate.model_validate(
            {
                "parameters": {
                    "long_value": {
                        "defaultValue": {
                            "value": "line one\nline two with a lot of content "
                            "that should not stretch the inventory table"
                        },
                        "conditionalValues": {
                            "android_prod": {
                                "value": "android value with enough words to wrap badly"
                            },
                            "ios_prod": {
                                "value": "ios value with enough words to wrap badly"
                            },
                            "web_prod": {"value": "web value"},
                        },
                        "valueType": "STRING",
                    }
                }
            }
        ),
        "etag-1",
    )

    rows = describe_project_key_values(
        {"mm-firebase-yoigo": template},
        [_target("yoigo", "mm-firebase-yoigo", environment="pro")],
    )

    assert len(rows[0]) == 4
    assert rows[0][0] == "yoigo"
    assert rows[0][1] == "long_value"
    assert rows[0][2] == "default, android_prod, ios_prod, web_prod"
    assert "\n" not in rows[0][3]
    assert len(rows[0][3]) <= 96
    assert "+2 mas" in rows[0][3]


def test_project_key_value_rows_can_filter_by_condition_group():
    template = map_template(
        "mm-firebase-yoigo",
        NetworkRemoteConfigTemplate.model_validate(
            {
                "parameters": {
                    "flag": {
                        "defaultValue": {"value": "false"},
                        "conditionalValues": {
                            "Android - Dev": {"value": "true"},
                            "iOS - Dev": {"value": "false"},
                        },
                        "valueType": "BOOLEAN",
                    }
                }
            }
        ),
        "etag-1",
    )
    condition_group = FirebasePluginConfig(
        condition_groups={
            "android": {
                "label": "Android",
                "condition_contains": ["Android"],
            }
        }
    ).condition_groups["android"]

    rows = describe_project_key_values(
        {"mm-firebase-yoigo": template},
        [_target("yoigo", "mm-firebase-yoigo")],
        condition_group,
    )

    assert rows == [
        [
            "yoigo",
            "flag",
            "default, Android - Dev",
            "Bool · default=false, Android - Dev=true",
        ]
    ]


def test_project_key_value_items_include_expandable_value_details():
    template = map_template(
        "mm-firebase-yoigo",
        NetworkRemoteConfigTemplate.model_validate(
            {
                "parameters": {
                    "flag": {
                        "defaultValue": {"value": "false"},
                        "conditionalValues": {
                            "Android - Dev": {"value": "true"},
                        },
                        "valueType": "BOOLEAN",
                        "description": "Activates a feature.",
                    }
                }
            }
        ),
        "etag-1",
    )

    items = describe_project_key_value_items(
        {"mm-firebase-yoigo": template},
        [_target("Yoigo", "mm-firebase-yoigo")],
    )

    assert len(items) == 1
    assert items[0].project_label == "Yoigo"
    assert items[0].key == "flag"
    assert items[0].type_label == "Bool"
    assert items[0].description == "Activates a feature."
    assert items[0].environment_summary == "default, Android - Dev"
    assert items[0].value_rows == [
        ["default", "false", "Literal", "si"],
        ["Android - Dev", "true", "Literal", "si"],
    ]


def test_project_key_value_items_expose_json_values_as_tree_details():
    template = map_template(
        "mm-firebase-yoigo",
        NetworkRemoteConfigTemplate.model_validate(
            {
                "parameters": {
                    "deviceDealsConfiguration": {
                        "defaultValue": {
                            "value": (
                                '{"smartphone":["P09718P","P0978M5"],'
                                '"recommendedGroupIds":["G075DGT"]}'
                            )
                        },
                        "valueType": "JSON",
                    }
                }
            }
        ),
        "etag-1",
    )

    items = describe_project_key_value_items(
        {"mm-firebase-yoigo": template},
        [_target("Yoigo", "mm-firebase-yoigo")],
    )

    assert items[0].value_rows == [
        [
            "default",
            "objeto · 2 claves",
            "Literal",
            "si",
        ]
    ]
    assert items[0].json_details[0].title == "default"
    assert items[0].json_details[0].value == {
        "recommendedGroupIds": ["G075DGT"],
        "smartphone": ["P09718P", "P0978M5"],
    }


def test_key_comparison_items_merge_inventory_and_values_by_key(ui_template):
    other_template = _template_with_feature_as_string(ui_template)
    templates = {
        "mm-firebase-yoigo": ui_template,
        "mm-guuk-firebase-prod": other_template,
    }
    items = describe_key_comparison_items(
        templates,
        [
            _target(
                "Yoigo",
                "mm-firebase-yoigo",
                environment="pro",
                brand="Yoigo",
            ),
            _target(
                "Guuk",
                "mm-guuk-firebase-prod",
                environment="pro",
                brand="Guuk",
            ),
        ],
        build_key_inventory(templates),
    )

    assert [item.key for item in items] == [
        "feature_enabled",
        "legacy_untyped",
        "welcome_text",
    ]
    feature = items[0]
    assert feature.type_label == "Bool / String"
    assert feature.present_count == 2
    assert feature.project_count == 2
    assert feature.status_label == "conflicto de tipo"
    assert feature.has_issues is True
    assert feature.description_lines == ["Kill switch"]
    assert feature.value_rows == [
        ["Yoigo", "PRO", "default", "false", "Literal", "si"],
        ["", "", "android_prod", "true", "Literal", "si"],
        ["Guuk", "PRO", "default", "false", "Literal", "si"],
        ["", "", "android_prod", "true", "Literal", "si"],
    ]

    legacy = items[1]
    assert legacy.status_label == "falta en 1"
    assert legacy.value_rows == [
        ["Yoigo", "PRO", "default", "objeto · 1 clave", "Literal", "si"],
        ["Guuk", "PRO", "—", "No existe", "—", "—"],
    ]
    assert legacy.json_details[0].title == "Yoigo · default"
    assert legacy.json_details[0].value == {"a": 1}


def test_key_comparison_items_disambiguate_same_brand_project_environments(
    ui_template,
):
    dev_template = replace(ui_template, project_id="mm-firebase-yoigo-dev")
    templates = {
        "mm-firebase-yoigo": ui_template,
        "mm-firebase-yoigo-dev": dev_template,
    }
    items = describe_key_comparison_items(
        templates,
        [
            _target(
                "Yoigo PRO",
                "mm-firebase-yoigo",
                environment="pro",
                brand="Yoigo",
            ),
            _target(
                "Yoigo DEV",
                "mm-firebase-yoigo-dev",
                environment="dev",
                brand="Yoigo",
            ),
        ],
        build_key_inventory(templates),
    )

    assert items[0].value_rows[0][:2] == ["Yoigo", "PRO"]
    assert items[0].value_rows[2][:2] == ["Yoigo", "DEV"]


def test_project_key_value_rows_hide_keys_without_group_values_when_default_is_off():
    template = map_template(
        "mm-firebase-yoigo",
        NetworkRemoteConfigTemplate.model_validate(
            {
                "parameters": {
                    "flag": {
                        "defaultValue": {"value": "false"},
                        "conditionalValues": {"iOS - Dev": {"value": "true"}},
                        "valueType": "BOOLEAN",
                    }
                }
            }
        ),
        "etag-1",
    )
    condition_group = FirebasePluginConfig(
        condition_groups={
            "android": {
                "include_default": False,
                "condition_contains": ["Android"],
            }
        }
    ).condition_groups["android"]

    assert (
        describe_project_key_values(
            {"mm-firebase-yoigo": template},
            [_target("yoigo", "mm-firebase-yoigo")],
            condition_group,
        )
        == []
    )


def test_key_inventory_marks_mixed_legacy_values_as_not_bulk_safe():
    template = map_template(
        "mm-firebase-yoigo",
        NetworkRemoteConfigTemplate.model_validate(
            {
                "parameters": {
                    "legacy_mixed": {
                        "defaultValue": {"value": '{"enabled": true}'},
                        "conditionalValues": {
                            "ios_prod": {"value": "plain string"},
                        },
                    }
                }
            }
        ),
        "etag-1",
    )

    inventory = build_key_inventory({"mm-firebase-yoigo": template})

    profile = inventory.key_profiles["legacy_mixed"]
    assert profile.value_types == ["UNKNOWN"]
    assert profile.inferred_value_types == ["JSON", "STRING"]
    assert profile.issues == ["local_type_conflict", "unknown_type"]
    assert inventory.bulk_safe_keys == []
    assert inventory.bulk_blocked_keys == {
        "legacy_mixed": ["local_type_conflict", "unknown_type"],
    }
    assert inventory.unknown_type_keys == {
        "mm-firebase-yoigo": ["legacy_mixed"],
    }


def test_key_inventory_marks_firebase_managed_values_as_not_bulk_safe():
    template = map_template(
        "mm-firebase-yoigo",
        NetworkRemoteConfigTemplate.model_validate(
            {
                "parameters": {
                    "rollout_key": {
                        "defaultValue": {"rolloutValue": {"rolloutId": "rollout-1"}},
                        "valueType": "BOOLEAN",
                    }
                }
            }
        ),
        "etag-1",
    )

    inventory = build_key_inventory({"mm-firebase-yoigo": template})

    profile = inventory.key_profiles["rollout_key"]
    assert profile.issues == ["unsupported_value_source"]
    assert profile.is_bulk_safe is False
    observation = profile.observations["mm-firebase-yoigo"]
    assert observation.value_sources == ["rolloutValue"]
    assert observation.unsupported_value_sources == ["rolloutValue"]
    assert observation.unsupported_value_count == 1
    assert describe_key_inventory(inventory) == [
        ["rollout_key", "1/1", "Bool", "managed value"]
    ]


def _inventory_ctx(ui_template, **data) -> WorkflowContext:
    ctx = _ctx()
    ctx.data["firebase_targets"] = [
        _target("yoigo", "mm-firebase-yoigo", environment="dev"),
        _target("guuk", "mm-guuk-firebase-prod", environment="pro"),
    ]
    ctx.data.update(data)
    ctx.firebase.get_remote_config.side_effect = [
        ClientSuccess(data=ui_template),
        ClientSuccess(data=_template_with_feature_as_string(ui_template)),
    ]
    return ctx


def test_fanout_list_keys_reads_every_project_and_reports_inventory(ui_template):
    ctx = _inventory_ctx(ui_template)

    result = execute_firebase_remoteconfig_fanout_list_keys_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_keys"] == [
        "feature_enabled",
        "legacy_untyped",
        "welcome_text",
    ]
    assert result.metadata["firebase_remoteconfig_common_keys"] == [
        "feature_enabled",
        "welcome_text",
    ]
    assert result.metadata["firebase_remoteconfig_missing_keys"] == {
        "mm-firebase-yoigo": [],
        "mm-guuk-firebase-prod": ["legacy_untyped"],
    }
    assert result.metadata["firebase_remoteconfig_type_conflicts"] == {
        "feature_enabled": ["BOOLEAN", "STRING"],
    }
    assert result.metadata["firebase_remoteconfig_bulk_safe_keys"] == [
        "welcome_text",
    ]
    assert result.metadata["firebase_remoteconfig_bulk_blocked_keys"] == {
        "feature_enabled": ["type_conflict"],
        "legacy_untyped": ["missing"],
    }
    assert result.metadata["firebase_remoteconfig_key_profiles"]["welcome_text"] == {
        "key": "welcome_text",
        "bulk_safe": True,
        "bulk_value_type": "STRING",
        "issues": [],
        "present_projects": ["mm-firebase-yoigo", "mm-guuk-firebase-prod"],
        "missing_projects": [],
        "value_types": ["STRING"],
        "declared_value_types": ["STRING"],
        "inferred_value_types": ["STRING"],
        "observations": {
            "mm-firebase-yoigo": {
                "project_id": "mm-firebase-yoigo",
                "key": "welcome_text",
                "declared_type": "STRING",
                "inferred_types": ["STRING"],
                "effective_type": "STRING",
                "decision": "declared",
                "value_count": 1,
                "conditional_value_count": 0,
                "value_sources": ["value"],
                "unsupported_value_sources": [],
                "unsupported_value_count": 0,
                "local_type_conflict": False,
            },
            "mm-guuk-firebase-prod": {
                "project_id": "mm-guuk-firebase-prod",
                "key": "welcome_text",
                "declared_type": "STRING",
                "inferred_types": ["STRING"],
                "effective_type": "STRING",
                "decision": "declared",
                "value_count": 1,
                "conditional_value_count": 0,
                "value_sources": ["value"],
                "unsupported_value_sources": [],
                "unsupported_value_count": 0,
                "local_type_conflict": False,
            },
        },
    }
    assert result.metadata["firebase_remoteconfig_project_key_values"][
        "mm-firebase-yoigo"
    ]["feature_enabled"] == {
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
    assert result.metadata["firebase_remoteconfig_value_types"] == [
        "BOOLEAN",
        "JSON",
        "STRING",
    ]
    assert [call.args[0] for call in ctx.firebase.get_remote_config.call_args_list] == [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
    ]
    ctx.textual.table.assert_not_called()
    ctx.textual.dim_text.assert_any_call(
        "2/2 proyectos leidos · 3 claves unicas · 2 comunes · "
        "1 conflicto de tipo"
    )
    ctx.textual.dim_text.assert_any_call("Claves y valores")
    ctx.textual.collapsible_list.assert_called_once()
    value_entries = ctx.textual.collapsible_list.call_args.args[0]
    assert len(value_entries) == 3
    assert value_entries[0].title == "feature_enabled  [Bool / String]"
    assert value_entries[0].right == "2/2 · conflicto de tipo"
    assert value_entries[0].style == "warning"
    assert value_entries[0].body[0] == "Kill switch"
    assert isinstance(value_entries[0].body[1], Table)
    assert value_entries[0].body[1].flex_column == 3
    assert value_entries[0].body[1].headers == [
        "Marca",
        "Entorno",
        "Condicion",
        "Valor",
        "Origen",
        "Editable",
    ]
    assert value_entries[0].body[1].rows == [
        ["yoigo", "DEV", "default", "false", "Literal", "si"],
        ["", "", "android_prod", "true", "Literal", "si"],
        ["guuk", "PRO", "default", "false", "Literal", "si"],
        ["", "", "android_prod", "true", "Literal", "si"],
    ]
    assert value_entries[1].title == "legacy_untyped  [JSON]"
    assert value_entries[1].right == "1/2 · falta en 1"
    assert value_entries[1].children[0].title == "yoigo · default"
    assert isinstance(value_entries[1].children[0].body[0], Text)
    assert value_entries[1].children[0].body[0].plain == "a  1"


def test_fanout_list_keys_applies_condition_group_view(ui_template):
    ctx = _inventory_ctx(ui_template, condition_group="android")
    ctx.firebase.config = FirebasePluginConfig(
        condition_groups={
            "android": {
                "label": "Android",
                "condition_contains": ["android"],
            }
        }
    )

    result = execute_firebase_remoteconfig_fanout_list_keys_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_condition_group"] == "android"
    assert result.metadata["firebase_condition_group_label"] == "Android"
    value_entries = ctx.textual.collapsible_list.call_args.args[0]
    assert value_entries[0].title == "feature_enabled  [Bool / String]"
    assert value_entries[0].body[1].rows == [
        ["yoigo", "DEV", "default", "false", "Literal", "si"],
        ["", "", "android_prod", "true", "Literal", "si"],
        ["guuk", "PRO", "default", "false", "Literal", "si"],
        ["", "", "android_prod", "true", "Literal", "si"],
    ]
    ctx.textual.dim_text.assert_any_call("Vista de valores: Android")


def test_fanout_list_keys_rejects_unknown_condition_group(ui_template):
    ctx = _inventory_ctx(ui_template, condition_group="android")
    ctx.firebase.config = FirebasePluginConfig(
        condition_groups={
            "ios": {
                "label": "iOS",
                "condition_contains": ["ios"],
            }
        }
    )

    result = execute_firebase_remoteconfig_fanout_list_keys_step(ctx)

    assert isinstance(result, Error)
    assert "agrupacion de condiciones" in result.message


def test_fanout_list_keys_keeps_partial_read_failures(ui_template):
    ctx = _ctx()
    ctx.data["firebase_targets"] = [
        _target("yoigo", "mm-firebase-yoigo"),
        _target("guuk", "mm-guuk-firebase-prod"),
    ]
    ctx.firebase.get_remote_config.side_effect = [
        ClientError(error_message="403", error_code="PERMISSION_DENIED"),
        ClientSuccess(data=ui_template),
    ]

    result = execute_firebase_remoteconfig_fanout_list_keys_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_failed_projects"] == {
        "mm-firebase-yoigo": "403",
    }
    assert result.metadata["firebase_remoteconfig_project_key_counts"] == {
        "mm-guuk-firebase-prod": 3,
    }
    ctx.textual.warning_text.assert_called_once()
    assert ctx.textual.table.call_args.kwargs["title"] == "Estado de lectura"
    entries = ctx.textual.collapsible_list.call_args.args[0]
    assert entries[0].right == "1/2 · 1 sin leer"
    assert entries[0].body[-1].rows[0] == [
        "yoigo",
        "—",
        "—",
        "No leido",
        "—",
        "—",
    ]


def test_fanout_list_keys_errors_when_every_read_fails():
    ctx = _ctx()
    ctx.data["firebase_targets"] = [
        _target("yoigo", "mm-firebase-yoigo"),
        _target("guuk", "mm-guuk-firebase-prod"),
    ]
    ctx.firebase.get_remote_config.return_value = ClientError(
        error_message="403",
        error_code="PERMISSION_DENIED",
    )

    result = execute_firebase_remoteconfig_fanout_list_keys_step(ctx)

    assert isinstance(result, Error)
    assert "ningun proyecto" in result.message


def test_fanout_list_keys_requires_targets():
    ctx = _ctx()

    result = execute_firebase_remoteconfig_fanout_list_keys_step(ctx)

    assert isinstance(result, Error)
    assert "firebase_select_targets" in result.message


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


def test_plan_validates_every_project_independently():
    ctx = _plan_ctx()
    ctx.firebase.validate_remote_config_change.side_effect = [
        ClientSuccess(data=_change()),
        ClientError(
            error_message="no existe la clave", error_code="TEMPLATE_EDIT_ERROR"
        ),
    ]
    ctx.textual.ask_multiselect.return_value = ["mm-firebase-yoigo"]

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Success)
    assert [
        entry.target.label for entry in result.metadata["firebase_fanout_plan"]
    ] == ["yoigo"]
    # The project that cannot take the change is kept in the report, not dropped.
    assert any(
        entry.status == "error" for entry in result.metadata["firebase_fanout_rejected"]
    )


def test_plan_exits_when_no_project_needs_the_change():
    ctx = _plan_ctx()
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change(new_value="false")
    )

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Exit)
    ctx.textual.ask_multiselect.assert_not_called()


def test_plan_exits_when_the_user_selects_no_project():
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


def test_plan_allows_mixed_known_environments_with_project_confirmation():
    ctx = _plan_ctx()
    ctx.data["firebase_targets"] = [
        _target("yoigo-dev", "mm-firebase-yoigo-dev", environment="dev"),
        _target("yoigo-pro", "mm-firebase-yoigo-pro", environment="pro"),
    ]
    ctx.firebase.validate_remote_config_change.side_effect = [
        ClientSuccess(data=_change()),
        ClientSuccess(data=_change()),
    ]
    ctx.textual.ask_multiselect.return_value = [
        "mm-firebase-yoigo-dev",
        "mm-firebase-yoigo-pro",
    ]

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Success)
    assert [
        call.args[0]
        for call in ctx.firebase.validate_remote_config_change.call_args_list
    ] == ["mm-firebase-yoigo-dev", "mm-firebase-yoigo-pro"]
    assert [
        entry.target.environment
        for entry in result.metadata["firebase_fanout_plan"]
    ] == ["dev", "pro"]


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


def test_plan_rejects_a_key_blocked_by_the_inventory():
    ctx = _plan_ctx(key="feature_enabled", value="true")
    ctx.data["firebase_remoteconfig_key_profiles"] = {
        "feature_enabled": {
            "bulk_safe": False,
            "issues": ["type_conflict"],
            "value_types": ["BOOLEAN", "STRING"],
            "missing_projects": [],
        }
    }
    ctx.data["firebase_remoteconfig_failed_projects"] = {}

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Error)
    assert "no es apta para bulk" in result.message
    assert "Bool / String" in result.message
    ctx.firebase.validate_remote_config_change.assert_not_called()


def test_plan_rejects_bulk_when_the_inventory_had_read_failures():
    ctx = _plan_ctx(key="welcome_text", value="hola")
    ctx.data["firebase_remoteconfig_key_profiles"] = {
        "welcome_text": {"bulk_safe": True}
    }
    ctx.data["firebase_remoteconfig_failed_projects"] = {"mm-guuk-firebase-prod": "403"}

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Error)
    assert "no pudo leer todos los proyectos" in result.message
    ctx.firebase.validate_remote_config_change.assert_not_called()


def test_plan_prompts_only_for_bulk_safe_keys_when_inventory_exists(ui_template):
    ctx = _plan_ctx(key="", value="", condition="")
    ctx.data["firebase_remoteconfig_key_profiles"] = {
        "welcome_text": {"bulk_safe": True},
        "feature_enabled": {
            "bulk_safe": False,
            "issues": ["type_conflict"],
            "value_types": ["BOOLEAN", "STRING"],
        },
    }
    ctx.data["firebase_remoteconfig_bulk_safe_keys"] = ["welcome_text"]
    ctx.data["firebase_remoteconfig_failed_projects"] = {}
    ctx.firebase.get_remote_config.return_value = ClientSuccess(data=ui_template)
    ctx.firebase.validate_remote_config_change.return_value = ClientSuccess(
        data=_change()
    )
    ctx.textual.ask_option.side_effect = ["__default__", "welcome_text"]
    ctx.textual.ask_text.return_value = "hola nueva"
    ctx.textual.ask_multiselect.return_value = [
        "mm-firebase-yoigo",
        "mm-guuk-firebase-prod",
    ]

    result = execute_firebase_remoteconfig_fanout_plan_step(ctx)

    assert isinstance(result, Success)
    assert [
        call.args[:4]
        for call in ctx.firebase.validate_remote_config_change.call_args_list
    ] == [
        ("mm-firebase-yoigo", "welcome_text", "hola nueva", None),
        ("mm-guuk-firebase-prod", "welcome_text", "hola nueva", None),
    ]
    parameter_options = ctx.textual.ask_option.call_args_list[1].args[1]
    assert [option.value for option in parameter_options] == ["welcome_text"]


# --- publish ----------------------------------------------------------------


def _publish_ctx(**data) -> WorkflowContext:
    ctx = _ctx()
    ctx.data["firebase_fanout_plan"] = [
        UIFanoutEntry(target=_target("yoigo", "mm-firebase-yoigo"), change=_change()),
        UIFanoutEntry(
            target=_target("guuk", "mm-guuk-firebase-prod"), change=_change()
        ),
    ]
    ctx.data.update(data)
    return ctx


def test_publish_continues_after_one_project_fails():
    ctx = _publish_ctx()
    ctx.firebase.publish_remote_config_change.side_effect = [
        ClientSuccess(data=_published()),  # yoigo validation
        ClientSuccess(data=_published()),  # yoigo publish
        ClientSuccess(data=_published()),  # guuk validation
        ClientError(error_message="403", error_code="PERMISSION_DENIED"),
    ]

    result = execute_firebase_remoteconfig_fanout_publish_step(ctx)

    # Nine good publishes must not be lost because the tenth project denies it.
    assert isinstance(result, Success)
    assert result.metadata["firebase_fanout_published"] == 1
    assert result.metadata["firebase_fanout_failed"] == 1
    outcomes = result.metadata["firebase_fanout_outcomes"]
    assert [outcome.succeeded for outcome in outcomes] == [True, False]


def test_publish_validates_each_project_before_writing_it():
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


def test_publish_skips_a_project_whose_validation_fails():
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
    # Three calls, not four: the failed project was never published.
    assert ctx.firebase.publish_remote_config_change.call_count == 3


def test_publish_fails_when_every_project_fails():
    ctx = _publish_ctx()
    ctx.firebase.publish_remote_config_change.return_value = ClientError(
        error_message="403", error_code="PERMISSION_DENIED"
    )

    result = execute_firebase_remoteconfig_fanout_publish_step(ctx)

    assert isinstance(result, Error)
    assert "0 proyectos publicados" in result.message


def test_dry_run_publishes_nothing():
    ctx = _publish_ctx(dry_run=True)
    ctx.firebase.publish_remote_config_change.return_value = ClientSuccess(
        data=_published()
    )

    result = execute_firebase_remoteconfig_fanout_publish_step(ctx)

    assert isinstance(result, Success)
    assert "validados" in result.message
    flags = [
        call.kwargs["validate_only"]
        for call in ctx.firebase.publish_remote_config_change.call_args_list
    ]
    assert flags == [True, True]


def test_publish_requires_a_plan():
    result = execute_firebase_remoteconfig_fanout_publish_step(_ctx())

    assert isinstance(result, Error)
    assert "firebase_remoteconfig_fanout_plan" in result.message
