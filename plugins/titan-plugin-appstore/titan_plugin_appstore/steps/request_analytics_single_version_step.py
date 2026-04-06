"""
Request Analytics Step - For single version analysis.

Creates Analytics Report request or shows existing reports.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager


def request_analytics_single_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Request analytics reports for one or more apps (waterfall processing).

    This step checks if Analytics Reports are available or creates a new request
    for each selected app sequentially.

    Inputs (from ctx.data):
        - selected_apps: List of selected app dicts (with id, name)
        OR
        - app_id: Single app ID (fallback)

    Outputs (saved to ctx.data):
        - analytics_results: Dict[app_id, status] for each app
        - analytics_request_status: Overall status
        - has_completed_reports: boolean (true if ANY app has completed reports)

    Returns:
        Success with summary
        Error if all apps fail
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Request Analytics Reports")

    try:
        # Get list of apps to process
        selected_apps = ctx.data.get("selected_apps", [])

        # Fallback to single app if selected_apps is empty
        if not selected_apps:
            app_id = ctx.data.get("app_id")
            app_name = ctx.data.get("app_name", "Unknown")
            if app_id:
                selected_apps = [{"id": app_id, "name": app_name}]

        if not selected_apps:
            ctx.textual.error_text("No apps selected")
            ctx.textual.end_step("error")
            return Error("No apps selected")

        # Show summary
        if len(selected_apps) == 1:
            ctx.textual.text(f"Processing 1 app: {selected_apps[0]['name']}")
        else:
            ctx.textual.text(f"Processing {len(selected_apps)} apps (waterfall):")
            for app in selected_apps:
                ctx.textual.text(f"  • {app['name']}")

        ctx.textual.text("")

        # Load credentials once
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Get analytics service
        from ..clients.services.analytics_service import AnalyticsService
        analytics = AnalyticsService(client._api)

        # Track results for each app
        results = {}
        completed_reports_count = 0
        pending_count = 0
        created_count = 0
        unavailable_count = 0
        failed_count = 0

        # Process each app sequentially (waterfall)
        for idx, app_data in enumerate(selected_apps, 1):
            app_id = app_data["id"]
            app_name = app_data["name"]

            ctx.textual.text("=" * 60)
            ctx.textual.text(f"APP {idx}/{len(selected_apps)}: {app_name}")
            ctx.textual.text("=" * 60)
            ctx.textual.text("")

            # Check Analytics API access
            ctx.textual.text("Checking Analytics API access...")
            analytics_access_result = analytics.check_analytics_api_access(app_id)

            has_analytics = False
            match analytics_access_result:
                case ClientSuccess(data=access):
                    has_analytics = access
                case ClientError(error_message=err):
                    ctx.textual.error_text(f"❌ Failed to check Analytics access: {err}")
                    results[app_id] = {"status": "failed", "error": str(err)}
                    failed_count += 1
                    ctx.textual.text("")
                    continue

            if not has_analytics:
                ctx.textual.error_text("❌ Analytics API not available for this app")
                ctx.textual.text("")
                ctx.textual.text("This means:")
                ctx.textual.text("  - App may be too new (needs 14+ days of data)")
                ctx.textual.text("  - Or App Store Connect account doesn't have access")
                ctx.textual.text("")
                results[app_id] = {"status": "unavailable"}
                unavailable_count += 1
                ctx.textual.text("")
                continue

            ctx.textual.success_text("✓ Analytics API is accessible")
            ctx.textual.text("")

            # Skip cleanup - it can cause race conditions
            # The API will handle stuck requests automatically
            ctx.textual.text("Checking for existing requests...")

            # Check for existing completed reports
            existing_result = analytics.find_existing_request_with_reports(app_id)

            existing = None
            match existing_result:
                case ClientSuccess(data=existing_data):
                    existing = existing_data
                case ClientError(error_message=err):
                    ctx.textual.warning_text(f"  ⚠️  Failed to check existing reports: {err}")

            if existing:
                request_id, reports = existing
                ctx.textual.text("")
                ctx.textual.success_text("🎉 ANALYTICS REPORTS ARE READY!")
                ctx.textual.text("")
                ctx.textual.text(f"  Request ID: {request_id}")
                ctx.textual.text(f"  Available reports: {len(reports)}")
                ctx.textual.text("")

                for report in reports:
                    category = report.get("attributes", {}).get("category", "Unknown")
                    ctx.textual.text(f"    ✓ {category}")

                ctx.textual.text("")
                results[app_id] = {
                    "status": "ready",
                    "request_id": request_id,
                    "reports_count": len(reports)
                }
                completed_reports_count += 1
                ctx.textual.text("")
                continue

            # No existing reports - check if there's a pending request
            ctx.textual.text("")
            ctx.textual.text("🔍 Checking for pending requests...")

            # Try with different query params to handle cache/race conditions
            # Some requests may not show up immediately with include=reports
            query_params = {"limit": 50}  # First try without include
            response = analytics.api.get(
                f"/apps/{app_id}/analyticsReportRequests",
                query_params=query_params
            )
            requests_data = response.get("data", [])

            # If no requests found, try with include=reports (more detailed)
            if not requests_data:
                query_params = {"include": "reports", "limit": 50}
                response = analytics.api.get(
                    f"/apps/{app_id}/analyticsReportRequests",
                    query_params=query_params
                )
                requests_data = response.get("data", [])

            ctx.textual.text(f"  Found {len(requests_data)} total request(s)")

            if requests_data:
                # There's a pending request
                pending_id = requests_data[0]["id"]
                ctx.textual.text("")
                ctx.textual.text("⏳ ANALYTICS REQUEST IS PROCESSING...")
                ctx.textual.text("")
                ctx.textual.text(f"  Request ID: {pending_id}")
                ctx.textual.text("")
                ctx.textual.text("  Status: Processing (typically takes 30-60 minutes)")
                ctx.textual.text("")

                results[app_id] = {
                    "status": "pending",
                    "request_id": pending_id
                }
                pending_count += 1
                ctx.textual.text("")
                continue

            # No existing request - create a new one
            ctx.textual.text("")
            ctx.textual.text("📊 Creating new Analytics Report request...")
            ctx.textual.text("")

            create_result = analytics.create_analytics_report_request(app_id)

            match create_result:
                case ClientSuccess(data=request_id):
                    ctx.textual.success_text(f"✓ Request created: {request_id}")
                    ctx.textual.text("")
                    ctx.textual.text("⏳ ANALYTICS REPORTS ARE BEING GENERATED...")
                    ctx.textual.text("  This process takes 30-60 minutes.")
                    ctx.textual.text("")

                    results[app_id] = {
                        "status": "created",
                        "request_id": request_id
                    }
                    created_count += 1
                    ctx.textual.text("")

                case ClientError(error_message=err):
                    # Handle "already exists" error as a pending request
                    if "already have such an entity" in err.lower():
                        ctx.textual.text("")
                        ctx.textual.text("⏳ ANALYTICS REQUEST ALREADY EXISTS")
                        ctx.textual.text("")
                        ctx.textual.text("  An Analytics request is already active for this app.")
                        ctx.textual.text("  (It may be processing or stuck)")
                        ctx.textual.text("")

                        results[app_id] = {
                            "status": "pending",
                            "note": "invisible_request"
                        }
                        pending_count += 1
                        ctx.textual.text("")

                    else:
                        # Other errors
                        ctx.textual.error_text(f"❌ Failed to create request: {err}")
                        results[app_id] = {
                            "status": "failed",
                            "error": str(err)
                        }
                        failed_count += 1
                        ctx.textual.text("")

        # Show summary after processing all apps
        ctx.textual.text("=" * 60)
        ctx.textual.text("SUMMARY")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")
        ctx.textual.text(f"Total apps processed: {len(selected_apps)}")
        ctx.textual.text("")

        if completed_reports_count > 0:
            ctx.textual.success_text(f"✓ {completed_reports_count} app(s) with READY reports")
        if created_count > 0:
            ctx.textual.text(f"📊 {created_count} app(s) with NEW requests created")
        if pending_count > 0:
            ctx.textual.text(f"⏳ {pending_count} app(s) with PENDING requests")
        if unavailable_count > 0:
            ctx.textual.warning_text(f"⚠️  {unavailable_count} app(s) UNAVAILABLE")
        if failed_count > 0:
            ctx.textual.error_text(f"❌ {failed_count} app(s) FAILED")

        ctx.textual.text("")
        ctx.textual.text("=" * 60)
        ctx.textual.text("💡 NEXT STEPS")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")

        if completed_reports_count > 0:
            ctx.textual.success_text("✅ Apps with ready reports:")
            ctx.textual.text("   → Run 'Version Health Check' to see metrics")
            ctx.textual.text("")

        if created_count > 0 or pending_count > 0:
            ctx.textual.text("⏳ Apps with pending/new requests:")
            ctx.textual.text("   1. Wait 30-60 minutes for reports to complete")
            ctx.textual.text("   2. Run this workflow again to check status")
            ctx.textual.text("   3. Then run 'Version Health Check'")
            ctx.textual.text("")

        if unavailable_count > 0:
            ctx.textual.text("⚠️  Unavailable apps may be too new (need 14+ days)")
            ctx.textual.text("")

        # Save results to context
        ctx.data["analytics_results"] = results
        ctx.data["has_completed_reports"] = completed_reports_count > 0

        # Set overall status
        if completed_reports_count > 0:
            ctx.data["analytics_request_status"] = "ready"
        elif pending_count > 0 or created_count > 0:
            ctx.data["analytics_request_status"] = "pending"
        elif unavailable_count > 0:
            ctx.data["analytics_request_status"] = "unavailable"
        else:
            ctx.data["analytics_request_status"] = "failed"

        # Determine overall result
        total_success = completed_reports_count + created_count + pending_count
        if total_success == 0:
            ctx.textual.end_step("error")
            return Error(f"All {len(selected_apps)} app(s) failed or unavailable")
        elif failed_count > 0 or unavailable_count > 0:
            ctx.textual.end_step("warning")
            return Success(f"Processed {len(selected_apps)} app(s): {total_success} successful, {failed_count + unavailable_count} issues")
        else:
            ctx.textual.end_step("success")
            return Success(f"Successfully processed {len(selected_apps)} app(s)")

    except Exception as e:
        error_msg = f"Failed to request analytics: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["request_analytics_single_version_step"]
