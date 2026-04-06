"""
Product report step for iOS.

Displays a product-oriented report combining:
  - App Store Analytics: reach (active users, downloads, sessions)
  - Performance API: stability (crash rates, hang rates per version)
  - AI summary oriented to product managers
"""

from typing import Optional

from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ai.models import AIMessage

from ..credentials import CredentialsManager


def product_report_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Display a product report for the selected app.

    Shows reach (Analytics) + stability (Performance API) + AI interpretation.
    Data stored in ctx.data["product_report_data"] for the PDF step.

    Inputs (from ctx.data):
        app_id (str): App Store Connect app ID.
        app_name (str): App name for display.
        selected_version_string (str): Version to focus analysis on.
        appstore_client: The App Store Connect client.

    Returns:
        Success: Report displayed.
        Error: No app selected.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Product Report")

    app_id: Optional[str] = ctx.get("app_id")
    app_name: Optional[str] = ctx.get("app_name", "Unknown App")
    selected_version: Optional[str] = ctx.get("selected_version_string")

    if not app_id:
        ctx.textual.error_text("No app selected.")
        ctx.textual.end_step("error")
        return Error("No app selected")

    # Load credentials and create client
    issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()
    if not key_id or not p8_path:
        ctx.textual.error_text("App Store Connect credentials not configured")
        ctx.textual.end_step("error")
        return Error("Credentials not configured. Run setup workflow first.")

    from ..clients.appstore_client import AppStoreConnectClient
    appstore_client = AppStoreConnectClient(
        key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
    )

    ctx.textual.text("")
    ctx.textual.bold_primary_text(f"━━  {app_name}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    ctx.textual.text("")

    analytics_data = None
    performance_data = None
    ai_summary = None

    # ── 1. Current Version Info ────────────────────────────────────────
    try:
        with ctx.textual.loading(f"Fetching {app_name} version info..."):
            versions_result = appstore_client.list_versions(
                app_id=app_id,
                platform="IOS"
            )

        match versions_result:
            case ClientSuccess(data=versions):
                # Filter for READY_FOR_SALE versions
                ready_versions = [v for v in versions if v.state == "READY_FOR_SALE"]
                if ready_versions:
                    current = ready_versions[0]
                    version_string = current.version_string
                    ctx.textual.text(f"  Current version: {version_string}")
                    ctx.textual.text("")
            case ClientError(error_message=err):
                ctx.textual.warning_text(f"  Version info unavailable: {err}")
                ctx.textual.text("")

    except Exception as e:
        ctx.textual.warning_text(f"  Version info error: {e}")
        ctx.textual.text("")

    # ── 2. Sales Reports: Reach Data ───────────────────────────────────────
    try:
        # Get vendor number from credentials (optional)
        vendor_number = CredentialsManager.get_vendor_number()

        if vendor_number:
            with ctx.textual.loading(f"Fetching {app_name} sales data..."):
                # Get sales/propagation metrics from App Store Connect
                sales_result = appstore_client.metrics.get_propagation_from_sales(
                    vendor_number=vendor_number,
                    app_name=app_name,
                    days=30
                )

            match sales_result:
                case ClientSuccess(data=propagation):
                    analytics_data = {
                        "active_devices": propagation.total_installs if hasattr(propagation, 'total_installs') else "N/A",
                        "downloads": propagation.total_units if hasattr(propagation, 'total_units') else "N/A",
                    }
                    _render_analytics_section(ctx, analytics_data, selected_version)
                case ClientError(error_message=err):
                    ctx.textual.warning_text(f"  Sales data unavailable: {err}")
                    ctx.textual.text("")
        else:
            ctx.textual.dim_text("  Sales Reports: vendor number not configured")
            ctx.textual.dim_text("  (Run setup wizard to add vendor number)")
            ctx.textual.text("")

    except Exception as e:
        ctx.textual.warning_text(f"  Sales data error: {e}")
        ctx.textual.text("")

    # ── 3. Performance Metrics: Stability Data ─────────────────────────────
    try:
        with ctx.textual.loading(f"Fetching {app_name} stability data..."):
            # Get performance metrics from App Store Connect (same as Xcode Organizer)
            perf_result = appstore_client.metrics.get_performance_metrics(
                app_id=app_id,
                platform="IOS"
            )

        match perf_result:
            case ClientSuccess(data=perf_data):
                # Extract crash/hang metrics grouped by version
                crash_result = appstore_client.metrics.extract_crash_metrics_by_version(perf_data)

                match crash_result:
                    case ClientSuccess(data=metrics_by_version):
                        # Convert to list format for rendering
                        # Note: Performance API values are already in correct scale (2.10 = 2.10%)
                        performance_data = [
                            {
                                "version": version,
                                "crash_rate": f"{data['crash_rate']:.2f}%" if data['crash_rate'] else "N/A",
                                "hang_rate": f"{data['hang_rate']:.2f}%" if data['hang_rate'] else "N/A",
                                "crash_rate_numeric": data['crash_rate'],  # For crash-free calculation
                            }
                            for version, data in metrics_by_version.items()
                        ]
                        _render_stability_section(ctx, performance_data, selected_version)
                    case ClientError(error_message=err):
                        ctx.textual.warning_text(f"  Could not extract crash metrics: {err}")
                        ctx.textual.text("")
            case ClientError(error_message=err):
                ctx.textual.warning_text(f"  Performance metrics unavailable: {err}")
                ctx.textual.text("")

    except Exception as e:
        ctx.textual.warning_text(f"  Performance metrics error: {e}")
        ctx.textual.text("")

    # ── 4. AI Analysis ────────────────────────────────────────────────
    if ctx.ai and (analytics_data or performance_data):
        report_text = _format_report_for_ai(
            app_name=app_name,
            analytics=analytics_data,
            performance=performance_data,
            selected_version=selected_version,
        )
        messages = _build_ai_messages(report_text)

        try:
            with ctx.textual.loading("AI analyzing..."):
                response = ctx.ai.generate(messages, max_tokens=800)
            ai_summary = response.content.strip()
            ctx.textual.panel(
                ai_summary,
                panel_type="info",
                use_markdown=True,
                show_icon=False
            )
            ctx.textual.text("")
        except Exception as e:
            ctx.textual.warning_text(f"  AI analysis failed: {e}")
            ctx.textual.text("")

    # Store data for PDF export step
    report_data = {
        "app_id": app_id,
        "app_name": app_name,
        "selected_version": selected_version,
        "analytics_data": analytics_data,
        "performance_data": performance_data,
        "ai_summary": ai_summary,
    }
    ctx.set("product_report_data", report_data)

    ctx.textual.end_step("success")
    return Success(
        f"Product report complete for {app_name}",
        metadata={"app_id": app_id, "version": selected_version},
    )


# ── Private render helpers ────────────────────────────────────────────

def _render_analytics_section(ctx, summary, selected_version: Optional[str] = None) -> None:
    """Render analytics reach data (propagation)."""
    ctx.textual.text("  Propagacion (Sales Reports, 30d)")
    ctx.textual.text(f"    Total installs: {summary.get('active_devices', 'N/A')}")
    ctx.textual.text(f"    New downloads: {summary.get('downloads', 'N/A')}")
    ctx.textual.text("")
    ctx.textual.dim_text("    → Cuantos usuarios impacto con cada version")
    ctx.textual.text("")


def _render_stability_section(ctx, metrics, selected_version: Optional[str] = None) -> None:
    """Render stability metrics by version."""
    ctx.textual.text("  Estabilidad (Performance API)")

    if isinstance(metrics, list) and metrics:
        headers = ["Version", "Crash Rate", "Hang Rate", "Estabilidad"]
        rows = []

        for metric in metrics[:8]:
            version_name = metric.get("version", "Unknown")
            crash_rate = metric.get("crash_rate", "N/A")
            hang_rate = metric.get("hang_rate", "N/A")
            crash_rate_numeric = metric.get("crash_rate_numeric")

            # Calculate crash-free rate from numeric value
            if crash_rate_numeric is not None and crash_rate_numeric > 0:
                crash_free = f"{100 - crash_rate_numeric:.2f}%"
            else:
                crash_free = "N/A"

            marker = "★ " if selected_version and version_name == selected_version else "  "
            rows.append([
                f"{marker}{version_name}",
                crash_rate,
                hang_rate,
                crash_free,
            ])

        ctx.textual.table(
            headers=headers,
            rows=rows,
            title="Estabilidad por version",
            full_width=False
        )
        ctx.textual.text("")
        ctx.textual.dim_text("    → De esos usuarios, que estabilidad tiene cada version")
        ctx.textual.text("")
    else:
        ctx.textual.dim_text("    No stability data available")
        ctx.textual.text("")


def _format_report_for_ai(
    app_name: str,
    analytics,
    performance,
    selected_version: Optional[str]
) -> str:
    """Format the report data as plain text for AI analysis."""
    lines = [f"App: {app_name}"]

    if selected_version:
        lines.append(f"Focus version: {selected_version}")

    lines.append("")
    lines.append("=== Analytics Reach ===")
    if analytics:
        # Adapt based on your Analytics API response structure
        lines.append(f"Active devices: {analytics.get('active_devices', 'N/A')}")
        lines.append(f"New downloads: {analytics.get('downloads', 'N/A')}")
    else:
        lines.append("No analytics data available")

    lines.append("")
    lines.append("=== Stability Metrics ===")
    if performance:
        # Adapt based on your Performance API response structure
        if isinstance(performance, list):
            for metric in performance[:5]:
                version = metric.get("version", "Unknown")
                crash = metric.get("crash_rate", "N/A")
                hang = metric.get("hang_rate", "N/A")
                lines.append(f"{version}: Crash={crash}, Hang={hang}")
        else:
            lines.append(str(performance))
    else:
        lines.append("No stability data available")

    return "\n".join(lines)


def _build_ai_messages(report_text: str) -> list[AIMessage]:
    """Build the message list for AI analysis."""
    system_prompt = (
        "Eres un asistente de product manager analizando metricas de iOS.\n\n"
        "Enfocate en responder estas preguntas clave:\n"
        "1) Si despliego una nueva version, cuantos usuarios impactare (propagacion)?\n"
        "2) Cual es la estabilidad actual de las versiones en produccion?\n"
        "3) Hay alertas de crash rate o hang rate preocupantes?\n"
        "4) Recomendaciones accionables.\n\n"
        "Proporciona un resumen ejecutivo conciso en español (max 200 palabras) con formato markdown."
    )

    user_prompt = f"Analiza este informe de producto iOS:\n\n{report_text}"

    return [
        AIMessage(role="system", content=system_prompt),
        AIMessage(role="user", content=user_prompt),
    ]


__all__ = ["product_report_step"]
