"""List Remote Config parameter keys with their configured values."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..operations.key_inventory_operations import template_key_values_to_metadata


def execute_firebase_remoteconfig_list_keys_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    List parameter keys and configured values in a Remote Config template.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_remoteconfig_template (UIRemoteConfigTemplate): From firebase_remoteconfig_get.

    Outputs (saved to ctx.data):
        firebase_remoteconfig_keys (list[str]): Parameter keys in template order.
        firebase_remoteconfig_key_values (dict[str, dict]): Default and conditional values per key.
        firebase_remoteconfig_key_count (int): Number of parameter keys.

    Returns:
        Success: If the template is present; empty projects return an empty list.
        Error: If the template is missing.
    """
    if ctx.textual:
        ctx.textual.begin_step("Listar claves")

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

    keys = [parameter.key for parameter in template.parameters]

    if ctx.textual:
        if keys:
            ctx.textual.table(
                headers=["Clave", "Tipo", "Valor por defecto", "Entornos/condiciones"],
                rows=[
                    [
                        parameter.key,
                        parameter.type_label,
                        parameter.default_display_value,
                        parameter.conditional_values_summary,
                    ]
                    for parameter in template.parameters
                ],
                title=f"Claves de {template.project_id}",
                flex_column=3,
            )
        else:
            ctx.textual.dim_text(
                f"{template.project_id} no tiene claves de Remote Config."
            )
        ctx.textual.end_step("success")

    return Success(
        f"{len(keys)} claves de Remote Config",
        metadata={
            "firebase_remoteconfig_keys": keys,
            "firebase_remoteconfig_key_values": template_key_values_to_metadata(
                template
            ),
            "firebase_remoteconfig_key_count": len(keys),
        },
    )
