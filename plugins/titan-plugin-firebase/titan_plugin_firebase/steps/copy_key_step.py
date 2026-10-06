"""Plan copying one missing Remote Config key to selected projects."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import OptionItem, SelectionOption

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
    target_map,
    targets_for_project_ids,
)
from ..operations.target_operations import parse_project_ids
from .prompts import blank_to_none


def execute_firebase_remoteconfig_copy_key_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Choose one missing Remote Config key and plan where to create it.

    Uses the deterministic inventory from `firebase_remoteconfig_fanout_list_keys`
    to find keys that exist in at least one selected project and are missing
    from at least one other selected project. The selected source key is copied
    as a full parameter payload; existing target keys are not overwritten.
    Source values managed by Firebase personalization, experiments, rollouts,
    or unknown future value-source fields are rejected.
    Targets may span several configured environments when the selection step
    has explicitly included them; publishing remains per project.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): From firebase_select_targets.
        firebase_remoteconfig_key_profiles (dict[str, dict]): From firebase_remoteconfig_fanout_list_keys.
        firebase_remoteconfig_failed_projects (dict[str, str], optional): From firebase_remoteconfig_fanout_list_keys.
        key (str, optional): Key to copy.
        firebase_key (str, optional): Key to copy, as emitted by an earlier step.
        source_project_id (str, optional): Project to copy the key from.
        firebase_source_project_id (str, optional): Source project emitted by an earlier step.
        target_project_ids (str | list[str], optional): Missing target projects to create the key in.
        firebase_target_project_ids (str | list[str], optional): Target projects emitted by an earlier step.

    Outputs (saved to ctx.data):
        firebase_key (str): Key selected for copying.
        firebase_copy_source_project_id (str): Project used as the source.
        firebase_copy_plan (list[UIRemoteConfigKeyCopyPlanEntry]): Entries selected for publishing.
        firebase_copy_rejected (list[UIRemoteConfigKeyCopyPlanEntry]): Missing destinations left out.

    Returns:
        Success: If at least one missing target is selected.
        Exit: If there are no missing keys or no selected destinations.
        Error: If inventory, source, or target inputs are invalid.
    """
    if ctx.textual:
        ctx.textual.begin_step("Planificar copia de clave")

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

    key = blank_to_none(ctx.get("key")) or blank_to_none(ctx.get("firebase_key"))
    if key is None:
        selected_key = _ask_key(ctx, profiles)
        if isinstance(selected_key, (Error, Exit)):
            return selected_key
        key = selected_key

    profile = profiles.get(key)
    if not isinstance(profile, Mapping):
        return _fail(ctx, f"La clave '{key}' no aparece en el inventario.")

    missing_targets = targets_for_project_ids(
        targets,
        _profile_list(profile, "missing_projects"),
    )
    if not missing_targets:
        return _exit(ctx, f"La clave '{key}' ya existe en todos los proyectos leídos.")

    source = _resolve_source(ctx, targets, profile)
    if isinstance(source, (Error, Exit)):
        return source

    source_type = source_value_type(profile, source.project_id)
    if source_type == RemoteConfigValueType.UNKNOWN or source_has_local_type_conflict(
        profile, source.project_id
    ):
        return _fail(
            ctx,
            f"La clave '{key}' no tiene un tipo determinista en "
            f"{source.reference()}. Revísala manualmente antes de copiarla.",
        )
    if source_has_unsupported_value_source(profile, source.project_id):
        return _fail(
            ctx,
            f"La clave '{key}' contiene valores gestionados por Firebase en "
            f"{source.reference()}. Titan no la copia hasta que exista soporte "
            "explícito para ese origen.",
        )

    planned = build_key_copy_plan(
        key=key,
        source=source,
        destinations=missing_targets,
        value_type=source_type,
    )
    chosen = _choose_destinations(ctx, planned)
    if isinstance(chosen, (Error, Exit)):
        return chosen

    rejected = [entry for entry in planned if entry not in chosen]
    if ctx.textual:
        ctx.textual.table(
            headers=["Proyecto destino", "Clave", "Tipo", "Origen"],
            rows=describe_key_copy_plan(chosen),
            title=f"Copia de {key}",
            flex_column=0,
        )
        ctx.textual.end_step("success")

    return Success(
        f"{len(chosen)} proyectos listos para crear {key}",
        metadata={
            "firebase_key": key,
            "firebase_copy_source_project_id": source.project_id,
            "firebase_copy_plan": chosen,
            "firebase_copy_rejected": rejected,
        },
    )


