"""
Submit For Review Step - Submit selected apps with builds to App Store Review.
"""

from typing import Dict, List, Tuple
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Exit
from titan_cli.core.result import ClientSuccess, ClientError

from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager
from ..models.view import AppSubmissionPackage
from ..models.version_states import (
    is_editable,
    can_submit,
    can_update_metadata,
    get_state_description,
    NON_EDITABLE_STATES,
)


def submit_for_review(ctx: WorkflowContext) -> WorkflowResult:
    """
    Submit each app with its selected build to App Store Review.

    For each app:
    1. Update What's New text in Spanish (es-ES)
    2. Update What's New text in English (en-US)
    3. Assign selected build to active version
    4. Submit version for review

    Continues even if individual apps fail (on_error: continue behavior).

    Inputs (from ctx.data):
        selected_apps (List[Dict]): Selected apps
        selected_builds (Dict[str, str]): Mapping of app_id -> build_id
        active_version_id (str): Version ID to submit

    Outputs (saved to ctx.data):
        submitted_apps (List[str]): List of successfully submitted app IDs
        failed_apps (List[Dict]): List of failed submissions with errors

    Returns:
        Success with summary of submitted/failed apps
        Exit if user cancels final confirmation
        Error if no apps to submit or missing context data
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Submit for Review")

    try:
        # Get submission packages from context
        packages_data = ctx.get("submission_packages", [])

        if not packages_data:
            ctx.textual.error_text("No submission packages found")
            ctx.textual.end_step("error")
            return Error("No submission packages")

        # Reconstruct packages from dicts
        packages = [AppSubmissionPackage(**pkg_dict) for pkg_dict in packages_data]

        # Separate packages by state using state helpers
        packages_ready = [
            pkg for pkg in packages
            if pkg.build_id and can_submit(pkg.version_state)
        ]
        packages_already_submitted = [
            pkg for pkg in packages
            if not is_editable(pkg.version_state)
        ]
        packages_no_build = [
            pkg for pkg in packages
            if not pkg.build_id and is_editable(pkg.version_state)
        ]

        # Show submission summary
        ctx.textual.text("")
        ctx.textual.bold_primary_text("📋 Submission Summary")
        ctx.textual.text("")

        if packages_ready:
            ctx.textual.success_text(f"✅ Ready to submit ({len(packages_ready)} app(s)):")
            for package in packages_ready:
                ctx.textual.text(f"  • {package.brand}: v{package.version_string} - Build {package.build_number}")

        if packages_already_submitted:
            ctx.textual.text("")
            ctx.textual.warning_text(f"⚠️ Already submitted/published ({len(packages_already_submitted)} app(s)):")
            for package in packages_already_submitted:
                state_desc = get_state_description(package.version_state)
                ctx.textual.dim_text(f"  • {package.brand}: v{package.version_string} - {state_desc}")

        if packages_no_build:
            ctx.textual.text("")
            ctx.textual.dim_text(f"⏭️ Skipped (no build) ({len(packages_no_build)} app(s)):")
            for package in packages_no_build:
                ctx.textual.dim_text(f"  • {package.brand}: v{package.version_string}")

        ctx.textual.text("")

        if not packages_ready:
            ctx.textual.warning_text("❌ No apps ready to submit")
            ctx.textual.text("")
            ctx.textual.text("All apps are either already submitted or don't have builds assigned.")
            ctx.textual.end_step("skipped")
            return Success("No apps to submit (all already submitted or no builds)")

        # Final confirmation
        if packages_ready:
            confirmed = ctx.textual.ask_confirm(
                f"Submit {len(packages_ready)} app(s) for App Store Review?",
                default=False,  # Default to No for safety
            )
        else:
            confirmed = False

        if not confirmed:
            ctx.textual.warning_text("Cancelled by user")
            ctx.textual.end_step("cancelled")
            return Exit("User cancelled submission")

        # Load credentials and initialize client
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()

        if not key_id or not p8_path:
            ctx.textual.error_text("App Store Connect credentials not configured")
            ctx.textual.end_step("error")
            return Error("Credentials not configured")

        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Track results
        submitted_apps: List[str] = []
        failed_apps: List[Dict[str, str]] = []

        # Submit each app
        ctx.textual.text("")
        ctx.textual.bold_primary_text("🚀 Submitting Apps...")
        ctx.textual.text("")

        for package in packages_ready:
            ctx.textual.text("")
            ctx.textual.bold_text(f"Processing {package.brand} - {package.app_name}...")
            state_desc = get_state_description(package.version_state)
            ctx.textual.dim_text(f"Version: {package.version_string} - {state_desc}")
            ctx.textual.dim_text(f"Build: {package.build_number} (ID: {package.build_id[:8]}...)")

            # Double-check state is submittable (should already be filtered)
            if not can_submit(package.version_state):
                state_desc = get_state_description(package.version_state)
                ctx.textual.warning_text(f"⚠️ {package.brand} skipped - {state_desc}")
                ctx.textual.dim_text("   This version cannot be submitted")
                failed_apps.append({
                    "app_id": package.app_id,
                    "app_name": package.app_name,
                    "error": f"Version in non-submittable state: {package.version_state}"
                })
                continue

            # Check if ready to submit
            if not package.is_ready_to_submit and package.readiness_errors:
                ctx.textual.warning_text(f"⚠️ {package.brand} not ready: {', '.join(package.readiness_errors)}")
                failed_apps.append({
                    "app_id": package.app_id,
                    "app_name": package.app_name,
                    "error": f"Not ready: {', '.join(package.readiness_errors)}"
                })
                continue

            try:
                # Step 1: Update What's New (only if state allows metadata updates)
                if can_update_metadata(package.version_state):
                    ctx.textual.dim_text("Updating release notes (ES)...")
                    result_es = client.update_whats_new(
                        package.version_id, "es-ES", package.whats_new_es
                    )

                    match result_es:
                        case ClientSuccess():
                            ctx.textual.dim_text("✓ Spanish release notes updated")
                        case ClientError(error_message=err):
                            if "cannot be edited at this time" in err.lower():
                                ctx.textual.warning_text("⚠️ Release notes locked (version may be in review)")
                            else:
                                raise Exception(f"Failed to update ES release notes: {err}")

                    # Step 2: Update What's New for en-US
                    ctx.textual.dim_text("Updating release notes (EN)...")
                    result_en = client.update_whats_new(
                        package.version_id, "en-US", package.whats_new_en
                    )

                    match result_en:
                        case ClientSuccess():
                            ctx.textual.dim_text("✓ English release notes updated")
                        case ClientError(error_message=err):
                            if "cannot be edited at this time" in err.lower():
                                ctx.textual.warning_text("⚠️ Release notes locked (version may be in review)")
                            else:
                                raise Exception(f"Failed to update EN release notes: {err}")
                else:
                    ctx.textual.dim_text("⏭️  Skipping release notes (version state doesn't allow editing)")

                # Step 3: Assign build to version
                ctx.textual.dim_text(f"Assigning build {package.build_number}...")
                result_assign = client.assign_build_to_version(package.version_id, package.build_id)

                match result_assign:
                    case ClientSuccess():
                        ctx.textual.dim_text("✓ Build assigned")
                    case ClientError(error_message=err):
                        raise Exception(f"Failed to assign build: {err}")

                # Step 4: Submit for review
                ctx.textual.dim_text("Submitting for review...")
                result_submit = client.submit_for_review(package.version_id)

                match result_submit:
                    case ClientSuccess():
                        ctx.textual.success_text(f"✅ {package.brand} submitted successfully!")
                        submitted_apps.append(package.app_id)
                    case ClientError(error_message=err):
                        if "does not allow 'CREATE'" in err:
                            raise Exception(f"Version already submitted or in review")
                        else:
                            raise Exception(f"Failed to submit: {err}")

            except Exception as e:
                error_msg = str(e)
                ctx.textual.error_text(f"❌ {package.brand} failed: {error_msg}")
                failed_apps.append({
                    "app_id": package.app_id,
                    "app_name": package.app_name,
                    "error": error_msg
                })

        # Save results to context
        ctx.set("submitted_apps", submitted_apps)
        ctx.set("failed_apps", failed_apps)

        # Show final summary
        ctx.textual.text("")
        ctx.textual.panel("Submission Complete", panel_type="success")
        ctx.textual.text("")

        if submitted_apps:
            ctx.textual.success_text(f"✅ Successfully submitted: {len(submitted_apps)} app(s)")

        if failed_apps:
            ctx.textual.warning_text(f"❌ Failed: {len(failed_apps)} app(s)")
            for failed in failed_apps:
                ctx.textual.dim_text(f"  • {failed['app_name']}: {failed['error']}")

        ctx.textual.end_step("success")

        return Success(
            f"Submitted {len(submitted_apps)} apps, {len(failed_apps)} failed"
        )

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["submit_for_review"]
