"""Show what a pending change would do, and get explicit confirmation."""

from __future__ import annotations

from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult


def execute_firebase_remoteconfig_diff_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Render the pending change and ask the user to confirm it.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_change (UIRemoteConfigChange): From firebase_remoteconfig_set_value.
        firebase_project_id (str): Target project.
        firebase_target_label (Optional[str]): Display label for the project.

    Outputs (saved to ctx.data):
        firebase_change_confirmed (bool): Always True when the step succeeds.

    Returns:
        Success: If the user confirms the change.
        Exit: If the change is a no-op, or the user declines.
        Error: If there is no pending change to show.
    """
    if ctx.textual:
        ctx.textual.begin_step("Revisar el cambio")

    change = ctx.get("firebase_change")
    if change is None:
        message = (
            "No hay ningún cambio pendiente. Ejecuta "
            "firebase_remoteconfig_set_value antes de este paso."
        )
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    project_id = ctx.get("firebase_project_id") or "?"
    target_label = ctx.get("firebase_target_label") or project_id

    if ctx.textual:
        ctx.textual.table(
            headers=["Campo", "Valor"],
            rows=[
                ["Proyecto", str(project_id)],
                ["Destino", str(target_label)],
                ["Parámetro", change.key],
                ["Valor de", change.target_label],
                ["Tipo", change.value_type.value],
                ["Antes", change.old_raw_value or "(sin valor)"],
                ["Después", change.new_raw_value],
            ],
            title="Cambio pendiente",
            flex_column=1,
        )
        if change.inherited_from_default:
            ctx.textual.dim_text(
                "La condición heredaba el valor por defecto; a partir de "
                "ahora tendrá uno propio."
            )

    if change.is_noop:
        message = f"{change.key} ya vale {change.new_raw_value}: nada que publicar"
        if ctx.textual:
            ctx.textual.warning_text(message)
            ctx.textual.end_step("skipped")
        return Exit(message)

    if ctx.textual:
        confirmed = ctx.textual.ask_confirm(
            f"¿Publicar este cambio en {target_label}?",
            default=False,
        )
        if not confirmed:
            message = "Cambio descartado por el usuario"
            ctx.textual.warning_text(message)
            ctx.textual.end_step("skipped")
            return Exit(message)
        ctx.textual.end_step("success")

    return Success(
        f"Cambio confirmado para {change.key}",
        metadata={"firebase_change_confirmed": True},
    )
