"""Validate one change against every selected project and pick which get it."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from typing import Any, Mapping, Optional

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import SelectionOption

from ..models.view import UIFanoutEntry
from ..models.values import display_value_types
from ..operations.fanout_operations import (
    describe_plan,
    plan_summary,
    publishable_entries,
    select_entries,
)
from .prompts import (
    ask_condition,
    ask_parameter,
    ask_value,
    blank_to_none,
    display_for_target,
)


def execute_firebase_remoteconfig_fanout_plan_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Build the per-project plan for one parameter change.

    Every project has its own template, so the change is validated against
    each one: the parameter may not exist there, the condition may not either,
    and the value may clash with a different declared type. Projects that
    cannot take the change are reported, not allowed to sink the rest.
    Values managed by Firebase personalization, experiments, rollouts, or
    unknown future value-source fields are not bulk-editable.
    Targets may span several configured environments when the selection step
    has explicitly included them; publishing remains per project.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): From firebase_select_targets.
        firebase_remoteconfig_key_profiles (dict[str, dict], optional): From firebase_remoteconfig_fanout_list_keys.
        firebase_remoteconfig_bulk_safe_keys (list[str], optional): From firebase_remoteconfig_fanout_list_keys.
        firebase_remoteconfig_failed_projects (dict[str, str], optional): From firebase_remoteconfig_fanout_list_keys.
        key (str): Parameter to change.
        value (str): New value.
        condition (str, optional): Condition to write instead of the default.

    Outputs (saved to ctx.data):
        firebase_fanout_plan (list[UIFanoutEntry]): Entries chosen to publish.
        firebase_fanout_rejected (list[UIFanoutEntry]): Entries left out.

    Returns:
        Success: If at least one project is selected for publishing.
        Exit: If no project can take the change, or the user selects none.
        Error: If inputs are missing.
    """
    if ctx.textual:
        ctx.textual.begin_step("Planificar el cambio por proyecto")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    targets = ctx.get("firebase_targets")
    if not targets:
        return _fail(
            ctx,
            "Faltan los proyectos. Ejecuta firebase_select_targets antes de este paso.",
        )

    inventory_error = _bulk_inventory_error(ctx)
    if inventory_error is not None:
        return _fail(ctx, inventory_error)

    key = blank_to_none(ctx.get("key")) or blank_to_none(ctx.get("firebase_key"))
    value = blank_to_none(ctx.get("value")) or blank_to_none(
        ctx.get("firebase_new_value")
    )
    condition = blank_to_none(ctx.get("condition")) or blank_to_none(
        ctx.get("firebase_condition")
    )

    if key is not None:
        safety_error = _bulk_safety_error(ctx, str(key))
        if safety_error is not None:
            return _fail(ctx, safety_error)

    if key is None or value is None:
        # The parameters, their types and the conditions live in the projects,
        # so the first target's template is what the prompts are built from.
        # Every other project is validated against it afterwards.
        asked = _ask_change(ctx, targets[0], key, condition)
        if isinstance(asked, str):
            return _fail(ctx, asked)
        key, value, condition = asked
    entries = _validate_everywhere(ctx, targets, str(key), str(value), condition)

    if ctx.textual:
        ctx.textual.table(
            headers=["Proyecto", "Estado", "Cambio"],
            rows=describe_plan(entries),
            title=f"Plan para {key}",
            flex_column=2,
        )
        counts = plan_summary(entries)
        ctx.textual.dim_text(
            f"{counts['ready']} con cambio · {counts['noop']} sin cambio · "
            f"{counts['error']} con error"
        )

    ready = publishable_entries(entries)
    if not ready:
        message = f"Ningún proyecto necesita el cambio de {key}"
        if ctx.textual:
            ctx.textual.warning_text(message)
            ctx.textual.end_step("skipped")
        return Exit(message)

    chosen = _confirm_projects(ctx, ready)
    if not chosen:
        message = "No se seleccionó ningún proyecto para publicar"
        if ctx.textual:
            ctx.textual.warning_text(message)
            ctx.textual.end_step("skipped")
        return Exit(message)

    rejected = [entry for entry in entries if entry not in chosen]
    if ctx.textual:
        ctx.textual.end_step("success")

    return Success(
        f"{len(chosen)} proyectos listos para publicar",
        metadata={
            "firebase_fanout_plan": chosen,
            "firebase_fanout_rejected": rejected,
        },
    )


def _ask_change(ctx, reference_target, key, condition):
    """
    Ask for the parameter, the target value and the new value interactively.

    Returns the (key, value, condition) tuple, or an error message.
    """
    if not ctx.textual:
        return "Faltan key o value. Pásalos como parámetros del workflow."

    loading = ctx.textual.loading(
        f"Leyendo {reference_target.project_id} como referencia..."
    )
    with loading:
        result = ctx.firebase.get_remote_config(reference_target.project_id)

    match result:
        case ClientError(error_message=error_message):
            return (
                f"No se pudo leer {reference_target.project_id} como "
                f"referencia: {error_message}"
            )

    template = result.data
    if condition is None:
        condition, answered = ask_condition(ctx, template)
        if not answered:
            return "No se seleccionó ningún destino"

    prompt_template = template
    if key is None:
        bulk_safe_keys = _bulk_safe_key_set(ctx)
        if bulk_safe_keys is not None:
            safe_parameters = [
                parameter
                for parameter in template.parameters
                if parameter.key in bulk_safe_keys
            ]
            if not safe_parameters:
                return "No hay claves comunes con tipo estable para editar en bulk."
            hidden = len(template.parameters) - len(safe_parameters)
            if hidden:
                ctx.textual.dim_text(
                    f"{hidden} clave(s) ocultas porque requieren revisión por proyecto."
                )
            prompt_template = replace(template, parameters=safe_parameters)

    parameter = (
        prompt_template.parameter(key)
        if key
        else ask_parameter(ctx, prompt_template, condition)
    )
    if parameter is None:
        return (
            f"El parámetro '{key}' no existe en {template.project_id}"
            if key
            else "No se seleccionó ningún parámetro"
        )
    safety_error = _bulk_safety_error(ctx, parameter.key)
    if safety_error is not None:
        return safety_error

    current = parameter.value_for(condition)
    ctx.textual.dim_text(
        f"En {reference_target.reference()}: {display_for_target(parameter, condition)}"
    )
    value = ask_value(
        ctx,
        parameter.key,
        parameter.value_type,
        current.raw_value if current else None,
        condition,
    )
    if value is None:
        return "No se introdujo ningún valor"

    return parameter.key, value, condition