def _ask_key(
    ctx: WorkflowContext,
    profiles: Mapping[str, Mapping[str, Any]],
) -> str | WorkflowResult:
    """Ask which missing key should be copied."""
    candidates = copyable_key_names(profiles)
    if not candidates:
        return _exit(ctx, "No hay claves faltantes que copiar.")
    if not ctx.textual:
        return _fail(ctx, "Falta key. Pásala como parámetro del workflow.")

    selected = ctx.textual.ask_option(
        "¿Qué clave quieres copiar?",
        [
            OptionItem(
                value=key,
                title=key,
                description=describe_copy_candidate(profiles[key]),
            )
            for key in candidates
        ],
    )
    if selected is None:
        return _exit(ctx, "No se seleccionó ninguna clave.")
    return str(selected)


def _resolve_source(
    ctx: WorkflowContext,
    targets,
    profile: Mapping[str, Any],
):
    """Resolve the source project for the copy."""
    source_id = blank_to_none(ctx.get("source_project_id")) or blank_to_none(
        ctx.get("firebase_source_project_id")
    )
    present_ids = _profile_list(profile, "present_projects")
    present_targets = targets_for_project_ids(targets, present_ids)
    by_id = target_map(present_targets)

    if source_id is not None:
        source = by_id.get(source_id)
        if source is None:
            return _fail(
                ctx,
                f"El proyecto origen '{source_id}' no contiene la clave seleccionada.",
            )
        return source

    if len(present_targets) == 1:
        return present_targets[0]

    if not ctx.textual:
        return _fail(
            ctx,
            "Falta source_project_id. Hay varios proyectos origen posibles.",
        )

    selected = ctx.textual.ask_option(
        "¿Desde qué proyecto copiamos la clave?",
        [
            OptionItem(
                value=target.project_id,
                title=target.reference(),
                description=(
                    f"tipo {source_value_type(profile, target.project_id).display_label}"
                ),
            )
            for target in present_targets
        ],
    )
    if selected is None:
        return _exit(ctx, "No se seleccionó ningún proyecto origen.")
    source = by_id.get(str(selected))
    if source is None:
        return _fail(ctx, f"El proyecto origen '{selected}' no es válido.")
    return source


def _choose_destinations(
    ctx: WorkflowContext,
    entries,
):
    """Choose which missing projects will receive the copied key."""
    requested_ids = _requested_target_ids(ctx)
    if requested_ids:
        invalid_ids = sorted(
            set(requested_ids) - {entry.target.project_id for entry in entries}
        )
        if invalid_ids:
            return _fail(
                ctx,
                "Los proyectos destino no son proyectos donde falte la clave: "
                f"{', '.join(invalid_ids)}.",
            )
        chosen = select_key_copy_entries(entries, requested_ids)
    else:
        if not ctx.textual:
            return _fail(
                ctx,
                "Falta target_project_ids. Pásalos para confirmar destinos sin TUI.",
            )
        selected = ctx.textual.ask_multiselect(
            "¿En qué proyectos creamos la clave?",
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
        return _exit(ctx, "No se seleccionó ningún proyecto destino.")
    return chosen


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
    """Reject copy planning when an earlier inventory missed a project."""
    failed_projects = ctx.get("firebase_remoteconfig_failed_projects") or {}
    if not failed_projects:
        return None
    failed_ids = ", ".join(str(project_id) for project_id in sorted(failed_projects))
    return (
        "No se puede planificar la copia porque el inventario no pudo leer "
        f"todos los proyectos: {failed_ids}."
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
