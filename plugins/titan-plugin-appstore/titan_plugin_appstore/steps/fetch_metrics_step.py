"""
Fetch Metrics Step - Uses Performance Metrics + Sales Reports APIs.

NO POLLING - Instantaneous data retrieval.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager


def fetch_metrics_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch metrics using Performance Metrics + Sales Reports APIs.

    NO POLLING - Data is available immediately.

    Inputs (from ctx.data):
        - app_id: App ID
        - app_name: App name (for sales reports filtering)
        - version_1_string: Version 1 string
        - version_2_string: Version 2 string

    Outputs (saved to ctx.data):
        - metrics_method: "full" (both APIs) or "partial" (only performance)
        - propagation_metrics_v1: Propagation metrics for v1
        - propagation_metrics_v2: Propagation metrics for v2
        - stability_metrics_v1: Stability metrics for v1
        - stability_metrics_v2: Stability metrics for v2

    Returns:
        Success with metrics data
        Error if critical failure
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Fetch Metrics")

    try:
        app_id = ctx.data.get("app_id")
        app_name = ctx.data.get("app_name")
        version_1_string = ctx.data.get("version_1_string")
        version_2_string = ctx.data.get("version_2_string")

        if not all([app_id, version_1_string, version_2_string]):
            ctx.textual.error_text("Missing required context")
            ctx.textual.end_step("error")
            return Error("Missing context data")

        # Load credentials
        credentials = CredentialsManager.load_credentials()
        if not credentials:
            ctx.textual.error_text("No credentials configured")
            ctx.textual.end_step("error")
            return Error("Run setup first")

        issuer_id = credentials.get("issuer_id")
        key_id = credentials.get("key_id")
        p8_path = credentials.get("private_key_path")
        vendor_number = credentials.get("vendor_number")

        # Initialize client
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Initialize metrics service
        from ..clients.services.metrics_service import MetricsService
        metrics = MetricsService(client._api)

        ctx.textual.text("=" * 60)
        ctx.textual.text("Using INSTANT Metrics APIs (no polling!)")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")

        # ====================================================================
        # 1. STABILITY METRICS (Performance API)
        # ====================================================================
        ctx.textual.text("📊 Fetching Performance Metrics (crashes, hangs)...")

        try:
            perf_data = metrics.get_performance_metrics(app_id)
            crash_metrics = metrics.extract_crash_metrics_by_version(perf_data)

            # Get metrics for both versions
            stab_v1 = crash_metrics.get(version_1_string, {
                "crash_rate": 0.0,
                "hang_rate": 0.0,
                "terminations": 0,
                "hangs": 0,
            })

            stab_v2 = crash_metrics.get(version_2_string, {
                "crash_rate": 0.0,
                "hang_rate": 0.0,
                "terminations": 0,
                "hangs": 0,
            })

            # Add version strings
            stab_v1["version_string"] = version_1_string
            stab_v2["version_string"] = version_2_string

            ctx.textual.success_text(
                f"✓ V1 ({version_1_string}): "
                f"{stab_v1['crash_rate']:.4f}% crash rate, "
                f"{stab_v1['hang_rate']:.4f}% hang rate"
            )
            ctx.textual.success_text(
                f"✓ V2 ({version_2_string}): "
                f"{stab_v2['crash_rate']:.4f}% crash rate, "
                f"{stab_v2['hang_rate']:.4f}% hang rate"
            )

            ctx.data["stability_metrics_v1"] = stab_v1
            ctx.data["stability_metrics_v2"] = stab_v2

        except Exception as e:
            ctx.textual.error_text(f"⚠️  Performance Metrics failed: {e}")
            # Use fallback for stability
            ctx.textual.text("   Falling back to review analysis...")
            from ..clients.services.analytics_service import AnalyticsService
            analytics = AnalyticsService(client._api)
            stab_data = analytics.get_stability_metrics_from_reviews(
                app_id, [version_1_string, version_2_string]
            )
            ctx.data["stability_metrics_v1"] = stab_data.get(version_1_string, {})
            ctx.data["stability_metrics_v2"] = stab_data.get(version_2_string, {})

        ctx.textual.text("")

        # ====================================================================
        # 2. PROPAGATION METRICS (Sales Reports API)
        # ====================================================================
        if vendor_number:
            ctx.textual.text("📈 Fetching Sales Reports (installations)...")

            try:
                prop_data = metrics.get_propagation_from_sales(
                    vendor_number=vendor_number,
                    app_name=app_name,
                    days=30
                )

                if "error" in prop_data:
                    raise Exception(prop_data["error"])

                # Extract data for each version
                by_version = prop_data.get("by_version", {})

                prop_v1 = {
                    "version_string": version_1_string,
                    "total_units": by_version.get(version_1_string, 0),
                    "total_countries": prop_data.get("countries", 0),
                }

                prop_v2 = {
                    "version_string": version_2_string,
                    "total_units": by_version.get(version_2_string, 0),
                    "total_countries": prop_data.get("countries", 0),
                }

                ctx.textual.success_text(
                    f"✓ V1 ({version_1_string}): "
                    f"{prop_v1['total_units']:,} units"
                )
                ctx.textual.success_text(
                    f"✓ V2 ({version_2_string}): "
                    f"{prop_v2['total_units']:,} units"
                )

                ctx.data["propagation_metrics_v1"] = prop_v1
                ctx.data["propagation_metrics_v2"] = prop_v2
                ctx.data["metrics_method"] = "full"

            except Exception as e:
                ctx.textual.error_text(f"⚠️  Sales Reports failed: {e}")
                ctx.textual.text("   Falling back to build analysis...")
                # Use fallback
                from ..clients.services.analytics_service import AnalyticsService
                analytics = AnalyticsService(client._api)
                version_1_id = ctx.data.get("version_1_id")
                version_2_id = ctx.data.get("version_2_id")
                prop_data = analytics.get_propagation_metrics_from_builds(
                    app_id, [version_1_id, version_2_id]
                )
                ctx.data["propagation_metrics_v1"] = prop_data.get(version_1_id, {})
                ctx.data["propagation_metrics_v2"] = prop_data.get(version_2_id, {})
                ctx.data["metrics_method"] = "partial"

        else:
            # No vendor number - use fallback
            ctx.textual.text("⚠️  No Vendor Number configured")
            ctx.textual.text("   Using build activity as proxy for propagation...")

            from ..clients.services.analytics_service import AnalyticsService
            analytics = AnalyticsService(client._api)
            version_1_id = ctx.data.get("version_1_id")
            version_2_id = ctx.data.get("version_2_id")
            prop_data = analytics.get_propagation_metrics_from_builds(
                app_id, [version_1_id, version_2_id]
            )

            prop_v1 = prop_data.get(version_1_id, {})
            prop_v2 = prop_data.get(version_2_id, {})

            if "error" not in prop_v1:
                ctx.textual.success_text(
                    f"✓ V1 ({version_1_string}): "
                    f"{prop_v1.get('total_builds', 0)} builds"
                )

            if "error" not in prop_v2:
                ctx.textual.success_text(
                    f"✓ V2 ({version_2_string}): "
                    f"{prop_v2.get('total_builds', 0)} builds"
                )

            ctx.data["propagation_metrics_v1"] = prop_v1
            ctx.data["propagation_metrics_v2"] = prop_v2
            ctx.data["metrics_method"] = "partial"

        ctx.textual.text("")
        ctx.textual.text("=" * 60)
        ctx.textual.success_text("✅ Metrics fetched successfully!")
        ctx.textual.text("=" * 60)

        ctx.textual.end_step("success")

        return Success("Metrics fetched instantly (no polling)")

    except Exception as e:
        error_msg = f"Failed to fetch metrics: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["fetch_metrics_step"]
