"""
Show Diagnostics Step - Display crashes and hangs without Xcode.

Useful for CI/CD environments where Xcode Organizer is not available.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..clients.appstore_client import AppStoreConnectClient
from ..operations.diagnostics_operations import DiagnosticsOperations
from ..credentials import CredentialsManager
from titan_cli.core.result import ClientSuccess, ClientError


def show_diagnostics_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show diagnostics (crashes and hangs) for a version.

    This step provides access to crash and hang data without Xcode Organizer,
    perfect for CI/CD environments.

    Inputs (from ctx.data):
        - app_id: App ID
        - version_string: Version to analyze

    Outputs (saved to ctx.data):
        - diagnostics_summary: Complete diagnostics data
        - top_hangs: Top 5 hang signatures
        - top_crashes: Top 5 crash signatures

    Returns:
        Success with diagnostics info
        Error if retrieval fails
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Show Diagnostics")

    try:
        app_id = ctx.data.get("app_id")
        version_string = ctx.data.get("version_string")

        if not all([app_id, version_string]):
            ctx.textual.error_text("Missing required inputs: app_id, version_string")
            ctx.textual.end_step("error")
            return Error("Missing context data")

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

        # Initialize diagnostics operations
        diag_ops = DiagnosticsOperations(client)

        ctx.textual.text("=" * 60)
        ctx.textual.text(f"Diagnostics for version: {version_string}")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")

        # Get diagnostics summary
        ctx.textual.text("📊 Fetching diagnostics data...")

        summary_result = diag_ops.get_diagnostics_summary(app_id, version_string)

        match summary_result:
            case ClientSuccess(data=summary):
                # Store in context
                ctx.data["diagnostics_summary"] = summary
                ctx.data["top_hangs"] = summary.get("top_hangs", [])
                ctx.data["top_crashes"] = summary.get("top_crashes", [])

                # Display metrics summary
                metrics = summary.get("metrics", {})

                if metrics:
                    ctx.textual.text("")
                    ctx.textual.text("📈 METRICS SUMMARY")
                    ctx.textual.text("-" * 60)
                    ctx.textual.text(f"  Crash Rate:    {metrics.get('crash_rate', 0):.4f}%")
                    ctx.textual.text(f"  Hang Rate:     {metrics.get('hang_rate', 0):.4f}%")
                    ctx.textual.text(f"  Terminations:  {metrics.get('terminations', 0):,}")
                    ctx.textual.text(f"  Hangs:         {metrics.get('hangs', 0):,}")
                    ctx.textual.text("")

                # Display hang reports
                top_hangs = summary.get("top_hangs", [])

                if top_hangs and summary.get("hang_reports_available"):
                    ctx.textual.text("⏱️  TOP HANGS (Most Frequent)")
                    ctx.textual.text("-" * 60)

                    for i, hang in enumerate(top_hangs, 1):
                        ctx.textual.text(f"{i}. Signature: {hang.get('signature', 'Unknown')}")
                        ctx.textual.text(f"   Frequency: {hang.get('frequency', 0)} occurrences")
                        ctx.textual.text(f"   Duration:  {hang.get('duration', 0)}ms avg")
                        ctx.textual.text(f"   Devices:   {hang.get('affected_devices', 0)}")

                        # Show partial stack trace if available
                        stack = hang.get("stack_trace", [])
                        if stack:
                            ctx.textual.text("   Stack:")
                            for frame in stack[:3]:  # First 3 frames
                                ctx.textual.text(f"     {frame}")
                        ctx.textual.text("")

                elif not summary.get("hang_reports_available"):
                    ctx.textual.warning_text("⚠️  Detailed hang reports not available via API")
                    ctx.textual.text("")
                    ctx.textual.text("   To view detailed hang reports:")
                    ctx.textual.text("   1. [link=https://appstoreconnect.apple.com]Open App Store Connect[/link]")
                    ctx.textual.text("   2. Your App → TestFlight or App Store")
                    ctx.textual.text("   3. Sidebar: Crashes & Hangs → Hangs tab")
                    ctx.textual.text("   4. Filter by version: " + version_string)
                    ctx.textual.text("")

                # Display crash reports
                top_crashes = summary.get("top_crashes", [])

                if top_crashes and summary.get("crash_reports_available"):
                    ctx.textual.text("💥 TOP CRASHES (Most Frequent)")
                    ctx.textual.text("-" * 60)

                    for i, crash in enumerate(top_crashes, 1):
                        ctx.textual.text(f"{i}. Signature: {crash.get('signature', 'Unknown')}")
                        ctx.textual.text(f"   Type:      {crash.get('crash_type', 'Unknown')}")
                        ctx.textual.text(f"   Frequency: {crash.get('frequency', 0)} occurrences")
                        ctx.textual.text(f"   Devices:   {crash.get('affected_devices', 0)}")

                        # Show partial stack trace
                        stack = crash.get("stack_trace", [])
                        if stack:
                            ctx.textual.text("   Stack:")
                            for frame in stack[:3]:
                                ctx.textual.text(f"     {frame}")
                        ctx.textual.text("")

                elif not summary.get("crash_reports_available"):
                    ctx.textual.warning_text("⚠️  Detailed crash reports not available via API")
                    ctx.textual.text("")
                    ctx.textual.text("   To view detailed crash reports:")
                    ctx.textual.text("   1. [link=https://appstoreconnect.apple.com]Open App Store Connect[/link]")
                    ctx.textual.text("   2. Your App → TestFlight or App Store")
                    ctx.textual.text("   3. Sidebar: Crashes & Hangs → Crashes tab")
                    ctx.textual.text("   4. Filter by version: " + version_string)
                    ctx.textual.text("")

                # Summary
                ctx.textual.text("=" * 60)
                ctx.textual.text("📋 NEXT STEPS")
                ctx.textual.text("-" * 60)

                if metrics.get("hang_rate", 0) > 10.0:
                    ctx.textual.error_text("🔴 Critical hang rate detected!")
                    ctx.textual.text("   → Investigate main thread blocking operations")
                    ctx.textual.text("   → Check for synchronous network calls")
                    ctx.textual.text("   → Review Core Data operations")

                if metrics.get("crash_rate", 0) > 1.0:
                    ctx.textual.error_text("🔴 Critical crash rate detected!")
                    ctx.textual.text("   → Review crash logs in App Store Connect")
                    ctx.textual.text("   → Check for memory issues (OOM)")
                    ctx.textual.text("   → Investigate watchdog kills")

                ctx.textual.text("")
                ctx.textual.text("🌐 For full details, visit:")
                ctx.textual.text("   [link=https://appstoreconnect.apple.com]App Store Connect → Crashes & Hangs[/link]")
                ctx.textual.text("")

                ctx.textual.end_step("success")

                return Success("Diagnostics retrieved successfully")

            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to get diagnostics: {err}")
                ctx.textual.text("")
                ctx.textual.text("💡 Alternative: Use App Store Connect Web UI")
                ctx.textual.text("   1. Go to: https://appstoreconnect.apple.com")
                ctx.textual.text("   2. Your App → Crashes & Hangs")
                ctx.textual.text("   3. Filter by version: " + version_string)
                ctx.textual.end_step("error")
                return Error(err)

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["show_diagnostics_step"]
