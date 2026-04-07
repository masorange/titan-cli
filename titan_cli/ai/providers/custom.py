"""
Custom AI Provider - OpenAI-compatible endpoints (LiteLLM, vLLM, etc.)

Supports any OpenAI-compatible API endpoint, including:
- LiteLLM proxy servers
- vLLM inference servers
- Custom on-premise deployments
- Other OpenAI-compatible services
"""

from typing import Optional
from openai import OpenAI, OpenAIError, APIError, AuthenticationError, RateLimitError

from .base import AIProvider
from ..models import AIRequest, AIResponse
from ..exceptions import (
    AIProviderAuthenticationError,
    AIProviderRateLimitError,
    AIProviderAPIError,
)


class CustomProvider(AIProvider):
    """
    Custom AI provider for OpenAI-compatible endpoints.

    Uses the OpenAI Python SDK to communicate with any OpenAI-compatible API.
    This includes LiteLLM proxy servers, vLLM, and custom deployments.

    Args:
        base_url: The base URL of the API endpoint (required)
        model: Model name/identifier (required)
        api_key: API key for authentication (optional - some endpoints don't require auth)
        max_tokens: Maximum tokens in response (default: 4096)
        temperature: Sampling temperature 0-1 (default: 0.7)
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """Initialize custom provider with OpenAI-compatible client."""
        if not base_url:
            raise ValueError("base_url is required for custom provider")

        if not model:
            raise ValueError("model is required for custom provider")

        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._base_url = base_url

        # Initialize OpenAI client with custom base URL
        # Use "sk-placeholder" if no API key provided (some endpoints don't need auth)
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key or "sk-placeholder",
        )

    @property
    def name(self) -> str:
        """Provider name."""
        return f"custom ({self._base_url})"

    def generate(self, request: AIRequest) -> AIResponse:
        """
        Generate completion using custom OpenAI-compatible endpoint.

        Args:
            request: AI request with messages, max_tokens, temperature

        Returns:
            AI response with generated content

        Raises:
            AIProviderAuthenticationError: Invalid API key
            AIProviderRateLimitError: Rate limit exceeded
            AIProviderAPIError: Other API errors
        """
        try:
            # Convert AIMessage list to OpenAI format
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]

            # Call OpenAI-compatible API
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=request.max_tokens or self._max_tokens,
                temperature=request.temperature or self._temperature,
            )

            # Extract response content
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason or "stop"

            # Extract usage if available
            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return AIResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=finish_reason,
            )

        except AuthenticationError as e:
            raise AIProviderAuthenticationError(
                f"Authentication failed for custom endpoint: {str(e)}"
            )
        except RateLimitError as e:
            raise AIProviderRateLimitError(
                f"Rate limit exceeded for custom endpoint: {str(e)}"
            )
        except APIError as e:
            raise AIProviderAPIError(
                f"API error from custom endpoint: {str(e)}"
            )
        except OpenAIError as e:
            raise AIProviderAPIError(
                f"Custom provider error: {str(e)}"
            )

    def validate_api_key(self, api_key: Optional[str] = None) -> bool:
        """
        Validate API key by making a minimal test request.

        Args:
            api_key: Optional API key to test (uses instance key if not provided)

        Returns:
            True if valid, False otherwise

        Note:
            Some custom endpoints don't require API keys.
            In that case, this method attempts a test request to validate connectivity.
        """
        test_client = OpenAI(
            base_url=self._base_url,
            api_key=api_key or self._client.api_key,
        )

        try:
            # Attempt minimal request to validate connectivity/auth
            test_client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except AuthenticationError:
            return False
        except Exception:
            # Other errors (rate limit, model not found, etc.) mean auth is OK
            # The endpoint is reachable and auth passed
            return True
