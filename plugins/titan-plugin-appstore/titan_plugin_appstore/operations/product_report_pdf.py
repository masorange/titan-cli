"""
Product report PDF operations for iOS.

Generates a product-oriented PDF report from the data collected by product_report_step.
Uses the shared PdfReport builder from utils/pdf_report.py.
"""

from datetime import datetime
from typing import Optional, Any

from ..utils.pdf_report import PdfReport


def generate_product_report(
    report_data: dict,
    output_dir: str,
) -> str:
    """
    Generate a product-oriented PDF report for iOS and return the file path.

    Args:
        report_data: Report dict (output of product_report_step).
            Contains: app_id, app_name, selected_version, analytics_data,
            performance_data, ai_summary.
        output_dir: Directory where the PDF will be saved.

    Returns:
        Absolute path to the generated PDF file.
    """
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    app_name: str = report_data.get("app_name", "Unknown App")
    subtitle = f"{app_name}  —  {date_str}"

    pdf = (
        PdfReport()
        .header("Product Report — iOS", subtitle)
    )

    selected_version: Optional[str] = report_data.get("selected_version")
    analytics_data: Optional[Any] = report_data.get("analytics_data")
    performance_data: Optional[Any] = report_data.get("performance_data")
    ai_summary: Optional[str] = report_data.get("ai_summary")

    pdf.section(app_name)

    # Current version context
    if selected_version:
        pdf.stats_row([
            ("Version seleccionada", selected_version),
        ])

    # Analytics reach data
    if analytics_data:
        _render_analytics_section(pdf, analytics_data)
    else:
        pdf.text("Alcance (App Store Analytics): no disponible", muted=True)

    # Performance/Stability data
    if performance_data:
        _render_stability_section(pdf, performance_data, selected_version)
    else:
        pdf.text("Estabilidad (Performance API): no disponible", muted=True)

    # AI analysis
    if ai_summary:
        pdf.text("Analisis AI:", muted=False)
        pdf.markdown(ai_summary)

    return pdf.save(output_dir, "product-report-ios")


def _render_analytics_section(pdf: PdfReport, analytics_data: Any) -> None:
    """
    Render analytics reach data to the PDF.

    Args:
        pdf: PdfReport instance.
        analytics_data: Analytics data structure from product_report_step.
    """
    # TODO: Adapt based on actual Analytics API response structure
    # Placeholder implementation - will be updated when Analytics API is implemented
    if isinstance(analytics_data, dict):
        reach_header = ["Metrica", "Valor"]
        reach_rows = []

        if "active_devices" in analytics_data:
            reach_rows.append(["Dispositivos activos (30d)", str(analytics_data["active_devices"])])
        if "downloads" in analytics_data:
            reach_rows.append(["Descargas nuevas", str(analytics_data["downloads"])])

        if reach_rows:
            pdf.table(
                reach_header,
                reach_rows,
                title="Alcance — App Store Analytics (ultimos 30 dias)",
                col_widths=[80, 80],
            )
        else:
            pdf.text("Alcance (App Store Analytics): no hay metricas disponibles", muted=True)
    else:
        pdf.text("Alcance (App Store Analytics): formato de datos no reconocido", muted=True)


def _render_stability_section(
    pdf: PdfReport,
    performance_data: Any,
    selected_version: Optional[str] = None
) -> None:
    """
    Render stability metrics to the PDF.

    Args:
        pdf: PdfReport instance.
        performance_data: Performance/stability data from product_report_step.
        selected_version: Version string to highlight in the table (optional).
    """
    # TODO: Adapt based on actual Performance API response structure
    # Placeholder implementation - will be updated when Performance API is implemented
    if isinstance(performance_data, list):
        stability_header = ["Version", "Crash Rate", "Hang Rate"]
        stability_rows = []

        for metric in performance_data[:8]:
            version_name = metric.get("version", "Unknown")
            crash_rate = metric.get("crash_rate", "N/A")
            hang_rate = metric.get("hang_rate", "N/A")

            # Add marker for selected version
            marker = "★ " if selected_version and version_name == selected_version else ""
            stability_rows.append([
                f"{marker}{version_name}",
                str(crash_rate),
                str(hang_rate),
            ])

        if stability_rows:
            pdf.table(
                stability_header,
                stability_rows,
                title="Estabilidad por version — Performance API (ultimos 7 dias)",
                col_widths=[50, 55, 55],
            )
        else:
            pdf.text("Estabilidad (Performance API): no hay metricas disponibles", muted=True)
    elif isinstance(performance_data, dict):
        # Handle dict format if needed
        stability_header = ["Metrica", "Valor"]
        stability_rows = []

        for key, value in performance_data.items():
            stability_rows.append([key, str(value)])

        if stability_rows:
            pdf.table(
                stability_header,
                stability_rows,
                title="Estabilidad — Performance API (ultimos 7 dias)",
                col_widths=[80, 80],
            )
        else:
            pdf.text("Estabilidad (Performance API): no hay metricas disponibles", muted=True)
    else:
        pdf.text("Estabilidad (Performance API): formato de datos no reconocido", muted=True)
