"""
Check and Setup Step - Verifies credentials or launches setup wizard automatically.
"""

import re
from pathlib import Path
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..credentials import CredentialsManager
from ..clients.appstore_client import AppStoreConnectClient
from ..exceptions import AppStoreConnectError


def check_and_setup_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Check if App Store Connect is configured.
    If not configured, automatically launches setup wizard.

    This step is transparent - it handles configuration verification
    and setup in a single step without exposing the wizard as separate.

    Outputs (saved to ctx.data):
        credentials_configured (bool): True if configured
        setup_completed (bool): True if setup ran successfully

    Returns:
        Success with configuration status
        Error if setup failed or was cancelled
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Check App Store Connect Configuration")

    try:
        is_configured = CredentialsManager.is_configured()

        if is_configured:
            # Credentials exist - show status
            issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()

            ctx.textual.success_text("✅ App Store Connect is configured")
            ctx.textual.text(f"  Key ID: {key_id}")
            ctx.textual.text(f"  Issuer ID: {issuer_id or '(Individual Key)'}")
            ctx.textual.text(f"  Private Key: {p8_path}")

            ctx.data["credentials_configured"] = True
            ctx.data["setup_completed"] = False  # Didn't run setup, was already configured

            ctx.textual.end_step("success")
            return Success("App Store Connect configured")

        else:
            # No credentials - run setup wizard automatically
            ctx.textual.text("")
            ctx.textual.warning_text("⚠️  App Store Connect not configured")
            ctx.textual.text("\nStarting configuration wizard...")
            ctx.textual.text("")

            # Run embedded setup wizard
            setup_result = _run_setup_wizard(ctx)

            if isinstance(setup_result, Error):
                ctx.textual.end_step("error")
                return setup_result

            ctx.data["credentials_configured"] = True
            ctx.data["setup_completed"] = True

            ctx.textual.end_step("success")
            return Success("App Store Connect configured successfully")

    except Exception as e:
        error_msg = f"Configuration check failed: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


