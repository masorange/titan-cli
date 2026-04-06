"""
Fetch Production Version Step - Automatically get latest READY_FOR_SALE version.

This step finds the latest production version without user interaction.
Supports multiple apps (analyzes all selected apps).
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager
from titan_cli.core.result import ClientSuccess, ClientError


def fetch_production_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Automatically fetch the latest production version for all selected apps.

    This step finds the most recent version in READY_FOR_SALE state,
    which is the version currently live on the App Store.

    Inputs (from ctx.data):
        - selected_apps (list): Apps to analyze (from select_app_step)
        - app_id: Single app (fallback for backward compatibility)

    Outputs (saved to ctx.data):
        - version_string: Production version string (common across apps)
        - app_name: App name (from first app)

    Returns:
        Success with production version info
        Error if no production version found for any app
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Fetch Production Version(s)")

    try:
        # Get apps to analyze
        selected_apps = ctx.data.get("selected_apps", [])

        apps_to_analyze = []
        if selected_apps:
            apps_to_analyze = [{"id": app["id"], "name": app["name"]} for app in selected_apps]
        else:
            # Fallback to single app
            app_id = ctx.data.get("app_id")
            app_name = ctx.data.get("app_name")
            if not app_id:
                ctx.textual.error_text("Missing required input: selected_apps or app_id")
                ctx.textual.end_step("error")
                return Error("Missing app_id in context")
            apps_to_analyze = [{"id": app_id, "name": app_name}]

        # Load credentials
        credentials = CredentialsManager.load_credentials()
        if not credentials:
            ctx.textual.error_text("No credentials configured")
            ctx.textual.end_step("error")
            return Error("Run setup wizard first")

        issuer_id = credentials.get("issuer_id")
        key_id = credentials.get("key_id")
        p8_path = credentials.get("private_key_path")

        # Initialize client
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        ctx.textual.text(f"🔍 Searching for production versions in {len(apps_to_analyze)} app(s)...")
        ctx.textual.text("")

        production_versions_found = []
        apps_without_production = []

        # Check each app
        for app_info in apps_to_analyze:
            app_id = app_info["id"]
            app_name = app_info["name"]

            ctx.textual.text(f"📱 {app_name}:")

            # Get all versions
            versions_result = client.list_versions(app_id)

            match versions_result:
                case ClientSuccess(data=versions):
                    if not versions:
                        ctx.textual.warning_text(f"  ⚠️  No versions found")
                        apps_without_production.append(app_name)
                        continue

                    # Filter by READY_FOR_SALE state
                    production_versions = [
                        v for v in versions if v.state == "READY_FOR_SALE"
                    ]

                    if not production_versions:
                        ctx.textual.warning_text(f"  ⚠️  No production version (no READY_FOR_SALE)")
                        apps_without_production.append(app_name)
                        continue

                    # Sort by created date (newest first)
                    production_versions.sort(
                        key=lambda v: v.created_date or "", reverse=True
                    )

                    # Take the latest
                    latest_production = production_versions[0]

                    production_versions_found.append({
                        "app_id": app_id,
                        "app_name": app_name,
                        "version": latest_production
                    })

                    ctx.textual.success_text(
                        f"  ✅ {latest_production.version_string} "
                        f"(released {latest_production.created_date[:10] if latest_production.created_date else 'unknown'})"
                    )

                case ClientError(error_message=err):
                    ctx.textual.error_text(f"  ❌ Failed: {err}")
                    apps_without_production.append(app_name)

        ctx.textual.text("")

        # Check if we found any production versions
        if not production_versions_found:
            ctx.textual.error_text("❌ No production versions found in any app")
            ctx.textual.text("   All apps must have at least one version in READY_FOR_SALE state")
            ctx.textual.end_step("error")
            return Error("No production versions available")

        # Check if all apps have the same version
        version_strings = set(item["version"].version_string for item in production_versions_found)

        if len(version_strings) == 1:
            # All apps have the same production version
            version_string = list(version_strings)[0]
            ctx.textual.success_text(f"✅ All {len(production_versions_found)} app(s) have production version: {version_string}")
        else:
            # Different versions across apps
            ctx.textual.warning_text(f"⚠️  Apps have different production versions:")
            for version_str in sorted(version_strings):
                apps_with_this_version = [
                    item["app_name"] for item in production_versions_found
                    if item["version"].version_string == version_str
                ]
                ctx.textual.text(f"   • {version_str}: {', '.join(apps_with_this_version)}")

            # Use the most common version
            from collections import Counter
            version_counter = Counter(item["version"].version_string for item in production_versions_found)
            version_string = version_counter.most_common(1)[0][0]
            ctx.textual.text(f"\n   Using most common version: {version_string}")

        # Show apps without production versions
        if apps_without_production:
            ctx.textual.text("")
            ctx.textual.warning_text(f"⚠️  {len(apps_without_production)} app(s) without production version:")
            for app_name in apps_without_production:
                ctx.textual.text(f"   • {app_name}")

        # Store in context
        ctx.data["version_string"] = version_string
        ctx.data["app_name"] = production_versions_found[0]["app_name"]  # First app for compatibility

        ctx.textual.text("")
        ctx.textual.end_step("success")

        return Success(f"Found production version: {version_string}")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["fetch_production_version_step"]
