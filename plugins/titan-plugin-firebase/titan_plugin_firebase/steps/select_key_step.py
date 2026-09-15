"""Browse a template's parameters and pick one key."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import OptionItem

# Above this many parameters the flat list stops being navigable, so the step
# asks for a filter first.
FILTER_THRESHOLD = 25
TABLE_PREVIEW_LIMIT = 40


def execute_firebase_remoteconfig_select_key_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Choose one Remote Config parameter.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_remoteconfig_template (UIRemoteConfigTemplate): From
            `firebase_remoteconfig_get`.
        firebase_condition (Optional[str]): Write target, from
            `firebase_remoteconfig_conditions`.
        key (str, optional): Preselected parameter key.

    Outputs (via result metadata):
        firebase_key (str): Selected parameter key.
        firebase_value_type (str): Effective value type of the parameter.
        firebase_current_value (Optional[str]): Raw current value for the
            selected target, or None when the target has no value yet.

    Returns:
        Success: If a parameter is selected.
        Error: If the template is missing, the key does not exist, or the user
            cancels.
    """
    if ctx.textual:
        ctx.textual.begin_step("Seleccionar parámetro")

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

    condition = ctx.get("firebase_condition")
    preselected = ctx.get("key") or ctx.get("firebase_key")

    if preselected:
        parameter = template.parameter(str(preselected))
        if parameter is None:
            message = (
                f"El parámetro '{preselected}' no existe en "
                f"{template.project_id}."
            )
            if ctx.textual:
                ctx.textual.error_text(message)
                ctx.textual.end_step("error")
            return Error(message)
        return _success(ctx, parameter, condition)

    if not template.parameters:
        message = f"{template.project_id} no tiene parámetros de Remote Config."
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    if not ctx.textual:
        return Error("Se necesita la TUI para seleccionar un parámetro")

    candidates = list(template.parameters)
    if len(candidates) > FILTER_THRESHOLD:
        needle = ctx.textual.ask_text(
            f"{len(candidates)} parámetros. Filtra por texto (vacío = todos):",
            default="",
        )
        if needle:
            lowered = needle.strip().lower()
            filtered = [
                parameter
                for parameter in candidates
                if lowered in parameter.key.lower()
                or lowered in (parameter.description or "").lower()
            ]
            if not filtered:
                message = f"Ningún parámetro coincide con '{needle}'."
                ctx.textual.error_text(message)
                ctx.textual.end_step("error")
                return Error(message)
            candidates = filtered

    _render_table(ctx, template, candidates, condition)

    selected = ctx.textual.ask_option(
        "¿Qué parámetro?",
        [
            OptionItem(
                value=parameter.key,
                title=parameter.key,
                description=_option_description(parameter, condition),
            )
            for parameter in candidates
        ],
    )
    if selected is None:
        message = "No se seleccionó ningún parámetro"
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
        return Error(message)

    parameter = template.parameter(str(selected))
    if parameter is None:
        message = f"El parámetro '{selected}' ya no está en la plantilla."
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
        return Error(message)

    return _success(ctx, parameter, condition)


def _render_table(ctx, template, candidates, condition) -> None:
    """Show the candidate parameters and the value for the chosen target."""
    shown = candidates[:TABLE_PREVIEW_LIMIT]
    target_header = f"Valor ({condition})" if condition else "Valor por defecto"
    ctx.textual.table(
        headers=["Clave", "Tipo", target_header, "Condiciones"],
        rows=[
            [
                parameter.key,
                parameter.value_type.value,
                _display_for_target(parameter, condition),
                str(len(parameter.conditional_values)) or "0",
            ]
            for parameter in shown
        ],
        title=f"Parámetros de {template.project_id}",
        flex_column=2,
    )
    if len(candidates) > len(shown):
        ctx.textual.dim_text(
            f"Mostrando {len(shown)} de {len(candidates)}; la lista de "
            "selección incluye todos."
        )


def _display_for_target(parameter, condition) -> str:
    """Render the value for the selected target, flagging inheritance."""
    value = parameter.value_for(condition)
    if value is None:
        if condition is None:
            return "—"
        default = parameter.default_value
        inherited = default.display_value if default else "—"
        return f"(hereda) {inherited}"
    return value.display_value


def _option_description(parameter, condition) -> str:
    """One-line description for the option list."""
    parts = [parameter.value_type.value, _display_for_target(parameter, condition)]
    if parameter.description:
        parts.append(parameter.description)
    return " · ".join(part for part in parts if part)


def _success(ctx, parameter, condition) -> WorkflowResult:
    """Report the selected parameter and its current value for the target."""
    value = parameter.value_for(condition)
    if ctx.textual:
        ctx.textual.text(
            f"{parameter.key} ({parameter.value_type.value}) = "
            f"{_display_for_target(parameter, condition)}"
        )
        ctx.textual.end_step("success")
    return Success(
        f"Parámetro seleccionado: {parameter.key}",
        metadata={
            "firebase_key": parameter.key,
            "firebase_value_type": parameter.value_type.value,
            "firebase_current_value": value.raw_value if value else None,
        },
    )
