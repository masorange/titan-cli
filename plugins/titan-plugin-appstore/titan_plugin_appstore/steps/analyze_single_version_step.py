"""
Analyze Single Version Step - Complete analysis of one version.

Combines stability and propagation metrics into a single comprehensive view.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..clients.appstore_client import AppStoreConnectClient
from ..operations.analysis_operations import AnalysisOperations
from ..credentials import CredentialsManager
from titan_cli.core.result import ClientSuccess, ClientError


def _display_analysis(ctx: WorkflowContext, analysis, app_num: int, total_apps: int):
    """Helper function to display analysis results for one app."""
    ctx.textual.text("")
    ctx.textual.text("=" * 70)
    ctx.textual.text(f"APP {app_num}/{total_apps}: {analysis.app_name}")
    ctx.textual.text(f"Version: {analysis.version_string}")
    ctx.textual.text("=" * 70)
    ctx.textual.text("")

    # Stability metrics
    ctx.textual.text("📉 STABILITY METRICS")
    ctx.textual.text("-" * 70)
    ctx.textual.text(f"  Crash Rate:    {analysis.stability.crash_rate:.4f}%")
    ctx.textual.text(f"  Hang Rate:     {analysis.stability.hang_rate:.4f}%")
    ctx.textual.text(f"  Terminations:  {analysis.stability.terminations:,}")
    ctx.textual.text(f"  Hangs:         {analysis.stability.hangs:,}")
    ctx.textual.text("")

    # Propagation metrics
    ctx.textual.text("📈 PROPAGATION METRICS")
    ctx.textual.text("-" * 70)
    ctx.textual.text(f"  Total Units:   {analysis.propagation.total_units:,}")
    ctx.textual.text(f"  Countries:     {analysis.propagation.countries}")
    ctx.textual.text(f"  Market Share:  {analysis.propagation.market_share:.1f}%")
    ctx.textual.text("")

    # Health assessment
    ctx.textual.text("🏥 HEALTH ASSESSMENT")
    ctx.textual.text("-" * 70)

    status_emoji = {
        "healthy": "🟢",
        "warning": "🟡",
        "critical": "🔴",
        "unknown": "⚪",
    }
    emoji = status_emoji.get(analysis.status, "❓")

    ctx.textual.text(f"  Status:        {emoji} {analysis.status.upper()}")
    ctx.textual.text(f"  Health Score:  {analysis.health_score:.1f}/100")
    ctx.textual.text("")

    # Recommendations
    recommendations = analysis.get_recommendations()
    if recommendations:
        ctx.textual.text("💡 RECOMMENDATIONS")
        ctx.textual.text("-" * 70)
        for rec in recommendations:
            ctx.textual.text(f"  ⚠️  {rec}")
        ctx.textual.text("")

    ctx.textual.text("=" * 70)
    ctx.textual.text("")


def analyze_single_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Analyze version(s) combining stability and propagation metrics.

    Supports analyzing multiple apps if selected_apps is present.

    This step uses the AnalysisOperations to combine:
    1. Performance metrics (crashes, hangs)
    2. Sales reports (installations, countries)
    3. Health score calculation
    4. Status assessment
    5. Recommendations

    Inputs (from ctx.data):
        - selected_apps (list, optional): Multiple apps to analyze
        - app_id: Single app ID (fallback if selected_apps not present)
        - version_string: Version to analyze (e.g., "26.13.0")
        - app_name: App name (optional, for sales reports)

    Outputs (saved to ctx.data):
        - version_analyses (list): List of VersionAnalysisView for all apps
        - version_analysis: First analysis (for backward compatibility)
        - health_score: First app's health score
        - status: First app's status
        - recommendations: First app's recommendations

    Returns:
        Success with analysis data
        Error if analysis fails
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Analyze Version(s)")

    try:
        # Check if multiple apps are selected
        selected_apps = ctx.data.get("selected_apps", [])
        version_string = ctx.data.get("version_string")

        # Build list of apps to analyze
        apps_to_analyze = []

        if selected_apps:
            # Multiple apps selected
            apps_to_analyze = [
                {"id": app["id"], "name": app["name"]}
                for app in selected_apps
            ]
        else:
            # Single app (backward compatibility)
            app_id = ctx.data.get("app_id")
            app_name = ctx.data.get("app_name")
            if app_id:
                apps_to_analyze = [{"id": app_id, "name": app_name}]

        if not apps_to_analyze:
            ctx.textual.error_text("No apps to analyze")
            ctx.textual.end_step("error")
            return Error("No apps selected")

        if not version_string:
            ctx.textual.error_text("Missing version_string")
            ctx.textual.end_step("error")
            return Error("version_string required")

        # Load credentials
        credentials = CredentialsManager.load_credentials()
        if not credentials:
            ctx.textual.error_text("No credentials configured")
            ctx.textual.end_step("error")
            return Error("Run setup wizard first")

        issuer_id = credentials.get("issuer_id")
        key_id = credentials.get("key_id")
        p8_path = credentials.get("private_key_path")
        vendor_number = credentials.get("vendor_number")

        # Initialize client
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Initialize analysis operations
        analysis_ops = AnalysisOperations(client)

        # Analyze each app
        all_analyses = []

        ctx.textual.text("=" * 70)
        ctx.textual.text(f"ANALYZING {len(apps_to_analyze)} APP(S) - VERSION {version_string}")
        ctx.textual.text("=" * 70)
        ctx.textual.text("")

        for idx, app_info in enumerate(apps_to_analyze, 1):
            app_id = app_info["id"]
            app_name = app_info["name"]

            ctx.textual.text(f"[{idx}/{len(apps_to_analyze)}] Analyzing {app_name}...")

            analysis_result = analysis_ops.analyze_version(
                app_id=app_id,
                version_string=version_string,
                vendor_number=vendor_number,
                app_name=app_name,
            )

            match analysis_result:
                case ClientSuccess(data=analysis):
                    all_analyses.append(analysis)
                    _display_analysis(ctx, analysis, idx, len(apps_to_analyze))

                case ClientError(error_message=err):
                    ctx.textual.error_text(f"  ✗ Failed: {err}")
                    ctx.textual.text("")

        # Store results
        if all_analyses:
            ctx.data["version_analyses"] = all_analyses
            ctx.data["version_analysis"] = all_analyses[0]  # First for compatibility
            ctx.data["health_score"] = all_analyses[0].health_score
            ctx.data["status"] = all_analyses[0].status
            ctx.data["recommendations"] = all_analyses[0].get_recommendations()

            ctx.textual.text("=" * 70)
            ctx.textual.success_text(f"✅ Analyzed {len(all_analyses)} of {len(apps_to_analyze)} app(s)")
            ctx.textual.text("=" * 70)

            ctx.textual.end_step("success")

            return Success(f"Analyzed {len(all_analyses)} app(s)")
        else:
            ctx.textual.error_text("All analyses failed")
            ctx.textual.end_step("error")
            return Error("All analyses failed")

    except Exception as e:
        error_msg = f"Unexpected error during analysis: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["analyze_single_version_step"]
