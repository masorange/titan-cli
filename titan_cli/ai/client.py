"""
AI Client - Main facade for AI functionality
"""

import sys
from typing import Optional, List

from titan_cli.core.models import (
    AIConfig,
    AIConnectionKind,
    AIDirectProvider,
    AIGatewayType,
)
from titan_cli.core.secrets import SecretManager
from .exceptions import AIConfigurationError
from .models import AIMessage, AIRequest, AIResponse
from .providers import (
    AIProvider,
    AnthropicProvider,
    GeminiProvider,
    LiteLLMProvider,
    OpenAIProvider,
)


def get_provider_classes() -> dict[str, type[AIProvider]]:
    """Return the direct-provider class registry."""
    return {
        AIDirectProvider.ANTHROPIC.value: AnthropicProvider,
        AIDirectProvider.GEMINI.value: GeminiProvider,
        AIDirectProvider.OPENAI.value: OpenAIProvider,
    }


def get_gateway_classes() -> dict[str, type[AIProvider]]:
    """Return the gateway-provider class registry."""
    return {
        AIGatewayType.OPENAI_COMPATIBLE.value: LiteLLMProvider,
    }


# Backward-compatible snapshot for external imports/tests.
PROVIDER_CLASSES = get_provider_classes()

PROVIDER_PACKAGES = {
    AIDirectProvider.ANTHROPIC.value: "anthropic",
    AIDirectProvider.GEMINI.value: "google-genai google-auth",
    AIDirectProvider.OPENAI.value: "openai",
    AIGatewayType.OPENAI_COMPATIBLE.value: "openai",
}


def get_provider_install_command(provider_name: str) -> Optional[str]:
    """Return the recommended install command for a missing provider dependency."""
    package_spec = PROVIDER_PACKAGES.get(provider_name)
    if not package_spec:
        return None

    try:
        from titan_cli.core.plugins.community import is_running_in_pipx

        if is_running_in_pipx():
            return f"pipx inject titan-cli {package_spec}"
    except Exception:
        pass

    return f"{sys.executable} -m pip install {package_spec}"

class AIClient:
    """
    Main client for AI functionality.

    This facade simplifies AI usage by:
    - Reading configuration from AIConfig.
    - Retrieving secrets from SecretManager.
    - Instantiating the correct AI provider.
    - Providing a simple `generate()` and `chat()` interface.
    """

    def __init__(
        self,
        ai_config: AIConfig,
        secrets: SecretManager,
        connection_id: Optional[str] = None,
    ):
        """
        Initialize AI client.

        Args:
            ai_config: The AI configuration.
            secrets: The SecretManager for handling API keys.
            connection_id: The specific AI connection ID to use. If None, uses the default.
        """
        self.ai_config = ai_config
        self.secrets = secrets

        requested_id = connection_id or ai_config.default_connection

        if requested_id and requested_id in ai_config.connections:
            self.connection_id = requested_id
        elif ai_config.connections:
            self.connection_id = list(ai_config.connections.keys())[0]
        else:
            raise AIConfigurationError("No AI connections configured.")

        self._provider: Optional[AIProvider] = None

    @property
    def provider(self) -> AIProvider:
        """
        Get configured provider (lazy loading).

        Returns:
            Provider instance.

        Raises:
            AIConfigurationError: If AI is not enabled or configured incorrectly.
        """
        if self._provider:
            return self._provider

        connection_config = self.ai_config.connections.get(self.connection_id)
        if not connection_config:
            raise AIConfigurationError(
                f"AI connection '{self.connection_id}' not found in configuration."
            )

        if connection_config.kind == AIConnectionKind.GATEWAY:
            source_name = connection_config.gateway_type.value
            provider_class = get_gateway_classes().get(source_name)
        else:
            source_name = connection_config.provider.value
            provider_class = get_provider_classes().get(source_name)

        if not provider_class:
            raise AIConfigurationError(f"Unknown AI source type: {source_name}")

        api_key_name = f"{self.connection_id}_api_key"
        api_key = self.secrets.get(api_key_name)

        if not api_key and connection_config.kind != AIConnectionKind.GATEWAY:
            raise AIConfigurationError(
                f"API key for connection '{self.connection_id}' ({source_name}) not found."
            )

        kwargs = {"model": connection_config.default_model}

        if api_key:
            kwargs["api_key"] = api_key

        if connection_config.base_url:
            kwargs["base_url"] = connection_config.base_url

        if (
            connection_config.kind == AIConnectionKind.GATEWAY
            and not connection_config.base_url
        ):
            raise AIConfigurationError(
                f"base_url is required for gateway connection '{self.connection_id}'"
            )

        try:
            self._provider = provider_class(**kwargs)
        except ImportError as exc:
            install_command = get_provider_install_command(source_name)
            error_message = str(exc).strip()
            if install_command and install_command not in error_message:
                error_message = f"{error_message}\nInstall with: {install_command}"
            raise AIConfigurationError(error_message) from exc
        return self._provider

    def generate(
        self,
        messages: List[AIMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AIResponse:
        """
        Generate response using configured AI provider.

        Args:
            messages: List of conversation messages.
            max_tokens: Optional override for the maximum number of tokens.
            temperature: Optional override for the temperature.

        Returns:
            AI response with generated content.
        """
        connection_cfg = self.ai_config.connections.get(self.connection_id)
        if not connection_cfg:
            raise AIConfigurationError(
                f"AI connection '{self.connection_id}' not found for generation."
            )

        request = AIRequest(
            messages=messages,
            max_tokens=(
                max_tokens
                if max_tokens is not None
                else (
                    None
                    if connection_cfg.kind == AIConnectionKind.GATEWAY
                    else connection_cfg.max_tokens
                )
            ),
            temperature=(
                temperature
                if temperature is not None
                else (
                    None
                    if connection_cfg.kind == AIConnectionKind.GATEWAY
                    else connection_cfg.temperature
                )
            ),
        )
        return self.provider.generate(request)

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Simple chat interface for single-turn conversations.

        Args:
            prompt: User prompt/question.
            system_prompt: Optional system prompt to set context.
            max_tokens: Optional override for the maximum number of tokens.
            temperature: Optional override for the temperature.

        Returns:
            AI response text.
        """
        messages = []
        if system_prompt:
            messages.append(AIMessage(role="system", content=system_prompt))
        messages.append(AIMessage(role="user", content=prompt))

        response = self.generate(
            messages, max_tokens=max_tokens, temperature=temperature
        )
        return response.content

    def is_available(self) -> bool:
        """
        Check if AI is available and configured correctly.

        Returns:
            True if AI can be used.
        """
        if not self.ai_config or not self.ai_config.connections:
            return False

        connection_cfg = self.ai_config.connections.get(self.connection_id)
        if not connection_cfg:
            return False

        try:
            return self.provider is not None
        except AIConfigurationError:
            return False
