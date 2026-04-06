"""
Prompt Version Step - Interactive version string input with validation.
"""

import re
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Exit, Skip
from titan_cli.core.result import ClientSuccess, ClientError

from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager
from ..operations.version_operations import VersionOperations


VERSION_PATTERN = re.compile(r"^\d+(\.\d+){1,3}$")


def prompt_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompt user to enter version string with validation.

    Inputs (from ctx.data):
        selected_apps (List[Dict]): Selected apps from select_app_step
        default_version (str, optional): Default version to suggest

    Params (from workflow params, accessed via ctx.get()):
        default_version (str, optional): Default version override
        validate_format (bool): Enable format validation (default: True)
        show_existing (bool): Show existing versions (default: True)

    Outputs (saved to ctx.data):
        version_string (str): Validated version string

    Returns:
        Success with version string
        Error if validation fails
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Enter Version Number")

    try:
        # Get selected apps from context (from select_app_step)
        selected_apps = ctx.get("selected_apps", [])
        if not selected_apps:
            # Fallback to single app for backward compatibility
            app_id = ctx.get("app_id")
            if not app_id:
                ctx.textual.error_text("No apps selected")
                ctx.textual.end_step("error")
                return Error("No apps selected. Run select_app_step first.")
            selected_apps = [{"id": app_id, "name": ctx.get("app_name", "Unknown")}]

        # Get params (from ctx.data, set by workflow executor)
        validate_format = ctx.get("validate_format", True)
        show_existing = ctx.get("show_existing", True)
        default_version = ctx.get("default_version", "1.0.0")

        # Load credentials and initialize client
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()
        if not key_id or not p8_path:
            ctx.textual.error_text("Credentials not configured")
            ctx.textual.end_step("error")
            return Error("Credentials not configured")

        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        operations = VersionOperations(client)

        # Group apps by brand
        from ..models.view import AppView
        brands = {}
        for app_dict in selected_apps:
            # Reconstruct AppView to use get_brand()
            app_view = AppView(
                id=app_dict["id"],
                name=app_dict["name"],
                bundle_id=app_dict.get("bundle_id", ""),
                sku=app_dict.get("sku", ""),
                primary_locale="en-US"
            )
            brand = app_view.get_brand()
            if brand not in brands:
                brands[brand] = []
            brands[brand].append(app_dict)

        # Show existing versions grouped by brand (only latest per brand)
        if show_existing:
            ctx.textual.text(f"📱 Selected {len(selected_apps)} app(s) from {len(brands)} brand(s)\n")

            for brand, apps in brands.items():
                ctx.textual.text(f"🏷️  {brand} ({len(apps)} app{'s' if len(apps) > 1 else ''}):")

                # Get latest version from first app of the brand
                first_app = apps[0]
                app_id = first_app["id"]

                ctx.textual.text("   Fetching latest version...")
                table_lines = operations.get_versions_summary_table(app_id, limit=1)
                for line in table_lines[2:]:  # Skip header lines
                    ctx.textual.text(f"   {line}")
                ctx.textual.text("")

        # Check for versions in preparation (not READY_FOR_SALE)
        ctx.textual.text("🔍 Checking for versions in preparation...\n")

        versions_in_preparation = []
        for app_dict in selected_apps:
            app_id = app_dict["id"]
            app_name = app_dict["name"]

            # List all versions for this app
            versions_result = client.list_versions(app_id, platform="IOS")

            match versions_result:
                case ClientSuccess(data=versions):
                    # Filter versions not in READY_FOR_SALE
                    in_prep = [v for v in versions if v.state != "READY_FOR_SALE"]
                    for v in in_prep:
                        versions_in_preparation.append({
                            "app_id": app_id,
                            "app_name": app_name,
                            "version": v
                        })
                case ClientError(error_message=err):
                    ctx.textual.warning_text(f"⚠️ Could not check versions for {app_name}: {err}")

        if versions_in_preparation:
            ctx.textual.warning_text(
                f"⚠️ Found {len(versions_in_preparation)} version(s) in preparation:\n"
            )

            # Group by app to show unique apps and get the first version for each
            apps_with_existing_versions = {}
            for item in versions_in_preparation:
                app_id = item['app_id']
                app_name = item['app_name']
                version = item['version']

                if app_id not in apps_with_existing_versions:
                    apps_with_existing_versions[app_id] = {
                        'name': app_name,
                        'version': version,  # Use first version found (most recent)
                        'all_versions': []
                    }
                apps_with_existing_versions[app_id]['all_versions'].append(version)

            for app_id, info in apps_with_existing_versions.items():
                versions_str = ", ".join([f"{v.version_string} ({v.format_state()})" for v in info['all_versions']])
                ctx.textual.text(f"  • {info['name']}: {versions_str}")

            ctx.textual.text(
                f"\n💡 These apps already have versions in preparation.\n"
                f"   They will use existing versions (skip creation) and continue workflow.\n"
            )

            # Separate apps into two groups
            apps_with_versions_ids = set(apps_with_existing_versions.keys())
            apps_to_create_versions = [app for app in selected_apps if app['id'] not in apps_with_versions_ids]
            apps_using_existing = [app for app in selected_apps if app['id'] in apps_with_versions_ids]

            # Show the plan
            ctx.textual.text("")
            if apps_to_create_versions:
                ctx.textual.success_text(f"✓ Will create NEW versions for {len(apps_to_create_versions)} app(s):")
                for app in apps_to_create_versions:
                    ctx.textual.dim_text(f"  • {app['name']}")
                ctx.textual.text("")

            if apps_using_existing:
                ctx.textual.text(f"🔄 Will use EXISTING versions for {len(apps_using_existing)} app(s):")
                for app in apps_using_existing:
                    existing_version = apps_with_existing_versions[app['id']]['version']
                    ctx.textual.dim_text(f"  • {app['name']}: v{existing_version.version_string}")
                ctx.textual.text("")

            # Ask user if they want to continue
            ctx.textual.text(f"📋 Next steps:")

            if apps_to_create_versions:
                ctx.textual.text(f"  1. Create {len(apps_to_create_versions)} new version(s)")
                ctx.textual.text(f"  2. Configure all {len(selected_apps)} app(s) (builds, release notes, submit)")
            else:
                ctx.textual.text(f"  • Configure all {len(selected_apps)} app(s) (builds, release notes, submit)")

            ctx.textual.text("")

            should_continue = ctx.textual.ask_confirm(
                f"Continue?",
                default=True
            )

            if not should_continue:
                ctx.textual.text("Workflow cancelled by user")
                ctx.textual.end_step("cancelled")
                from titan_cli.engine import Exit
                return Exit("User cancelled workflow")

            # Save existing versions to context for create_version_step to use
            existing_versions_map = {}
            for app_id, info in apps_with_existing_versions.items():
                existing_versions_map[app_id] = {
                    'version_id': info['version'].id,
                    'version_string': info['version'].version_string,
                    'state': info['version'].state,
                }

            ctx.data['existing_versions_by_app_id'] = existing_versions_map
            ctx.data['apps_to_create_versions'] = apps_to_create_versions

            # If ALL apps have existing versions, skip version prompt entirely
            if not apps_to_create_versions:
                ctx.textual.success_text(f"\n✓ All apps have existing versions")
                ctx.textual.text("   Skipping version creation step...")

                # Set version_string from first existing version for consistency
                first_existing = list(existing_versions_map.values())[0]
                ctx.data["version_string"] = first_existing['version_string']

                ctx.textual.text("")
                ctx.textual.end_step("success")
                return Success(f"Using existing versions (v{first_existing['version_string']})")

            ctx.textual.success_text(f"\n✓ Proceeding with {len(apps_to_create_versions)} new version(s)\n")

        # Suggest next version (using YY.WW.0 logic from first selected app)
        first_app_id = selected_apps[0]["id"]
        suggested = operations.suggest_next_version(first_app_id)
        ctx.textual.text(f"💡 Suggested next version: {suggested} (YY.WW.0 format)\n")

        # Prompt for version
        version_string = None
        max_attempts = 3
        attempts = 0

        while attempts < max_attempts:
            attempts += 1

            version_input = ctx.textual.ask_text(
                f"Enter version number:",
                default=suggested if attempts == 1 else "",
            )

            version_string = version_input.strip()

            # Validate format
            if validate_format and not VERSION_PATTERN.match(version_string):
                ctx.textual.error_text(
                    f"❌ Invalid format: '{version_string}'. "
                    "Expected format: MAJOR.MINOR[.PATCH][.BUILD] (e.g., 1.2.3)"
                )
                if attempts < max_attempts:
                    ctx.textual.text("Please try again.\n")
                continue

            # Check if version exists
            exists_result = client.version_exists(app_id, version_string)

            match exists_result:
                case ClientSuccess(data=exists):
                    if exists:
                        ctx.textual.error_text(f"❌ Version {version_string} already exists")
                        if attempts < max_attempts:
                            ctx.textual.text("Please enter a different version.\n")
                        continue
                case ClientError(error_message=err):
                    ctx.textual.warning_text(f"⚠️ Could not check if version exists: {err}")
                    # Continue anyway, let create_version handle duplicates

            # Valid version
            break

        if attempts >= max_attempts:
            ctx.textual.error_text("Maximum attempts exceeded")
            ctx.textual.end_step("error")
            return Error("Failed to get valid version after 3 attempts")

        # Save to context
        ctx.data["version_string"] = version_string

        ctx.textual.success_text(f"✓ Version: {version_string}")
        ctx.textual.end_step("success")

        return Success(f"Version string: {version_string}")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["prompt_version_step"]
