"""
Data models for App Store Connect plugin.
"""

from .network import (
    AppResponse,
    AppStoreVersionResponse,
    AppAttributes,
    VersionAttributes,
    BuildResponse,
    BuildAttributes,
    LocalizationResponse,
    LocalizationAttributes,
)
from .view import AppView, VersionView, VersionSummaryView, BuildView, WhatsNewPreview
from .mappers import NetworkToViewMapper

__all__ = [
    # Network models (API responses)
    "AppResponse",
    "AppStoreVersionResponse",
    "AppAttributes",
    "VersionAttributes",
    "BuildResponse",
    "BuildAttributes",
    "LocalizationResponse",
    "LocalizationAttributes",
    # View models (TUI-optimized)
    "AppView",
    "VersionView",
    "VersionSummaryView",
    "BuildView",
    "WhatsNewPreview",
    # Mapper
    "NetworkToViewMapper",
]
