"""List the conditions of a template and pick the write target."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import OptionItem

# Sentinel for "the parameter's default value", which is not a condition but is
# one of the choices a write target can take.
DEFAULT_TARGET = "__default__"


def execute_firebase_remoteconfig_conditions_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Show the template's conditions and choose which value a write targets.

    Remote Config has no "environment" concept of its own: conditions are
    where a project models audiences, platforms and environments, so they are
    read from the template rather than configured by hand.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_remoteconfig_template (UIRemoteConfigTemplate): From firebase_remoteconfig_get.
        condition (str, optional): Preselected condition name, or "default".

    Outputs (saved to ctx.data):
        firebase_condition (Optional[str]): Condition name, None for the default.
        firebase_condition_label (str): User-facing label for the target.

    Returns:
        Success: If a target is chosen (or only the default exists).
        Error: If the template is missing or the user cancels.
    """
    if ctx.textual:
        ctx.textual.begin_step("Condiciones de Remote Config")

    template = ctx.get("firebase_remoteconfig_template")
    if template is None:
        message = (
            "Falta la plantilla de Remote Config. Ejecuta "
            "firebase_remoteconfig_get antes de este paso."
        )
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    if ctx.textual and template.conditions:
        ctx.textual.table(
            headers=["Condición", "Expresión", "Color"],
            rows=[
                [
                    condition.name,
                    condition.display_expression,
                    condition.tag_color or "—",
                ]
                for condition in template.conditions
            ],
            title=f"Condiciones de {template.project_id}",
            flex_column=1,
        )

    preselected = ctx.get("condition") or ctx.get("firebase_condition")
    if preselected is not None:
        condition_name = _normalize_preselection(str(preselected))
        if condition_name is not None and not any(
            condition.name == condition_name for condition in template.conditions
        ):
            message = (
                f"La condición '{condition_name}' no existe en la plantilla de "
                f"{template.project_id}."
            )
            if ctx.textual:
                ctx.textual.error_text(message)
                ctx.textual.end_step("error")
            return Error(message)
        return _success(ctx, condition_name)

    if not template.conditions:
        if ctx.textual:
            ctx.textual.dim_text(
                "La plantilla no define condiciones: se usará el valor por defecto."
            )
        return _success(ctx, None)

    if not ctx.textual:
        return _success(ctx, None)

    options = [
        OptionItem(
            value=DEFAULT_TARGET,
            title="Valor por defecto",
            description="Se aplica cuando ninguna condición coincide",
        )
    ]
    options.extend(
        OptionItem(
            value=condition.name,
            title=condition.name,
            description=condition.display_expression,
        )
        for condition in template.conditions
    )

    selected = ctx.textual.ask_option(
        "¿Sobre qué valor quieres trabajar?",
        options,
    )
    if selected is None:
        message = "No se seleccionó ningún destino"
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
        return Error(message)

    return _success(ctx, None if selected == DEFAULT_TARGET else str(selected))


def _normalize_preselection(value: str) -> str | None:
    """Map the textual forms of "the default value" to None."""
    normalized = value.strip()
    if not normalized or normalized.lower() in {
        "default",
        "defaultvalue",
        DEFAULT_TARGET,
    }:
        return None
    return normalized


def _success(ctx: WorkflowContext, condition_name: str | None) -> WorkflowResult:
    """Report the chosen write target."""
    label = condition_name or "valor por defecto"
    if ctx.textual:
        ctx.textual.text(f"Destino: {label}")
        ctx.textual.end_step("success")
    return Success(
        f"Destino de escritura: {label}",
        metadata={
            "firebase_condition": condition_name,
            "firebase_condition_label": label,
        },
    )
