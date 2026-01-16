"""
Models for Plugin Marketplace metadata.

Defines data structures for plugins in the marketplace registry.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class PluginInfo(BaseModel):
    """Plugin metadata as stored in marketplace registry.json"""

    id: str = Field(..., description="Unique plugin identifier (e.g., 'git', 'github')")
    name: str = Field(..., description="Display name of the plugin")
    package: str = Field(..., description="PyPI package name (e.g., 'titan-plugin-git')")
    version: str = Field(..., description="Current version (e.g., '1.0.0')")
    description: str = Field(..., description="Short description of the plugin")
    category: str = Field(
        "official",
        description="Category: 'official' or 'community'"
    )
    verified: bool = Field(
        True,
        description="Whether plugin has been verified/reviewed"
    )
    author: str = Field(..., description="Plugin author/maintainer")
    license: str = Field("MIT", description="License type")
    min_titan_version: str = Field(
        "1.0.0",
        description="Minimum required Titan CLI version"
    )
    max_titan_version: Optional[str] = Field(
        None,
        description="Maximum compatible Titan CLI version (if any)"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of plugin IDs this plugin depends on"
    )
    python_dependencies: List[str] = Field(
        default_factory=list,
        description="Python package dependencies"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Search keywords for discovery"
    )
    homepage: Optional[str] = Field(
        None,
        description="Plugin homepage URL"
    )
    repository: Optional[str] = Field(
        None,
        description="Source code repository URL"
    )

    class Config:
        """Pydantic config"""
        extra = "allow"  # Allow additional fields for forward compatibility


class MarketplaceRegistry(BaseModel):
    """Complete marketplace registry structure"""

    version: str = Field(
        "1.0.0",
        description="Registry schema version"
    )
    last_updated: str = Field(
        ...,
        description="ISO 8601 timestamp of last update"
    )
    plugins: dict[str, PluginInfo] = Field(
        default_factory=dict,
        description="Map of plugin ID -> PluginInfo"
    )

    class Config:
        """Pydantic config"""
        extra = "allow"
