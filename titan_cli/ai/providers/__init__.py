"""
AI providers.

Each provider is imported when first asked for, not with the package: their SDKs
(google-genai, openai) take most of a second to import, and importing `.base` alone
must stay cheap.
"""

from importlib import import_module

from .base import AIProvider

_PROVIDERS = {
    "AnthropicProvider": ".anthropic",
    "GeminiProvider": ".gemini",
    "LiteLLMProvider": ".litellm",
    "OpenAIProvider": ".openai",
}


def __getattr__(name: str):
    module = _PROVIDERS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module, __name__), name)


__all__ = ["AIProvider", *_PROVIDERS]
