"""
Select version step for the iOS product report.

Shows all App Store Connect versions with their release status and lets the user
pick one by index. Falls back to manual text input if the API fails.
"""

from typing import Optional

from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error

from ..credentials import CredentialsManager


def select_product_report_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show App Store versions and let the user pick a version by number.

    Displays each version with its platform version string and status.
    Caches version info in ctx for later steps.

    Inputs (from ctx.data):
        app_id (str): The App Store Connect app ID.
        app_name (str): The app name for display.
        appstore_client: The App Store Connect client instance.

    Outputs (to ctx.data):
        selected_version_id (str): The version ID chosen by the user.
        selected_version_string (str): The version string (e.g., "26.10.2").

    Returns:
        Success: Version selected.
        Error: No app selected or invalid input.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select Version")

    app_id: Optional[str] = ctx.get("app_id")
    app_name: Optional[str] = ctx.get("app_name", "Unknown App")

    if not app_id:
        ctx.textual.error_text("No app selected.")
        ctx.textual.end_step("error")
        return Error("No app selected")

    # List of (version_string, version_id, status_label) for display
    options: list[tuple[str, str, str]] = []

    # Load credentials and create client
    issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()
    if not key_id or not p8_path:
        ctx.textual.error_text("App Store Connect credentials not configured")
        ctx.textual.end_step("error")
        return Error("Credentials not configured. Run setup workflow first.")

    from ..clients.appstore_client import AppStoreConnectClient
    appstore_client = AppStoreConnectClient(
        key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
    )

    with ctx.textual.loading(f"Fetching versions for {app_name}..."):
        try:
            # Fetch all versions from App Store Connect
            versions_result = appstore_client.list_versions(
                app_id=app_id,
                platform="IOS"
            )

            match versions_result:
                case ClientSuccess(data=versions):
                    # Map state to Spanish labels
                    status_labels = {
                        "READY_FOR_SALE": "En venta",
                        "PROCESSING_FOR_APP_STORE": "Procesando",
                        "PENDING_DEVELOPER_RELEASE": "Pendiente",
                        "PREPARE_FOR_SUBMISSION": "Preparación",
                        "WAITING_FOR_REVIEW": "Esperando revisión",
                        "IN_REVIEW": "En revisión",
                        "PENDING_APPLE_RELEASE": "Pendiente Apple",
                        "DEVELOPER_REJECTED": "Rechazada",
                        "REMOVED_FROM_SALE": "Retirada",
                    }

                    for version in versions[:20]:  # Limit to 20 versions
                        version_string = version.version_string
                        version_id = version.id
                        state = version.state or ""
                        status_label = status_labels.get(state, state.replace("_", " ").title() if state else "Unknown")

                        if version_string and version_id:
                            options.append((version_string, version_id, status_label))

                case ClientError(error_message=err):
                    ctx.textual.warning_text(f"Could not fetch versions: {err}")

        except Exception as e:
            ctx.textual.warning_text(f"Error fetching versions: {e}")

    ctx.textual.text("")

    if options:
        ctx.textual.text(f"  Versiones disponibles ({app_name}):")
        ctx.textual.text("")
        for i, (version_str, _, status) in enumerate(options):
            line = f"    {i + 1}. {version_str}  ← {status}"
            if status == "En venta":
                ctx.textual.text(line)
            else:
                ctx.textual.dim_text(line)
        ctx.textual.text("")

        raw = ctx.textual.ask_text(
            f"Selecciona el número de versión a analizar [1-{len(options)}]:",
            default="1",
        )

        raw = (raw or "").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                selected_string, selected_id, _ = options[idx]
            else:
                ctx.textual.error_text(f"  Número fuera de rango (1-{len(options)}).")
                ctx.textual.end_step("error")
                return Error("Index out of range")
        else:
            # Fallback: try to find by version string
            matching = [opt for opt in options if opt[0] == raw]
            if matching:
                selected_string, selected_id, _ = matching[0]
            else:
                ctx.textual.error_text(f"  Version '{raw}' not found.")
                ctx.textual.end_step("error")
                return Error(f"Version '{raw}' not found")
    else:
        ctx.textual.warning_text("  No versions found in App Store Connect.")
        ctx.textual.text("")
        selected_string = ctx.textual.ask_text(
            "Escribe el nombre de versión manualmente (ej. 26.10.2):",
            default="",
        )
        selected_string = (selected_string or "").strip()
        selected_id = ""  # No ID available for manual input

    if not selected_string:
        ctx.textual.error_text("  No se introdujo ninguna versión.")
        ctx.textual.end_step("error")
        return Error("No version selected")

    ctx.set("selected_version_id", selected_id)
    ctx.set("selected_version_string", selected_string)

    ctx.textual.text("")
    ctx.textual.success_text(f"  Versión seleccionada: {selected_string}")
    ctx.textual.text("")
    ctx.textual.end_step("success")
    return Success(f"Version selected: {selected_string}")


__all__ = ["select_product_report_version_step"]
