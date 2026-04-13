"""
AI Client - Main facade for AI functionality
"""

import sys
from typing import Optional, List

from titan_cli.core.models import AIConfig
from titan_cli.core.secrets import SecretManager
from .exceptions import AIConfigurationError
from .models import AIMessage, AIRequest, AIResponse
from .providers import AIProvider, AnthropicProvider, GeminiProvider, CustomProvider


def get_provider_classes() -> dict[str, type[AIProvider]]:
    """Return the current provider class registry."""
    return {
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "custom": CustomProvider,
    }


# Backward-compatible snapshot for external imports/tests.
PROVIDER_CLASSES = get_provider_classes()

PROVIDER_PACKAGES = {
    "anthropic": "anthropic",
    "gemini": "google-genai google-auth",
    "custom": "openai",
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

    def __init__(self, ai_config: AIConfig, secrets: SecretManager, provider_id: Optional[str] = None):
        """
        Initialize AI client.

        Args:
            ai_config: The AI configuration.
            secrets: The SecretManager for handling API keys.
            provider_id: The specific provider ID to use. If None, uses the default.
        """
        self.ai_config = ai_config
        self.secrets = secrets

        # Determine provider_id with fallback
        requested_id = provider_id or ai_config.default

        # Validate that the provider exists, fallback to first available if default is invalid
        if requested_id and requested_id in ai_config.providers:
            self.provider_id = requested_id
        elif ai_config.providers:
            # Fallback to first available provider
            self.provider_id = list(ai_config.providers.keys())[0]
        else:
            raise AIConfigurationError("No AI providers configured.")

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

        provider_config = self.ai_config.providers.get(self.provider_id)
        if not provider_config:
            raise AIConfigurationError(f"AI provider '{self.provider_id}' not found in configuration.")

        provider_name = provider_config.provider
        provider_class = get_provider_classes().get(provider_name)

        if not provider_class:
            raise AIConfigurationError(f"Unknown AI provider type: {provider_name}")

        # Get API key (optional for custom provider)
        api_key_name = f"{self.provider_id}_api_key"
        api_key = self.secrets.get(api_key_name)

        # For custom provider, API key is optional
        # For other providers, API key is required
        if not api_key and provider_name != "custom":
            raise AIConfigurationError(f"API key for provider '{self.provider_id}' ({provider_name}) not found.")

        # Build provider kwargs
        kwargs = {"model": provider_config.model}

        # Add API key if present
        if api_key:
            kwargs["api_key"] = api_key

        # Add base_url if present
        if provider_config.base_url:
            kwargs["base_url"] = provider_config.base_url

        # For custom provider, base_url is required
        if provider_name == "custom" and not provider_config.base_url:
            raise AIConfigurationError(f"base_url is required for custom provider '{self.provider_id}'")

        try:
            self._provider = provider_class(**kwargs)
        except ImportError as exc:
            install_command = get_provider_install_command(provider_name)
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
        provider_cfg = self.ai_config.providers.get(self.provider_id)
        if not provider_cfg:
            raise AIConfigurationError(f"AI provider '{self.provider_id}' not found for generation.")

        request = AIRequest(
            messages=messages,
            max_tokens=(
                max_tokens
                if max_tokens is not None
                else (
                    None if provider_cfg.provider == "custom" else provider_cfg.max_tokens
                )
            ),
            temperature=(
                temperature
                if temperature is not None
                else (
                    None if provider_cfg.provider == "custom" else provider_cfg.temperature
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
        if not self.ai_config or not self.ai_config.providers:
            return False
        
        provider_cfg = self.ai_config.providers.get(self.provider_id)
        if not provider_cfg:
            return False

        try:
            # This will attempt to instantiate the provider, which includes key checks.
            # Make sure to call self.provider to trigger the instantiation and checks
            return self.provider is not None
        except AIConfigurationError:
            return False
