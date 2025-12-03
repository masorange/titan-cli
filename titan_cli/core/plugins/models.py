# titan_cli/core/plugins/models.py
from pydantic import BaseModel, Field
from typing import Dict, Any, List

class PluginConfig(BaseModel):
    """
    Represents the configuration for an individual plugin.
    """
    enabled: bool = Field(True, description="Whether the plugin is enabled.")
    config: Dict[str, Any] = Field(default_factory=dict, description="Plugin-specific configuration options.")

class GitPluginConfig(BaseModel):
    """Configuration for Git plugin."""
    main_branch: str = Field("main", description="Main/default branch name")
    default_remote: str = Field("origin", description="Default remote name")
    protected_branches: List[str] = Field(default_factory=lambda: ["main"], description="Protected branches")
