"""Show what a pending change would do, and get explicit confirmation."""

from __future__ import annotations

from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult


def execute_firebase_remoteconfig_diff_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Render the pending change and ask the user to confirm it.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_change_set (UIRemoteConfigChangeSet): From firebase_remoteconfig_set_value.
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

    change_set = ctx.get("firebase_change_set")
    if change_set is None:
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
        ctx.textual.text(
            f"{change_set.key} ({change_set.value_type.value}) = "
            f"{change_set.new_raw_value} en {target_label}"
        )
        ctx.textual.table(
            headers=["Destino", "Antes", "Después"],
            rows=[
                [
                    change.target_label,
                    change.old_raw_value
                    if change.old_raw_value is not None
                    else "(sin valor)",
                    change.new_raw_value if not change.is_noop else "= sin cambio",
                ]
                for change in change_set.changes
            ],
            title="Cambio pendiente",
            flex_column=2,
        )
        inherited = [
            change.target_label
            for change in change_set.pending
            if change.inherited_from_default
        ]
        if inherited:
            ctx.textual.dim_text(
                "Estas condiciones heredaban el valor por defecto y a partir "
                f"de ahora tendrán uno propio: {', '.join(inherited)}"
            )

    if change_set.is_noop:
        message = (
            f"{change_set.key} ya vale {change_set.new_raw_value} en todos los "
            "destinos: nada que publicar"
        )
        if ctx.textual:
            ctx.textual.warning_text(message)
            ctx.textual.end_step("skipped")
        return Exit(message)

    if ctx.textual:
        confirmed = ctx.textual.ask_confirm(
            f"¿Publicar en {len(change_set.pending)} destino(s) de "
            f"{target_label}?",
            default=False,
        )
        if not confirmed:
            message = "Cambio descartado por el usuario"
            ctx.textual.warning_text(message)
            ctx.textual.end_step("skipped")
            return Exit(message)
        ctx.textual.end_step("success")

    return Success(
        f"Cambio confirmado para {change_set.key}",
        metadata={"firebase_change_confirmed": True},
    )
