"""
Debug Sales Reports Step - Show what's in the Sales Report.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager
from titan_cli.core.result import ClientSuccess, ClientError


def debug_sales_reports_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Download and show Sales Report contents for debugging.

    This step helps diagnose why propagation metrics are returning 0.

    Inputs (from ctx.data):
        app_name: App name to search for (optional)

    Outputs:
        Displays all unique app titles in the Sales Report

    Returns:
        Success with debug info
        Error if download fails
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Debug Sales Reports")

    try:
        # Get app name if provided
        search_app_name = ctx.data.get("app_name", "")

        # Load credentials
        credentials = CredentialsManager.load_credentials()
        if not credentials:
            ctx.textual.error_text("No credentials configured")
            ctx.textual.end_step("error")
            return Error("Run setup wizard first")

        vendor_number = credentials.get("vendor_number")
        if not vendor_number:
            ctx.textual.error_text("Vendor number not configured")
            ctx.textual.text("Sales Reports require a vendor number.")
            ctx.textual.text("Re-run setup wizard to add it.")
            ctx.textual.end_step("error")
            return Error("Vendor number required")

        # Initialize client
        issuer_id = credentials.get("issuer_id")
        key_id = credentials.get("key_id")
        p8_path = credentials.get("private_key_path")

        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        ctx.textual.text("=" * 60)
        ctx.textual.text("SALES REPORT DEBUG")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")

        # Download sales report
        ctx.textual.text(f"Vendor Number: {vendor_number}")
        ctx.textual.text("Downloading latest sales report...")

        sales_result = client.metrics.get_sales_report(
            vendor_number=vendor_number,
            frequency="DAILY"
        )

        match sales_result:
            case ClientSuccess(data=gzip_data):
                ctx.textual.success_text(f"✓ Downloaded {len(gzip_data)} bytes")
            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to download: {err}")
                ctx.textual.end_step("error")
                return Error(err)

        # Parse TSV
        ctx.textual.text("Parsing TSV data...")

        parse_result = client.metrics.parse_sales_report_tsv(gzip_data)

        match parse_result:
            case ClientSuccess(data=rows):
                ctx.textual.success_text(f"✓ Parsed {len(rows)} rows")
            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to parse: {err}")
                ctx.textual.end_step("error")
                return Error(err)

        # Extract unique app titles
        unique_titles = sorted(set(r.get("Title", "N/A") for r in rows))

        ctx.textual.text("")
        ctx.textual.text("=" * 60)
        ctx.textual.text(f"AVAILABLE APP TITLES ({len(unique_titles)})")
        ctx.textual.text("=" * 60)
        ctx.textual.text("")

        for idx, title in enumerate(unique_titles, 1):
            # Highlight if it matches the search
            if search_app_name and title == search_app_name:
                ctx.textual.success_text(f"  {idx}. {title} ← MATCH!")
            else:
                ctx.textual.text(f"  {idx}. {title}")

        ctx.textual.text("")

        # Show what we're searching for
        if search_app_name:
            ctx.textual.text("=" * 60)
            ctx.textual.text(f"SEARCHING FOR: '{search_app_name}'")
            ctx.textual.text("=" * 60)
            ctx.textual.text("")

            if search_app_name in unique_titles:
                ctx.textual.success_text("✓ Found exact match!")

                # Show data for this app
                app_rows = [r for r in rows if r.get("Title") == search_app_name]
                ctx.textual.text(f"  Total rows: {len(app_rows)}")

                # Show versions
                versions = set(r.get("Version", "unknown") for r in app_rows)
                ctx.textual.text(f"  Versions: {', '.join(sorted(versions))}")

                # Show countries
                countries = set(r.get("Country Code", "?") for r in app_rows)
                ctx.textual.text(f"  Countries: {len(countries)}")

                # Show total units
                total_units = sum(int(r.get("Units", 0)) for r in app_rows)
                ctx.textual.text(f"  Total units: {total_units:,}")

            else:
                ctx.textual.error_text("✗ No exact match found")
                ctx.textual.text("")
                ctx.textual.text("Possible reasons:")
                ctx.textual.text("  1. App name mismatch (Title field is different)")
                ctx.textual.text("  2. No sales data for this app yesterday")
                ctx.textual.text("  3. Try a different app name")

        ctx.textual.text("")
        ctx.textual.text("=" * 60)

        ctx.textual.end_step("success")
        return Success(f"Found {len(unique_titles)} app(s) in sales report")

    except Exception as e:
        error_msg = f"Debug failed: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["debug_sales_reports_step"]
