"""Plan copying several missing Remote Config keys across projects."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import SelectionOption

from ..models.values import RemoteConfigValueType
from ..operations.sync_key_operations import (
    build_key_copy_plan,
    copyable_key_names,
    describe_copy_candidate,
    describe_key_copy_plan,
    select_key_copy_entries,
    source_has_local_type_conflict,
    source_has_unsupported_value_source,
    source_value_type,
    targets_for_project_ids,
)
from ..operations.target_operations import parse_project_ids
from .prompts import blank_to_none


def execute_firebase_remoteconfig_sync_plan_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Build a plan to create several missing Remote Config keys.

    This is the multi-key counterpart of `firebase_remoteconfig_copy_key`.
    It uses the deterministic key inventory to find keys that are missing from
    at least one selected project, selects only keys with a deterministic
    source project, and emits a copy plan consumed by
    `firebase_remoteconfig_sync_publish`. Keys whose source values are managed
    by Firebase personalization, experiments, rollouts, or unknown future
    value-source fields are left out.
    Targets may span several configured environments when the selection step
    has explicitly included them; publishing remains per project.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): From firebase_select_targets.
        firebase_remoteconfig_key_profiles (dict[str, dict]): From firebase_remoteconfig_fanout_list_keys.
        firebase_remoteconfig_failed_projects (dict[str, str], optional): From firebase_remoteconfig_fanout_list_keys.
        keys (str | list[str], optional): Keys to synchronize.
        firebase_keys (str | list[str], optional): Keys emitted by an earlier step.
        source_project_id (str, optional): Source project used for every selected key when it contains it.
        firebase_source_project_id (str, optional): Source project emitted by an earlier step.
        target_project_ids (str | list[str], optional): Missing target projects to create keys in.
        firebase_target_project_ids (str | list[str], optional): Target projects emitted by an earlier step.

    Outputs (saved to ctx.data):
        firebase_copy_plan (list[UIRemoteConfigKeyCopyPlanEntry]): Entries selected for publishing.
        firebase_sync_keys (list[str]): Keys selected for synchronization.
        firebase_sync_rejected_keys (dict[str, str]): Candidate keys skipped and why.

    Returns:
        Success: If at least one copy entry is planned.
        Exit: If there are no syncable missing keys or no selected destinations.
        Error: If inventory, source, or target inputs are invalid.
    """
    if ctx.textual:
        ctx.textual.begin_step("Planificar sincronización de claves")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    targets = ctx.get("firebase_targets")
    if not targets:
        return _fail(
            ctx,
            "Faltan los proyectos. Ejecuta firebase_select_targets antes de este paso.",
        )

    inventory_error = _inventory_error(ctx)
    if inventory_error is not None:
        return _fail(ctx, inventory_error)

    profiles = ctx.get("firebase_remoteconfig_key_profiles")
    if not isinstance(profiles, Mapping):
        return _fail(
            ctx,
            "Falta el inventario de claves. Ejecuta "
            "firebase_remoteconfig_fanout_list_keys antes de este paso.",
        )

    preferred_source_id = blank_to_none(ctx.get("source_project_id")) or blank_to_none(
        ctx.get("firebase_source_project_id")
    )
    candidates, rejected = _sync_candidates(profiles, targets, preferred_source_id)
    requested_keys = _requested_keys(ctx)
    if requested_keys:
        invalid = sorted(set(requested_keys) - set(candidates))
        if invalid:
            details = ", ".join(
                f"{key} ({rejected.get(key, 'no sincronizable')})" for key in invalid
            )
            return _fail(
                ctx,
                "Estas claves no son sincronizables con el inventario actual: "
                f"{details}.",
            )
        selected_keys = requested_keys
    else:
        if not candidates:
            return _exit(ctx, "No hay claves faltantes con origen determinista.")
        selected_keys = _ask_keys(ctx, profiles, candidates)
        if isinstance(selected_keys, (Error, Exit)):
            return selected_keys

    requested_target_ids = _requested_target_ids(ctx)
    plan = []
    for key in selected_keys:
        profile = profiles[key]
        source = _source_for_profile(profile, targets, preferred_source_id)
        if source is None:
            rejected[key] = "origen ambiguo"
            continue
        value_type = source_value_type(profile, source.project_id)
        destinations = targets_for_project_ids(
            targets,
            _profile_list(profile, "missing_projects"),
        )
        entries = build_key_copy_plan(
            key=key,
            source=source,
            destinations=destinations,
            value_type=value_type,
        )
        chosen = _choose_destinations(ctx, key, entries, requested_target_ids)
        if isinstance(chosen, (Error, Exit)):
            return chosen
        plan.extend(chosen)

    if not plan:
        return _exit(ctx, "No se seleccionó ningún destino para sincronizar.")

    if ctx.textual:
        ctx.textual.table(
            headers=["Proyecto destino", "Clave", "Tipo", "Origen"],
            rows=describe_key_copy_plan(plan),
            title="Plan de sincronización",
            flex_column=0,
        )
        if rejected:
            ctx.textual.dim_text(
                f"{len(rejected)} clave(s) quedan fuera por requerir revisión."
            )
        ctx.textual.end_step("success")

    return Success(
        f"{len(plan)} copias de claves listas para publicar",
        metadata={
            "firebase_copy_plan": plan,
            "firebase_sync_keys": selected_keys,
            "firebase_sync_rejected_keys": rejected,
        },
    )


