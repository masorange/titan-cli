"""
Request Analytics Step - Flujo completo correcto (2026)

1. POST /v1/analyticsReportRequests (sin filters)
2. Polling con include=reports
3. Download TSV por categoría
4. Parse con pandas
5. Cálculo de métricas filtrando por appVersion
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager


def request_analytics_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Request analytics - flujo completo API o fallback.

    Inputs (from ctx.data):
        - app_id
        - version_1_string (e.g., "26.11.2")
        - version_2_string (e.g., "26.10.1")

    Outputs (saved to ctx.data):
        - analytics_method: "api" or "fallback"
        - propagation_metrics_v1
        - propagation_metrics_v2
        - stability_metrics_v1
        - stability_metrics_v2

    Returns:
        Success with metrics
        Error if both fail
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Get Analytics Data")

    try:
        app_id = ctx.data.get("app_id")
        version_1_id = ctx.data.get("version_1_id")
        version_2_id = ctx.data.get("version_2_id")
        version_1_string = ctx.data.get("version_1_string")
        version_2_string = ctx.data.get("version_2_string")

        if not all([app_id, version_1_string, version_2_string]):
            ctx.textual.error_text("Missing required context")
            ctx.textual.end_step("error")
            return Error("Missing context")

        # Load credentials
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Get analytics service
        from ..clients.services.analytics_service import AnalyticsService
        analytics = AnalyticsService(client._api)

        # Check Analytics API access
        ctx.textual.text("Checking Analytics API access...")
        has_analytics = analytics.check_analytics_api_access(app_id)

        if not has_analytics:
            ctx.textual.text("⚠️  Analytics API not available - using FALLBACK")
            use_fallback = True
        else:
            ctx.textual.success_text("✓ Analytics API accessible")

            try:
                # 🧹 Clean up stuck requests first
                ctx.textual.text("Checking for existing requests...")
                deleted_count = analytics.cleanup_existing_requests(app_id)
                if deleted_count > 0:
                    ctx.textual.text(f"  ✓ Cleaned up {deleted_count} stuck request(s)")

                # 🔍 Check if there are existing completed reports we can reuse
                existing = analytics.find_existing_request_with_reports(app_id)
                if existing:
                    request_id, completed_reports = existing
                    ctx.textual.success_text(f"✓ Found existing completed reports!")
                    reports = completed_reports
                else:
                    # Check if there's a pending request
                    query_params = {"include": "reports", "limit": 5}
                    response = analytics.api.get(
                        f"/apps/{app_id}/analyticsReportRequests",
                        query_params=query_params
                    )
                    requests_data = response.get("data", [])

                    if requests_data:
                        # There's a pending request
                        pending_id = requests_data[0]["id"]
                        ctx.textual.text(f"📊 Analytics request already exists: {pending_id}")
                        ctx.textual.text("")
                        ctx.textual.text("⏳ Reports are still processing...")
                        ctx.textual.text("   This typically takes 30-60 minutes.")
                        ctx.textual.text("")
                        ctx.textual.text("💡 Run this workflow again in 30-60 minutes to download reports.")
                        ctx.textual.text("   Or use fallback mode for immediate results.")
                        ctx.textual.text("")

                        # Fall back to builds + reviews
                        ctx.textual.text("Using FALLBACK for now (builds + reviews)...")
                        use_fallback = True
                    else:
                        # 1️⃣ Create new request
                        ctx.textual.text("Creating new analytics request...")
                        request_id = analytics.create_analytics_report_request(app_id)
                        ctx.textual.success_text(f"✓ Request created: {request_id}")
                        ctx.textual.text("")
                        ctx.textual.text("📊 Analytics reports are being generated...")
                        ctx.textual.text("   This process takes 30-60 minutes.")
                        ctx.textual.text("")
                        ctx.textual.text("💡 Run this workflow again in 30-60 minutes to get results.")
                        ctx.textual.text("   Or continue with fallback mode for immediate results.")
                        ctx.textual.text("")

                        # Fall back to builds + reviews
                        ctx.textual.text("Using FALLBACK for now (builds + reviews)...")
                        use_fallback = True

                # If we got here and still have reports, process them
                if not use_fallback and 'reports' in locals():
                    # 3️⃣ Download and parse TSV
                    usage_df = None
                    crash_df = None

                    for report in reports:
                        report_id = report.get("id")
                        category = report.get("attributes", {}).get("category")

                        ctx.textual.text(f"Downloading {category} report...")
                        tsv_data = analytics.download_report_tsv(report_id)

                        ctx.textual.text(f"Parsing {category} TSV...")
                        df = analytics.parse_tsv_to_dataframe(tsv_data)

                        if category == "APP_USAGE":
                            usage_df = df
                            ctx.textual.success_text(f"✓ APP_USAGE: {len(df)} rows")
                        elif category == "CRASHES":
                            crash_df = df
                            ctx.textual.success_text(f"✓ CRASHES: {len(df)} rows")

                    if usage_df is None or crash_df is None:
                        ctx.textual.text("⚠️  Missing required reports - using FALLBACK")
                        use_fallback = True
                    else:
                        # 4️⃣ Calculate metrics
                        ctx.textual.text("Calculating metrics...")

                        prop_v1 = analytics.calculate_propagation_metrics(usage_df, version_1_string)
                        prop_v2 = analytics.calculate_propagation_metrics(usage_df, version_2_string)

                        stab_v1 = analytics.calculate_stability_metrics(usage_df, crash_df, version_1_string)
                        stab_v2 = analytics.calculate_stability_metrics(usage_df, crash_df, version_2_string)

                        if "error" in prop_v1 or "error" in prop_v2:
                            ctx.textual.text("⚠️  Error calculating metrics - using FALLBACK")
                            use_fallback = True
                        else:
                            # Success with Analytics API!
                            ctx.textual.success_text(
                                f"✓ V1 ({version_1_string}): {prop_v1['total_sessions']:,} sessions, "
                                f"{stab_v1['crash_rate']:.4f}% crash rate"
                            )
                            ctx.textual.success_text(
                                f"✓ V2 ({version_2_string}): {prop_v2['total_sessions']:,} sessions, "
                                f"{stab_v2['crash_rate']:.4f}% crash rate"
                            )

                            ctx.data["analytics_method"] = "api"
                            ctx.data["propagation_metrics_v1"] = prop_v1
                            ctx.data["propagation_metrics_v2"] = prop_v2
                            ctx.data["stability_metrics_v1"] = stab_v1
                            ctx.data["stability_metrics_v2"] = stab_v2

                            ctx.textual.end_step("success")

                            return Success(
                                f"Analytics API successful: {prop_v1['total_sessions'] + prop_v2['total_sessions']:,} total sessions"
                            )

            except Exception as e:
                ctx.textual.text(f"⚠️  Analytics API failed: {str(e)}")
                ctx.textual.text("Falling back to builds + reviews")
                use_fallback = True

        # FALLBACK mode
        if use_fallback:
            ctx.textual.text("\n📊 FALLBACK: Using builds + reviews...")

            # Propagation from builds
            ctx.textual.text("Analyzing build data...")
            prop_data = analytics.get_propagation_metrics_from_builds(
                app_id, [version_1_id, version_2_id]
            )

            prop_v1 = prop_data.get(version_1_id, {})
            prop_v2 = prop_data.get(version_2_id, {})

            if "error" not in prop_v1:
                ctx.textual.success_text(
                    f"✓ V1 ({version_1_string}): {prop_v1.get('total_builds', 0)} builds"
                )

            if "error" not in prop_v2:
                ctx.textual.success_text(
                    f"✓ V2 ({version_2_string}): {prop_v2.get('total_builds', 0)} builds"
                )

            # Stability from reviews
            ctx.textual.text("Analyzing customer reviews...")
            stab_data = analytics.get_stability_metrics_from_reviews(
                app_id, [version_1_string, version_2_string]
            )

            stab_v1 = stab_data.get(version_1_string, {})
            stab_v2 = stab_data.get(version_2_string, {})

            if "error" not in stab_v1:
                ctx.textual.success_text(
                    f"✓ V1 ({version_1_string}): {stab_v1.get('average_rating', 0):.1f}★"
                )

            if "error" not in stab_v2:
                ctx.textual.success_text(
                    f"✓ V2 ({version_2_string}): {stab_v2.get('average_rating', 0):.1f}★"
                )

            ctx.data["analytics_method"] = "fallback"
            ctx.data["propagation_metrics_v1"] = prop_v1
            ctx.data["propagation_metrics_v2"] = prop_v2
            ctx.data["stability_metrics_v1"] = stab_v1
            ctx.data["stability_metrics_v2"] = stab_v2

            ctx.textual.end_step("success")

            return Success("Fallback metrics calculated from builds + reviews")

    except Exception as e:
        error_msg = f"Failed: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)
