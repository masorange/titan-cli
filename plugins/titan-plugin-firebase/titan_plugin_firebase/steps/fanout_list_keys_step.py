"""Inventory Remote Config keys across several Firebase projects."""

from __future__ import annotations

from contextlib import nullcontext

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import CollapsibleEntry, Table, build_json_entry

from ..config import FirebaseConditionGroupConfig
from ..messages import msg
from ..operations.key_inventory_operations import (
    RemoteConfigKeyComparisonItem,
    build_key_inventory,
    describe_key_comparison_items,
    describe_project_inventory,
    key_profiles_to_metadata,
    project_conditions_to_metadata,
    project_key_values_to_metadata,
)


def execute_firebase_remoteconfig_fanout_list_keys_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    List and compare Remote Config parameter keys and values across projects.

    Reads every selected project's active template one by one. The inventory
    exposes common keys, missing keys per project, deterministic type profiles,
    default values, condition values, value sources, bulk-safe keys, and keys
    whose type differs between projects.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): From firebase_select_targets.
        condition_group (str, optional): Configured condition/value group to display.
        firebase_condition_group (str, optional): Same group, as emitted by earlier steps.

    Outputs (saved to ctx.data):
        firebase_remoteconfig_keys (list[str]): All keys seen in at least one project.
        firebase_remoteconfig_common_keys (list[str]): Keys present in every readable project.
        firebase_remoteconfig_missing_keys (dict[str, list[str]]): project_id to missing keys.
        firebase_remoteconfig_key_profiles (dict[str, dict]): Deterministic value-free profile per key, including value sources.
        firebase_remoteconfig_project_key_values (dict[str, dict]): project_id to key value snapshots, including value_source and editable.
        firebase_remoteconfig_project_conditions (dict[str, list[dict]]): project_id to template conditions.
        firebase_remoteconfig_bulk_safe_keys (list[str]): Keys present in every readable project with one stable known type.
        firebase_remoteconfig_bulk_blocked_keys (dict[str, list[str]]): key to blocker reasons for bulk edits.
        firebase_remoteconfig_type_conflicts (dict[str, list[str]]): key to observed effective types.
        firebase_remoteconfig_value_types (list[str]): Effective value types observed.
        firebase_remoteconfig_declared_value_types (list[str]): Declared value types observed.
        firebase_remoteconfig_unknown_type_keys (dict[str, list[str]]): project_id to keys whose effective type is UNKNOWN.
        firebase_remoteconfig_project_key_counts (dict[str, int]): project_id to key count.
        firebase_remoteconfig_failed_projects (dict[str, str]): project_id to read error.
        firebase_condition_group (str, optional): Condition group used for the value table view.
        firebase_condition_group_label (str, optional): Display label for the selected condition group.

    Returns:
        Success: If at least one project template could be read.
        Error: If the plugin is unavailable, targets are missing, or every read fails.
    """
    if ctx.textual:
        ctx.textual.begin_step(msg.Inventory.STEP_TITLE)

    if not ctx.firebase:
        return _fail(ctx, msg.Inventory.PLUGIN_UNAVAILABLE)

    targets = ctx.get("firebase_targets")
    if not targets:
        return _fail(
            ctx,
            msg.Inventory.TARGETS_REQUIRED,
        )

    templates = {}
    failed_projects: dict[str, str] = {}
    for target in targets:
        loading = (
            ctx.textual.loading(
                msg.Inventory.READING_PROJECT.format(project_id=target.project_id)
            )
            if ctx.textual
            else nullcontext()
        )
        with loading:
            result = ctx.firebase.get_remote_config(target.project_id)

        match result:
            case ClientSuccess(data=template):
                templates[target.project_id] = template
            case ClientError(error_message=error_message):
                failed_projects[target.project_id] = error_message
            case _:
                failed_projects[target.project_id] = msg.Inventory.UNEXPECTED_RESPONSE

    if not templates:
        return _fail(ctx, msg.Inventory.NO_READABLE_PROJECTS)

    inventory = build_key_inventory(templates)
    try:
        condition_group_name, condition_group = _condition_group_from_context(ctx)
    except ValueError as exc:
        return _fail(ctx, str(exc))

    if ctx.textual:
        if failed_projects:
            ctx.textual.warning_text(
                msg.Inventory.PROJECT_READ_FAILURES.format(
                    count=len(failed_projects)
                )
            )
            ctx.textual.table(
                headers=list(msg.Inventory.READ_STATUS_HEADERS),
                rows=describe_project_inventory(targets, inventory, failed_projects),
                title=msg.Inventory.READ_STATUS_TITLE,
                flex_column=0,
                show_cursor=False,
            )
        if condition_group_name and condition_group:
            ctx.textual.dim_text(
                msg.Inventory.VALUE_VIEW.format(
                    label=_condition_group_label(condition_group_name, condition_group)
                )
            )
        elif ctx.firebase.config.condition_groups:
            ctx.textual.dim_text(
                msg.Inventory.CONFIGURED_VALUE_VIEWS.format(
                    groups=", ".join(sorted(ctx.firebase.config.condition_groups))
                )
            )
        ctx.textual.dim_text(
            _inventory_summary(
                readable_projects=len(templates),
                selected_projects=len(targets),
                unique_keys=len(inventory.keys),
                common_keys=len(inventory.common_keys),
                conflict_keys=len(inventory.type_conflicts),
            )
        )
        if inventory.keys:
            comparison_items = describe_key_comparison_items(
                templates,
                targets,
                inventory,
                condition_group,
                failed_projects,
            )
            if comparison_items:
                ctx.textual.dim_text(msg.Inventory.KEYS_AND_VALUES)
                ctx.textual.collapsible_list(
                    [
                        _collapsible_key_entry(item)
                        for item in comparison_items
                    ]
                )
            else:
                ctx.textual.dim_text(msg.Inventory.NO_VALUES_IN_VIEW)
        else:
            ctx.textual.dim_text(msg.Inventory.NO_KEYS)
        if inventory.type_conflicts:
            ctx.textual.warning_text(
                msg.Inventory.TYPE_CONFLICT_WARNING.format(
                    count=len(inventory.type_conflicts)
                )
            )
        blocked_count = len(inventory.bulk_blocked_keys)
        if blocked_count:
            ctx.textual.dim_text(
                msg.Inventory.BULK_SUMMARY.format(
                    safe=len(inventory.bulk_safe_keys),
                    blocked=blocked_count,
                )
            )
        unknown_count = sum(len(keys) for keys in inventory.unknown_type_keys.values())
        if unknown_count:
            ctx.textual.warning_text(
                msg.Inventory.UNKNOWN_TYPE_WARNING.format(count=unknown_count)
            )
        ctx.textual.end_step("success")

    return Success(
        msg.Inventory.SUCCESS.format(
            unique=len(inventory.keys),
            common=len(inventory.common_keys),
            projects=inventory.project_count,
        ),
        metadata={
            "firebase_remoteconfig_keys": inventory.keys,
            "firebase_remoteconfig_common_keys": inventory.common_keys,
            "firebase_remoteconfig_missing_keys": inventory.missing_keys,
            "firebase_remoteconfig_key_profiles": key_profiles_to_metadata(
                inventory.key_profiles
            ),
            "firebase_remoteconfig_project_key_values": (
                project_key_values_to_metadata(templates)
            ),
            "firebase_remoteconfig_project_conditions": project_conditions_to_metadata(
                templates
            ),
            "firebase_remoteconfig_bulk_safe_keys": inventory.bulk_safe_keys,
            "firebase_remoteconfig_bulk_blocked_keys": inventory.bulk_blocked_keys,
            "firebase_remoteconfig_type_conflicts": inventory.type_conflicts,
            "firebase_remoteconfig_value_types": inventory.value_types,
            "firebase_remoteconfig_declared_value_types": inventory.declared_value_types,
            "firebase_remoteconfig_unknown_type_keys": _non_empty(
                inventory.unknown_type_keys
            ),
            "firebase_remoteconfig_project_key_counts": inventory.project_key_counts,
            "firebase_remoteconfig_failed_projects": failed_projects,
            **_condition_group_metadata(condition_group_name, condition_group),
        },
    )


def _non_empty(values: dict[str, list[str]]) -> dict[str, list[str]]:
    """Keep only projects that have entries to report."""
    return {key: items for key, items in values.items() if items}


def _collapsible_key_entry(
    item: RemoteConfigKeyComparisonItem,
) -> CollapsibleEntry:
    """Adapt one cross-project key comparison to Titan's collapsible list."""
    body = [
        *item.description_lines,
        Table(
            headers=list(msg.Inventory.VALUE_HEADERS),
            rows=item.value_rows,
            show_cursor=False,
            flex_column=3,
        ),
    ]
    return CollapsibleEntry(
        title=f"{item.key}  [{item.type_label}]",
        right=(
            f"{item.present_count}/{item.project_count} · {item.status_label}"
        ),
        body=body,
        children=[
            build_json_entry(detail.title, detail.value)
            for detail in item.json_details
        ],
        style="warning" if item.has_issues else None,
    )


