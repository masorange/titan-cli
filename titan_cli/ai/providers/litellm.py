"""
LiteLLM Provider - OpenAI-compatible endpoints (LiteLLM, vLLM, etc.)

Supports any OpenAI-compatible API endpoint, including:
- LiteLLM proxy servers
- vLLM inference servers
- Custom on-premise deployments
- Other OpenAI-compatible services
"""

from typing import Optional

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
from ..litellm_client import LiteLLMClient
from ..models import AIRequest, AIResponse
from ..exceptions import (
    AIProviderAuthenticationError,
    AIProviderRateLimitError,
    AIProviderAPIError,
)


class LiteLLMProvider(AIProvider):
    """
    LiteLLM/OpenAI-compatible provider.

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
        """Initialize LiteLLM provider with OpenAI-compatible client."""
        if not base_url:
            raise ValueError("base_url is required for LiteLLM provider")

        if not model:
            raise ValueError("model is required for LiteLLM provider")

        if not OPENAI_AVAILABLE:
            error_msg = "LiteLLM provider requires 'openai' library.\n"
            if OPENAI_IMPORT_ERROR:
                error_msg += f"Import error: {OPENAI_IMPORT_ERROR}\n"
            error_msg += "Install with: poetry add openai"
            raise ImportError(error_msg)

        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        gateway_client = LiteLLMClient(base_url=base_url, api_key=api_key)
        self._base_url = gateway_client.base_url
        self._http_client = gateway_client._http_client
        self._client = gateway_client._client

    @property
    def name(self) -> str:
        """Provider name."""
        return f"litellm ({self._base_url})"

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

            request_kwargs = {
                "model": self._model,
                "messages": messages,
                "stream": False,
            }

            if request.max_tokens is not None:
                request_kwargs["max_tokens"] = request.max_tokens

            if request.temperature is not None:
                request_kwargs["temperature"] = request.temperature

            response = self._client.chat.completions.create(**request_kwargs)
            choice = response.choices[0]
            usage = response.usage
            content = choice.message.content or ""
            response_model = response.model or self._model
            finish_reason = choice.finish_reason or "stop"

            return AIResponse(
                content=content,
                model=response_model,
                usage=(
                    {
                        "input_tokens": usage.prompt_tokens,
                        "output_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                    if usage
                    else {}
                ),
                finish_reason=finish_reason,
            )

        except AuthenticationError as e:
            raise AIProviderAuthenticationError(
                f"Authentication failed for LiteLLM endpoint: {str(e)}"
            )
        except RateLimitError as e:
            raise AIProviderRateLimitError(
                f"Rate limit exceeded for LiteLLM endpoint: {str(e)}"
            )
        except APIError as e:
            raise AIProviderAPIError(
                f"API error from LiteLLM endpoint: {str(e)}"
            )
        except OpenAIError as e:
            raise AIProviderAPIError(
                f"LiteLLM provider error: {str(e)}"
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
        try:
            LiteLLMClient(
                base_url=self._base_url,
                api_key=api_key or self._client.api_key,
            ).test_connection(model=self._model)
            return True
        except AuthenticationError:
            return False
        except Exception:
            # Other errors (rate limit, model not found, etc.) mean auth is OK
            # The endpoint is reachable and auth passed
            return True
