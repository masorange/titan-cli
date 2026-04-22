"""OpenAI direct provider."""

from typing import Optional

from titan_cli.core.models import AIDirectProvider

from .base import AIProvider
from ..constants import get_default_model
from ..exceptions import (
    AIProviderAPIError,
    AIProviderAuthenticationError,
    AIProviderRateLimitError,
)
from ..models import AIRequest, AIResponse

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


class OpenAIProvider(AIProvider):
    """Direct provider for OpenAI-hosted models."""

    def __init__(
        self,
        api_key: str,
        model: str = get_default_model(AIDirectProvider.OPENAI),
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key, model)
        if not OPENAI_AVAILABLE:
            error_msg = "OpenAI provider requires 'openai' library.\n"
            if OPENAI_IMPORT_ERROR:
                error_msg += f"Import error: {OPENAI_IMPORT_ERROR}\n"
            error_msg += "Install with: poetry add openai"
            raise ImportError(error_msg)

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url.rstrip("/")
        self.client = OpenAI(**kwargs)

    @property
    def name(self) -> str:
        return "openai"

    def generate(self, request: AIRequest) -> AIResponse:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[msg.to_dict() for msg in request.messages],
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            choice = response.choices[0]
            usage = response.usage
            return AIResponse(
                content=choice.message.content or "",
                model=response.model,
                usage=(
                    {
                        "input_tokens": usage.prompt_tokens,
                        "output_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                    if usage
                    else {}
                ),
                finish_reason=choice.finish_reason or "stop",
            )
        except AuthenticationError as e:
            raise AIProviderAuthenticationError(f"OpenAI authentication failed: {e}")
        except RateLimitError as e:
            raise AIProviderRateLimitError(f"OpenAI rate limit exceeded: {e}")
        except APIError as e:
            raise AIProviderAPIError(f"OpenAI API error: {e}")
        except OpenAIError as e:
            raise AIProviderAPIError(f"OpenAI provider error: {e}")
