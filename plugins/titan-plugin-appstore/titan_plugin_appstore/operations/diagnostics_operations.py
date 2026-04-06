"""
Diagnostics Operations - Fetch crash and hang reports from App Store Connect.

Provides programmatic access to crash logs and hang reports without Xcode.
"""

from typing import List, Optional, Dict, Any
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from ..clients.appstore_client import AppStoreConnectClient


class DiagnosticsOperations:
    """
    Operations for accessing diagnostics (crashes and hangs).

    Useful for CI/CD environments where Xcode Organizer is not available.
    """

    def __init__(self, client: AppStoreConnectClient):
        """
        Initialize diagnostics operations.

        Args:
            client: App Store Connect client
        """
        self.client = client
        self.api = client._api

    def get_hang_reports(
        self,
        app_id: str,
        version_string: Optional[str] = None,
        limit: int = 20,
    ) -> ClientResult[List[Dict[str, Any]]]:
        """
        Get hang reports for an app version.

        Args:
            app_id: App ID
            version_string: Filter by version (optional)
            limit: Max number of reports to return

        Returns:
            ClientResult[List[Dict]] with hang report data
        """
        try:
            # Build query params
            query_params = {
                "limit": str(limit),
                "sort": "-frequency",  # Most frequent first
            }

            if version_string:
                query_params["filter[appVersion]"] = version_string

            # Note: This endpoint requires correct API path
            # App Store Connect API v1.6+ has diagnostics endpoints
            url = self.api._build_url(
                f"/apps/{app_id}/perfPowerMetrics/hangData",
                query_params=query_params
            )

            headers = self.api._get_headers()
            headers["Accept"] = "application/json"

            import requests
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            data = response.json()

            # Extract hang reports
            hang_reports = []

            if "data" in data:
                for item in data["data"]:
                    attributes = item.get("attributes", {})

                    hang_report = {
                        "signature": attributes.get("signature", "Unknown"),
                        "frequency": attributes.get("frequency", 0),
                        "duration": attributes.get("duration", 0),
                        "stack_trace": attributes.get("stackTrace", []),
                        "affected_devices": attributes.get("deviceCount", 0),
                    }

                    hang_reports.append(hang_report)

            return ClientSuccess(
                data=hang_reports,
                message=f"Retrieved {len(hang_reports)} hang report(s)"
            )

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return ClientError(
                    error_message=(
                        "Hang reports endpoint not available. "
                        "Use App Store Connect web UI instead: "
                        "https://appstoreconnect.apple.com → App → Crashes & Hangs"
                    ),
                    error_code="ENDPOINT_NOT_AVAILABLE"
                )
            else:
                return ClientError(
                    error_message=f"API error: {str(e)}",
                    error_code="API_ERROR"
                )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to get hang reports: {str(e)}",
                error_code="FETCH_ERROR"
            )

    def get_crash_reports(
        self,
        app_id: str,
        version_string: Optional[str] = None,
        limit: int = 20,
    ) -> ClientResult[List[Dict[str, Any]]]:
        """
        Get crash reports for an app version.

        Args:
            app_id: App ID
            version_string: Filter by version (optional)
            limit: Max number of reports to return

        Returns:
            ClientResult[List[Dict]] with crash report data
        """
        try:
            query_params = {
                "limit": str(limit),
                "sort": "-frequency",
            }

            if version_string:
                query_params["filter[appVersion]"] = version_string

            url = self.api._build_url(
                f"/apps/{app_id}/perfPowerMetrics/crashData",
                query_params=query_params
            )

            headers = self.api._get_headers()
            headers["Accept"] = "application/json"

            import requests
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            data = response.json()

            crash_reports = []

            if "data" in data:
                for item in data["data"]:
                    attributes = item.get("attributes", {})

                    crash_report = {
                        "signature": attributes.get("signature", "Unknown"),
                        "frequency": attributes.get("frequency", 0),
                        "crash_type": attributes.get("crashType", "Unknown"),
                        "stack_trace": attributes.get("stackTrace", []),
                        "affected_devices": attributes.get("deviceCount", 0),
                    }

                    crash_reports.append(crash_report)

            return ClientSuccess(
                data=crash_reports,
                message=f"Retrieved {len(crash_reports)} crash report(s)"
            )

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return ClientError(
                    error_message=(
                        "Crash reports endpoint not available. "
                        "Use App Store Connect web UI instead."
                    ),
                    error_code="ENDPOINT_NOT_AVAILABLE"
                )
            else:
                return ClientError(
                    error_message=f"API error: {str(e)}",
                    error_code="API_ERROR"
                )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to get crash reports: {str(e)}",
                error_code="FETCH_ERROR"
            )

    def get_diagnostics_summary(
        self,
        app_id: str,
        version_string: str,
    ) -> ClientResult[Dict[str, Any]]:
        """
        Get complete diagnostics summary (crashes + hangs).

        Args:
            app_id: App ID
            version_string: Version to analyze

        Returns:
            ClientResult[Dict] with summary data
        """
        # Get performance metrics (we already have this)
        from ..clients.services.metrics_service import MetricsService
        metrics = MetricsService(self.api)

        perf_result = metrics.get_performance_metrics(app_id)

        match perf_result:
            case ClientSuccess(data=perf_data):
                crash_metrics_result = metrics.extract_crash_metrics_by_version(
                    perf_data
                )

                match crash_metrics_result:
                    case ClientSuccess(data=crash_metrics):
                        version_metrics = crash_metrics.get(version_string, {})
                    case ClientError():
                        version_metrics = {}
            case ClientError():
                version_metrics = {}

        # Try to get detailed reports (may not be available via API)
        hang_reports_result = self.get_hang_reports(
            app_id, version_string, limit=5
        )
        crash_reports_result = self.get_crash_reports(
            app_id, version_string, limit=5
        )

        summary = {
            "version_string": version_string,
            "metrics": version_metrics,
            "top_hangs": [],
            "top_crashes": [],
            "hang_reports_available": False,
            "crash_reports_available": False,
        }

        match hang_reports_result:
            case ClientSuccess(data=hangs):
                summary["top_hangs"] = hangs[:5]
                summary["hang_reports_available"] = True
            case ClientError():
                pass

        match crash_reports_result:
            case ClientSuccess(data=crashes):
                summary["top_crashes"] = crashes[:5]
                summary["crash_reports_available"] = True
            case ClientError():
                pass

        return ClientSuccess(
            data=summary,
            message=f"Diagnostics summary for {version_string}"
        )
