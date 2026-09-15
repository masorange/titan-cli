"""Ask for a new parameter value and validate it against the live template."""

from __future__ import annotations

from contextlib import nullcontext

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from .prompts import ask_value, blank_to_none, normalize_value_type


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
        firebase_condition (Optional[str]): Condition to write, None for the default.
        firebase_value_type (Optional[str]): Type reported by the read.
        firebase_current_value (Optional[str]): Current raw value.
        value (str, optional): New value, for non-interactive runs.

    Outputs (saved to ctx.data):
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
    value_type = normalize_value_type(ctx.get("firebase_value_type"))
    current_value = ctx.get("firebase_current_value")

    new_value = blank_to_none(ctx.get("value"))
    if new_value is None:
        if not ctx.textual:
            return _fail(ctx, "Se necesita la TUI para introducir un valor")
        new_value = ask_value(ctx, str(key), value_type, current_value, condition)
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
                    f"{change.key} [{change.target_label}] → {change.new_raw_value}"
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


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
