"""
Setup Wizard Step - Interactive configuration wizard for App Store Connect.
"""

import re
from pathlib import Path
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error

from ..credentials import CredentialsManager
from ..clients.appstore_client import AppStoreConnectClient
from ..exceptions import AppStoreConnectError


def setup_wizard_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Interactive setup wizard for App Store Connect credentials.

    Inputs (from ctx.data):
        needs_setup (bool, optional): If True, forces setup

    Outputs (saved to ctx.data):
        setup_completed (bool): True if setup completed successfully

    Returns:
        Success if credentials configured and verified
        Error if setup failed or was cancelled
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    # Check if setup is needed
    needs_setup = ctx.get("needs_setup", False)
    if not needs_setup and CredentialsManager.is_configured():
        ctx.data["setup_completed"] = True
        return Success("Already configured")

    ctx.textual.begin_step("App Store Connect Setup Wizard")

    try:
        ctx.textual.text("=" * 60)
        ctx.textual.text("  App Store Connect Configuration")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")

        # Step 1: Get Issuer ID (optional for Individual Keys)
        ctx.textual.text("📋 Step 1: Issuer ID")
        ctx.textual.text("")
        ctx.textual.text("For Team Keys: Enter your Issuer ID")
        ctx.textual.text("For Individual Keys: Leave empty or press Enter")
        ctx.textual.text("")

        issuer_id = ctx.textual.ask_text(
            "Issuer ID (optional):",
            default=""
        ).strip()

        is_individual_key = not issuer_id

        # Step 2: Get Key ID
        ctx.textual.text("")
        ctx.textual.text("📋 Step 2: Key ID")
        ctx.textual.text("")

        key_id = None
        while not key_id:
            key_id_input = ctx.textual.ask_text(
                "Key ID (e.g., ABC123XYZ):",
                default=""
            ).strip()

            if not key_id_input:
                ctx.textual.error_text("❌ Key ID is required")
                continue

            # Validate format (alphanumeric, typically 10 chars)
            if re.match(r'^[A-Z0-9]{8,12}$', key_id_input):
                key_id = key_id_input
            else:
                ctx.textual.error_text(
                    "❌ Invalid Key ID format. Expected format: ABC123XYZ (8-12 alphanumeric)"
                )
                retry = ctx.textual.ask_yes_no("Try again?", default=True)
                if not retry:
                    ctx.textual.end_step("error")
                    return Error("Setup cancelled")

        # Step 3: Get P8 file path
        ctx.textual.text("")
        ctx.textual.text("📋 Step 3: Private Key (.p8 file)")
        ctx.textual.text("")
        ctx.textual.text("Enter the path to your downloaded .p8 file")
        ctx.textual.text("Example: ~/Downloads/AuthKey_ABC123XYZ.p8")
        ctx.textual.text("")

        p8_file_path = None
        while not p8_file_path:
            p8_input = ctx.textual.ask_text(
                "Path to .p8 file:",
                default=f"~/Downloads/AuthKey_{key_id}.p8"
            ).strip()

            # Expand ~ to home directory
            expanded_path = Path(p8_input).expanduser()

            if not expanded_path.exists():
                ctx.textual.error_text(f"❌ File not found: {expanded_path}")
                retry = ctx.textual.ask_yes_no("Try again?", default=True)
                if not retry:
                    ctx.textual.end_step("error")
                    return Error("Setup cancelled")
                continue

            if not str(expanded_path).endswith('.p8'):
                ctx.textual.error_text("❌ File must be a .p8 private key file")
                retry = ctx.textual.ask_yes_no("Try again?", default=True)
                if not retry:
                    ctx.textual.end_step("error")
                    return Error("Setup cancelled")
                continue

            p8_file_path = str(expanded_path)

        # Step 4: Copy .p8 file to .appstore_connect/
        ctx.textual.text("")
        ctx.textual.text("📋 Step 4: Installing credentials...")

        project_root = CredentialsManager._find_project_root()
        appstore_dir = project_root / ".appstore_connect"
        appstore_dir.mkdir(parents=True, exist_ok=True)

        # Copy p8 file
        import shutil
        p8_filename = Path(p8_file_path).name
        dest_p8_path = appstore_dir / p8_filename

        shutil.copy2(p8_file_path, dest_p8_path)
        ctx.textual.success_text(f"✓ Copied .p8 file to {dest_p8_path}")

        # Relative path for credentials
        relative_p8_path = f".appstore_connect/{p8_filename}"

        # Step 5: Save credentials
        CredentialsManager.save_credentials(
            key_id=key_id,
            issuer_id=issuer_id if issuer_id else None,
            private_key_path=relative_p8_path
        )
        ctx.textual.success_text("✓ Saved credentials to .appstore_connect/credentials.json")

        # Step 6: Test connection
        ctx.textual.text("")
        ctx.textual.text("📋 Step 5: Testing connection...")
        ctx.textual.text("")

        try:
            client = AppStoreConnectClient(
                key_id=key_id,
                issuer_id=issuer_id if issuer_id else None,
                private_key_path=str(dest_p8_path)
            )

            # Test by listing apps
            apps = client.list_apps()

            ctx.textual.success_text(f"✅ Connection successful!")
            ctx.textual.text(f"   Found {len(apps)} app(s) in your account")

            if apps:
                ctx.textual.text("\n   Apps:")
                for app in apps[:5]:  # Show first 5
                    ctx.textual.text(f"     - {app.display_name()}")
                if len(apps) > 5:
                    ctx.textual.text(f"     ... and {len(apps) - 5} more")

        except AppStoreConnectError as e:
            ctx.textual.error_text(f"⚠️  Connection test failed: {str(e)}")
            ctx.textual.text("\nCredentials saved, but connection couldn't be verified.")
            ctx.textual.text("Please check your credentials are correct.")

        # Summary
        ctx.textual.text("")
        ctx.textual.text("=" * 60)
        ctx.textual.text("  Configuration Complete")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")
        ctx.textual.text(f"  Key Type: {'Individual' if is_individual_key else 'Team'}")
        ctx.textual.text(f"  Key ID: {key_id}")
        if not is_individual_key:
            ctx.textual.text(f"  Issuer ID: {issuer_id}")
        ctx.textual.text(f"  Private Key: {relative_p8_path}")
        ctx.textual.text("")
        ctx.textual.success_text("✅ Ready to use App Store Connect API!")

        ctx.data["setup_completed"] = True
        ctx.textual.end_step("success")

        return Success("App Store Connect configured successfully")

    except Exception as e:
        error_msg = f"Setup wizard failed: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["setup_wizard_step"]
