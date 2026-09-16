"""Browse a template's parameters and pick one key."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import OptionItem

# Above this many parameters the flat list stops being navigable, so the step
# asks for a filter first.
FILTER_THRESHOLD = 25
TABLE_PREVIEW_LIMIT = 40
MAX_VALUE_COLUMNS = 3


def execute_firebase_remoteconfig_select_key_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Choose one Remote Config parameter.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_remoteconfig_template (UIRemoteConfigTemplate): From firebase_remoteconfig_get.
        firebase_conditions (list, optional): Targets, from firebase_remoteconfig_conditions.
        key (str, optional): Preselected parameter key.

    Outputs (saved to ctx.data):
        firebase_key (str): Selected parameter key.
        firebase_value_type (str): Effective value type of the parameter.
        firebase_current_value (Optional[str]): Current value of the first target, None if unset.

    Returns:
        Success: If a parameter is selected.
        Error: If the template is missing, the key is unknown, or the user cancels.
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

    targets = _targets(ctx)
    condition = targets[0]
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

    _render_table(ctx, template, candidates, targets)

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


def _targets(ctx) -> list:
    """Selected write targets, defaulting to the parameter's default value."""
    targets = ctx.get("firebase_conditions")
    if isinstance(targets, (list, tuple)) and targets:
        return list(targets)
    return [None]


def _render_table(ctx, template, candidates, targets) -> None:
    """Show the candidate parameters and their value in each chosen target."""
    shown = candidates[:TABLE_PREVIEW_LIMIT]
    # One column per target, capped: past a handful the table stops fitting and
    # the selection list below is the real navigation aid anyway.
    columns = targets[:MAX_VALUE_COLUMNS]
    headers = ["Clave", "Tipo"] + [
        _column_header(target) for target in columns
    ]
    ctx.textual.table(
        headers=headers,
        rows=[
            [parameter.key, parameter.value_type.value]
            + [_display_for_target(parameter, target) for target in columns]
            for parameter in shown
        ],
        title=f"Parámetros de {template.project_id}",
        flex_column=len(headers) - 1,
    )
    if len(targets) > len(columns):
        ctx.textual.dim_text(
            f"Mostrando {len(columns)} de {len(targets)} destinos."
        )
    if len(candidates) > len(shown):
        ctx.textual.dim_text(
            f"Mostrando {len(shown)} de {len(candidates)} parámetros; la lista "
            "de selección incluye todos."
        )


def _column_header(target) -> str:
    """Column title for one write target."""
    if target is None:
        return "Por defecto"
    return target if len(target) <= 28 else f"{target[:27]}…"


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
