"""
Analysis Operations - Combine stability and propagation metrics.

High-level operations that orchestrate multiple API calls to provide
comprehensive version analysis.
"""

from typing import Optional, List, Tuple
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..clients.appstore_client import AppStoreConnectClient
from ..clients.services.metrics_service import MetricsService
from ..models.analysis import (
    VersionAnalysisView,
    StabilityMetrics,
    PropagationMetrics,
    VersionComparisonView,
)


class AnalysisOperations:
    """
    High-level operations for version analysis.

    Responsibilities:
    - Combine stability + propagation metrics
    - Generate health scores
    - Compare versions
    - Provide recommendations
    """

    def __init__(self, client: AppStoreConnectClient):
        """
        Initialize analysis operations.

        Args:
            client: App Store Connect client
        """
        self.client = client
        self.metrics = client.metrics

    def analyze_version(
        self,
        app_id: str,
        version_string: str,
        vendor_number: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> ClientResult[VersionAnalysisView]:
        """
        Analyze a single version combining stability and propagation.

        This is the main operation that combines:
        1. Performance metrics (crashes, hangs) from Performance API
        2. Propagation metrics (units, countries) from Sales Reports API

        Args:
            app_id: App Store Connect app ID
            version_string: Version to analyze (e.g., "1.2.3")
            vendor_number: Vendor number for sales reports (optional)
            app_name: App name for sales filtering (optional, required if vendor_number provided)

        Returns:
            ClientResult[VersionAnalysisView] with combined metrics
        """
        # Step 1: Get version ID
        version_result = self.client.list_versions(
            app_id, version_string=version_string
        )

        match version_result:
            case ClientSuccess(data=versions):
                if not versions:
                    return ClientError(
                        error_message=f"Version {version_string} not found",
                        error_code="VERSION_NOT_FOUND",
                    )
                version_id = versions[0].id
            case ClientError() as error:
                return error

        # Step 2: Get stability metrics
        stability_result = self._get_stability_metrics(app_id, version_string)

        match stability_result:
            case ClientSuccess(data=stability):
                pass
            case ClientError() as error:
                # Create empty stability if failed
                stability = StabilityMetrics(version_string=version_string)

        # Step 3: Get propagation metrics (optional)
        propagation: PropagationMetrics

        if vendor_number and app_name:
            propagation_result = self._get_propagation_metrics(
                vendor_number, app_name, version_string, app_id
            )

            match propagation_result:
                case ClientSuccess(data=prop):
                    propagation = prop
                case ClientError():
                    # Create empty propagation if failed
                    propagation = PropagationMetrics(version_string=version_string)
        else:
            # No vendor number, use empty propagation
            propagation = PropagationMetrics(version_string=version_string)

        # Step 4: Get app info
        app_result = self.client.get_app(app_id)

        match app_result:
            case ClientSuccess(data=app):
                final_app_name = app.name
            case ClientError():
                final_app_name = app_name or "Unknown"

        # Step 5: Build analysis view
        analysis = VersionAnalysisView(
            version_id=version_id,
            version_string=version_string,
            app_id=app_id,
            app_name=final_app_name,
            stability=stability,
            propagation=propagation,
        )

        # Compute health metrics
        analysis.compute_health_score()
        analysis.compute_status()

        return ClientSuccess(
            data=analysis,
            message=f"Analysis complete for v{version_string}",
        )

    def compare_versions(
        self,
        app_id: str,
        current_version: str,
        previous_version: str,
        vendor_number: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> ClientResult[VersionComparisonView]:
        """
        Compare two versions side-by-side.

        Args:
            app_id: App ID
            current_version: Current version string
            previous_version: Previous version string
            vendor_number: Vendor number (optional)
            app_name: App name (optional)

        Returns:
            ClientResult[VersionComparisonView] with comparison data
        """
        # Analyze current version
        current_result = self.analyze_version(
            app_id, current_version, vendor_number, app_name
        )

        match current_result:
            case ClientSuccess(data=current_analysis):
                pass
            case ClientError() as error:
                return error

        # Analyze previous version
        previous_result = self.analyze_version(
            app_id, previous_version, vendor_number, app_name
        )

        match previous_result:
            case ClientSuccess(data=previous_analysis):
                pass
            case ClientError():
                # If previous version analysis fails, still return current
                previous_analysis = None

        # Build comparison
        comparison = VersionComparisonView(
            current_version=current_analysis,
            previous_version=previous_analysis,
        )

        comparison.compute_deltas()

        return ClientSuccess(
            data=comparison,
            message=f"Comparison complete: {previous_version} → {current_version}",
        )

    def analyze_latest_versions(
        self,
        app_id: str,
        count: int = 2,
        vendor_number: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> ClientResult[List[VersionAnalysisView]]:
        """
        Analyze the latest N versions.

        Args:
            app_id: App ID
            count: Number of versions to analyze (default: 2)
            vendor_number: Vendor number (optional)
            app_name: App name (optional)

        Returns:
            ClientResult[List[VersionAnalysisView]] with analysis for each version
        """
        # Get latest versions
        versions_result = self.client.list_versions(app_id)

        match versions_result:
            case ClientSuccess(data=versions):
                if not versions:
                    return ClientError(
                        error_message="No versions found",
                        error_code="NO_VERSIONS",
                    )

                # Sort by created date (newest first)
                sorted_versions = sorted(
                    versions,
                    key=lambda v: v.created_date or "",
                    reverse=True,
                )

                # Take latest N
                latest_versions = sorted_versions[:count]
            case ClientError() as error:
                return error

        # Analyze each version
        analyses = []

        for version in latest_versions:
            analysis_result = self.analyze_version(
                app_id, version.version_string, vendor_number, app_name
            )

            match analysis_result:
                case ClientSuccess(data=analysis):
                    analyses.append(analysis)
                case ClientError():
                    # Skip failed analyses
                    pass

        if not analyses:
            return ClientError(
                error_message="Failed to analyze any versions",
                error_code="ANALYSIS_FAILED",
            )

        return ClientSuccess(
            data=analyses,
            message=f"Analyzed {len(analyses)} version(s)",
        )

    def _get_stability_metrics(
        self, app_id: str, version_string: str
    ) -> ClientResult[StabilityMetrics]:
        """
        Get stability metrics for a version.

        Args:
            app_id: App ID
            version_string: Version string

        Returns:
            ClientResult[StabilityMetrics]
        """
        # Get performance metrics
        perf_result = self.metrics.get_performance_metrics(app_id)

        match perf_result:
            case ClientSuccess(data=perf_data):
                pass
            case ClientError() as error:
                return error

        # Extract crash metrics
        crash_result = self.metrics.extract_crash_metrics_by_version(perf_data)

        match crash_result:
            case ClientSuccess(data=crash_metrics):
                version_metrics = crash_metrics.get(
                    version_string,
                    {
                        "crash_rate": 0.0,
                        "hang_rate": 0.0,
                        "terminations": 0,
                        "hangs": 0,
                    },
                )

                stability = StabilityMetrics(
                    version_string=version_string,
                    crash_rate=version_metrics["crash_rate"],
                    hang_rate=version_metrics["hang_rate"],
                    terminations=version_metrics["terminations"],
                    hangs=version_metrics["hangs"],
                )

                return ClientSuccess(
                    data=stability,
                    message=f"Stability metrics for v{version_string}",
                )
            case ClientError() as error:
                return error

    def _get_propagation_metrics(
        self, vendor_number: str, app_name: str, version_string: str, app_id: str
    ) -> ClientResult[PropagationMetrics]:
        """
        Get propagation metrics for a version.

        Attempts Analytics Reports API first (activeDevices, sessions, appUnits),
        falls back to Sales Reports if not available.

        Args:
            vendor_number: Vendor number
            app_name: App name
            version_string: Version string
            app_id: App ID (for Analytics API)

        Returns:
            ClientResult[PropagationMetrics]
        """
        # DEBUG: Print what we're searching for
        print(f"\n=== DEBUG: _get_propagation_metrics ===")
        print(f"App ID: {app_id}")
        print(f"App Name: '{app_name}'")
        print(f"Version: {version_string}")
        print(f"Vendor Number: {vendor_number}")
        print("=" * 50 + "\n")

        # Try Analytics Reports API first (preferred method)
        from ..clients.services.analytics_service import AnalyticsService
        analytics = AnalyticsService(self.client._api)

        # Check if Analytics API is available and has existing reports
        analytics_access = analytics.check_analytics_api_access(app_id)
        print(f"DEBUG: Analytics API access: {analytics_access}")

        if analytics_access:
            try:
                # Check for existing completed reports
                existing_result = analytics.find_existing_request_with_reports(app_id)

                match existing_result:
                    case ClientSuccess(data=existing):
                        print(f"DEBUG: Found existing Analytics reports: {existing is not None}")
                    case _:
                        existing = None
                        print(f"DEBUG: No existing Analytics reports found")

                if existing:
                    request_id, reports = existing
                    print(f"DEBUG: Using Analytics reports (count: {len(reports)})")

                    # Download and parse APP_USAGE report
                    for report in reports:
                        category = report.get("attributes", {}).get("category")
                        if category == "APP_USAGE":
                            report_id = report.get("id")
                            tsv_data = analytics.download_report_tsv(report_id)
                            usage_df = analytics.parse_tsv_to_dataframe(tsv_data)

                            # Calculate propagation metrics using Analytics data
                            prop_result = analytics.calculate_propagation_metrics(usage_df, version_string)

                            match prop_result:
                                case ClientSuccess(data=prop_view):
                                    if not prop_view.error:
                                        # Convert PropagationMetricsView to PropagationMetrics
                                        propagation = PropagationMetrics(
                                            version_string=version_string,
                                            total_units=prop_view.total_units,
                                            countries=0,  # Analytics API doesn't provide countries
                                            market_share=0.0,  # Would need all versions data
                                        )
                                        return ClientSuccess(
                                            data=propagation,
                                            message=f"Propagation from Analytics API for v{version_string}",
                                        )
                            break
            except Exception as e:
                # Analytics failed, continue to Sales Reports fallback
                print(f"DEBUG: Analytics API failed: {e}")
                pass

        # Fallback to Sales Reports
        print(f"DEBUG: Falling back to Sales Reports...")
        print(f"DEBUG: Calling get_propagation_from_sales(vendor={vendor_number}, app={app_name})")

        sales_result = self.metrics.get_propagation_from_sales(
            vendor_number=vendor_number,
            app_name=app_name,
            days=30,
        )

        print(f"DEBUG: Sales Reports result: {sales_result}")

        match sales_result:
            case ClientSuccess(data=prop_data):
                # Get data for this version
                by_version = prop_data.by_version
                total_all_versions = sum(by_version.values()) if by_version else 1

                version_units = by_version.get(version_string, 0)
                market_share = (
                    (version_units / total_all_versions * 100)
                    if total_all_versions > 0
                    else 0.0
                )

                propagation = PropagationMetrics(
                    version_string=version_string,
                    total_units=version_units,
                    countries=prop_data.countries,
                    market_share=market_share,
                )

                return ClientSuccess(
                    data=propagation,
                    message=f"Propagation metrics for v{version_string}",
                )
            case ClientError() as error:
                return error
