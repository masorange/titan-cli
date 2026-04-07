"""
Display Active Versions Health - Dashboard showing all versions with active users.

Shows comprehensive health metrics for all versions that have active users:
- User distribution across versions
- Crash rates and hang rates
- Release dates and version states
- Ranking by number of active users/crashes
"""

from datetime import datetime
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError


def display_active_versions_health(ctx: WorkflowContext) -> WorkflowResult:
    """
    Display comprehensive health dashboard for all active versions.

    Shows ALL versions with active users (no limits):
    - User distribution (from crash data as proxy)
    - Crash rates / Hang rates
    - Release dates
    - Version ranking

    Inputs (from ctx.data):
        - app_id: App ID
        - app_name: App name

    Returns:
        Success with dashboard displayed
        Error if data fetch fails
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Active Versions Health Dashboard")

    try:
        app_id = ctx.data.get("app_id")
        app_name = ctx.data.get("app_name", "App")

        if not app_id:
            ctx.textual.error_text("No app_id found in context")
            ctx.textual.end_step("error")
            return Error("Missing app_id")

        # Load credentials and initialize client
        from ..clients.appstore_client import AppStoreConnectClient
        from ..credentials import CredentialsManager
        from ..clients.services.metrics_service import MetricsService
        from ..clients.services.analytics_service import AnalyticsService

        credentials = CredentialsManager.load_credentials()
        if not credentials:
            ctx.textual.error_text("No credentials configured")
            ctx.textual.end_step("error")
            return Error("Run setup first")

        issuer_id = credentials.get("issuer_id")
        key_id = credentials.get("key_id")
        p8_path = credentials.get("private_key_path")
        vendor_number = credentials.get("vendor_number")

        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )
        metrics_service = MetricsService(client._api)
        analytics_service = AnalyticsService(client._api)

        # ====================================================================
        # 1. FETCH PERFORMANCE METRICS (identifies active versions)
        # ====================================================================
        ctx.textual.text("Fetching performance data for all versions...")

        perf_result = metrics_service.get_performance_metrics(app_id, platform="IOS")

        match perf_result:
            case ClientSuccess(data=perf_data):
                crash_result = metrics_service.extract_crash_metrics_by_version(perf_data)

                match crash_result:
                    case ClientSuccess(data=all_crash_metrics):
                        if not all_crash_metrics:
                            ctx.textual.error_text("No crash data available - no active users detected")
                            ctx.textual.end_step("error")
                            return Error("No performance data")
                    case ClientError(error_message=err):
                        ctx.textual.error_text(f"Failed to extract crash metrics: {err}")
                        ctx.textual.end_step("error")
                        return Error(f"Crash extraction failed: {err}")
            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to fetch performance metrics: {err}")
                ctx.textual.end_step("error")
                return Error(f"Performance fetch failed: {err}")

        # ====================================================================
        # 2. FETCH VERSION METADATA (dates, states)
        # ====================================================================
        ctx.textual.text("Fetching version metadata...")

        # Get all versions sorted by date
        versions_result = analytics_service.get_app_versions_sorted(app_id, limit=50)

        match versions_result:
            case ClientSuccess(data=all_versions):
                # Create lookup dict for version metadata
                version_metadata = {}
                for v in all_versions:
                    version_metadata[v.versionString] = {
                        "release_date": v.earliestReleaseDate or v.createdDate or "Unknown",
                        "created_date": v.createdDate or "Unknown",
                        "has_active_users": v.has_active_users if hasattr(v, 'has_active_users') else True,
                    }
            case ClientError(error_message=err):
                ctx.textual.warning_text(f"Could not fetch version metadata: {err}")
                version_metadata = {}

        # ====================================================================
        # 3. FETCH SALES/PROPAGATION DATA (if available)
        # ====================================================================
        propagation_data = {}
        if vendor_number:
            ctx.textual.text("Fetching sales/propagation data...")

            prop_result = metrics_service.get_propagation_from_sales(
                vendor_number=vendor_number,
                app_name=app_name,
                days=30
            )

            match prop_result:
                case ClientSuccess(data=prop_metrics):
                    if not prop_metrics.error:
                        propagation_data = prop_metrics.by_version
                case _:
                    pass  # Sales data optional

        # ====================================================================
        # 4. COMBINE DATA AND PREPARE DISPLAY
        # ====================================================================

        # Combine all data sources
        combined_data = []
        total_crashes = sum(m.get("terminations", 0) for m in all_crash_metrics.values())
        total_units = sum(propagation_data.values()) if propagation_data else total_crashes

        for version_string, crash_metrics in all_crash_metrics.items():
            metadata = version_metadata.get(version_string, {})
            units = propagation_data.get(version_string, crash_metrics.get("terminations", 0))

            combined_data.append({
                "version": version_string,
                "units": units,
                "crash_rate": crash_metrics.get("crash_rate", 0.0),
                "hang_rate": crash_metrics.get("hang_rate", 0.0),
                "terminations": crash_metrics.get("terminations", 0),
                "hangs": crash_metrics.get("hangs", 0),
                "release_date": metadata.get("release_date", "Unknown"),
                "pct_distribution": (units / total_units * 100) if total_units > 0 else 0,
            })

        # Sort by units (most users first)
        combined_data.sort(key=lambda x: x["units"], reverse=True)

        # ====================================================================
        # 5. DISPLAY DASHBOARD
        # ====================================================================

        ctx.textual.text("")
        ctx.textual.text("━" * 100)
        ctx.textual.text(f"📊 ACTIVE VERSIONS HEALTH DASHBOARD - {app_name}")
        ctx.textual.text(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ctx.textual.text("━" * 100)
        ctx.textual.text("")

        # Summary
        ctx.textual.text("═" * 100)
        ctx.textual.text("🎯 SUMMARY")
        ctx.textual.text("═" * 100)
        ctx.textual.text("")

        metric_label = "Total Users" if propagation_data else "Total Crashes"
        ctx.textual.text(f"  Total Active Versions:   {len(combined_data)}")
        ctx.textual.text(f"  {metric_label:23s}  {total_units:,}")
        ctx.textual.text(f"  Data Source:             {'Sales Reports + Performance' if propagation_data else 'Performance Metrics'}")
        ctx.textual.text("")

        # Main Table
        ctx.textual.text("═" * 100)
        ctx.textual.text("📋 VERSION HEALTH DETAILS (All Active Versions)")
        ctx.textual.text("═" * 100)
        ctx.textual.text("")

        # Table header
        ctx.textual.text("┌──────┬────────────┬─────────────┬──────────┬────────────┬────────────┬──────────────┬──────────────┐")
        ctx.textual.text("│ Rank │ Version    │ Users/      │ Distrib. │ Crash Rate │ Hang Rate  │ Release Date │ Status       │")
        ctx.textual.text("│      │            │ Crashes     │          │            │            │              │              │")
        ctx.textual.text("├──────┼────────────┼─────────────┼──────────┼────────────┼────────────┼──────────────┼──────────────┤")

        # Table rows
        for idx, data in enumerate(combined_data, 1):
            version = data["version"][:10]
            units = data["units"]
            pct = data["pct_distribution"]
            crash_rate = data["crash_rate"]
            hang_rate = data["hang_rate"]
            release_date = data["release_date"][:10] if data["release_date"] != "Unknown" else "Unknown   "

            # Status based on crash rate
            if crash_rate < 1:
                status = "🟢 EXCELLENT"
            elif crash_rate < 3:
                status = "🟡 GOOD    "
            elif crash_rate < 5:
                status = "🟠 WARNING "
            else:
                status = "🔴 CRITICAL"

            # Rank icons
            if idx == 1:
                rank = "🥇 #1 "
            elif idx == 2:
                rank = "🥈 #2 "
            elif idx == 3:
                rank = "🥉 #3 "
            else:
                rank = f"   #{idx:2d}"

            ctx.textual.text(
                f"│ {rank} │ {version:10s} │ {units:>11,} │ {pct:>6.1f}% │ {crash_rate:>9.2f}% │ {hang_rate:>9.2f}% │ {release_date:12s} │ {status} │"
            )

        ctx.textual.text("└──────┴────────────┴─────────────┴──────────┴────────────┴────────────┴──────────────┴──────────────┘")
        ctx.textual.text("")

        # Distribution visualization (bar chart)
        if len(combined_data) > 1:
            ctx.textual.text("═" * 100)
            ctx.textual.text("📊 USER DISTRIBUTION")
            ctx.textual.text("═" * 100)
            ctx.textual.text("")

            max_units = max(d["units"] for d in combined_data)

            for data in combined_data[:10]:  # Show top 10
                version = data["version"][:10]
                units = data["units"]
                pct = data["pct_distribution"]

                # Scale bar to 60 chars max
                bar_length = int((units / max_units) * 60) if max_units > 0 else 0
                bar = "█" * bar_length

                ctx.textual.text(f"  {version:10s} │ {bar} {pct:>5.1f}% ({units:,})")

            if len(combined_data) > 10:
                ctx.textual.text(f"  ... and {len(combined_data) - 10} more versions")

            ctx.textual.text("")

        # Key insights
        ctx.textual.text("═" * 100)
        ctx.textual.text("💡 KEY INSIGHTS")
        ctx.textual.text("═" * 100)
        ctx.textual.text("")

        if combined_data:
            top_version = combined_data[0]
            avg_crash = sum(d["crash_rate"] for d in combined_data) / len(combined_data)
            best_stability = min(combined_data, key=lambda x: x["crash_rate"])

            ctx.textual.text(f"  • Most adopted version: {top_version['version']} ({top_version['pct_distribution']:.1f}% of users)")
            ctx.textual.text(f"  • Most stable version:  {best_stability['version']} ({best_stability['crash_rate']:.2f}% crash rate)")
            ctx.textual.text(f"  • Average crash rate:   {avg_crash:.2f}%")

            if top_version["crash_rate"] > avg_crash * 1.5:
                ctx.textual.text(f"  ⚠️  WARNING: Most adopted version has higher than average crash rate!")
            else:
                ctx.textual.text(f"  ✅ Good: Most adopted version has acceptable stability")

        ctx.textual.text("")
        ctx.textual.text("━" * 100)
        ctx.textual.text("")

        # Save to context for potential follow-up workflows
        ctx.data["active_versions_count"] = len(combined_data)
        ctx.data["active_versions_data"] = combined_data

        ctx.textual.end_step("success")
        return Success(
            f"Displayed health dashboard for {len(combined_data)} active versions",
            metadata={"versions_analyzed": len(combined_data)}
        )

    except Exception as e:
        ctx.textual.error_text(f"Unexpected error: {e}")
        ctx.textual.end_step("error")
        return Error(str(e))


__all__ = ["display_active_versions_health"]
