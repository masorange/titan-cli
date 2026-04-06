"""
Metrics Service - Sales Reports + Power & Performance Metrics APIs.

Uses the correct APIs for immediate data (no polling):
- Sales Reports: For propagation/distribution data
- Power & Performance Metrics: For stability/crash data
"""

import gzip
from typing import List, Dict, Any, Optional
from io import BytesIO
from datetime import datetime, timedelta
from pydantic import BaseModel

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network.appstore_api import AppStoreConnectAPI
from ...exceptions import APIError


class SalesReportData(BaseModel):
    """View model for sales report data."""
    raw_data: bytes
    parsed_rows: List[Dict[str, Any]] = []


class PerformanceMetricsData(BaseModel):
    """View model for performance metrics."""
    raw_json: Dict[str, Any]
    crash_metrics_by_version: Dict[str, Dict[str, float]] = {}


class PropagationMetrics(BaseModel):
    """View model for propagation metrics."""
    total_units: int = 0
    countries: int = 0
    by_version: Dict[str, int] = {}
    latest_version: str = "unknown"
    error: Optional[str] = None


class MetricsService:
    """
    Service for immediate metrics using Sales Reports and Performance APIs.

    No polling required - all data is available instantly.
    """

    def __init__(self, api_client: AppStoreConnectAPI):
        """
        Initialize metrics service.

        Args:
            api_client: Low-level API client for HTTP requests
        """
        self.api = api_client

    def get_sales_report(
        self,
        vendor_number: str,
        report_type: str = "SALES",
        report_sub_type: str = "SUMMARY",
        frequency: str = "DAILY",
        report_date: Optional[str] = None,
        max_days_back: int = 14
    ) -> ClientResult[bytes]:
        """
        Download sales report (Gzip TSV format) with automatic fallback.

        If no report is found for the requested date, automatically tries
        previous dates up to max_days_back.

        Args:
            vendor_number: Vendor number (e.g., "80012345")
            report_type: Report type (default: "SALES")
            report_sub_type: Report subtype (default: "SUMMARY")
            frequency: DAILY, WEEKLY, or MONTHLY
            report_date: Report date (YYYY-MM-DD for DAILY, YYYY-MM for MONTHLY)
                        If None, starts from yesterday and searches backwards
            max_days_back: Maximum days to search back (default: 14)

        Returns:
            ClientResult with gzipped TSV data (bytes)
        """
        import requests

        # Determine starting date
        if report_date:
            start_date = datetime.strptime(report_date, "%Y-%m-%d")
            days_to_try = 1  # Only try the specified date
        else:
            # Start from yesterday and search backwards
            start_date = datetime.now() - timedelta(days=1)
            days_to_try = max_days_back

        last_error = None
        tried_dates = []

        # Try dates from newest to oldest
        for days_offset in range(days_to_try):
            try_date = start_date - timedelta(days=days_offset)
            try_date_str = try_date.strftime("%Y-%m-%d")
            tried_dates.append(try_date_str)

            query_params = {
                "filter[reportType]": report_type,
                "filter[reportSubType]": report_sub_type,
                "filter[frequency]": frequency,
                "filter[vendorNumber]": vendor_number,
                "filter[reportDate]": try_date_str,
            }

            # This endpoint returns binary Gzip data, not JSON
            url = self.api._build_url("/salesReports", query_params=query_params)
            headers = self.api._get_headers()

            try:
                response = requests.get(url, headers=headers, timeout=60)
                response.raise_for_status()

                # Success! Return the data
                return ClientSuccess(
                    data=response.content,
                    message=f"Downloaded sales report for {try_date_str}" +
                            (f" (searched back {days_offset} days)" if days_offset > 0 else "")
                )

            except requests.exceptions.HTTPError as e:
                last_error = str(e)
                # If 404, try next date. If other error, stop searching
                if e.response.status_code != 404:
                    # Non-404 error, stop trying
                    return ClientError(
                        error_message=f"Sales report API error: {last_error}",
                        error_code="API_ERROR"
                    )
                # Continue to next date if 404
                continue

            except Exception as e:
                # Unexpected error
                return ClientError(
                    error_message=f"Unexpected error downloading sales report: {str(e)}",
                    error_code="UNKNOWN_ERROR"
                )

        # No report found after trying all dates
        first_date = tried_dates[0]
        last_date = tried_dates[-1] if len(tried_dates) > 1 else first_date
        date_range = f"{last_date} to {first_date}" if len(tried_dates) > 1 else first_date

        return ClientError(
            error_message=f"No sales report found for dates {date_range}. Tried {len(tried_dates)} dates.",
            error_code="NO_DATA"
        )

    def parse_sales_report_tsv(self, gzip_data: bytes) -> ClientResult[List[Dict[str, Any]]]:
        """
        Parse gzipped sales report TSV.

        Args:
            gzip_data: Gzipped TSV data

        Returns:
            ClientResult with list of row dicts
        """
        try:
            # Decompress Gzip
            with gzip.GzipFile(fileobj=BytesIO(gzip_data)) as f:
                tsv_content = f.read().decode('utf-8')

            # Parse TSV
            lines = tsv_content.strip().split('\n')
            if not lines:
                return ClientSuccess(
                    data=[],
                    message="No data in sales report"
                )

            # First line is header
            headers = lines[0].split('\t')

            # Parse data rows
            rows = []
            for line in lines[1:]:
                values = line.split('\t')
                row_dict = dict(zip(headers, values))
                rows.append(row_dict)

            return ClientSuccess(
                data=rows,
                message=f"Parsed {len(rows)} row(s) from sales report"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to parse sales report: {str(e)}",
                error_code="PARSE_ERROR"
            )

    def get_performance_metrics(
        self, app_id: str, platform: str = "IOS"
    ) -> ClientResult[Dict[str, Any]]:
        """
        Get Power & Performance metrics (crashes, hangs, memory, etc.).

        This is the same data shown in Xcode Organizer - Energy & Metrics.

        Args:
            app_id: App ID
            platform: Platform (default: "IOS")

        Returns:
            ClientResult with performance metrics JSON
        """
        try:
            query_params = {
                "filter[platform]": platform,
            }

            # Set correct Accept header for metrics
            headers = self.api._get_headers()
            headers["Accept"] = "application/vnd.apple.xcode-metrics+json"

            url = self.api._build_url(
                f"/apps/{app_id}/perfPowerMetrics",
                query_params=query_params
            )

            import requests
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            metrics_data = response.json()

            return ClientSuccess(
                data=metrics_data,
                message="Retrieved performance metrics"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to get performance metrics: {str(e)}",
                error_code="API_ERROR"
            )

    def extract_crash_metrics_by_version(
        self, perf_data: Dict[str, Any]
    ) -> ClientResult[Dict[str, Dict[str, float]]]:
        """
        Extract crash/termination metrics grouped by app version.

        Args:
            perf_data: Performance metrics JSON from get_performance_metrics()

        Returns:
            ClientResult with dict of {version: {"crash_rate": float, "hang_rate": float}}
        """
        try:
            metrics_by_version = {}

            # Correct structure: perf_data.productData[].metricCategories[]
            product_data_list = perf_data.get("productData", [])

            for product in product_data_list:
                metric_categories = product.get("metricCategories", [])

                for category in metric_categories:
                    category_id = category.get("identifier")

                    # Focus on TERMINATION (crashes) and HANG
                    if category_id not in ["TERMINATION", "HANG"]:
                        continue

                    metrics = category.get("metrics", [])

                    for metric in metrics:
                        metric_id = metric.get("identifier", "")
                        datasets = metric.get("datasets", [])

                        for dataset in datasets:
                            points = dataset.get("points", [])

                            for point in points:
                                version = point.get("version", "unknown")
                                value = point.get("value", 0)

                                if version not in metrics_by_version:
                                    metrics_by_version[version] = {
                                        "crash_rate": 0.0,
                                        "hang_rate": 0.0,
                                        "terminations": 0,
                                        "hangs": 0,
                                    }

                                if category_id == "TERMINATION":
                                    # TERMINATION has onScreen and background metrics
                                    # Sum both for total crash rate
                                    if metric_id in ["onScreen", "background"]:
                                        metrics_by_version[version]["crash_rate"] += value
                                        metrics_by_version[version]["terminations"] += int(value * 100)
                                elif category_id == "HANG":
                                    metrics_by_version[version]["hang_rate"] = value
                                    metrics_by_version[version]["hangs"] = int(value * 100)

            return ClientSuccess(
                data=metrics_by_version,
                message=f"Extracted crash metrics for {len(metrics_by_version)} version(s)"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to extract crash metrics: {str(e)}",
                error_code="PARSE_ERROR"
            )

    def get_propagation_from_sales(
        self, vendor_number: str, app_name: str, days: int = 30
    ) -> ClientResult[PropagationMetrics]:
        """
        Get propagation metrics from sales reports.

        Args:
            vendor_number: Vendor number
            app_name: App name to filter (matches "Title" field in sales report)
            days: Number of days to analyze (currently uses latest available day)

        Returns:
            ClientResult with PropagationMetrics
        """
        try:
            # Download latest daily report (defaults to yesterday)
            report_result = self.get_sales_report(
                vendor_number=vendor_number,
                frequency="DAILY"
            )

            match report_result:
                case ClientSuccess(data=gzip_data):
                    pass
                case ClientError() as error:
                    return ClientError(
                        error_message=f"Failed to get sales report: {error.error_message}",
                        error_code=error.error_code
                    )

            # Parse TSV
            parse_result = self.parse_sales_report_tsv(gzip_data)

            match parse_result:
                case ClientSuccess(data=rows):
                    pass
                case ClientError() as error:
                    return ClientError(
                        error_message=f"Failed to parse sales report: {error.error_message}",
                        error_code=error.error_code
                    )

            # DEBUG: Print all unique app titles
            unique_titles = set(r.get("Title", "N/A") for r in rows)
            print(f"\n=== DEBUG: Sales Report Titles ===")
            print(f"Looking for: '{app_name}'")
            print(f"Available titles in report: {sorted(unique_titles)}")
            print(f"Total rows: {len(rows)}")
            print("=" * 50 + "\n")

            # Filter by app name (field is "Title" in sales reports)
            app_rows = [r for r in rows if r.get("Title") == app_name]

            if not app_rows:
                return ClientSuccess(
                    data=PropagationMetrics(
                        error=f"No sales data found for app: {app_name}. Available: {sorted(unique_titles)}"
                    ),
                    message=f"No sales data found for {app_name}"
                )

            # Calculate metrics
            total_units = sum(int(r.get("Units", 0)) for r in app_rows)
            countries = len(set(r.get("Country Code") for r in app_rows))

            # Group by version if available
            versions = {}
            for row in app_rows:
                version = row.get("Version", "unknown")
                units = int(row.get("Units", 0))

                if version not in versions:
                    versions[version] = 0
                versions[version] += units

            metrics = PropagationMetrics(
                total_units=total_units,
                countries=countries,
                by_version=versions,
                latest_version=max(versions.keys()) if versions else "unknown"
            )

            return ClientSuccess(
                data=metrics,
                message=f"Retrieved propagation metrics for {app_name}"
            )

        except Exception as e:
            return ClientError(
                error_message=f"Failed to get propagation metrics: {str(e)}",
                error_code="API_ERROR"
            )
