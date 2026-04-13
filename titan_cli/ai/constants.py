"""
AI source constants.

Minimal defaults for direct providers and gateway-style model entry.
Models are not hardcoded beyond sensible suggestions.
"""

from typing import Dict


# Default models (can be overridden by user)
PROVIDER_DEFAULTS: Dict[str, str] = {
    "anthropic": "claude-3-5-sonnet-20241022",
    "openai": "gpt-5",
    "gemini": "gemini-1.5-pro",
    "openai_compatible": "",
}


# Provider metadata
PROVIDER_INFO: Dict[str, Dict[str, str]] = {
    "anthropic": {
        "name": "Claude (Anthropic)",
        "api_key_url": "https://console.anthropic.com/",
        "api_key_prefix": "sk-ant-",
    },
    "openai": {
        "name": "OpenAI",
        "api_key_url": "https://platform.openai.com/api-keys",
        "api_key_prefix": "sk-",
    },
    "gemini": {
        "name": "Gemini (Google)",
        "api_key_url": "https://makersuite.google.com/app/apikey",
        "api_key_prefix": "AIza",
    },
    "openai_compatible": {
        "name": "LiteLLM / OpenAI-compatible Gateway",
        "api_key_url": "",  # No specific URL - depends on deployment
        "api_key_prefix": "",  # No specific prefix - varies by implementation
    },
}


def get_default_model(provider: str) -> str:
    """
    Get default model for a provider

    Args:
        provider: Provider key (e.g., "anthropic")

    Returns:
        Default model string
    """
    return PROVIDER_DEFAULTS.get(provider, "")


def get_provider_name(provider: str) -> str:
    """
    Get human-readable provider name

    Args:
        provider: Provider key

    Returns:
        Provider display name
    """
    return PROVIDER_INFO.get(provider, {}).get("name", provider.title())
