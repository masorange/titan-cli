"""
Analytics Service - App Store Connect Analytics API (CORRECTO 2026)

Implementa el flujo completo:
1. POST /v1/analyticsReportRequests (sin filters!)
2. Polling con include=reports&fields[analyticsReports]=category,status
3. Download TSV desde /v1/analyticsReports/{report_id}/download
4. Parse TSV con pandas filtrando por appVersion
5. Cálculo de métricas de propagación y estabilidad
"""

import time
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network.appstore_api import AppStoreConnectAPI
from ...exceptions import APIError


class VersionInfo(BaseModel):
    """Simple version info model."""
    id: str
    versionString: str
    earliestReleaseDate: Optional[str] = None
    createdDate: Optional[str] = None
    has_active_users: bool = False


class PropagationMetricsView(BaseModel):
    """View model for propagation metrics."""
    version_string: str
    total_sessions: int = 0
    total_devices: int = 0
    total_units: int = 0
    daily_metrics: List[Dict[str, Any]] = []
    avg_daily_growth: float = 0.0
    error: Optional[str] = None


class StabilityMetricsView(BaseModel):
    """View model for stability metrics."""
    version_string: str
    crash_rate: float = 0.0
    total_crashes: int = 0
    total_sessions: int = 0
    retention_d1: float = 0.0
    retention_d7: float = 0.0
    error: Optional[str] = None


