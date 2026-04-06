"""
Fetch Versions Step - Interactive version selection for analytics comparison.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager


def fetch_versions_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Interactive selection of 2 versions to compare.

    Shows up to 10 latest production versions with metadata:
    - Version number
    - Release date
    - Active users indicator (has crash data)

    Inputs (from ctx.data):
        app_id: App Store Connect app ID

    Outputs (saved to ctx.data):
        - latest_versions: List of 2 selected version dicts
        - version_1_id: ID of first selected version
        - version_2_id: ID of second selected version
        - version_1_string: Version string of first
        - version_2_string: Version string of second

    Returns:
        Success with selected versions
        Error if insufficient versions
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Fetch Versions")

    try:
        app_id = ctx.data.get("app_id")

        if not app_id:
            ctx.textual.error_text("No app_id found in context")
            ctx.textual.end_step("error")
            return Error("No app_id found. Run select_app_step first.")

        # Load credentials and create client
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        # Get analytics service and metrics service
        from ..clients.services.analytics_service import AnalyticsService
        from ..clients.services.metrics_service import MetricsService

        analytics = AnalyticsService(client._api)
        metrics_service = MetricsService(client._api)

        # Fetch up to 10 latest production versions
        ctx.textual.text("Fetching production versions...")
        versions_result = analytics.get_app_versions_sorted(app_id, limit=10)

        # Handle ClientResult
        match versions_result:
            case ClientSuccess(data=all_versions):
                # Convert VersionInfo objects to dicts for compatibility
                all_versions = [
                    {
                        "id": v.id,
                        "versionString": v.versionString,
                        "earliestReleaseDate": v.earliestReleaseDate,
                        "createdDate": v.createdDate,
                    }
                    for v in all_versions
                ]
            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to fetch versions: {err}")
                ctx.textual.end_step("error")
                return Error(f"Failed to fetch versions: {err}")

        if len(all_versions) < 2:
            ctx.textual.error_text(f"Found only {len(all_versions)} version(s). Need at least 2.")
            ctx.textual.end_step("error")
            return Error(f"Insufficient versions: found {len(all_versions)}, need 2")

        # Get performance data to check which versions have active users
        ctx.textual.text("Checking which versions have active users...")
        versions_with_data = {}

        perf_result = metrics_service.get_performance_metrics(app_id, platform="IOS")
        match perf_result:
            case ClientSuccess(data=perf_data):
                crash_result = metrics_service.extract_crash_metrics_by_version(perf_data)
                match crash_result:
                    case ClientSuccess(data=crash_metrics):
                        versions_with_data = crash_metrics
                    case _:
                        pass  # No crash data available
            case _:
                pass  # Performance metrics not available

        # Format release dates and prepare display data
        from datetime import datetime

        version_display_data = []
        for idx, version in enumerate(all_versions):
            version_str = version["versionString"]
            # Try earliestReleaseDate first, then createdDate
            release_date = version.get("earliestReleaseDate") or version.get("createdDate", "Unknown")

            # Check if version has active users and get crash rate
            crash_data = versions_with_data.get(version_str, {})
            has_users = bool(crash_data)
            crash_rate = crash_data.get("crash_rate", 0.0) if has_users else None

            # Format release date
            if release_date != "Unknown":
                try:
                    date_obj = datetime.fromisoformat(release_date.replace('Z', '+00:00'))
                    date_str = date_obj.strftime("%Y-%m-%d")
                except:
                    date_str = release_date[:10] if len(release_date) >= 10 else release_date
            else:
                date_str = "Unknown"

            version_display_data.append({
                "idx": idx,
                "version": version_str,
                "date": date_str,
                "has_users": has_users,
                "crash_rate": crash_rate
            })

        # Prepare version selection using SelectionOption (with all info in labels)
        from titan_cli.ui.tui.widgets import SelectionOption

        # Build version objects for selection
        class VersionChoice:
            def __init__(self, idx, version_str, date_str, crash_rate, version_dict):
                self.idx = idx
                self.version = version_str
                self.date = date_str
                self.crash_rate = crash_rate
                self.version_dict = version_dict

            def display_label(self):
                # Compact format: version + date + crash indicator
                if self.crash_rate is not None:
                    if self.crash_rate > 10:
                        status = f"🔴 {self.crash_rate:>5.2f}%"
                    elif self.crash_rate > 5:
                        status = f"🟡 {self.crash_rate:>5.2f}%"
                    else:
                        status = f"🟢 {self.crash_rate:>5.2f}%"
                    return f"{self.version:10} │ {self.date:12} │ {status}"
                else:
                    return f"{self.version:10} │ {self.date:12} │ No crash data"

        version_choices = [
            VersionChoice(
                idx=data['idx'],
                version_str=data['version'],
                date_str=data['date'],
                crash_rate=data['crash_rate'],
                version_dict=all_versions[data['idx']]
            )
            for data in version_display_data
        ]

        # Create selection options (none selected by default)
        selection_options = [
            SelectionOption(
                value=choice,
                label=choice.display_label(),
                selected=False
            )
            for choice in version_choices
        ]

        # Ask user to select 2 versions
        ctx.textual.text("Select 2 versions to compare (use Space to select, Enter to confirm):")
        ctx.textual.text("")

        selected_versions_objs = ctx.textual.ask_multiselect(
            "Select exactly 2 versions:",
            options=selection_options
        )

        # Validate exactly 2 selections
        while len(selected_versions_objs) != 2:
            if len(selected_versions_objs) < 2:
                ctx.textual.error_text(f"⚠️  You selected {len(selected_versions_objs)} version(s). Please select exactly 2.")
            else:
                ctx.textual.error_text(f"⚠️  You selected {len(selected_versions_objs)} version(s). Please select only 2.")

            ctx.textual.text("")
            selected_versions_objs = ctx.textual.ask_multiselect(
                "Select exactly 2 versions:",
                options=selection_options
            )

        # Sort selections by index to maintain order (latest first)
        selected_versions_objs.sort(key=lambda v: v.idx)

        version_1 = selected_versions_objs[0].version_dict
        version_2 = selected_versions_objs[1].version_dict

        # Store in context
        selected_versions = [version_1, version_2]
        ctx.data["latest_versions"] = selected_versions
        ctx.data["version_1_id"] = version_1["id"]
        ctx.data["version_2_id"] = version_2["id"]
        ctx.data["version_1_string"] = version_1["versionString"]
        ctx.data["version_2_string"] = version_2["versionString"]

        # Display selection
        ctx.textual.text("")
        ctx.textual.success_text(f"✓ First:  {version_1['versionString']}")
        ctx.textual.success_text(f"✓ Second: {version_2['versionString']}")
        ctx.textual.end_step("success")

        return Success(f"Fetched versions: {version_1['versionString']} vs {version_2['versionString']}")

    except Exception as e:
        error_msg = f"Failed to fetch versions: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)
