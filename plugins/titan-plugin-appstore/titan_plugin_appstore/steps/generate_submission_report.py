"""
Generate Submission Report Step - Show beautiful summary in TUI.
"""

from typing import Dict, List
from collections import defaultdict

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error

from ..models.view import AppSubmissionPackage
from ..models.version_states import get_state_description, is_editable


def generate_submission_report(ctx: WorkflowContext) -> WorkflowResult:
    """
    Display a beautiful summary of the submission workflow in the TUI.

    Shows:
    - Summary statistics in a panel
    - Per-brand detailed information
    - Build assignments
    - Release notes
    - Submission status and errors

    Inputs (from ctx.data):
        submission_packages (List[Dict]): All submission packages
        submitted_apps (List[str]): Successfully submitted app IDs
        failed_apps (List[Dict]): Failed submissions with errors
        version_string (str): Version string

    Returns:
        Success with summary
        Error if no data found
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Workflow Summary")

    try:
        # Get context data
        packages_data = ctx.get("submission_packages", [])
        submitted_apps = ctx.get("submitted_apps", [])
        failed_apps = ctx.get("failed_apps", [])
        version_string = ctx.get("version_string", "Unknown")

        if not packages_data:
            ctx.textual.error_text("No submission data found")
            ctx.textual.end_step("error")
            return Error("No submission data")

        # Reconstruct packages
        packages = [AppSubmissionPackage(**pkg_dict) for pkg_dict in packages_data]

        # Create failed_apps lookup for errors
        failed_lookup = {app["app_id"]: app["error"] for app in failed_apps}

        # Categorize packages and add status
        submitted_packages = []
        already_submitted_packages = []
        failed_packages = []
        ready_packages = []

        for package in packages:
            # Get state description
            state_desc = get_state_description(package.version_state)

            if package.app_id in submitted_apps:
                package.status_emoji = "✅"
                package.status_text = "Submitted Successfully"
                submitted_packages.append(package)
            elif package.app_id in failed_lookup:
                package.status_emoji = "❌"
                package.status_text = "Failed"
                package.error = failed_lookup[package.app_id]
                failed_packages.append(package)
            elif not is_editable(package.version_state):
                # Extract emoji from state description
                package.status_emoji = state_desc.split()[0]
                package.status_text = state_desc
                already_submitted_packages.append(package)
            elif not package.build_id:
                package.status_emoji = "⏭️"
                package.status_text = "No Build Assigned"
                ready_packages.append(package)
            else:
                package.status_emoji = "⚪"
                package.status_text = state_desc
                ready_packages.append(package)

        # Group all packages by brand for detailed view
        brands: Dict[str, List] = defaultdict(list)
        for package in packages:
            brands[package.brand].append(package)

        # Display summary header
        ctx.textual.text("")
        ctx.textual.text("")
        ctx.textual.panel("📊 WORKFLOW SUMMARY", panel_type="success")
        ctx.textual.text("")

        # Display statistics
        ctx.textual.bold_primary_text(f"Version: {version_string}")
        ctx.textual.text("")

        # Summary stats in columns
        total = len(packages)
        ctx.textual.text(f"📱 Total Apps:           {total}")
        ctx.textual.success_text(f"✅ Submitted:            {len(submitted_packages)}")
        ctx.textual.warning_text(f"⚠️  Already Submitted:    {len(already_submitted_packages)}")
        ctx.textual.error_text(f"❌ Failed:               {len(failed_packages)}")
        if ready_packages:
            ctx.textual.dim_text(f"⏭️  Not Submitted:        {len(ready_packages)}")

        # Show submitted apps
        if submitted_packages:
            ctx.textual.text("")
            ctx.textual.text("")
            ctx.textual.panel("✅ SUCCESSFULLY SUBMITTED", panel_type="success")
            ctx.textual.text("")
            for pkg in submitted_packages:
                ctx.textual.success_text(f"  ✅ {pkg.brand}")
                ctx.textual.dim_text(f"     Version: {pkg.version_string} | Build: {pkg.build_number}")
                if pkg.whats_new_es:
                    ctx.textual.dim_text(f"     🇪🇸 {pkg.whats_new_es[:60]}...")
                if pkg.whats_new_en:
                    ctx.textual.dim_text(f"     🇬🇧 {pkg.whats_new_en[:60]}...")
                ctx.textual.text("")

        # Show already submitted apps
        if already_submitted_packages:
            ctx.textual.text("")
            ctx.textual.panel("⚠️  ALREADY SUBMITTED", panel_type="warning")
            ctx.textual.text("")
            for pkg in already_submitted_packages:
                ctx.textual.warning_text(f"  ⚠️  {pkg.brand}")
                ctx.textual.dim_text(f"     Version: {pkg.version_string} | State: {pkg.version_state}")
                if pkg.build_number:
                    ctx.textual.dim_text(f"     Build: {pkg.build_number}")
                ctx.textual.text("")

        # Show failed apps
        if failed_packages:
            ctx.textual.text("")
            ctx.textual.panel("❌ FAILED SUBMISSIONS", panel_type="error")
            ctx.textual.text("")
            for pkg in failed_packages:
                ctx.textual.error_text(f"  ❌ {pkg.brand}")
                ctx.textual.dim_text(f"     Version: {pkg.version_string}")
                if hasattr(pkg, 'error') and pkg.error:
                    ctx.textual.text(f"     Error: {pkg.error}")
                ctx.textual.text("")

        # Show detailed by brand section
        ctx.textual.text("")
        ctx.textual.panel("📱 DETAILS BY BRAND", panel_type="info")
        ctx.textual.text("")

        for brand_name in sorted(brands.keys()):
            brand_packages = brands[brand_name]

            ctx.textual.text("")
            ctx.textual.bold_primary_text(f"🏷️  {brand_name}")
            ctx.textual.text("─" * 60)

            for pkg in brand_packages:
                ctx.textual.text(f"  {pkg.status_emoji} {pkg.status_text}")
                ctx.textual.dim_text(f"     App: {pkg.app_name}")
                ctx.textual.dim_text(f"     Version: {pkg.version_string} ({pkg.version_state})")

                if pkg.build_number:
                    ctx.textual.dim_text(f"     Build: {pkg.build_number}")

                if pkg.whats_new_es or pkg.whats_new_en:
                    ctx.textual.dim_text("     Release Notes:")
                    if pkg.whats_new_es:
                        ctx.textual.dim_text(f"       🇪🇸 {pkg.whats_new_es}")
                    if pkg.whats_new_en:
                        ctx.textual.dim_text(f"       🇬🇧 {pkg.whats_new_en}")

                if hasattr(pkg, 'error') and pkg.error:
                    ctx.textual.error_text(f"     ⚠️  {pkg.error}")

                ctx.textual.text("")

        # Final summary
        ctx.textual.text("")
        ctx.textual.panel("✨ WORKFLOW COMPLETED", panel_type="success")
        ctx.textual.text("")

        if submitted_packages:
            ctx.textual.success_text(f"🎉 Successfully submitted {len(submitted_packages)} app(s) for review!")

        if already_submitted_packages:
            ctx.textual.warning_text(f"ℹ️  {len(already_submitted_packages)} app(s) were already submitted/published")

        if failed_packages:
            ctx.textual.error_text(f"⚠️  {len(failed_packages)} app(s) failed - review errors above")

        ctx.textual.text("")
        ctx.textual.end_step("success")

        return Success(f"Workflow summary displayed")

    except Exception as e:
        error_msg = f"Failed to generate summary: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["generate_submission_report"]
