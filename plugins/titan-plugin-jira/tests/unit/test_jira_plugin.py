"""
Unit tests for JiraPlugin configuration

Tests plugin configuration schema and default values.
"""

import pytest
from unittest.mock import Mock

from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.plugin import JiraPlugin
from titan_plugin_jira.models.view import UIJiraUser
from titan_cli.core.plugins.models import JiraPluginConfig


class TestPluginConfigSchema:
    """Tests for plugin configuration schema."""

    def test_config_schema_excludes_technical_fields(self):
        """Test that technical fields are excluded from wizard (TESTING.md Section 1.3)."""
        plugin = JiraPlugin()
        schema = plugin.get_config_schema()

        properties = schema.get("properties", {})

        # These should NOT be in wizard (excluded for simplicity)
        assert "timeout" not in properties, \
            "timeout should be excluded from wizard (has default: 30s)"
        assert "enable_cache" not in properties, \
            "enable_cache should be excluded from wizard (has default: True)"
        assert "cache_ttl" not in properties, \
            "cache_ttl should be excluded from wizard (has default: 300s)"

    def test_config_schema_includes_required_fields(self):
        """Test that required fields are present in schema."""
        plugin = JiraPlugin()
        schema = plugin.get_config_schema()

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # These SHOULD be in wizard
        assert "base_url" in properties, "base_url should be in wizard"
        assert "email" in properties, "email should be in wizard"

        # api_token is required (even though stored in secrets)
        assert "api_token" in required, "api_token should be marked as required"

    def test_config_uses_default_values(self):
        """Test that technical fields use sensible defaults."""
        config = JiraPluginConfig(
            base_url="https://test.atlassian.net",
            email="test@example.com"
        )

        # Verify defaults apply automatically
        assert config.timeout == 30, \
            "Default timeout should be 30 seconds"
        assert config.enable_cache is True, \
            "Cache should be enabled by default"
        assert config.cache_ttl == 300, \
            "Default cache TTL should be 300 seconds (5 minutes)"

    def test_config_allows_overriding_defaults(self):
        """Test that defaults can be manually overridden in config.toml."""
        config = JiraPluginConfig(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            timeout=60,  # Override default
            enable_cache=False,  # Override default
            cache_ttl=600  # Override default
        )

        # Verify overrides work
        assert config.timeout == 60
        assert config.enable_cache is False
        assert config.cache_ttl == 600

    def test_config_optional_fields(self):
        """Test that optional fields work correctly."""
        # Without default_project
        config1 = JiraPluginConfig(
            base_url="https://test.atlassian.net",
            email="test@example.com"
        )
        assert config1.default_project is None

        # With default_project
        config2 = JiraPluginConfig(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            default_project="ECAPP"
        )
        assert config2.default_project == "ECAPP"


class TestPluginConfigValidation:
    """Tests for configuration validation."""

    def test_config_validates_base_url_format(self):
        """Test that base_url validation works."""
        from pydantic import ValidationError

        # Valid URL
        config = JiraPluginConfig(
            base_url="https://company.atlassian.net",
            email="user@example.com"
        )
        assert config.base_url == "https://company.atlassian.net"

        # Invalid URL should fail validation
        with pytest.raises(ValidationError):
            JiraPluginConfig(
                base_url="not-a-url",
                email="user@example.com"
            )

    def test_config_validates_email_format(self):
        """Test that email validation works."""
        from pydantic import ValidationError

        # Valid email
        config = JiraPluginConfig(
            base_url="https://test.atlassian.net",
            email="user@example.com"
        )
        assert config.email == "user@example.com"

        # Invalid email should fail validation
        with pytest.raises(ValidationError):
            JiraPluginConfig(
                base_url="https://test.atlassian.net",
                email="not-an-email"
            )


class TestValidateToken:
    """Tests for token validation."""

    def test_validate_token_returns_user_data_on_success(self):
        """Should unwrap ClientSuccess[UIJiraUser] correctly."""
        plugin = JiraPlugin()
        plugin._client = Mock()
        plugin._client.project_key = "ECAPP"
        plugin._token_source = {"name": "jira_api_token", "type": "global"}
        plugin._client.get_current_user.return_value = ClientSuccess(
            data=UIJiraUser(
                account_id="abc123",
                display_name="John Doe",
                email="john.doe@example.com",
                active=True,
            ),
            message="Current user retrieved",
        )

        result = plugin.validate_token()

        assert result["valid"] is True
        assert result["error"] is None
        assert result["user"] == "John Doe"
        assert result["email"] == "john.doe@example.com"
        assert result["warnings"] == []

    def test_validate_token_returns_client_error_message(self):
        """Should unwrap ClientError without throwing AttributeError."""
        plugin = JiraPlugin()
        plugin._client = Mock()
        plugin._client.project_key = None
        plugin._token_source = {"name": "jira_api_token", "type": "global"}
        plugin._client.get_current_user.return_value = ClientError(
            error_message="Unauthorized",
            error_code="GET_USER_ERROR",
        )

        result = plugin.validate_token()

        assert result["valid"] is False
        assert result["error"] == "Unauthorized"
        assert result["user"] is None
        assert result["email"] is None
        assert "No default_project configured." in result["warnings"][0]
