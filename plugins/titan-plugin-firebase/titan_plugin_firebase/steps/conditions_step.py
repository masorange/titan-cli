"""Pick which values of a parameter a change will write."""

from __future__ import annotations

from typing import Optional

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import SelectionOption

from .prompts import DEFAULT_TARGET, condition_option_label, normalize_target


def execute_firebase_remoteconfig_conditions_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Choose the targets a write will touch: the default value, conditions, or both.

    Remote Config has no "environment" concept of its own: conditions are where
    a project models audiences, platforms and environments, so they are read
    from the template rather than configured by hand. Several can be chosen at
    once, and because a publish replaces the whole template they all land in a
    single Remote Config version.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_remoteconfig_template (UIRemoteConfigTemplate): From firebase_remoteconfig_get.
        condition (str, optional): Preselected target, or several separated by commas.

    Outputs (saved to ctx.data):
        firebase_conditions (list): One entry per target; None means the default value.
        firebase_conditions_label (str): User-facing description of the targets.

    Returns:
        Success: If at least one target is chosen.
        Error: If the template is missing, a named condition does not exist, or the user cancels.
    """
    if ctx.textual:
        ctx.textual.begin_step("Destinos del cambio")

    template = ctx.get("firebase_remoteconfig_template")
    if template is None:
        return _fail(
            ctx,
            "Falta la plantilla de Remote Config. Ejecuta "
            "firebase_remoteconfig_get antes de este paso.",
        )

    preselected = ctx.get("condition") or ctx.get("firebase_conditions")
    if preselected:
        targets, unknown = _from_preselection(preselected, template)
        if unknown:
            return _fail(
                ctx,
                f"Estas condiciones no existen en {template.project_id}: "
                f"{', '.join(unknown)}.",
            )
        return _success(ctx, targets)

    if not template.conditions:
        if ctx.textual:
            ctx.textual.dim_text(
                "La plantilla no define condiciones: se usará el valor por "
                "defecto."
            )
        return _success(ctx, [None])

    if not ctx.textual:
        return _success(ctx, [None])

    # A list, not a table: these expressions run to three lines each, and a
    # table of thirteen rows with uneven heights reads as merged blocks.
    options = [
        SelectionOption(
            value=DEFAULT_TARGET,
            label="Valor por defecto — se aplica si ninguna condición coincide",
            selected=False,
        )
    ]
    options.extend(
        SelectionOption(
            value=condition.name,
            label=condition_option_label(condition),
            selected=False,
        )
        for condition in template.conditions
    )

    selected = ctx.textual.ask_multiselect(
        "¿Sobre qué valores quieres escribir?",
        options,
    )
    if not selected:
        return _fail(ctx, "No se seleccionó ningún destino")

    return _success(ctx, [normalize_target(value) for value in selected])


def _from_preselection(value: object, template) -> tuple[list, list[str]]:
    """Read targets passed as a param, reporting the ones that do not exist."""
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple)):
        raw = [part if part is None else str(part).strip() for part in value]
    else:
        raw = []

    known = {condition.name for condition in template.conditions}
    targets: list[Optional[str]] = []
    unknown: list[str] = []
    for item in raw:
        target = normalize_target(item)
        if target is not None and target not in known:
            unknown.append(target)
            continue
        if target not in targets:
            targets.append(target)
    return (targets or [None]), unknown


def _success(ctx: WorkflowContext, targets: list) -> WorkflowResult:
    """Report the chosen targets."""
    labels = [target or "valor por defecto" for target in targets]
    label = ", ".join(labels)
    if ctx.textual:
        ctx.textual.text(f"Destinos: {label}")
        ctx.textual.end_step("success")
    return Success(
        f"{len(targets)} destino(s): {label}",
        metadata={
            "firebase_conditions": targets,
            "firebase_conditions_label": label,
        },
    )


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