class AnalyticsService:
    """
    Service for App Store Connect Analytics Reports.

    Flujo completo:
    - Request analytics (ONE_TIME_SNAPSHOT)
    - Polling reports (status=COMPLETED, category=APP_USAGE/CRASHES)
    - Download TSV
    - Parse con pandas (filtro por appVersion)
    - Cálculo de métricas
    """

    def __init__(self, api_client: AppStoreConnectAPI):
        """
        Initialize analytics service.

        Args:
            api_client: Low-level API client for HTTP requests
        """
        self.api = api_client

    def get_app_versions_sorted(
        self, app_id: str, limit: int = 2
    ) -> ClientResult[List[VersionInfo]]:
        """
        Get latest app versions sorted by creation date.

        IMPORTANT: Returns versions with ACTIVE USERS, not all READY_FOR_SALE.
        Uses Performance Metrics to identify versions with real activity.

        Args:
            app_id: App ID
            limit: Number of versions (default: 2)

        Returns:
            ClientResult with list of VersionInfo models
        """
        try:
            from datetime import datetime, timedelta

            query_params = {
                "limit": 50,
                "filter[platform]": "IOS",
            }

            response_data = self.api.get(
                f"/apps/{app_id}/appStoreVersions", query_params=query_params
            )

            versions = response_data.get("data", [])

            # First: Get versions with active users from Performance Metrics
            versions_with_users = set()
            try:
                from .metrics_service import MetricsService
                metrics = MetricsService(self.api)
                perf_result = metrics.get_performance_metrics(app_id)

                match perf_result:
                    case ClientSuccess(data=perf_data):
                        crash_result = metrics.extract_crash_metrics_by_version(perf_data)
                        match crash_result:
                            case ClientSuccess(data=crash_metrics):
                                versions_with_users = set(crash_metrics.keys())
                            case _:
                                pass
                    case _:
                        pass
            except:
                # If Performance Metrics fails, fallback to recent READY_FOR_SALE
                pass

            # Filter candidates
            candidates = []
            cutoff_date = (datetime.now() - timedelta(days=90)).isoformat()

            for version in versions:
                attributes = version.get("attributes", {})
                version_string = attributes.get("versionString")
                state = attributes.get("appStoreState")
                created_date = attributes.get("createdDate", "")

                # Skip if not READY_FOR_SALE
                if state != "READY_FOR_SALE":
                    continue

                # Prioritize versions with active users
                has_active_users = version_string in versions_with_users

                # Or recent releases (last 90 days)
                is_recent = created_date >= cutoff_date

                # Include if has users OR is recent
                if has_active_users or is_recent:
                    candidates.append(VersionInfo(
                        id=version.get("id"),
                        versionString=version_string,
                        earliestReleaseDate=attributes.get("earliestReleaseDate"),
                        createdDate=created_date,
                        has_active_users=has_active_users
                    ))

            # Sort: Active users first, then by date
            candidates.sort(
                key=lambda x: (not x.has_active_users, x.createdDate or ""),
                reverse=True
            )

            result = candidates[:limit]

            return ClientSuccess(
                data=result,
                message=f"Found {len(result)} version(s) with active users"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to get versions: {str(e)}",
                error_code="API_ERROR"
            )
        except Exception as e:
            return ClientError(
                error_message=f"Failed to get versions: {str(e)}",
                error_code="UNKNOWN_ERROR"
            )

    def check_analytics_api_access(self, app_id: str) -> ClientResult[bool]:
        """
        Check if Analytics API is accessible.

        Args:
            app_id: App ID to test

        Returns:
            ClientResult with True if accessible, False otherwise
        """
        try:
            query_params = {"limit": 1}
            self.api.get(f"/apps/{app_id}/analyticsReportRequests", query_params=query_params)

            return ClientSuccess(
                data=True,
                message="Analytics API is accessible"
            )

        except APIError as e:
            return ClientSuccess(
                data=False,
                message=f"Analytics API not accessible: {str(e)}"
            )

    def cleanup_existing_requests(self, app_id: str) -> ClientResult[int]:
        """
        Clean up stuck/failed analytics requests.

        Args:
            app_id: App ID

        Returns:
            ClientResult with number of requests deleted
        """
        try:
            query_params = {"include": "reports", "limit": 20}
            response = self.api.get(
                f"/apps/{app_id}/analyticsReportRequests",
                query_params=query_params
            )

            requests_data = response.get("data", [])
            included_reports = response.get("included", [])

            if not requests_data:
                return ClientSuccess(
                    data=0,
                    message="No analytics requests to clean up"
                )

            deleted_count = 0

            for req in requests_data:
                req_id = req["id"]
                req_created = req.get("attributes", {}).get("createdDate", "")

                # Don't delete recent requests (< 2 hours) - they may still be processing
                if req_created:
                    from datetime import datetime, timedelta
                    try:
                        created_dt = datetime.fromisoformat(req_created.replace("Z", "+00:00"))
                        age = datetime.now(created_dt.tzinfo) - created_dt
                        if age < timedelta(hours=2):
                            # Skip recent requests - still processing
                            continue
                    except:
                        pass

                # Get reports for THIS specific request (filter by relationship)
                req_relationships = req.get("relationships", {}).get("reports", {}).get("data", [])
                req_report_ids = {r["id"] for r in req_relationships}

                req_reports = [
                    r for r in included_reports
                    if r.get("id") in req_report_ids and r.get("type") == "analyticsReports"
                ]

                # Check if has useful completed reports (APP_USAGE, CRASHES)
                useful_completed = [
                    r for r in req_reports
                    if r.get("attributes", {}).get("category") in ["APP_USAGE", "CRASHES"]
                ]

                # Delete if:
                # 1. No reports at all AND request is old (> 2 hours)
                # 2. Only FRAMEWORK_USAGE reports
                should_delete = (
                    not req_reports or
                    not useful_completed
                )

                if should_delete:
                    try:
                        self.api.delete(f"/analyticsReportRequests/{req_id}")
                        deleted_count += 1
                    except:
                        pass

            return ClientSuccess(
                data=deleted_count,
                message=f"Deleted {deleted_count} analytics request(s)"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to clean up requests: {str(e)}",
                error_code="API_ERROR"
            )

    def find_existing_request_with_reports(
        self, app_id: str
    ) -> ClientResult[Optional[Tuple[str, List[Dict[str, Any]]]]]:
        """
        Find existing request with COMPLETED reports.

        Args:
            app_id: App ID

        Returns:
            ClientResult with tuple of (request_id, completed_reports) or None
        """
        try:
            query_params = {"include": "reports", "limit": 50}
            response = self.api.get(
                f"/apps/{app_id}/analyticsReportRequests",
                query_params=query_params
            )

            requests_data = response.get("data", [])
            included_reports = response.get("included", [])

            for req in requests_data:
                req_id = req["id"]

                # Get completed APP_USAGE and CRASHES reports
                completed_reports = [
                    r for r in included_reports
                    if r.get("type") == "analyticsReports"
                    and r.get("attributes", {}).get("category") in ["APP_USAGE", "CRASHES"]
                ]

                if len(completed_reports) >= 2:  # Has both APP_USAGE and CRASHES
                    return ClientSuccess(
                        data=(req_id, completed_reports),
                        message=f"Found existing request {req_id} with {len(completed_reports)} report(s)"
                    )

            return ClientSuccess(
                data=None,
                message="No existing request with completed reports found"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to find existing request: {str(e)}",
                error_code="API_ERROR"
            )

    def create_analytics_report_request(
        self, app_id: str
    ) -> ClientResult[str]:
        """
        ✅ CORRECTO: POST sin filters, solo app relationship.

        Args:
            app_id: App ID

        Returns:
            ClientResult with request ID
        """
        try:
            payload = {
                "data": {
                    "type": "analyticsReportRequests",
                    "attributes": {
                        "accessType": "ONE_TIME_SNAPSHOT"
                    },
                    "relationships": {
                        "app": {
                            "data": {
                                "type": "apps",
                                "id": app_id
                            }
                        }
                    }
                }
            }

            response = self.api.post("/analyticsReportRequests", json_data=payload)
            request_id = response.get("data", {}).get("id")

            if not request_id:
                return ClientError(
                    error_message="No request ID in response",
                    error_code="API_ERROR"
                )

            return ClientSuccess(
                data=request_id,
                message=f"Created analytics request {request_id}"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to create analytics request: {str(e)}",
                error_code="API_ERROR"
            )

    def poll_reports(
        self, request_id: str, max_wait_minutes: int = 120
    ) -> ClientResult[List[Dict[str, Any]]]:
        """
        ✅ CORRECTO: Polling con include=reports&fields[analyticsReports]=category,status

        Args:
            request_id: Analytics request ID
            max_wait_minutes: Max time to wait (default: 120 = 2 hours)

        Returns:
            ClientResult with list of completed reports (APP_USAGE, CRASHES, INSTALLS)
        """
        try:
            max_iterations = max_wait_minutes // 5  # Poll every 5 minutes

            for i in range(max_iterations):
                try:
                    query_params = {
                        "include": "reports",
                        "fields[analyticsReports]": "category,status"
                    }

                    response = self.api.get(
                        f"/analyticsReportRequests/{request_id}",
                        query_params=query_params
                    )

                    # Filter completed reports
                    included = response.get("included", [])
                    completed_reports = [
                        rep for rep in included
                        if rep.get("type") == "analyticsReports"
                        and rep.get("attributes", {}).get("status") == "COMPLETED"
                        and rep.get("attributes", {}).get("category") in ["APP_USAGE", "CRASHES", "INSTALLS"]
                    ]

                    if completed_reports:
                        return ClientSuccess(
                            data=completed_reports,
                            message=f"Found {len(completed_reports)} completed report(s)"
                        )

                    # Wait 5 minutes
                    if i < max_iterations - 1:
                        time.sleep(300)

                except APIError as e:
                    # Rate limit handling
                    if hasattr(e, "status_code") and e.status_code == 429:
                        time.sleep(600)  # Wait 10 minutes on rate limit
                        continue
                    return ClientError(
                        error_message=f"API error during polling: {str(e)}",
                        error_code="API_ERROR"
                    )

            return ClientError(
                error_message=f"Reports not ready after {max_wait_minutes} minutes",
                error_code="TIMEOUT"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to poll reports: {str(e)}",
                error_code="POLLING_ERROR"
            )

    def download_report_tsv(self, report_id: str) -> ClientResult[bytes]:
        """
        ✅ CORRECTO: GET /v1/analyticsReports/{report_id}/download → URL temporal

        Args:
            report_id: Analytics report ID

        Returns:
            ClientResult with TSV data (bytes)
        """
        try:
            # Get download URL
            response = self.api.get(f"/analyticsReports/{report_id}/download")
            download_url = response.get("data", {}).get("attributes", {}).get("downloadUrl")

            if not download_url:
                return ClientError(
                    error_message="No download URL in response",
                    error_code="API_ERROR"
                )

            # Download TSV (direct HTTP, not through API client)
            import requests
            tsv_response = requests.get(download_url, timeout=60)
            tsv_response.raise_for_status()

            return ClientSuccess(
                data=tsv_response.content,
                message=f"Downloaded report {report_id}"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to download report: {str(e)}",
                error_code="DOWNLOAD_ERROR"
            )

    def parse_tsv_to_dataframe(self, tsv_data: bytes) -> ClientResult[Any]:
        """
        ✅ CORRECTO: Parse TSV con pandas (sep='\\t')

        Args:
            tsv_data: Raw TSV bytes

        Returns:
            ClientResult with pandas DataFrame
        """
        try:
            import pandas as pd
            from io import BytesIO

            df = pd.read_csv(BytesIO(tsv_data), sep="\t")

            return ClientSuccess(
                data=df,
                message=f"Parsed TSV with {len(df)} row(s)"
            )

        except ImportError:
            return ClientError(
                error_message="pandas not installed. Run: pip install pandas",
                error_code="DEPENDENCY_ERROR"
            )
        except Exception as e:
            return ClientError(
                error_message=f"Failed to parse TSV: {str(e)}",
                error_code="PARSE_ERROR"
            )

    def calculate_propagation_metrics(
        self, usage_df, version_string: str
    ) -> ClientResult[PropagationMetricsView]:
        """
        ✅ CORRECTO: Filtro por appVersion, extrae sessions, activeDevices, appUnits

        Args:
            usage_df: pandas DataFrame from APP_USAGE report
            version_string: Version string (e.g., "26.11.2")

        Returns:
            ClientResult with PropagationMetricsView
        """
        try:
            # Filter by version
            df_version = usage_df[usage_df["appVersion"].astype(str) == version_string]

            if df_version.empty:
                return ClientSuccess(
                    data=PropagationMetricsView(
                        version_string=version_string,
                        error=f"No data for version {version_string}"
                    ),
                    message=f"No data for version {version_string}"
                )

            # Sort by date
            if "date" in df_version.columns:
                df_version = df_version.sort_values("date")

            # Extract metrics
            total_sessions = df_version["sessions"].sum() if "sessions" in df_version.columns else 0
            total_devices = df_version["activeDevices"].sum() if "activeDevices" in df_version.columns else 0
            total_units = df_version["appUnits"].sum() if "appUnits" in df_version.columns else 0

            # Calculate daily growth
            daily_metrics = []
            prev_sessions = None

            for _, row in df_version.iterrows():
                date = row.get("date", "")
                sessions = int(row.get("sessions", 0))
                devices = int(row.get("activeDevices", 0))

                growth_pct = None
                if prev_sessions and prev_sessions > 0:
                    growth_pct = ((sessions - prev_sessions) / prev_sessions) * 100

                daily_metrics.append({
                    "date": str(date),
                    "sessions": sessions,
                    "activeDevices": devices,
                    "growth_pct": growth_pct,
                })

                prev_sessions = sessions

            avg_growth = sum(m["growth_pct"] for m in daily_metrics if m["growth_pct"] is not None) / max(1, len([m for m in daily_metrics if m["growth_pct"] is not None]))

            metrics = PropagationMetricsView(
                version_string=version_string,
                total_sessions=int(total_sessions),
                total_devices=int(total_devices),
                total_units=int(total_units),
                daily_metrics=daily_metrics,
                avg_daily_growth=float(avg_growth)
            )

            return ClientSuccess(
                data=metrics,
                message=f"Calculated propagation metrics for {version_string}"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to calculate propagation metrics: {str(e)}",
                error_code="CALCULATION_ERROR"
            )

    def calculate_stability_metrics(
        self, usage_df, crash_df, version_string: str
    ) -> ClientResult[StabilityMetricsView]:
        """
        ✅ CORRECTO: Filtro por appVersion, extrae crashes, crashRate, retention_D1/D7

        Args:
            usage_df: DataFrame from APP_USAGE
            crash_df: DataFrame from CRASHES
            version_string: Version string

        Returns:
            ClientResult with StabilityMetricsView
        """
        try:
            # Filter by version
            df_usage_v = usage_df[usage_df["appVersion"].astype(str) == version_string]
            df_crash_v = crash_df[crash_df["appVersion"].astype(str) == version_string]

            # Sessions and crashes
            total_sessions = df_usage_v["sessions"].sum() if "sessions" in df_usage_v.columns and not df_usage_v.empty else 0
            total_crashes = df_crash_v["crashes"].sum() if "crashes" in df_crash_v.columns and not df_crash_v.empty else 0

            # Crash rate
            crash_rate = (total_crashes / total_sessions * 100) if total_sessions > 0 else 0

            # Retention (from APP_USAGE columns: retention_D1, retention_D7)
            retention_d1 = 0.0
            retention_d7 = 0.0

            if "retention_D1" in df_usage_v.columns and not df_usage_v.empty:
                retention_d1 = df_usage_v["retention_D1"].mean()

            if "retention_D7" in df_usage_v.columns and not df_usage_v.empty:
                retention_d7 = df_usage_v["retention_D7"].mean()

            metrics = StabilityMetricsView(
                version_string=version_string,
                crash_rate=float(crash_rate),
                total_crashes=int(total_crashes),
                total_sessions=int(total_sessions),
                retention_d1=float(retention_d1) if retention_d1 else 0.0,
                retention_d7=float(retention_d7) if retention_d7 else 0.0
            )

            return ClientSuccess(
                data=metrics,
                message=f"Calculated stability metrics for {version_string}"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to calculate stability metrics: {str(e)}",
                error_code="CALCULATION_ERROR"
            )

    # FALLBACK methods (when Analytics API unavailable)
    def get_propagation_metrics_from_builds(
        self, app_id: str, version_ids: List[str]
    ) -> ClientResult[Dict[str, Any]]:
        """FALLBACK: Estimate from builds."""
        try:
            metrics = {}

            for version_id in version_ids:
                try:
                    query_params = {"filter[preReleaseVersion.version]": version_id, "limit": 50}
                    response = self.api.get(f"/apps/{app_id}/builds", query_params=query_params)
                    builds = response.get("data", [])

                    upload_dates = [b.get("attributes", {}).get("uploadedDate") for b in builds if b.get("attributes", {}).get("uploadedDate")]
                    upload_dates.sort()

                    metrics[version_id] = {
                        "total_builds": len(builds),
                        "first_upload": upload_dates[0] if upload_dates else None,
                        "last_upload": upload_dates[-1] if upload_dates else None,
                        "estimated_activity": "high" if len(builds) > 10 else "medium" if len(builds) > 3 else "low",
                    }

                except Exception as e:
                    metrics[version_id] = {"error": str(e)}

            return ClientSuccess(
                data=metrics,
                message=f"Estimated propagation metrics for {len(metrics)} version(s)"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to get propagation metrics from builds: {str(e)}",
                error_code="FALLBACK_ERROR"
            )

    def get_stability_metrics_from_reviews(
        self, app_id: str, version_strings: List[str]
    ) -> ClientResult[Dict[str, Any]]:
        """FALLBACK: Estimate from reviews."""
        try:
            metrics = {}
            crash_keywords = ["crash", "crashes", "freeze", "freezes", "stuck", "error", "bug", "cierra", "falla"]

            for version_string in version_strings:
                try:
                    query_params = {"filter[territory]": "ESP", "limit": 50}
                    response = self.api.get(f"/apps/{app_id}/customerReviews", query_params=query_params)
                    reviews = response.get("data", [])

                    total_reviews = 0
                    crash_mentions = 0
                    ratings = []

                    for review in reviews:
                        attributes = review.get("attributes", {})
                        review_body = (attributes.get("body") or "").lower()
                        rating = attributes.get("rating", 0)

                        if version_string in review_body or version_string.replace(".", "") in review_body:
                            total_reviews += 1
                            ratings.append(rating)

                            if any(keyword in review_body for keyword in crash_keywords):
                                crash_mentions += 1

                    avg_rating = sum(ratings) / len(ratings) if ratings else 0
                    crash_mention_rate = (crash_mentions / total_reviews * 100) if total_reviews > 0 else 0

                    metrics[version_string] = {
                        "total_reviews": total_reviews,
                        "average_rating": avg_rating,
                        "crash_mention_rate": crash_mention_rate,
                        "estimated_stability": "high" if crash_mention_rate < 10 and avg_rating > 4 else "medium" if crash_mention_rate < 25 else "low",
                    }

                except Exception as e:
                    metrics[version_string] = {"error": str(e)}

            return ClientSuccess(
                data=metrics,
                message=f"Estimated stability metrics for {len(metrics)} version(s)"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to get stability metrics from reviews: {str(e)}",
                error_code="FALLBACK_ERROR"
            )
