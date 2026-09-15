"""Ask for a new parameter value and validate it against the live template."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Optional

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import ChoiceOption

from ..models.values import RemoteConfigValueType


def execute_firebase_remoteconfig_set_value_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Ask for the new value of the selected parameter and validate it.

    Nothing is published here: the step produces a validated change that
    `firebase_remoteconfig_diff` shows and `firebase_remoteconfig_publish`
    applies.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_project_id (str): Target project.
        firebase_key (str): Parameter to change.
        firebase_condition (Optional[str]): Condition to write, or None for the
            default value.
        firebase_value_type (Optional[str]): Type reported by the read.
        firebase_current_value (Optional[str]): Current raw value.
        value (str, optional): New value, for non-interactive runs.

    Outputs (via result metadata):
        firebase_change (UIRemoteConfigChange): The validated change.
        firebase_new_value (str): Exact string that will be stored.

    Returns:
        Success: If the value is valid for the parameter type.
        Error: If inputs are missing, the value is invalid, or the user cancels.
    """
    if ctx.textual:
        ctx.textual.begin_step("Nuevo valor")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    project_id = ctx.get("firebase_project_id") or ctx.get("project_id")
    key = ctx.get("firebase_key") or ctx.get("key")
    if not project_id or not key:
        return _fail(
            ctx,
            "Faltan project_id o key. Ejecuta firebase_select_target y "
            "firebase_remoteconfig_select_key antes de este paso.",
        )

    condition = ctx.get("firebase_condition")
    value_type = _value_type(ctx.get("firebase_value_type"))
    current_value = ctx.get("firebase_current_value")

    new_value = ctx.get("value")
    if new_value is None:
        if not ctx.textual:
            return _fail(ctx, "Se necesita la TUI para introducir un valor")
        new_value = _ask_value(ctx, str(key), value_type, current_value, condition)
        if new_value is None:
            return _fail(ctx, "No se introdujo ningún valor")

    loading = (
        ctx.textual.loading("Validando el valor contra la plantilla...")
        if ctx.textual
        else nullcontext()
    )
    with loading:
        result = ctx.firebase.validate_remote_config_change(
            str(project_id),
            str(key),
            str(new_value),
            condition,
        )

    match result:
        case ClientSuccess(data=change):
            if ctx.textual:
                ctx.textual.text(
                    f"{change.key} [{change.target_label}] → "
                    f"{change.new_raw_value}"
                )
                if change.creates_conditional_value:
                    ctx.textual.dim_text(
                        "La condición no tenía valor propio: se creará uno."
                    )
                ctx.textual.end_step("success")
            return Success(
                f"Valor validado para {change.key}",
                metadata={
                    "firebase_change": change,
                    "firebase_new_value": change.new_raw_value,
                },
            )
        case ClientError(error_message=error_message):
            return _fail(ctx, error_message)

    return _fail(ctx, "Respuesta inesperada al validar el valor")


def _value_type(raw: Optional[object]) -> RemoteConfigValueType:
    """Normalize the type reported by the read step."""
    if isinstance(raw, RemoteConfigValueType):
        return raw
    if isinstance(raw, str):
        return RemoteConfigValueType.__members__.get(
            raw.strip().upper(),
            RemoteConfigValueType.UNKNOWN,
        )
    return RemoteConfigValueType.UNKNOWN


def _ask_value(
    ctx: WorkflowContext,
    key: str,
    value_type: RemoteConfigValueType,
    current_value: Optional[object],
    condition: Optional[object],
) -> Optional[str]:
    """Prompt for the new value in the shape the type calls for."""
    target = condition or "valor por defecto"
    current = str(current_value) if current_value is not None else ""

    if value_type == RemoteConfigValueType.BOOLEAN:
        chosen = ctx.textual.ask_choice(
            f"{key} [{target}] — valor actual: {current or '(sin valor)'}",
            options=[
                ChoiceOption(value="true", label="true", variant="success"),
                ChoiceOption(value="false", label="false", variant="error"),
            ],
        )
        return str(chosen) if chosen is not None else None

    if value_type == RemoteConfigValueType.JSON:
        # JSON values are routinely multi-line; a single-line input would make
        # anything non-trivial uneditable.
        return ctx.textual.ask_multiline(
            f"{key} [{target}] — JSON:",
            default=current,
        )

    hint = "número" if value_type == RemoteConfigValueType.NUMBER else "texto"
    return ctx.textual.ask_text(
        f"{key} [{target}] — nuevo valor ({hint}):",
        default=current,
    )


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