def _validate_everywhere(
    ctx: WorkflowContext,
    targets,
    key: str,
    value: str,
    condition: Optional[object],
) -> list[UIFanoutEntry]:
    """Validate the change against each target, one project at a time."""
    entries: list[UIFanoutEntry] = []
    for target in targets:
        loading = (
            ctx.textual.loading(f"Validando en {target.project_id}...")
            if ctx.textual
            else nullcontext()
        )
        with loading:
            result = ctx.firebase.validate_remote_config_change(
                target.project_id,
                key,
                value,
                str(condition) if condition else None,
            )

        match result:
            case ClientSuccess(data=change):
                entries.append(UIFanoutEntry(target=target, change=change))
            case ClientError(error_message=error_message):
                entries.append(UIFanoutEntry(target=target, error=error_message))
            case _:
                entries.append(
                    UIFanoutEntry(
                        target=target,
                        error="Respuesta inesperada al validar el cambio",
                    )
                )
    return entries


def _confirm_projects(
    ctx: WorkflowContext,
    ready: list[UIFanoutEntry],
) -> list[UIFanoutEntry]:
    """
    Confirm per project.

    A multi-select is the per-project confirmation: it names every project
    that will be written and requires a positive choice for each, instead of
    one blanket yes for ten production projects.
    """
    if not ctx.textual:
        return []

    options = [
        SelectionOption(
            value=entry.target.project_id,
            label=f"{entry.target.reference()} · {entry.detail}",
            selected=False,
        )
        for entry in ready
    ]
    selected = ctx.textual.ask_multiselect(
        "¿En qué proyectos publicas el cambio?",
        options,
    )
    return select_entries(ready, [str(value) for value in selected or []])


def _bulk_inventory_error(ctx: WorkflowContext) -> Optional[str]:
    """Reject bulk planning when an earlier inventory could not read every target."""
    if ctx.get("firebase_remoteconfig_key_profiles") is None:
        return None
    failed_projects = ctx.get("firebase_remoteconfig_failed_projects") or {}
    if not failed_projects:
        return None
    failed_ids = ", ".join(str(project_id) for project_id in sorted(failed_projects))
    return (
        "No se puede validar un cambio bulk porque el inventario no pudo leer "
        f"todos los proyectos: {failed_ids}."
    )


def _bulk_safety_error(ctx: WorkflowContext, key: str) -> Optional[str]:
    """Return why a key cannot be edited in bulk, or None when it can."""
    profiles = ctx.get("firebase_remoteconfig_key_profiles")
    if profiles is None:
        return None
    if not isinstance(profiles, Mapping):
        return "El inventario de claves tiene un formato inesperado."

    profile = profiles.get(key)
    if not isinstance(profile, Mapping):
        return (
            f"La clave '{key}' no aparece en el inventario multi-proyecto. "
            "Vuelve a listar las claves antes de publicar en bulk."
        )
    if profile.get("bulk_safe") is True:
        return None

    reasons = _bulk_blocker_reasons(profile)
    detail = ", ".join(reasons) if reasons else "requiere revisión por proyecto"
    return f"La clave '{key}' no es apta para bulk: {detail}."


def _bulk_blocker_reasons(profile: Mapping[str, Any]) -> list[str]:
    """Translate profile issue codes into user-facing reasons."""
    issues = {str(issue) for issue in profile.get("issues", []) or []}
    reasons: list[str] = []
    if "missing" in issues:
        missing = ", ".join(
            str(project_id) for project_id in profile.get("missing_projects", [])
        )
        reasons.append(f"falta en {missing}" if missing else "falta en algun proyecto")
    if "type_conflict" in issues:
        value_type_values = profile.get("value_types", [])
        if not isinstance(value_type_values, list):
            value_type_values = []
        value_types = " / ".join(display_value_types(value_type_values))
        reasons.append(
            f"tipos observados {value_types}" if value_types else "tipos incompatibles"
        )
    if "local_type_conflict" in issues:
        reasons.append("un proyecto tiene valores no tipados mezclados")
    if "unsupported_value_source" in issues:
        reasons.append("contiene valores gestionados por Firebase")
    if "unknown_type" in issues:
        reasons.append("no tiene un tipo determinista conocido")
    return reasons


def _bulk_safe_key_set(ctx: WorkflowContext) -> Optional[set[str]]:
    """Return the keys allowed by an earlier inventory, if one exists."""
    keys = ctx.get("firebase_remoteconfig_bulk_safe_keys")
    if keys is None:
        return None
    return {str(key) for key in keys if str(key).strip()}


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
