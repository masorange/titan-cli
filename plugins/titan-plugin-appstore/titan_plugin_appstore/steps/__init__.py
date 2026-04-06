"""
Workflow steps for App Store Connect plugin.

Note: setup_wizard_step is not exposed here as it's embedded
inside check_and_setup_step and runs automatically when needed.
"""

from .check_and_setup_step import check_and_setup_step
from .select_app_step import select_app_step
from .prompt_version_step import prompt_version_step
from .create_version_step import create_version_step
from .show_whats_new_preview import show_whats_new_preview
from .select_build_per_brand import select_build_per_brand
from .submit_for_review import submit_for_review
from .generate_submission_report import generate_submission_report
from .fetch_versions_step import fetch_versions_step
from .request_analytics_step import request_analytics_step
from .request_analytics_single_version_step import request_analytics_single_version_step
from .fetch_metrics_step import fetch_metrics_step
from .analyze_metrics_step import analyze_metrics_step
from .generate_analytics_report import generate_analytics_report
from .ai_insights_step import ai_insights_step
from .executive_dashboard_step import executive_dashboard_step
from .check_product_report_dependencies_step import check_product_report_dependencies_step
from .select_product_report_version_step import select_product_report_version_step
from .product_report_step import product_report_step
from .export_product_report_pdf_step import export_product_report_pdf_step
from .analyze_single_version_step import analyze_single_version_step
from .fetch_production_version_step import fetch_production_version_step
from .analyze_version_with_comparison_step import analyze_version_with_comparison_step
# DISABLED: Detailed crash/hang reports not available via API
# from .show_diagnostics_step import show_diagnostics_step
from .debug_sales_reports_step import debug_sales_reports_step

__all__ = [
    "check_and_setup_step",
    "select_app_step",
    "prompt_version_step",
    "create_version_step",
    "show_whats_new_preview",
    "select_build_per_brand",
    "submit_for_review",
    "generate_submission_report",
    "fetch_versions_step",
    "request_analytics_step",
    "request_analytics_single_version_step",
    "fetch_metrics_step",
    "analyze_metrics_step",
    "generate_analytics_report",
    "ai_insights_step",
    "executive_dashboard_step",
    "check_product_report_dependencies_step",
    "select_product_report_version_step",
    "product_report_step",
    "export_product_report_pdf_step",
    "analyze_single_version_step",
    "fetch_production_version_step",
    "analyze_version_with_comparison_step",
    # "show_diagnostics_step",  # DISABLED: Not available via API
    "debug_sales_reports_step",
]
