# titan_cli/core/plugins/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional

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
