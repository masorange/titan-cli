"""
Executive Dashboard Step - Impressive multi-version analytics visualization.
"""

from datetime import datetime
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def executive_dashboard_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Generate an impressive executive dashboard with multi-version analytics.

    Shows ALL versions with crash data, not just 2:
    - Evolution chart of crash rates
    - Stability ranking
    - Trend analysis (improving/worsening)
    - Top 3 best/worst versions
    - Visual sparklines

    Inputs (from ctx.data):
        - app_name: App name
        - All version metrics from analyze_metrics_step or previous steps

    Returns:
        Success with dashboard summary
        Error if generation fails
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Executive Dashboard")

    try:
        app_name = ctx.data.get("app_name", "App")

        # Get all versions with metrics from previous steps
        # We need to fetch this data fresh from Performance API
        from ..clients.appstore_client import AppStoreConnectClient
        from ..credentials import CredentialsManager
        from ..clients.services.metrics_service import MetricsService

        # Load credentials
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )
        metrics_service = MetricsService(client._api)

        app_id = ctx.data.get("app_id")
        if not app_id:
            ctx.textual.error_text("No app_id found")
            ctx.textual.end_step("error")
            return Error("No app_id in context")

        ctx.textual.text("Fetching performance data for all versions...")

        # Get performance metrics for all versions
        perf_data = metrics_service.get_performance_metrics(app_id, platform="IOS")
        all_metrics = metrics_service.extract_crash_metrics_by_version(perf_data)

        if not all_metrics:
            ctx.textual.error_text("No crash data available")
            ctx.textual.end_step("error")
            return Error("No performance data")

        # Sort versions by crash rate (best to worst)
        sorted_versions = sorted(
            all_metrics.items(),
            key=lambda x: x[1]["crash_rate"]
        )

        ctx.textual.text("")
        ctx.textual.text("━" * 80)
        ctx.textual.text(f"📊 EXECUTIVE DASHBOARD - {app_name}")
        ctx.textual.text(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ctx.textual.text("━" * 80)
        ctx.textual.text("")

        # === SUMMARY METRICS ===
        ctx.textual.text("═" * 80)
        ctx.textual.text("🎯 SUMMARY")
        ctx.textual.text("═" * 80)
        ctx.textual.text("")

        total_versions = len(sorted_versions)
        avg_crash_rate = sum(v[1]["crash_rate"] for v in sorted_versions) / total_versions
        best_version = sorted_versions[0][0]
        worst_version = sorted_versions[-1][0]
        best_crash = sorted_versions[0][1]["crash_rate"]
        worst_crash = sorted_versions[-1][1]["crash_rate"]

        # Summary in columns
        ctx.textual.text(f"  Total Versions Analyzed: {total_versions}")
        ctx.textual.text(f"  Average Crash Rate:      {avg_crash_rate:.4f}%")
        ctx.textual.text(f"  Best Version:            {best_version} ({best_crash:.4f}%)")
        ctx.textual.text(f"  Worst Version:           {worst_version} ({worst_crash:.4f}%)")
        ctx.textual.text("")

        # === STABILITY RANKING ===
        ctx.textual.text("═" * 80)
        ctx.textual.text("🏆 STABILITY RANKING (All Versions)")
        ctx.textual.text("═" * 80)
        ctx.textual.text("")

        ctx.textual.text("┌──────┬────────────┬────────────┬────────────┬──────────────┐")
        ctx.textual.text("│ Rank │ Version    │ Crash Rate │ Hang Rate  │ Status       │")
        ctx.textual.text("├──────┼────────────┼────────────┼────────────┼──────────────┤")

        for idx, (version, metrics) in enumerate(sorted_versions, 1):
            crash_rate = metrics["crash_rate"]
            hang_rate = metrics["hang_rate"]

            # Status icons
            if crash_rate < 2:
                status = "🟢 EXCELLENT"
            elif crash_rate < 5:
                status = "🟡 GOOD    "
            elif crash_rate < 10:
                status = "🟠 WARNING "
            else:
                status = "🔴 CRITICAL"

            # Highlight top 3 and bottom 3
            if idx == 1:
                prefix = "🥇"
            elif idx == 2:
                prefix = "🥈"
            elif idx == 3:
                prefix = "🥉"
            elif idx >= total_versions - 2:
                prefix = "⚠️ "
            else:
                prefix = "  "

            version_str = f"{version[:10]:<10}"
            ctx.textual.text(
                f"│ {prefix}{idx:2d}  │ {version_str} │ {crash_rate:>9.4f}% │ {hang_rate:>9.4f}% │ {status} │"
            )

        ctx.textual.text("└──────┴────────────┴────────────┴────────────┴──────────────┘")
        ctx.textual.text("")

        # === CRASH RATE EVOLUTION (Simple bar chart) ===
        ctx.textual.text("═" * 80)
        ctx.textual.text("📈 CRASH RATE EVOLUTION")
        ctx.textual.text("═" * 80)
        ctx.textual.text("")

        # Show last 10 versions (or all if less)
        recent_versions = list(reversed(sorted_versions))[:10]
        max_crash = max(v[1]["crash_rate"] for v in recent_versions)

        for version, metrics in recent_versions:
            crash_rate = metrics["crash_rate"]
            # Scale bar to 50 chars max
            bar_length = int((crash_rate / max(max_crash, 1)) * 50)
            bar = "█" * bar_length

            # Color based on severity
            if crash_rate < 2:
                icon = "🟢"
            elif crash_rate < 5:
                icon = "🟡"
            elif crash_rate < 10:
                icon = "🟠"
            else:
                icon = "🔴"

            version_str = f"{version[:10]:<10}"
            ctx.textual.text(f"  {icon} {version_str} │ {bar} {crash_rate:>6.2f}%")

        ctx.textual.text("")

        # === TREND ANALYSIS ===
        ctx.textual.text("═" * 80)
        ctx.textual.text("📊 TREND ANALYSIS")
        ctx.textual.text("═" * 80)
        ctx.textual.text("")

        # Compare recent vs older versions
        if len(sorted_versions) >= 4:
            recent_3 = sorted_versions[:3]
            avg_recent = sum(v[1]["crash_rate"] for v in recent_3) / 3

            older_3 = sorted_versions[-3:]
            avg_older = sum(v[1]["crash_rate"] for v in older_3) / 3

            diff = avg_recent - avg_older
            diff_pct = (diff / avg_older * 100) if avg_older > 0 else 0

            if diff < -0.5:  # Improving
                trend = "📈 IMPROVING"
                color = "🟢"
                msg = f"Recent versions are {abs(diff_pct):.1f}% more stable than older ones"
            elif diff > 0.5:  # Worsening
                trend = "📉 WORSENING"
                color = "🔴"
                msg = f"Recent versions are {abs(diff_pct):.1f}% less stable than older ones"
            else:
                trend = "➡️  STABLE"
                color = "🟡"
                msg = "Stability has remained consistent"

            ctx.textual.text(f"  {color} Overall Trend: {trend}")
            ctx.textual.text(f"  {msg}")
            ctx.textual.text("")
            ctx.textual.text(f"  Recent avg crash rate: {avg_recent:.4f}%")
            ctx.textual.text(f"  Older avg crash rate:  {avg_older:.4f}%")
        else:
            ctx.textual.text("  Insufficient data for trend analysis (need 4+ versions)")

        ctx.textual.text("")

        # === KEY INSIGHTS ===
        ctx.textual.text("═" * 80)
        ctx.textual.text("💡 KEY INSIGHTS")
        ctx.textual.text("═" * 80)
        ctx.textual.text("")

        # Top performers
        ctx.textual.text("  ✅ TOP 3 MOST STABLE VERSIONS:")
        for idx, (version, metrics) in enumerate(sorted_versions[:3], 1):
            ctx.textual.text(f"     {idx}. {version} - {metrics['crash_rate']:.4f}% crash rate")
        ctx.textual.text("")

        # Bottom performers
        ctx.textual.text("  ⚠️  TOP 3 LEAST STABLE VERSIONS:")
        for idx, (version, metrics) in enumerate(sorted_versions[-3:], 1):
            ctx.textual.text(f"     {idx}. {version} - {metrics['crash_rate']:.4f}% crash rate")
        ctx.textual.text("")

        # Recommendations
        ctx.textual.text("  🎯 RECOMMENDATIONS:")
        if avg_crash_rate > 10:
            ctx.textual.text("     • CRITICAL: Average crash rate exceeds 10% - immediate action required")
            ctx.textual.text("     • Investigate common crash patterns across versions")
            ctx.textual.text("     • Consider hotfix for worst performing versions")
        elif avg_crash_rate > 5:
            ctx.textual.text("     • Monitor crash rates closely")
            ctx.textual.text("     • Analyze crash logs for worst performing versions")
        else:
            ctx.textual.text("     • Overall stability is good")
            ctx.textual.text("     • Continue current development practices")

        ctx.textual.text("")
        ctx.textual.text("━" * 80)
        ctx.textual.text("")

        ctx.textual.end_step("success")

        return Success(f"Dashboard generated for {total_versions} versions")

    except Exception as e:
        error_msg = f"Failed to generate dashboard: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["executive_dashboard_step"]
