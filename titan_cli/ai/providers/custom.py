"""
Custom AI Provider - OpenAI-compatible endpoints (LiteLLM, vLLM, etc.)

Supports any OpenAI-compatible API endpoint, including:
- LiteLLM proxy servers
- vLLM inference servers
- Custom on-premise deployments
- Other OpenAI-compatible services
"""

import httpx
from typing import Optional
from urllib.parse import urlparse

try:
    from openai import (
        APIError,
        AuthenticationError,
        OpenAI,
        OpenAIError,
        RateLimitError,
    )
    OPENAI_AVAILABLE = True
    OPENAI_IMPORT_ERROR = None
except ImportError as e:
    OpenAI = None
    OpenAIError = Exception
    APIError = Exception
    AuthenticationError = Exception
    RateLimitError = Exception
    OPENAI_AVAILABLE = False
    OPENAI_IMPORT_ERROR = str(e)

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

        if not OPENAI_AVAILABLE:
            error_msg = "Custom provider requires 'openai' library.\n"
            if OPENAI_IMPORT_ERROR:
                error_msg += f"Import error: {OPENAI_IMPORT_ERROR}\n"
            error_msg += "Install with: poetry add openai"
            raise ImportError(error_msg)

        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._base_url = self._normalize_base_url(base_url)
        self._http_client = self._build_http_client()

        # Initialize OpenAI client with custom base URL
        # Use "sk-placeholder" if no API key provided (some endpoints don't need auth)
        self._client = OpenAI(
            base_url=self._base_url,
            api_key=api_key or "sk-placeholder",
            http_client=self._http_client,
        )

    @property
    def name(self) -> str:
        """Provider name."""
        return f"custom ({self._base_url})"

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        """Normalize base_url for OpenAI-compatible endpoints.

        If the URL only contains the scheme and host, assume the API root is `/v1`.
        If a path is already configured, keep it as-is.
        """
        normalized = base_url.rstrip("/")
        parsed = urlparse(normalized)

        if not parsed.path:
            return f"{normalized}/v1"

        return normalized

    @staticmethod
    def _build_http_client() -> httpx.Client:
        """Build an HTTP client tuned for tunneled OpenAI-compatible endpoints."""
        timeout = httpx.Timeout(connect=5.0, read=600.0, write=600.0, pool=600.0)
        return httpx.Client(http2=True, timeout=timeout, follow_redirects=True)

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

            # Some OpenAI-compatible endpoints only respond correctly in streaming mode.
            request_kwargs = {
                "model": self._model,
                "messages": messages,
                "stream": True,
            }

            if request.max_tokens is not None:
                request_kwargs["max_tokens"] = request.max_tokens

            if request.temperature is not None:
                request_kwargs["temperature"] = request.temperature

            stream = self._client.chat.completions.create(**request_kwargs)

            content_parts: list[str] = []
            finish_reason = "stop"
            response_model = self._model
            usage = {}

            for chunk in stream:
                if getattr(chunk, "model", None):
                    response_model = chunk.model

                if getattr(chunk, "usage", None):
                    usage = {
                        "input_tokens": chunk.usage.prompt_tokens,
                        "output_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }

                for choice in getattr(chunk, "choices", []) or []:
                    delta = getattr(choice, "delta", None)
                    if delta and getattr(delta, "content", None):
                        content_parts.append(delta.content)

                    if getattr(choice, "finish_reason", None):
                        finish_reason = choice.finish_reason

            content = "".join(content_parts)

            return AIResponse(
                content=content,
                model=response_model,
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
            http_client=self._build_http_client(),
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
