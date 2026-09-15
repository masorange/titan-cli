"""Validate one change against every selected project and pick which get it."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Optional

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import SelectionOption

from ..models.view import UIFanoutEntry
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

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): From firebase_select_targets.
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

    key = blank_to_none(ctx.get("key")) or blank_to_none(ctx.get("firebase_key"))
    value = blank_to_none(ctx.get("value")) or blank_to_none(
        ctx.get("firebase_new_value")
    )
    condition = blank_to_none(ctx.get("condition")) or blank_to_none(
        ctx.get("firebase_condition")
    )

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

    parameter = (
        template.parameter(key) if key else ask_parameter(ctx, template, condition)
    )
    if parameter is None:
        return (
            f"El parámetro '{key}' no existe en {template.project_id}"
            if key
            else "No se seleccionó ningún parámetro"
        )

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


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
