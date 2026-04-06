"""
Create Version Step - Create new app version in App Store Connect.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError

from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager
from ..models.view import VersionCreationRequest, AppSubmissionPackage, AppView


def create_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create a new app version in App Store Connect.

    Inputs (from ctx.data):
        app_id (str): App ID
        version_string (str): Version number
        app_name (str, optional): App name for display

    Params (from workflow params, accessed via ctx.get()):
        platform (str): Platform (default: "IOS")
        release_type (str): Release type (default: "MANUAL")
        copyright (str, optional): Copyright text
        earliest_release_date (str, optional): ISO 8601 date

    Outputs (saved to ctx.data):
        created_version (Dict): Created version details
        version_id (str): ID of created version

    Returns:
        Success with created version details
        Error if creation fails
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Create App Store Version")

    try:
        # Check if we have apps with existing versions (from prompt_version_step)
        existing_versions_by_app_id = ctx.get("existing_versions_by_app_id", {})
        apps_to_create = ctx.get("apps_to_create_versions", [])

        # If no apps_to_create, fall back to single app mode (backward compatibility)
        if not apps_to_create:
            app_id = ctx.get("app_id")
            version_string = ctx.get("version_string")
            app_name = ctx.get("app_name", "Unknown App")

            if not app_id or not version_string:
                ctx.textual.error_text("app_id and version_string required")
                ctx.textual.end_step("error")
                return Error("Missing required context data. Run previous steps first.")

            # Convert to list format for uniform processing
            apps_to_create = [{"id": app_id, "name": app_name}]

        version_string = ctx.get("version_string")
        if not version_string:
            ctx.textual.error_text("version_string required")
            ctx.textual.end_step("error")
            return Error("Missing version_string. Run prompt_version_step first.")

        # Get params (from ctx.data, set by workflow executor)
        platform = ctx.get("platform", "IOS")
        release_type = ctx.get("release_type", "MANUAL")
        copyright_text = ctx.get("copyright")
        earliest_release_date = ctx.get("earliest_release_date")

        # Load credentials and initialize client
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()
        if not key_id or not p8_path:
            ctx.textual.error_text("Credentials not configured")
            ctx.textual.end_step("error")
            return Error("Credentials not configured")

        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Show step header
        total_apps = len(existing_versions_by_app_id) + len(apps_to_create)
        ctx.textual.text(f"\n📦 STEP 1: Creating Versions")
        ctx.textual.text(f"   • {len(existing_versions_by_app_id)} app(s) already have versions (will use existing)")
        ctx.textual.text(f"   • {len(apps_to_create)} app(s) need new versions (creating now...)\n")

        if not apps_to_create:
            ctx.textual.success_text("✓ All apps have existing versions, skipping creation\n")

        # Create versions for apps that don't have them
        created_versions_map = {}
        for app_dict in apps_to_create:
            app_id = app_dict["id"]
            app_name = app_dict["name"]

            # Build request
            request = VersionCreationRequest(
                app_id=app_id,
                version_string=version_string,
                platform=platform,
                release_type=release_type,
                copyright=copyright_text,
                earliest_release_date=earliest_release_date,
            )

            # Display creation details
            ctx.textual.text(f"Creating version for: {app_name}")
            ctx.textual.text(f"  Version: {version_string}")

            # Create version
            version_result = client.create_version(request)

            # Use pattern matching for ClientResult
            match version_result:
                case ClientSuccess(data=created_version):
                    created_versions_map[app_id] = {
                        "id": created_version.id,
                        "version_string": created_version.version_string,
                        "platform": created_version.platform,
                        "state": created_version.state,
                        "release_type": created_version.release_type,
                    }

                    ctx.textual.success_text(f"  ✓ Created version {version_string}")
                    ctx.textual.dim_text(f"    Version ID: {created_version.id}")
                    ctx.textual.text("")

                case ClientError(error_message=err, error_code=code):
                    # Handle specific error types
                    if "conflict" in err.lower() or "already exists" in err.lower():
                        ctx.textual.error_text(f"  ❌ Version conflict: {err}")
                    elif code == "VALIDATION_ERROR":
                        ctx.textual.error_text(f"  ❌ Validation error: {err}")
                    else:
                        ctx.textual.error_text(f"  ❌ Failed: {err}")
                    ctx.textual.text("")
                    # Continue with other apps instead of failing completely

        # Combine created versions and existing versions
        all_versions_map = {}
        all_versions_map.update(existing_versions_by_app_id)
        all_versions_map.update(created_versions_map)

        # Save combined map to context for following steps
        ctx.data["versions_by_app_id"] = all_versions_map

        # For backward compatibility, save first version as active
        if all_versions_map:
            first_version = next(iter(all_versions_map.values()))
            ctx.data["version_id"] = first_version["id" if "id" in first_version else "version_id"]
            ctx.data["active_version_id"] = first_version["id" if "id" in first_version else "version_id"]

        # Create AppSubmissionPackage for each app
        # Get selected_apps to reconstruct AppView
        selected_apps_data = ctx.get("selected_apps", [])
        submission_packages = []

        for app_dict in selected_apps_data:
            app_id = app_dict["id"]
            version_info = all_versions_map.get(app_id)

            if version_info:
                # Reconstruct AppView
                app_view = AppView(
                    id=app_id,
                    name=app_dict["name"],
                    bundle_id=app_dict.get("bundle_id", ""),
                    sku=app_dict.get("sku", ""),
                    primary_locale="en-US"
                )

                # Create submission package
                package = AppSubmissionPackage(
                    app_id=app_id,
                    app_name=app_dict["name"],
                    brand=app_view.get_brand(),
                    version_id=version_info.get("id") or version_info.get("version_id"),
                    version_string=version_info.get("version_string"),
                    version_state=version_info.get("state", "PREPARE_FOR_SUBMISSION"),
                )

                submission_packages.append(package)

        # Save packages to context (as dicts for serialization)
        ctx.data["submission_packages"] = [pkg.model_dump() for pkg in submission_packages]

        # Show summary
        ctx.textual.success_text(f"\n✓ Version creation completed!")
        ctx.textual.text(f"  • {len(created_versions_map)} newly created")
        ctx.textual.text(f"  • {len(existing_versions_by_app_id)} existing")
        ctx.textual.text(f"  • {len(all_versions_map)} total versions ready")
        ctx.textual.text(f"  • {len(submission_packages)} submission packages prepared")

        ctx.textual.text(f"\n⏭️  Next: Configure all {len(all_versions_map)} app(s) (builds, release notes, submit)\n")

        ctx.textual.end_step("success")

        return Success(f"Processed {len(all_versions_map)} versions ({len(created_versions_map)} created, {len(existing_versions_by_app_id)} existing)")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(f"❌ {error_msg}")
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["create_version_step"]
