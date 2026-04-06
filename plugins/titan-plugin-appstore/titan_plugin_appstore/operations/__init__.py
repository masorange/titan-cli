"""
Business operations for App Store Connect.

Operations orchestrate complex workflows using the client.
"""

from .version_operations import VersionOperations
from .analysis_operations import AnalysisOperations
from .build_operations import (
    prepare_whats_new_previews,
    get_whats_new_texts,
    format_build_for_selection,
    filter_valid_builds,
    group_builds_by_brand,
    create_submission_summary,
    validate_submission_readiness,
    WHATS_NEW_TEXT_ES,
    WHATS_NEW_TEXT_EN,
)
from .product_report_pdf import generate_product_report

__all__ = [
    "VersionOperations",
    "AnalysisOperations",
    "prepare_whats_new_previews",
    "get_whats_new_texts",
    "format_build_for_selection",
    "filter_valid_builds",
    "group_builds_by_brand",
    "create_submission_summary",
    "validate_submission_readiness",
    "WHATS_NEW_TEXT_ES",
    "WHATS_NEW_TEXT_EN",
    "generate_product_report",
]
