"""
LLM Tools API client for fetching available models.

This module provides utilities to detect and interact with LLM Tools
(LiteLLM) endpoints for dynamically fetching available AI models.
"""
import requests
from typing import List, Optional
from dataclasses import dataclass


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
    api_key: str,
    provider_filter: Optional[str] = None,
) -> List[LLMModel]:
    """
    Fetch available models from LLM Tools API (LiteLLM format).

    The API uses OpenAI-compatible format and returns a list of available
    models with their metadata.

    Args:
        base_url: LLM Tools endpoint URL
        api_key: API key for authentication (required)
        provider_filter: Filter by provider ("anthropic" or "gemini")

    Returns:
        List of available models filtered by provider

    Raises:
        requests.RequestException: If API call fails
        ValueError: If api_key is not provided

    Examples:
        >>> models = fetch_available_models(
        ...     "https://llm.tools.example.com",
        ...     "sk-1234",
        ...     provider_filter="anthropic"
        ... )
        >>> len(models) > 0
        True
    """
    if not api_key:
        raise ValueError("API key is required to fetch models from LLM Tools")

    # LiteLLM uses OpenAI-compatible endpoint
    endpoint = f"{base_url.rstrip('/')}/v1/models"

    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(endpoint, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json()

    # Parse OpenAI-compatible response
    models = []
    for model_data in data.get("data", []):
        model_id = model_data.get("id", "")
        owned_by = model_data.get("owned_by", "").lower()

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
