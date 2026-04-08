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
    - User distribution (from Analytics activeDevices, Sales, or crash data)
    - Crash rates / Hang rates
    - Release dates
    - Version ranking

    Data Sources (in priority order):
    1. Analytics Reports API (activeDevices) - if recent cached data exists
    2. Sales Reports API (units) - if vendor_number available
    3. Performance Metrics API (crash data) - fallback

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
        # 0. TRY ANALYTICS REPORTS (activeDevices) - if cached data exists
        # ====================================================================
        analytics_active_devices = {}  # {version_string: active_devices_count}
        data_source = None

        ctx.textual.text("Checking for cached Analytics Reports data...")

        existing_result = analytics_service.find_existing_request_with_reports(app_id)

        match existing_result:
            case ClientSuccess(data=(req_id, reports)) if reports:
                ctx.textual.text(f"✅ Found existing analytics request with {len(reports)} report(s)")

                # Try to extract activeDevices from APP_USAGE report
                for report in reports:
                    category = report.get("attributes", {}).get("category")
                    if category == "APP_USAGE":
                        report_id = report.get("id")
                        ctx.textual.text(f"  Downloading APP_USAGE report...")

                        download_result = analytics_service.download_report_tsv(report_id)
                        match download_result:
                            case ClientSuccess(data=tsv_data):
                                parse_result = analytics_service.parse_tsv_to_dataframe(tsv_data)
                                match parse_result:
                                    case ClientSuccess(data=df):
                                        # Extract activeDevices by version
                                        if "appVersion" in df.columns and "activeDevices" in df.columns:
                                            version_devices = df.groupby("appVersion")["activeDevices"].sum()
                                            analytics_active_devices = version_devices.to_dict()
                                            ctx.textual.text(f"  ✅ Extracted activeDevices for {len(analytics_active_devices)} version(s)")
                                            data_source = "Analytics Reports API (activeDevices)"
                                        else:
                                            ctx.textual.warning_text(f"  ⚠️  APP_USAGE report missing required columns")
                                    case ClientError(error_message=err):
                                        ctx.textual.warning_text(f"  ⚠️  Failed to parse TSV: {err}")
                            case ClientError(error_message=err):
                                ctx.textual.warning_text(f"  ⚠️  Failed to download report: {err}")
                        break
            case _:
                ctx.textual.text("  No cached Analytics Reports found (will use fallback data)")

        # ====================================================================
        # 1. FETCH PERFORMANCE METRICS (crash/hang data + fallback for active versions)
        # ====================================================================
        ctx.textual.text("Fetching performance data...")

        all_crash_metrics = {}
        perf_result = metrics_service.get_performance_metrics(app_id, platform="IOS")

        match perf_result:
            case ClientSuccess(data=perf_data):
                crash_result = metrics_service.extract_crash_metrics_by_version(perf_data)

                match crash_result:
                    case ClientSuccess(data=crash_metrics):
                        all_crash_metrics = crash_metrics
                        if not all_crash_metrics and not analytics_active_devices:
                            ctx.textual.error_text("No performance or analytics data available")
                            ctx.textual.end_step("error")
                            return Error("No data sources available")
                    case ClientError(error_message=err):
                        if not analytics_active_devices:
                            ctx.textual.error_text(f"Failed to extract crash metrics: {err}")
                            ctx.textual.end_step("error")
                            return Error(f"Crash extraction failed: {err}")
                        ctx.textual.warning_text(f"Performance metrics unavailable: {err}")
            case ClientError(error_message=err):
                if not analytics_active_devices:
                    ctx.textual.error_text(f"Failed to fetch performance metrics: {err}")
                    ctx.textual.end_step("error")
                    return Error(f"Performance fetch failed: {err}")
                ctx.textual.warning_text(f"Performance metrics unavailable: {err}")

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
        # 3. FETCH SALES/PROPAGATION DATA (if available and not using Analytics)
        # ====================================================================
        propagation_data = {}
        if vendor_number and not analytics_active_devices:
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
                        if not data_source:
                            data_source = "Sales Reports API"
                case _:
                    pass  # Sales data optional

        # ====================================================================
        # 4. COMBINE DATA AND PREPARE DISPLAY
        # ====================================================================

        # Determine active versions from best available source
        if analytics_active_devices:
            # Use Analytics activeDevices (most accurate)
            active_versions = set(analytics_active_devices.keys())
            if not data_source:
                data_source = "Analytics Reports API (activeDevices)"
        elif all_crash_metrics:
            # Fallback to crash data
            active_versions = set(all_crash_metrics.keys())
            if not data_source:
                data_source = "Performance Metrics API (crash data)"
        else:
            ctx.textual.error_text("No data sources available to identify active versions")
            ctx.textual.end_step("error")
            return Error("No data sources")

        # Combine all data sources
        combined_data = []

        # Calculate totals based on priority: Analytics > Sales > Crashes
        if analytics_active_devices:
            total_units = sum(analytics_active_devices.values())
        elif propagation_data:
            total_units = sum(propagation_data.values())
        else:
            total_units = sum(m.get("terminations", 0) for m in all_crash_metrics.values())

        for version_string in active_versions:
            metadata = version_metadata.get(version_string, {})
            crash_metrics = all_crash_metrics.get(version_string, {})

            # User count priority: Analytics activeDevices > Sales > Crashes
            if analytics_active_devices and version_string in analytics_active_devices:
                units = int(analytics_active_devices[version_string])
            elif propagation_data and version_string in propagation_data:
                units = propagation_data[version_string]
            else:
                units = crash_metrics.get("terminations", 0)

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

        # Determine metric label based on data source
        if analytics_active_devices:
            metric_label = "Total Active Devices"
        elif propagation_data:
            metric_label = "Total Units (Sales)"
        else:
            metric_label = "Total Crashes"

        ctx.textual.text(f"  Total Active Versions:   {len(combined_data)}")
        ctx.textual.text(f"  {metric_label:23s}  {total_units:,}")
        ctx.textual.text(f"  Data Source:             {data_source}")
        ctx.textual.text("")

        # Main Table
        ctx.textual.text("═" * 100)
        ctx.textual.text("📋 VERSION HEALTH DETAILS (All Active Versions)")
        ctx.textual.text("═" * 100)
        ctx.textual.text("")

        # Table header - dynamic based on data source
        if analytics_active_devices:
            metric_header = "Devices     "
        elif propagation_data:
            metric_header = "Units       "
        else:
            metric_header = "Crashes     "

        ctx.textual.text("┌──────┬────────────┬─────────────┬──────────┬────────────┬────────────┬──────────────┬──────────────┐")
        ctx.textual.text(f"│ Rank │ Version    │ {metric_header}│ Distrib. │ Crash Rate │ Hang Rate  │ Release Date │ Status       │")
        ctx.textual.text("│      │            │             │          │            │            │              │              │")
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
