"""
Select Build Per Brand Step - Allow user to select a build for each app.
"""

from typing import Dict
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem

from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager
from ..operations.build_operations import (
    format_build_for_selection,
    filter_valid_builds,
    find_common_build_numbers,
    find_build_by_number,
)
from ..models.view import AppView, AppSubmissionPackage


def select_build_per_brand(ctx: WorkflowContext) -> WorkflowResult:
    """
    For each selected app, list available builds and let user select one.

    Builds are filtered to only show valid, non-expired builds.
    If no builds available for an app, that app is skipped with a warning.

    Inputs (from ctx.data):
        selected_apps (List[Dict]): Selected apps from previous step
        active_version_id (str): Active version ID to filter builds

    Outputs (saved to ctx.data):
        selected_builds (Dict[str, str]): Mapping of app_id -> build_id

    Returns:
        Success with selected builds
        Error if credentials missing or API fails
        Skip if no builds available for any app
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Select Builds")

    try:
        # Get selected apps from context
        selected_apps_data = ctx.get("selected_apps")
        version_id = ctx.get("active_version_id")

        if not selected_apps_data:
            ctx.textual.error_text("No apps selected in previous step")
            ctx.textual.end_step("error")
            return Error("No apps selected")

        # Convert dict data back to AppView objects
        selected_apps = [
            AppView(
                id=app["id"],
                name=app["name"],
                bundle_id=app["bundle_id"],
                sku=app["sku"],
                primary_locale="en-US",
            )
            for app in selected_apps_data
        ]

        # Load credentials and initialize client
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()

        if not key_id or not p8_path:
            ctx.textual.error_text("App Store Connect credentials not configured")
            ctx.textual.end_step("error")
            return Error("Credentials not configured")

        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Check if we have newly created versions (warn they won't have builds yet)
        apps_created = ctx.get("apps_to_create_versions", [])
        if apps_created:
            ctx.textual.text(f"\n⚠️  Note: {len(apps_created)} version(s) were just created.")
            ctx.textual.text("   Newly created versions won't have builds until you upload them.\n")

        # Get the version string we're configuring (e.g., "26.11.0")
        version_string = ctx.get("version_string")
        if not version_string:
            ctx.textual.error_text("No version_string in context")
            ctx.textual.end_step("error")
            return Error("version_string required from previous step")

        # STEP 1: Collect builds for ALL apps first (to find common builds)
        ctx.textual.text("\n🔍 Analyzing builds across all apps...\n")

        builds_by_app = {}
        apps_with_builds = []

        for app in selected_apps:
            brand = app.get_brand()

            builds_result = client.list_builds(app.id)

            match builds_result:
                case ClientSuccess(data=builds):
                    valid_builds = filter_valid_builds(builds)

                    if valid_builds:
                        builds_by_app[app.id] = valid_builds
                        apps_with_builds.append(app)
                        ctx.textual.text(f"  • {brand}: {len(valid_builds)} build(s) available")
                    else:
                        ctx.textual.dim_text(f"  • {brand}: No builds found")

                case ClientError(error_message=err):
                    ctx.textual.dim_text(f"  • {brand}: Error - {err}")

        if not apps_with_builds:
            ctx.textual.warning_text(f"\n❌ No builds found for any app\n")
            ctx.textual.text("💡 To continue, you need to:")
            ctx.textual.text("   1. Build your app (via Xcode or Fastlane)")
            ctx.textual.text("   2. Upload to App Store Connect")
            ctx.textual.text("   3. Wait for Apple to process the build (~5-10 minutes)")
            ctx.textual.text("   4. Run this workflow again\n")
            ctx.textual.text("📋 Example with Fastlane:")
            ctx.textual.text("   cd /tmp/apps-monorepo")
            ctx.textual.text(f"   bundle exec fastlane build:sta PROJECT=ragnarok BRAND=yoigo\n")
            ctx.textual.end_step("skipped")
            return Skip("No builds available")

        # STEP 2: Find common build NUMBERS (not IDs) available in ALL apps
        ctx.textual.text("")
        common_build_numbers = find_common_build_numbers(builds_by_app)

        # STEP 3: Decide selection mode
        selection_mode = "individual"  # Default

        if common_build_numbers and len(apps_with_builds) > 1:
            ctx.textual.success_text(
                f"✓ Found {len(common_build_numbers)} common build number(s) available for all {len(apps_with_builds)} app(s)\n"
            )
            ctx.textual.dim_text(f"   Common build numbers: {', '.join(common_build_numbers[:10])}")
            if len(common_build_numbers) > 10:
                ctx.textual.dim_text(f"   ... and {len(common_build_numbers) - 10} more\n")
            else:
                ctx.textual.text("")

            # Ask user: bulk or individual?
            mode_choice = ctx.textual.ask_choice(
                "How do you want to select builds?",
                options=[
                    ChoiceOption(
                        value="bulk",
                        label="Use same build number for all apps (bulk selection)",
                        variant="primary"
                    ),
                    ChoiceOption(
                        value="individual",
                        label="Select build individually per app",
                        variant="default"
                    ),
                ]
            )

            selection_mode = mode_choice

        # STEP 4: Execute selection based on mode
        selected_builds: Dict[str, str] = {}

        if selection_mode == "bulk":
            # BULK MODE: Select one build NUMBER, then find each app's build with that number
            ctx.textual.text("")
            ctx.textual.bold_primary_text(f"📦 Bulk Selection - Selecting for {len(apps_with_builds)} app(s)\n")

            # Show common build numbers as options
            # Use first app's builds to get details for display
            first_app_builds = builds_by_app[apps_with_builds[0].id]

            option_items = []
            for build_number in common_build_numbers:
                # Find a build with this number (from first app) to get upload date
                sample_build = find_build_by_number(first_app_builds, build_number)
                if sample_build:
                    value, title, description = format_build_for_selection(sample_build)
                    option_items.append(
                        OptionItem(
                            value=build_number,  # Use build NUMBER as value, not ID
                            title=title,
                            description=description
                        )
                    )

            selected_build_number = ctx.textual.ask_option(
                f"Select build number to use for ALL apps:",
                options=option_items,
            )

            if selected_build_number:
                # Find each app's build with this number and assign
                ctx.textual.text("")
                ctx.textual.text(f"🔍 Finding build {selected_build_number} for each app...\n")

                for app in apps_with_builds:
                    brand = app.get_brand()
                    app_builds = builds_by_app[app.id]

                    # Find this app's build with the selected number
                    app_build = find_build_by_number(app_builds, selected_build_number)

                    if app_build:
                        selected_builds[app.id] = app_build.id
                        ctx.textual.dim_text(f"  • {brand}: Found build {selected_build_number} (ID: {app_build.id[:8]}...)")
                    else:
                        ctx.textual.warning_text(f"  ⚠️ {brand}: Build {selected_build_number} not found")

                ctx.textual.text("")
                ctx.textual.success_text(f"✓ Assigned build number {selected_build_number} to {len(selected_builds)} app(s)\n")

        else:
            # INDIVIDUAL MODE: Select per app
            ctx.textual.text("")
            ctx.textual.bold_primary_text("🏷️  Individual Selection - Select per app\n")

            for app in apps_with_builds:
                brand = app.get_brand()
                version_builds = builds_by_app.get(app.id, [])

                ctx.textual.text("")
                ctx.textual.bold_primary_text(f"🏷️  {brand} - {app.name}")
                ctx.textual.text("")

                # Format builds for selection
                option_items = []
                for build in version_builds:
                    value, title, description = format_build_for_selection(build)
                    option_items.append(
                        OptionItem(
                            value=value,
                            title=title,
                            description=description
                        )
                    )

                # Ask user to select a build
                selected_build_id = ctx.textual.ask_option(
                    f"Select build for {brand}:",
                    options=option_items,
                )

                if selected_build_id:
                    selected_builds[app.id] = selected_build_id
                    ctx.textual.success_text(f"✓ Build selected for {brand}\n")

        # Check if any builds were selected
        if not selected_builds:
            ctx.textual.warning_text("\n❌ No builds selected for any app\n")

            # Check if we had newly created versions (they won't have builds yet)
            existing_versions = ctx.get("existing_versions_by_app_id", {})
            apps_created = ctx.get("apps_to_create_versions", [])

            if apps_created:
                apps_created_names = [app['name'] for app in apps_created]
                ctx.textual.text("💡 Newly created versions don't have builds yet.")
                ctx.textual.text(f"   Apps without builds: {', '.join(apps_created_names)}\n")
                ctx.textual.text("📋 Next steps:")
                ctx.textual.text("   1. Upload builds to App Store Connect (via Xcode/Fastlane)")
                ctx.textual.text("   2. Run this workflow again to select builds and submit\n")

                choice = ctx.textual.ask_choice(
                    "What do you want to do?",
                    options=[
                        ChoiceOption(
                            value="exit",
                            label="Exit workflow (upload builds first)",
                            variant="primary"
                        ),
                        ChoiceOption(
                            value="skip",
                            label="Skip this step (continue without builds)",
                            variant="default"
                        ),
                    ]
                )

                if choice == "exit":
                    ctx.textual.text("\nWorkflow paused. Upload builds and run again.")
                    ctx.textual.end_step("cancelled")
                    from titan_cli.engine import Exit
                    return Exit("User chose to upload builds first")

            ctx.textual.end_step("skipped")
            return Skip("No builds available or selected")

        # Save selections to context
        ctx.set("selected_builds", selected_builds)

        # Update submission packages with build assignments
        packages_data = ctx.get("submission_packages", [])
        if packages_data:
            packages = [AppSubmissionPackage(**pkg_dict) for pkg_dict in packages_data]

            for package in packages:
                if package.app_id in selected_builds:
                    build_id = selected_builds[package.app_id]

                    # Find the BuildView object for this build_id
                    app_builds = builds_by_app.get(package.app_id, [])
                    build = next((b for b in app_builds if b.id == build_id), None)

                    if build:
                        package.assign_build(build)

            # Save updated packages
            ctx.data["submission_packages"] = [pkg.model_dump() for pkg in packages]

        # Show summary
        ctx.textual.text("")
        ctx.textual.success_text(f"✓ Selected builds for {len(selected_builds)} app(s)")

        ctx.textual.end_step("success")

        return Success(f"Selected {len(selected_builds)} builds")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["select_build_per_brand"]
