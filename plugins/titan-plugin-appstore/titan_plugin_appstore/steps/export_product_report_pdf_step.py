"""
Export product report PDF step for iOS.

Asks the user whether to generate a PDF and where to save it.
Must run after product_report_step, which stores data in ctx.data["product_report_data"].
"""

import os

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Skip, Error

from ..operations.product_report_pdf import generate_product_report


def export_product_report_pdf_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Offer to export the product report as a PDF.

    Inputs (from ctx.data, set by product_report_step):
        product_report_data (dict): Report data for the selected app.
            Contains: app_id, app_name, selected_version, analytics_data,
            performance_data, ai_summary.

    Returns:
        Success: PDF generated or user declined.
        Skip: No report data available.
        Error: PDF generation failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    report_data = ctx.get("product_report_data")
    if not report_data:
        return Skip("No report data available for PDF export.")

    ctx.textual.begin_step("Export Product Report PDF")

    want_pdf = ctx.textual.ask_confirm("Export report as PDF?", default=False)
    if not want_pdf:
        ctx.textual.dim_text("  PDF export skipped.")
        ctx.textual.end_step("success")
        return Success("PDF export skipped.")

    default_dir = os.getcwd()
    output_dir = ctx.textual.ask_text(
        "Save directory (Enter for current directory):",
        default=default_dir,
    )
    if not output_dir:
        output_dir = default_dir

    output_dir = os.path.expanduser(output_dir.strip())

    if not os.path.isdir(output_dir):
        ctx.textual.error_text(f"  Directory does not exist: {output_dir}")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Directory does not exist: {output_dir}")

    ctx.textual.text("")
    try:
        with ctx.textual.loading("Generating PDF report..."):
            pdf_path = generate_product_report(
                report_data=report_data,
                output_dir=output_dir,
            )
        ctx.textual.panel(
            f"PDF saved: `{pdf_path}`",
            panel_type="success",
            use_markdown=True,
        )
    except Exception as e:
        ctx.textual.error_text(f"  Could not generate PDF: {e}")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"PDF generation failed: {e}")

    ctx.textual.text("")
    ctx.textual.end_step("success")
    return Success(f"PDF report saved: {pdf_path}")


__all__ = ["export_product_report_pdf_step"]
