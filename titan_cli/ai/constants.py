"""
AI source constants.

Minimal defaults for direct providers and gateway-style model entry.
Models are not hardcoded beyond sensible suggestions.
"""

from typing import TypeAlias

from titan_cli.core.models import AIDirectProvider, AIGatewayBackend

AISourceType: TypeAlias = AIDirectProvider | AIGatewayBackend | str


# Default models (can be overridden by user)
PROVIDER_DEFAULTS: dict[AISourceType, str] = {
    AIDirectProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
    AIDirectProvider.OPENAI: "gpt-5",
    AIDirectProvider.GEMINI: "gemini-1.5-pro",
    AIGatewayBackend.OPENAI_COMPATIBLE: "",
}


# Provider metadata
PROVIDER_INFO: dict[AISourceType, dict[str, str]] = {
    AIDirectProvider.ANTHROPIC: {
        "name": "Claude (Anthropic)",
        "api_key_url": "https://console.anthropic.com/",
        "api_key_prefix": "sk-ant-",
    },
    AIDirectProvider.OPENAI: {
        "name": "OpenAI",
        "api_key_url": "https://platform.openai.com/api-keys",
        "api_key_prefix": "sk-",
    },
    AIDirectProvider.GEMINI: {
        "name": "Gemini (Google)",
        "api_key_url": "https://makersuite.google.com/app/apikey",
        "api_key_prefix": "AIza",
    },
    AIGatewayBackend.OPENAI_COMPATIBLE: {
        "name": "LiteLLM / OpenAI-compatible Gateway",
        "api_key_url": "",  # No specific URL - depends on deployment
        "api_key_prefix": "",  # No specific prefix - varies by implementation
    },
}


def get_default_model(provider: AISourceType) -> str:
    """
    Get default model for a provider

    Args:
        provider: Provider key or enum value (e.g., "anthropic")

    Returns:
        Default model string
    """
    provider_key = getattr(provider, "value", provider)
    return PROVIDER_DEFAULTS.get(provider_key, "")


def get_provider_name(provider: AISourceType) -> str:
    """
    Get human-readable provider name

    Args:
        provider: Provider key or enum value

    Returns:
        Provider display name
    """
    provider_key = getattr(provider, "value", provider)
    return PROVIDER_INFO.get(provider_key, {}).get("name", str(provider_key).title())


def get_source_display_name(source: object) -> str:
    """Return a short human-readable label for a provider or gateway source."""
    if source is None:
        return "unknown"

    source_value = getattr(source, "value", source)
    source_value = str(source_value)

    source_labels = {
        "openai_compatible": "LiteLLM",
        "anthropic": "Anthropic",
        "gemini": "Gemini",
        "openai": "OpenAI",
    }
    return source_labels.get(source_value, source_value)


def get_connection_type_display_name(connection_type: object) -> str:
    """Return a short human-readable label for a connection type."""
    type_value = getattr(connection_type, "value", connection_type)
    type_value = str(type_value)

    connection_type_labels = {
        "gateway": "LLMGateway",
        "direct_provider": "DirectProvider",
    }
    return connection_type_labels.get(type_value, type_value)
