"""
Select App Step - Interactive app selection from App Store Connect.
"""

from typing import Dict, Any, List
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.ui.tui.widgets import SelectionOption

from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager
from ..utils.brand_detector import filter_apps_by_brands, get_project_brands


def select_app_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompt user to select one or more apps from App Store Connect.

    Inputs:
        None (loads from credentials)

    Outputs (saved to ctx.data):
        selected_apps (List[Dict]): List of selected app details
        app_ids (List[str]): List of selected app IDs

        # For single-app compatibility:
        selected_app (Dict): First selected app details
        app_id (str): ID of first selected app
        app_name (str): Name of first selected app
        bundle_id (str): Bundle ID of first selected app

    Returns:
        Success with selected app details
        Error if no apps available or no apps selected
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Select App")

    try:
        # Load credentials
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()

        if not key_id or not p8_path:
            ctx.textual.error_text("App Store Connect credentials not configured")
            ctx.textual.end_step("error")
            return Error("Credentials not configured. Run setup workflow first.")

        # Initialize client
        ctx.textual.text("Connecting to App Store Connect...")
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Fetch apps
        ctx.textual.text("Fetching apps...")
        apps_result = client.list_apps()

        # Use pattern matching for ClientResult
        match apps_result:
            case ClientSuccess(data=apps):
                if not apps:
                    ctx.textual.error_text("No apps found in App Store Connect")
                    ctx.textual.end_step("error")
                    return Error("No apps available")

                # Filter apps by Brands detected from Brands/ directory
                detected_brands = get_project_brands()

                if detected_brands:
                    ctx.textual.text(f"Detected brands: {', '.join(detected_brands)}")
                    filtered_apps = filter_apps_by_brands(apps)

                    if len(filtered_apps) < len(apps):
                        ctx.textual.text(f"Found {len(filtered_apps)} main app(s) from {len(apps)} total (filtered):")
                    else:
                        ctx.textual.text(f"Found {len(filtered_apps)} app(s):")

                    apps = filtered_apps
                else:
                    # No Brands/ directory found
                    ctx.textual.text(f"Found {len(apps)} app(s) (no brand filter applied):")

            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to fetch apps: {err}")
                ctx.textual.end_step("error")
                return Error(f"Failed to fetch apps: {err}")

        # Create SelectionOption objects (all selected by default)
        selection_options = [
            SelectionOption(value=app, label=app.display_name(), selected=True)
            for app in apps
        ]

        for idx, app in enumerate(apps, 1):
            ctx.textual.text(f"  {idx}. {app.display_name()}")

        ctx.textual.text("")

        # Prompt user to select (returns list of app objects)
        selected_apps = ctx.textual.ask_multiselect(
            "Select apps (all selected by default):",
            options=selection_options
        )

        if not selected_apps:
            ctx.textual.error_text("No apps selected")
            ctx.textual.end_step("error")
            return Error("No apps selected")

        # Save all selected apps to context
        ctx.data["selected_apps"] = [
            {
                "id": app.id,
                "name": app.name,
                "bundle_id": app.bundle_id,
                "sku": app.sku,
            }
            for app in selected_apps
        ]
        ctx.data["app_ids"] = [app.id for app in selected_apps]

        # For backward compatibility, save first app as singular
        first_app = selected_apps[0]
        ctx.data["selected_app"] = {
            "id": first_app.id,
            "name": first_app.name,
            "bundle_id": first_app.bundle_id,
            "sku": first_app.sku,
        }
        ctx.data["app_id"] = first_app.id
        ctx.data["app_name"] = first_app.name
        ctx.data["bundle_id"] = first_app.bundle_id

        # Show selection summary
        if len(selected_apps) == 1:
            ctx.textual.success_text(f"✓ Selected: {first_app.display_name()}")
        else:
            ctx.textual.success_text(f"✓ Selected {len(selected_apps)} apps:")
            for app in selected_apps:
                ctx.textual.text(f"  • {app.display_name()}")

        ctx.textual.end_step("success")

        return Success(f"Selected {len(selected_apps)} app(s)")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["select_app_step"]
