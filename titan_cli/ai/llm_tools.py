"""
Utilities for gateway model discovery.

This module keeps backward-compatible helpers used by the wizard while
delegating the actual gateway access to LiteLLMClient.
"""
from typing import List, Optional
from dataclasses import dataclass

from .litellm_client import LiteLLMClient


@dataclass
class LLMModel:
    """Model information from LLM Tools API."""

    id: str
    name: str
    description: Optional[str] = None

def is_llm_tools_url(base_url: str) -> bool:
    """
    Check if a base_url is an LLM Tools endpoint.

    Args:
        base_url: The base URL to check

    Returns:
        True if URL contains llm.tools pattern

    Examples:
        >>> is_llm_tools_url("https://llm.tools.example.com")
        True
        >>> is_llm_tools_url("https://api.anthropic.com")
        False
    """
    if not base_url:
        return False
    return "llm.tools" in base_url.lower()


def fetch_available_models(
    base_url: str,
    api_key: Optional[str],
    provider_filter: Optional[str] = None,
) -> List[LLMModel]:
    """
    Fetch available models from an OpenAI-compatible gateway.

    The gateway uses OpenAI-compatible format and returns a list of
    available models with their metadata.

    Args:
        base_url: Gateway endpoint URL
        api_key: API key for authentication if required
        provider_filter: Filter by source/model family

    Returns:
        List of available models filtered by source

    Raises:
        requests.RequestException: If API call fails
    """
    data = LiteLLMClient(base_url=base_url, api_key=api_key).list_models()
    models = []
    for model_data in data:
        model_id = model_data.id
        owned_by = (model_data.owned_by or "").lower()

        # Filter by provider if specified
        # Note: LLM Tools API doesn't use owned_by correctly, so we filter by model name
        if provider_filter:
            model_id_lower = model_id.lower()

            # Filter by model name pattern
            if provider_filter == "anthropic":
                # Only include models with "claude" in the name
                if "claude" not in model_id_lower:
                    continue
            elif provider_filter == "gemini":
                # Only include models with "gemini" in the name
                if "gemini" not in model_id_lower:
                    continue

        models.append(
            LLMModel(
                id=model_id,
                name=model_id,  # LiteLLM doesn't provide display name
                description=f"Provider: {owned_by}",
            )
        )

    return models
