"""
Show What's New Preview Step - Display preview of release notes before submission.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Exit, Error
from ..operations.build_operations import prepare_whats_new_previews, WHATS_NEW_TEXT_ES, WHATS_NEW_TEXT_EN
from ..models.view import AppView, AppSubmissionPackage


def show_whats_new_preview(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show preview of What's New text for all selected brands.

    Displays the standard texts in Spanish and English that will be
    used for all apps, and asks for user confirmation before proceeding.

    Inputs (from ctx.data):
        selected_apps (List[Dict]): Selected apps from previous step

    Outputs (saved to ctx.data):
        whats_new_confirmed (bool): True if user confirmed

    Returns:
        Success if user confirms
        Exit if user cancels
        Error if no apps selected
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Preview Release Notes")

    try:
        # Get selected apps from context
        selected_apps_data = ctx.get("selected_apps")

        if not selected_apps_data:
            ctx.textual.error_text("No apps selected in previous step")
            ctx.textual.end_step("error")
            return Error("No apps selected")

        # Convert dict data back to AppView objects for operations
        selected_apps = [
            AppView(
                id=app["id"],
                name=app["name"],
                bundle_id=app["bundle_id"],
                sku=app["sku"],
                primary_locale="en-US",  # Default, not critical for this step
            )
            for app in selected_apps_data
        ]

        # Prepare preview data
        previews = prepare_whats_new_previews(selected_apps)

        # Display preview table
        ctx.textual.text("")
        ctx.textual.bold_primary_text("📝 What's New in This Version")
        ctx.textual.text("")
        ctx.textual.dim_text(
            "The following text will be added to each app in both languages:"
        )
        ctx.textual.text("")

        # Create table with brand, ES text, EN text
        table_data = []
        for preview in previews:
            brand, text_es, text_en = preview.format_table_row()
            table_data.append([brand, text_es, text_en])

        # Display as panel/table
        ctx.textual.panel(
            "Release Notes Preview",
            panel_type="info",
        )

        for brand, text_es, text_en in table_data:
            ctx.textual.text("")
            ctx.textual.bold_text(f"🏷️  {brand}")
            ctx.textual.text(f"   🇪🇸 ES: {text_es}")
            ctx.textual.text(f"   🇬🇧 EN: {text_en}")

        ctx.textual.text("")

        # Ask for confirmation
        confirmed = ctx.textual.ask_confirm(
            "Do you want to proceed with these release notes?",
            default=True,
        )

        if not confirmed:
            ctx.textual.warning_text("Cancelled by user")
            ctx.textual.end_step("cancelled")
            return Exit("User cancelled workflow")

        # Save confirmation to context
        ctx.set("whats_new_confirmed", True)

        # Update submission packages with release notes
        packages_data = ctx.get("submission_packages", [])
        if packages_data:
            packages = [AppSubmissionPackage(**pkg_dict) for pkg_dict in packages_data]

            for package in packages:
                package.set_whats_new(WHATS_NEW_TEXT_ES, WHATS_NEW_TEXT_EN)

            # Save updated packages
            ctx.data["submission_packages"] = [pkg.model_dump() for pkg in packages]

        ctx.textual.success_text("✓ Release notes confirmed")
        ctx.textual.end_step("success")

        return Success("Release notes confirmed")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["show_whats_new_preview"]
