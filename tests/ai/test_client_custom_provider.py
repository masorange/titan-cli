"""Tests for AIClient integration with custom provider."""

from unittest.mock import Mock, patch

import pytest

from titan_cli.ai.client import AIClient
from titan_cli.ai.exceptions import AIConfigurationError
from titan_cli.core.models import AIConfig, AIConnectionKind, AIProviderConfig
from titan_cli.core.secrets import SecretManager


class TestAIClientCustomProvider:
    """Test suite for AIClient with custom provider."""

    def test_custom_provider_with_api_key(self):
        """Test custom provider initialization with API key."""
        ai_config = AIConfig(
            default_connection="custom-llm",
            connections={
                "custom-llm": AIProviderConfig(
                    name="Custom LLM",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="custom",
                    default_model="llama-2-7b",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-api-key"

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.CustomProvider") as mock_custom_class:
            mock_provider = Mock()
            mock_custom_class.return_value = mock_provider

            provider = client.provider

            mock_custom_class.assert_called_once_with(
                model="llama-2-7b",
                api_key="test-api-key",
                base_url="http://localhost:4000",
            )
            assert provider is mock_provider

    def test_custom_provider_without_api_key(self):
        """Test custom provider initialization without API key (allowed)."""
        ai_config = AIConfig(
            default_connection="local-llm",
            connections={
                "local-llm": AIProviderConfig(
                    name="Local LLM",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="custom",
                    default_model="mistral-7b",
                    base_url="http://localhost:8000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = None

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.CustomProvider") as mock_custom_class:
            mock_provider = Mock()
            mock_custom_class.return_value = mock_provider

            provider = client.provider

            mock_custom_class.assert_called_once_with(
                model="mistral-7b",
                base_url="http://localhost:8000",
            )
            assert provider is mock_provider

    def test_custom_provider_missing_base_url(self):
        """Test custom provider fails without base_url."""
        ai_config = AIConfig(
            default_connection="bad-custom",
            connections={
                "bad-custom": AIProviderConfig(
                    name="Bad Custom",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="custom",
                    default_model="llama-2-7b",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = None

        client = AIClient(ai_config, mock_secrets)

        with pytest.raises(
            AIConfigurationError, match="base_url is required for custom provider"
        ):
            _ = client.provider

    def test_custom_provider_with_litellm_url(self):
        """Test custom provider with LiteLLM proxy URL."""
        ai_config = AIConfig(
            default_connection="litellm",
            connections={
                "litellm": AIProviderConfig(
                    name="LiteLLM Proxy",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="custom",
                    default_model="gpt-3.5-turbo",
                    base_url="http://litellm-proxy:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "litellm-master-key"

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.CustomProvider") as mock_custom_class:
            mock_provider = Mock()
            mock_custom_class.return_value = mock_provider

            provider = client.provider

            mock_custom_class.assert_called_once_with(
                model="gpt-3.5-turbo",
                api_key="litellm-master-key",
                base_url="http://litellm-proxy:4000",
            )
            assert provider is mock_provider

    def test_custom_provider_in_provider_classes_dict(self):
        """Test that custom provider is registered in PROVIDER_CLASSES."""
        from titan_cli.ai.client import PROVIDER_CLASSES
        from titan_cli.ai.providers.custom import CustomProvider

        assert "custom" in PROVIDER_CLASSES
        assert PROVIDER_CLASSES["custom"] == CustomProvider

    def test_custom_provider_generate(self):
        """Test generate method with custom provider."""
        ai_config = AIConfig(
            default_connection="custom",
            connections={
                "custom": AIProviderConfig(
                    name="Custom",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="custom",
                    default_model="test-model",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-key"

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.CustomProvider") as mock_custom_class:
            mock_provider = Mock()
            mock_response = Mock()
            mock_response.content = "Generated text"
            mock_provider.generate.return_value = mock_response
            mock_custom_class.return_value = mock_provider

            from titan_cli.ai.models import AIMessage

            response = client.generate([AIMessage(role="user", content="Hello")])

            assert mock_provider.generate.called
            assert response.content == "Generated text"

    def test_custom_provider_generate_omits_default_sampling_params(self):
        """Test AIClient does not inject default max_tokens/temperature for custom providers."""
        ai_config = AIConfig(
            default_connection="custom",
            connections={
                "custom": AIProviderConfig(
                    name="Custom",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="custom",
                    default_model="test-model",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-key"

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.CustomProvider") as mock_custom_class:
            mock_provider = Mock()
            mock_response = Mock()
            mock_response.content = "Generated text"
            mock_provider.generate.return_value = mock_response
            mock_custom_class.return_value = mock_provider

            from titan_cli.ai.models import AIMessage

            client.generate([AIMessage(role="user", content="Hello")])

            request_arg = mock_provider.generate.call_args.args[0]
            assert request_arg.max_tokens is None
            assert request_arg.temperature is None

    def test_custom_provider_missing_dependency_shows_install_command(self):
        """Test missing custom provider dependency surfaces an install command."""
        ai_config = AIConfig(
            default_connection="custom",
            connections={
                "custom": AIProviderConfig(
                    name="Custom",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="custom",
                    default_model="test-model",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-key"

        client = AIClient(ai_config, mock_secrets)

        with patch(
            "titan_cli.ai.client.CustomProvider",
            side_effect=ImportError("No module named 'openai'"),
        ):
            with pytest.raises(AIConfigurationError, match="Install with:"):
                _ = client.provider