def _inventory_summary(
    *,
    readable_projects: int,
    selected_projects: int,
    unique_keys: int,
    common_keys: int,
    conflict_keys: int,
) -> str:
    """Render the compact health summary shown before the unified key list."""
    conflict_label = (
        msg.Inventory.TYPE_CONFLICT
        if conflict_keys == 1
        else msg.Inventory.TYPE_CONFLICT_PLURAL
    )
    return msg.Inventory.SUMMARY.format(
        readable=readable_projects,
        selected=selected_projects,
        unique=unique_keys,
        common=common_keys,
        conflicts=conflict_keys,
        conflict_label=conflict_label,
    )


def _condition_group_from_context(
    ctx: WorkflowContext,
) -> tuple[str | None, FirebaseConditionGroupConfig | None]:
    """Resolve the configured condition group used to filter value display."""
    requested = (
        _text(ctx.get("condition_group"))
        or _text(ctx.get("firebase_condition_group"))
        or ctx.firebase.config.default_condition_group
    )
    if requested is None:
        return None, None

    group_name = requested.casefold()
    group = ctx.firebase.config.condition_groups.get(group_name)
    if group is None:
        available = ", ".join(sorted(ctx.firebase.config.condition_groups)) or "ninguna"
        raise ValueError(
            "No existe la agrupacion de condiciones "
            f"'{requested}'. Disponibles: {available}."
        )
    return group_name, group


def _condition_group_label(
    group_name: str,
    group: FirebaseConditionGroupConfig,
) -> str:
    """Return the human-readable condition group label."""
    return group.label or group_name


def _condition_group_metadata(
    group_name: str | None,
    group: FirebaseConditionGroupConfig | None,
) -> dict[str, object]:
    """Publish selected condition group metadata when a view is active."""
    if group_name is None or group is None:
        return {}
    return {
        "firebase_condition_group": group_name,
        "firebase_condition_group_label": _condition_group_label(group_name, group),
    }


def _text(value: object) -> str | None:
    """Normalize empty workflow params."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