def _sync_candidates(
    profiles: Mapping[str, Mapping[str, Any]],
    targets,
    preferred_source_id: Optional[str],
) -> tuple[list[str], dict[str, str]]:
    """Return copyable keys that have a deterministic source."""
    candidates: list[str] = []
    rejected: dict[str, str] = {}
    for key in copyable_key_names(profiles):
        profile = profiles[key]
        source = _source_for_profile(profile, targets, preferred_source_id)
        if source is None:
            rejected[key] = "varios orígenes posibles"
            continue
        value_type = source_value_type(profile, source.project_id)
        if (
            value_type == RemoteConfigValueType.UNKNOWN
            or source_has_local_type_conflict(profile, source.project_id)
        ):
            rejected[key] = "tipo de origen no determinista"
            continue
        if source_has_unsupported_value_source(profile, source.project_id):
            rejected[key] = "origen gestionado por Firebase"
            continue
        candidates.append(key)
    return candidates, rejected


def _source_for_profile(
    profile: Mapping[str, Any],
    targets,
    preferred_source_id: Optional[str],
):
    """Resolve a deterministic source for one key profile."""
    present_targets = targets_for_project_ids(
        targets,
        _profile_list(profile, "present_projects"),
    )
    if preferred_source_id is not None:
        for target in present_targets:
            if target.project_id == preferred_source_id:
                return target
        return None
    if len(present_targets) == 1:
        return present_targets[0]
    return None


def _ask_keys(
    ctx: WorkflowContext,
    profiles: Mapping[str, Mapping[str, Any]],
    candidates: list[str],
) -> list[str] | WorkflowResult:
    """Ask which syncable keys should be created."""
    if not ctx.textual:
        return _fail(ctx, "Faltan keys. Pásalas como parámetro del workflow.")
    selected = ctx.textual.ask_multiselect(
        "¿Qué claves sincronizamos?",
        [
            SelectionOption(
                value=key,
                label=f"{key} · {describe_copy_candidate(profiles[key])}",
                selected=False,
            )
            for key in candidates
        ],
    )
    if not selected:
        return _exit(ctx, "No se seleccionó ninguna clave.")
    return [str(key) for key in selected]


def _choose_destinations(
    ctx: WorkflowContext,
    key: str,
    entries,
    requested_target_ids: list[str],
):
    """Choose destinations for one key."""
    if requested_target_ids:
        invalid = sorted(
            set(requested_target_ids) - {entry.target.project_id for entry in entries}
        )
        if invalid:
            return _fail(
                ctx,
                f"Para {key}, estos destinos no son proyectos donde falte "
                f"la clave: {', '.join(invalid)}.",
            )
        chosen = select_key_copy_entries(entries, requested_target_ids)
    else:
        if not ctx.textual:
            return _fail(
                ctx,
                "Falta target_project_ids. Pásalos para confirmar destinos sin TUI.",
            )
        selected = ctx.textual.ask_multiselect(
            f"¿Dónde creamos {key}?",
            [
                SelectionOption(
                    value=entry.target.project_id,
                    label=f"{entry.target.reference()} · {entry.detail}",
                    selected=False,
                )
                for entry in entries
            ],
        )
        chosen = select_key_copy_entries(
            entries, [str(value) for value in selected or []]
        )
    if not chosen:
        return _exit(ctx, f"No se seleccionó ningún destino para {key}.")
    return chosen


def _requested_keys(ctx: WorkflowContext) -> list[str]:
    """Read optional explicit key names."""
    raw = ctx.get("keys")
    if raw is None:
        raw = ctx.get("firebase_keys")
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        values = str(raw).replace("\n", ",").split(",")
    seen: set[str] = set()
    keys: list[str] = []
    for value in values:
        key = str(value).strip()
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _requested_target_ids(ctx: WorkflowContext) -> list[str]:
    """Read optional explicit target IDs."""
    raw = ctx.get("target_project_ids")
    if raw is None:
        raw = ctx.get("firebase_target_project_ids")
    return parse_project_ids(raw)


def _profile_list(profile: Mapping[str, Any], key: str) -> list[str]:
    """Return a profile list field as strings."""
    value = profile.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _inventory_error(ctx: WorkflowContext) -> Optional[str]:
    """Reject sync planning when an earlier inventory missed a project."""
    failed_projects = ctx.get("firebase_remoteconfig_failed_projects") or {}
    if not failed_projects:
        return None
    failed_ids = ", ".join(str(project_id) for project_id in sorted(failed_projects))
    return (
        "No se puede planificar la sincronización porque el inventario no pudo "
        f"leer todos los proyectos: {failed_ids}."
    )


def _exit(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report a controlled workflow exit."""
    if ctx.textual:
        ctx.textual.warning_text(message)
        ctx.textual.end_step("skipped")
    return Exit(message)


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
