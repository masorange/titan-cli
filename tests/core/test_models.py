import pytest
from pydantic import ValidationError

from titan_cli.core.models import (
    AIConfig,
    AIConnectionConfig,
    AIConnectionKind,
    AIGatewayType,
)


def test_aiconnectionconfig_direct_provider_full_fields():
    """Test a direct provider connection with all supported fields."""
    config = AIConnectionConfig(
        name="Test Provider",
        kind=AIConnectionKind.DIRECT_PROVIDER,
        provider="anthropic",
        default_model="claude-sonnet",
        base_url="https://api.example.com",
        temperature=0.5,
        max_tokens=1024,
    )
    assert config.name == "Test Provider"
    assert config.kind == AIConnectionKind.DIRECT_PROVIDER
    assert config.provider == "anthropic"
    assert config.default_model == "claude-sonnet"
    assert config.model == "claude-sonnet"
    assert config.base_url == "https://api.example.com"
    assert config.temperature == 0.5
    assert config.max_tokens == 1024


def test_aiconnectionconfig_gateway_required_fields():
    """Test a gateway connection with only its required fields."""
    config = AIConnectionConfig(
        name="OpenAI Compatible Gateway",
        kind=AIConnectionKind.GATEWAY,
        gateway_type=AIGatewayType.OPENAI_COMPATIBLE,
        base_url="https://gateway.example.com",
    )
    assert config.name == "OpenAI Compatible Gateway"
    assert config.kind == AIConnectionKind.GATEWAY
    assert config.gateway_type == AIGatewayType.OPENAI_COMPATIBLE
    assert config.base_url == "https://gateway.example.com"
    assert config.provider is None
    assert config.default_model is None
    assert config.temperature == 0.7
    assert config.max_tokens == 4096


def test_aiconnectionconfig_missing_required_fields():
    """Test AIConnectionConfig raises ValidationError for missing required fields."""
    with pytest.raises(ValidationError, match="name"):
        AIConnectionConfig(
            kind=AIConnectionKind.DIRECT_PROVIDER,
            provider="anthropic",
            default_model="claude-sonnet",
        )
    with pytest.raises(ValidationError, match="kind"):
        AIConnectionConfig(
            name="Bad Provider",
            provider="anthropic",
            default_model="claude-sonnet",
        )
    with pytest.raises(ValidationError, match="provider"):
        AIConnectionConfig(
            name="Bad Provider",
            kind=AIConnectionKind.DIRECT_PROVIDER,
            default_model="claude-sonnet",
        )


def test_aiconnectionconfig_gateway_rejects_provider():
    """Test gateway connections reject direct provider configuration."""
    with pytest.raises(
        ValidationError, match="gateway connections must not define 'provider'"
    ):
        AIConnectionConfig(
            name="Bad Gateway",
            kind=AIConnectionKind.GATEWAY,
            gateway_type=AIGatewayType.OPENAI_COMPATIBLE,
            provider="custom",
            base_url="https://gateway.example.com",
        )


def test_aiconfig_multiple_connections_and_default():
    """Test AIConfig with multiple connections and a default."""
    config = AIConfig(
        default_connection="corp-gemini",
        connections={
            "corp-gemini": AIConnectionConfig(
                name="Corporate Gemini",
                kind=AIConnectionKind.DIRECT_PROVIDER,
                provider="gemini",
                default_model="gemini-2.0",
                temperature=0.8,
            ),
            "personal-claude": AIConnectionConfig(
                name="Personal Claude",
                kind=AIConnectionKind.DIRECT_PROVIDER,
                provider="anthropic",
                default_model="claude-3",
                max_tokens=4096,
            ),
        },
    )
    assert config.default_connection == "corp-gemini"
    assert config.default == "corp-gemini"
    assert "corp-gemini" in config.connections
    assert "personal-claude" in config.providers

    corp_gemini = config.connections["corp-gemini"]
    assert corp_gemini.name == "Corporate Gemini"
    assert corp_gemini.provider == "gemini"
    assert corp_gemini.temperature == 0.8

    personal_claude = config.providers["personal-claude"]
    assert personal_claude.name == "Personal Claude"
    assert personal_claude.provider == "anthropic"
    assert personal_claude.max_tokens == 4096


def test_aiconfig_no_connections():
    """Test AIConfig with no connections."""
    config = AIConfig(connections={})
    assert config.default_connection is None
    assert config.default is None
    assert not config.connections
    assert not config.providers


def test_aiconfig_default_not_in_connections():
    """Test AIConfig raises ValidationError if default is not in connections."""
    with pytest.raises(
        ValidationError,
        match="Default connection 'non-existent' not found in configured connections.",
    ):
        AIConfig(
            default_connection="non-existent",
            connections={
                "corp-gemini": AIConnectionConfig(
                    name="Corporate Gemini",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="gemini",
                    default_model="gemini-2.0",
                )
            },
        )


def test_aiconfig_empty_connections_with_default():
    """Test AIConfig raises ValidationError if default is set but connections is empty."""
    with pytest.raises(
        ValidationError,
        match="Default connection 'some-default' not found in configured connections.",
    ):
        AIConfig(default_connection="some-default", connections={})
