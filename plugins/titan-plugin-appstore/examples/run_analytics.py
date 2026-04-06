#!/usr/bin/env python3
"""
Example script to run version analytics workflow programmatically.

This demonstrates how to use the analytics services directly
without going through the workflow system.
"""

import sys
from pathlib import Path

# Add plugin to path
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))

from titan_plugin_appstore.clients.appstore_client import AppStoreConnectClient
from titan_plugin_appstore.clients.services.analytics_service import AnalyticsService
from titan_plugin_appstore.credentials import CredentialsManager


def main():
    """Run analytics comparison for latest 2 versions."""

    print("🚀 App Store Analytics Runner\n")

    # 1. Load credentials
    print("📋 Loading credentials...")
    issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()

    if not key_id or not p8_path:
        print("❌ Error: App Store Connect not configured.")
        print("   Run: titan workflow run appstore:version-analytics")
        return 1

    print(f"   ✅ Key ID: {key_id}")
    print(f"   ✅ Private Key: {p8_path}\n")

    # 2. Initialize client
    print("🔌 Connecting to App Store Connect...")
    client = AppStoreConnectClient(
        key_id=key_id,
        issuer_id=issuer_id,
        private_key_path=p8_path,
    )

    # Test connection
    result = client.test_connection()
    if not result.is_success:
        print(f"❌ Connection failed: {result.error_message}")
        return 1

    print("   ✅ Connected!\n")

    # 3. List apps
    print("📱 Fetching apps...")
    apps_result = client.list_apps()

    if not apps_result.is_success:
        print(f"❌ Failed to fetch apps: {apps_result.error_message}")
        return 1

    apps = apps_result.data
    print(f"   ✅ Found {len(apps)} apps\n")

    # Display apps
    for i, app in enumerate(apps, 1):
        print(f"   {i}. {app.name} ({app.bundle_id})")

    # 4. Select app (use first for demo, or prompt user)
    if not apps:
        print("❌ No apps found in your account.")
        return 1

    selected_app = apps[0]
    print(f"\n🎯 Selected: {selected_app.name}\n")

    # 5. Get analytics service
    analytics = AnalyticsService(client._api)

    # 6. Fetch latest 2 versions
    print("📊 Fetching latest versions...")
    versions = analytics.get_app_versions_sorted(selected_app.id, limit=2)

    if len(versions) < 2:
        print(f"❌ Found only {len(versions)} version(s). Need at least 2.")
        return 1

    v1 = versions[0]
    v2 = versions[1]

    print(f"   ✅ V1: {v1['versionString']} (ID: {v1['id']})")
    print(f"   ✅ V2: {v2['versionString']} (ID: {v2['id']})\n")

    # 7. Request analytics (this is the main workflow)
    print("📈 Requesting analytics reports...")
    print("   (This may take 1-5 minutes)\n")

    from datetime import datetime, timedelta

    # Calculate date range
    if v1.get("earliestReleaseDate"):
        start_date = v1["earliestReleaseDate"][:10]
    else:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    end_date = datetime.now().strftime("%Y-%m-%d")

    print(f"   Date range: {start_date} to {end_date}")

    # Create APP_USAGE report
    print("\n🔄 Requesting APP_USAGE report...")
    usage_request_id = analytics.create_analytics_report_request(
        app_id=selected_app.id,
        version_ids=[v1["id"], v2["id"]],
        categories=["APP_USAGE"],
        start_date=start_date,
        end_date=end_date,
    )

    print(f"   ✅ Request ID: {usage_request_id}")
    print("   ⏳ Polling for completion...")

    success, download_url = analytics.poll_report_status(usage_request_id, max_wait_seconds=300)

    if not success:
        print("   ❌ Report timed out or failed.")
        return 1

    print("   ✅ Report ready!")
    print("   📥 Downloading...")

    raw_data = analytics.download_report_data(download_url)
    usage_data = analytics.parse_report_data(raw_data)

    print(f"   ✅ Downloaded {usage_data['count']} rows\n")

    # Create CRASHES report
    print("🔄 Requesting CRASHES report...")
    crash_request_id = analytics.create_analytics_report_request(
        app_id=selected_app.id,
        version_ids=[v1["id"], v2["id"]],
        categories=["CRASHES"],
        start_date=start_date,
        end_date=end_date,
    )

    print(f"   ✅ Request ID: {crash_request_id}")
    print("   ⏳ Polling...")

    success, download_url = analytics.poll_report_status(crash_request_id)

    if not success:
        print("   ⚠️  Crash report timed out (continuing anyway)")
        crash_data = {"rows": []}
    else:
        print("   ✅ Report ready!")
        print("   📥 Downloading...")
        raw_data = analytics.download_report_data(download_url)
        crash_data = analytics.parse_report_data(raw_data)
        print(f"   ✅ Downloaded {crash_data['count']} rows\n")

    # 8. Calculate metrics
    print("📊 Calculating metrics...\n")

    prop_v1 = analytics.calculate_propagation_metrics(usage_data["rows"], v1["id"])
    prop_v2 = analytics.calculate_propagation_metrics(usage_data["rows"], v2["id"])

    stab_v1 = analytics.calculate_stability_metrics(
        usage_data["rows"], crash_data["rows"], v1["id"]
    )
    stab_v2 = analytics.calculate_stability_metrics(
        usage_data["rows"], crash_data["rows"], v2["id"]
    )

    # 9. Display results
    print("=" * 60)
    print("PROPAGATION METRICS")
    print("=" * 60)
    print(f"{'Metric':<25} {v1['versionString']:<15} {v2['versionString']:<15}")
    print("-" * 60)
    print(
        f"{'Total Sessions':<25} {prop_v1.get('total_sessions', 0):>15,} {prop_v2.get('total_sessions', 0):>15,}"
    )
    print(
        f"{'Avg Daily Growth':<25} {prop_v1.get('avg_daily_growth', 0):>14.2f}% {prop_v2.get('avg_daily_growth', 0):>14.2f}%"
    )

    print("\n" + "=" * 60)
    print("STABILITY METRICS")
    print("=" * 60)
    print(f"{'Metric':<25} {v1['versionString']:<15} {v2['versionString']:<15}")
    print("-" * 60)
    print(
        f"{'Crash Rate':<25} {stab_v1.get('crash_rate', 0):>14.4f}% {stab_v2.get('crash_rate', 0):>14.4f}%"
    )
    print(
        f"{'Total Crashes':<25} {stab_v1.get('total_crashes', 0):>15,} {stab_v2.get('total_crashes', 0):>15,}"
    )
    print(
        f"{'Retention D1':<25} {stab_v1.get('retention_d1', 0):>14.2f}% {stab_v2.get('retention_d1', 0):>14.2f}%"
    )
    print(
        f"{'Retention D7':<25} {stab_v1.get('retention_d7', 0):>14.2f}% {stab_v2.get('retention_d7', 0):>14.2f}%"
    )

    print("\n✅ Analysis complete!")
    print("\nTo generate charts and HTML report, run:")
    print("   titan workflow run appstore:version-analytics\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
