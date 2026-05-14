# titan_cli/core/plugins/models.py
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .community_sources import PluginChannel


class PluginSourceConfig(BaseModel):
    """Source selection for a plugin within a project."""

    channel: PluginChannel = Field(
        PluginChannel.STABLE,
        description="Plugin source channel ('stable' or 'dev_local').",
    )
    path: Optional[str] = Field(None, description="Local repository path when channel is 'dev_local'.")
    repo_url: Optional[str] = Field(None, description="Git repository URL when channel is 'stable'.")
    requested_ref: Optional[str] = Field(None, description="User-facing tag/ref requested for a stable plugin source.")
    resolved_commit: Optional[str] = Field(None, description="Resolved commit SHA installed for a stable plugin source.")

    @model_validator(mode="after")
    def validate_channel_specific_fields(self) -> "PluginSourceConfig":
        """Validate source metadata according to the active channel."""
        if self.channel == PluginChannel.DEV_LOCAL:
            if not self.path:
                raise ValueError("dev_local plugin sources require 'path'")
        elif self.channel == PluginChannel.STABLE:
            if self.resolved_commit and not self.repo_url:
                raise ValueError("stable plugin sources with 'resolved_commit' require 'repo_url'")
        return self

class PluginConfig(BaseModel):
    """
    Represents the configuration for an individual plugin.
    """
    enabled: bool = Field(True, description="Whether the plugin is enabled.")
    config: Dict[str, Any] = Field(default_factory=dict, description="Plugin-specific configuration options.")
    source: PluginSourceConfig = Field(default_factory=PluginSourceConfig, description="Plugin source selection.")

class GitPluginConfig(BaseModel):
    """Configuration for Git plugin."""
    main_branch: str = Field("main", description="Main/default branch name")
    default_remote: str = Field("origin", description="Default remote name")

class GitHubPluginConfig(BaseModel):
    """Configuration for GitHub plugin."""
    repo_owner: str = Field(..., description="GitHub repository owner (user or organization).")
    repo_name: str = Field(..., description="GitHub repository name.")
    default_branch: str = Field(None, description="Default branch to use (e.g., 'main', 'develop').")
    pr_template_path: str = Field(None, description="Path to PR template file relative to repository root (e.g., '.github/pull_request_template.md', 'docs/PR_TEMPLATE.md'). Defaults to '.github/pull_request_template.md'.")
    auto_assign_prs: bool = Field(True, description="Automatically assign PRs to the author.")


class JiraPluginConfig(BaseModel):
    """
    Configuration for JIRA plugin.

    Credentials (base_url, email, api_token) should be configured at global level (~/.titan/config.toml).
    Project-specific settings (default_project) can override at project level (.titan/config.toml).
    """
    base_url: Optional[str] = Field(
        None,
        description="JIRA instance URL (e.g., 'https://jira.company.com')",
        json_schema_extra={"config_scope": "global"}
    )
    email: Optional[str] = Field(
        None,
        description="User email for authentication",
        json_schema_extra={"config_scope": "global"}
    )
    # api_token is stored in secrets, not in config.toml
    # It appears in the JSON schema for interactive configuration but is optional in the model
    api_token: Optional[str] = Field(
        None,
        description="JIRA API token (Personal Access Token)",
        json_schema_extra={"format": "password", "required_in_schema": True}
    )
    default_project: Optional[str] = Field(
        None,
        description="Default JIRA project key (e.g., 'ECAPP', 'PROJ')",
        json_schema_extra={"config_scope": "project"}
    )
    timeout: int = Field(
        30,
        description="Request timeout in seconds",
        json_schema_extra={"config_scope": "global"}
    )
    enable_cache: bool = Field(
        True,
        description="Enable caching for API responses",
        json_schema_extra={"config_scope": "global"}
    )
    cache_ttl: int = Field(
        300,
        description="Cache time-to-live in seconds",
        json_schema_extra={"config_scope": "global"}
    )

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        """Validate base_url is configured and properly formatted."""
        if not v:
            raise ValueError(
                "JIRA base_url not configured. "
                "Please add [plugins.jira.config] section with base_url in ~/.titan/config.toml"
            )
        if not v.startswith(('http://', 'https://')):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip('/')  # Normalize trailing slash

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Validate email is configured and has valid format."""
        if not v:
            raise ValueError(
                "JIRA email not configured. "
                "Please add [plugins.jira.config] section with email in ~/.titan/config.toml"
            )
        if '@' not in v:
            raise ValueError("email must be a valid email address")
        return v.lower()  # Normalize email to lowercase


class PoEditorPluginConfig(BaseModel):
    """Configuration for PoEditor plugin."""

    api_token: Optional[str] = Field(
        None,
        description="PoEditor API token",
        json_schema_extra={"format": "password", "required_in_schema": True},
    )

    default_project_id: Optional[str] = Field(
        None,
        description="Default PoEditor project ID",
        json_schema_extra={"config_scope": "project"},
    )

    timeout: int = Field(
        30,
        description="Request timeout in seconds",
        ge=1,
        le=300,
        json_schema_extra={"config_scope": "global"},
    )