def _run_setup_wizard(ctx: WorkflowContext) -> WorkflowResult:
    """
    Internal setup wizard - runs as part of check_and_setup_step.
    This is not exposed as a separate step.
    """
    try:
        ctx.textual.text("=" * 60)
        ctx.textual.text("  App Store Connect Configuration")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")

        # Step 1: Choose Key Type
        ctx.textual.text("📋 Step 1: Key Type")
        ctx.textual.text("")
        ctx.textual.text("Choose your API key type:")
        ctx.textual.text("")
        ctx.textual.text("  🏢 Team Key:")
        ctx.textual.text("     - Access to all apps in your team/organization")
        ctx.textual.text("     - Requires Issuer ID + Key ID + .p8 file")
        ctx.textual.text("")
        ctx.textual.text("  👤 Individual Key:")
        ctx.textual.text("     - Access limited to your personal account")
        ctx.textual.text("     - Only requires Key ID + .p8 file")
        ctx.textual.text("")

        from titan_cli.ui.tui.widgets import ChoiceOption

        key_type_choice = ctx.textual.ask_choice(
            "Select key type:",
            options=[
                ChoiceOption(
                    value="team",
                    label="Team Key (recommended)",
                    variant="primary"
                ),
                ChoiceOption(
                    value="individual",
                    label="Individual Key",
                    variant="default"
                )
            ]
        )

        is_individual_key = key_type_choice == "individual"

        # Step 1b: Get Issuer ID (only for Team Keys)
        issuer_id = None
        if not is_individual_key:
            ctx.textual.text("")
            ctx.textual.text("📋 Step 1b: Issuer ID")
            ctx.textual.text("")
            ctx.textual.text("Find your Issuer ID:")
            ctx.textual.text("  1. Go to App Store Connect → Users and Access → Keys")
            ctx.textual.text("  2. Look for 'Issuer ID' at the top of the page")
            ctx.textual.text("  3. Copy the UUID (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)")
            ctx.textual.text("")

            while not issuer_id:
                issuer_id_input = ctx.textual.ask_text(
                    "Issuer ID:",
                    default=""
                ).strip()

                if not issuer_id_input:
                    ctx.textual.error_text("❌ Issuer ID is required for Team Keys")
                    retry = ctx.textual.ask_yes_no("Try again?", default=True)
                    if not retry:
                        return Error("Setup cancelled")
                    continue

                # Validate UUID format
                if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', issuer_id_input, re.IGNORECASE):
                    issuer_id = issuer_id_input
                else:
                    ctx.textual.error_text(
                        "❌ Invalid Issuer ID format. Expected UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    )
                    retry = ctx.textual.ask_yes_no("Try again?", default=True)
                    if not retry:
                        return Error("Setup cancelled")

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
                    return Error("Setup cancelled")

        # Step 3: Get P8 file path
        ctx.textual.text("")
        ctx.textual.text("📋 Step 3: Private Key (.p8 file)")
        ctx.textual.text("")

        # Expected filename based on Key ID
        expected_p8_filename = f"AuthKey_{key_id}.p8"

        # Check in project's plugins/appstoreconnect/ directory first
        project_root = CredentialsManager._find_project_root()
        appstoreconnect_dir = project_root / "plugins" / "appstoreconnect"

        # Create directory if it doesn't exist
        appstoreconnect_dir.mkdir(parents=True, exist_ok=True)

        expected_p8_location = appstoreconnect_dir / expected_p8_filename

        ctx.textual.text(f"Looking for: plugins/appstoreconnect/{expected_p8_filename}")
        ctx.textual.text("")

        p8_file_path = None

        # Check if file exists in expected location
        if expected_p8_location.exists():
            ctx.textual.success_text(f"✓ Found .p8 file!")
            p8_file_path = str(expected_p8_location)
        else:
            # File not found - guide user to place it
            ctx.textual.error_text("❌ File not found")
            ctx.textual.text("")
            ctx.textual.text("Please place your .p8 private key file in:")
            ctx.textual.primary_text(f"  {expected_p8_location}")
            ctx.textual.text("")
            ctx.textual.text("How to get your .p8 file:")
            ctx.textual.text("  1. Go to App Store Connect → Users and Access → Keys")
            ctx.textual.text("  2. Download the key (if not already downloaded)")
            ctx.textual.text(f"  3. Rename the file to: {expected_p8_filename}")
            ctx.textual.text(f"  4. Move it to: plugins/appstoreconnect/")
            ctx.textual.text("")

            # Wait for user to place the file
            while not p8_file_path:
                ctx.textual.text("Press Enter when the file is in place...")
                ctx.textual.ask_text("", default="")

                # Check again
                if expected_p8_location.exists():
                    ctx.textual.success_text(f"✓ File found!")
                    p8_file_path = str(expected_p8_location)
                else:
                    ctx.textual.error_text(f"❌ File still not found at: {expected_p8_location}")
                    ctx.textual.text("")
                    retry = ctx.textual.ask_yes_no("Try again?", default=True)
                    if not retry:
                        return Error("Setup cancelled")

        # Step 4: Copy .p8 file to plugins/titan-plugin-appstore/.appstoreconnect/
        ctx.textual.text("")
        ctx.textual.text("📋 Step 4: Installing credentials...")

        project_root = CredentialsManager._find_project_root()

        # Create plugins/titan-plugin-appstore/.appstoreconnect/ directory
        appstore_dir = project_root / "plugins" / "titan-plugin-appstore" / ".appstoreconnect"
        appstore_dir.mkdir(parents=True, exist_ok=True)

        # Create .gitignore to protect credentials
        gitignore_path = appstore_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_content = """# App Store Connect Credentials
# DO NOT COMMIT THESE FILES
*.p8
credentials.json
*.mobileprovision
"""
            gitignore_path.write_text(gitignore_content)
            ctx.textual.success_text("✓ Created .gitignore to protect credentials")

        # Move p8 file to .appstoreconnect/ directory
        import shutil
        p8_filename = Path(p8_file_path).name
        dest_p8_path = appstore_dir / p8_filename

        # Only move if source and destination are different
        if Path(p8_file_path) != dest_p8_path:
            shutil.move(p8_file_path, dest_p8_path)
            ctx.textual.success_text(f"✓ Moved .p8 file to .appstoreconnect/")
        else:
            ctx.textual.success_text(f"✓ Using .p8 file from .appstoreconnect/")

        # Relative path for credentials (from project root)
        relative_p8_path = f"plugins/titan-plugin-appstore/.appstoreconnect/{p8_filename}"

        # Step 4: Get Vendor Number (optional for Sales Reports)
        ctx.textual.text("")
        ctx.textual.text("📋 Step 4: Vendor Number (Optional)")
        ctx.textual.text("")
        ctx.textual.text("Vendor Number is needed for Sales Reports (propagation metrics).")
        ctx.textual.text("You can find it in App Store Connect → Agreements, Tax, and Banking")
        ctx.textual.text("")
        ctx.textual.text("Format: 8-digit number (e.g., 80012345)")
        ctx.textual.text("")

        vendor_number = None
        vendor_input = ctx.textual.ask_text(
            "Vendor Number (leave empty to skip):",
            default=""
        ).strip()

        if vendor_input:
            # Validate format (8 digits)
            if re.match(r'^\d{8}$', vendor_input):
                vendor_number = vendor_input
                ctx.textual.success_text(f"✓ Vendor Number: {vendor_number}")
            else:
                ctx.textual.error_text("⚠️  Invalid format (expected 8 digits)")
                ctx.textual.text("   You can add it later by re-running setup")
        else:
            ctx.textual.text("⚠️  Skipped - Sales Reports will not be available")
            ctx.textual.text("   Performance Metrics will still work for crash data")

        # Step 5: Save credentials
        CredentialsManager.save_credentials(
            key_id=key_id,
            issuer_id=issuer_id if issuer_id else None,
            private_key_path=relative_p8_path,
            vendor_number=vendor_number
        )
        ctx.textual.success_text("✓ Saved credentials to plugins/titan-plugin-appstore/.appstoreconnect/credentials.json")

        # Step 6: Test connection
        ctx.textual.text("")
        ctx.textual.text("📋 Step 6: Testing connection...")
        ctx.textual.text("")

        try:
            from titan_cli.core.result import ClientSuccess, ClientError

            client = AppStoreConnectClient(
                key_id=key_id,
                issuer_id=issuer_id if issuer_id else None,
                private_key_path=str(dest_p8_path)
            )

            # Test by listing apps
            apps_result = client.list_apps()

            match apps_result:
                case ClientSuccess(data=apps):
                    ctx.textual.success_text(f"✅ Connection successful!")
                    ctx.textual.text(f"   Found {len(apps)} app(s) in your account")

                    if apps:
                        ctx.textual.text("\n   Apps:")
                        for app in apps[:5]:  # Show first 5
                            ctx.textual.text(f"     - {app.display_name()}")
                        if len(apps) > 5:
                            ctx.textual.text(f"     ... and {len(apps) - 5} more")

                case ClientError(error=err):
                    ctx.textual.error_text(f"⚠️  Connection test failed: {err}")
                    ctx.textual.text("\nCredentials saved, but connection couldn't be verified.")
                    ctx.textual.text("Please check your credentials are correct.")

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
        if vendor_number:
            ctx.textual.text(f"  Vendor Number: {vendor_number}")
        ctx.textual.text("")
        ctx.textual.success_text("✅ Ready to use App Store Connect API!")
        if vendor_number:
            ctx.textual.text("   • Performance Metrics: Enabled (crash data)")
            ctx.textual.text("   • Sales Reports: Enabled (propagation data)")
        else:
            ctx.textual.text("   • Performance Metrics: Enabled (crash data)")
            ctx.textual.text("   • Sales Reports: Disabled (no vendor number)")
        ctx.textual.text("")

        return Success("App Store Connect configured successfully")

    except Exception as e:
        return Error(f"Setup wizard failed: {str(e)}")


__all__ = ["check_and_setup_step"]
