"""
AI providers.

Each provider is imported when first asked for, not with the package: their SDKs
(google-genai, openai) take most of a second to import, and importing `.base` alone
must stay cheap.
"""

from .base import AIProvider

_PROVIDER_NAMES = ("AnthropicProvider", "GeminiProvider", "LiteLLMProvider", "OpenAIProvider")


def __getattr__(name: str):
    # Static imports, one per provider: nothing here is derived from the requested name.
    if name == "AnthropicProvider":
        from .anthropic import AnthropicProvider

        return AnthropicProvider
    if name == "GeminiProvider":
        from .gemini import GeminiProvider

        return GeminiProvider
    if name == "LiteLLMProvider":
        from .litellm import LiteLLMProvider

        return LiteLLMProvider
    if name == "OpenAIProvider":
        from .openai import OpenAIProvider

        return OpenAIProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["AIProvider", *_PROVIDER_NAMES]
