"""Tests for AIClient integration with LiteLLM provider."""

from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from titan_cli.ai.client import AIClient, get_gateway_classes
from titan_cli.ai.exceptions import AIConfigurationError
from titan_cli.core.models import AIConfig, AIConnectionKind, AIProviderConfig
from titan_cli.core.secrets import SecretManager


class TestAIClientLiteLLMProvider:
    """Test suite for AIClient with LiteLLM provider."""

    def test_litellm_provider_with_api_key(self):
        """Test LiteLLM provider initialization with API key."""
        ai_config = AIConfig(
            default_connection="custom-llm",
            connections={
                "custom-llm": AIProviderConfig(
                    name="Custom LLM",
                    kind=AIConnectionKind.GATEWAY,
                    gateway_type="openai_compatible",
                    default_model="llama-2-7b",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-api-key"

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.LiteLLMProvider") as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider

            provider = client.provider

            mock_provider_class.assert_called_once_with(
                model="llama-2-7b",
                api_key="test-api-key",
                base_url="http://localhost:4000",
            )
            assert provider is mock_provider

    def test_litellm_provider_without_api_key(self):
        """Test LiteLLM provider initialization without API key (allowed)."""
        ai_config = AIConfig(
            default_connection="local-llm",
            connections={
                "local-llm": AIProviderConfig(
                    name="Local LLM",
                    kind=AIConnectionKind.GATEWAY,
                    gateway_type="openai_compatible",
                    default_model="mistral-7b",
                    base_url="http://localhost:8000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = None

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.LiteLLMProvider") as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider

            provider = client.provider

            mock_provider_class.assert_called_once_with(
                model="mistral-7b",
                base_url="http://localhost:8000",
            )
            assert provider is mock_provider

    def test_litellm_provider_missing_base_url(self):
        """Test gateway connection validation fails without base_url."""
        with pytest.raises(
            ValidationError, match="gateway connections require 'base_url'"
        ):
            AIConfig(
                default_connection="bad-gateway",
                connections={
                    "bad-gateway": AIProviderConfig(
                        name="Bad Gateway",
                        kind=AIConnectionKind.GATEWAY,
                        gateway_type="openai_compatible",
                        default_model="llama-2-7b",
                    )
                },
            )

    def test_litellm_provider_with_litellm_url(self):
        """Test LiteLLM provider with LiteLLM proxy URL."""
        ai_config = AIConfig(
            default_connection="litellm",
            connections={
                "litellm": AIProviderConfig(
                    name="LiteLLM Proxy",
                    kind=AIConnectionKind.GATEWAY,
                    gateway_type="openai_compatible",
                    default_model="gpt-3.5-turbo",
                    base_url="http://litellm-proxy:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "litellm-master-key"

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.LiteLLMProvider") as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider

            provider = client.provider

            mock_provider_class.assert_called_once_with(
                model="gpt-3.5-turbo",
                api_key="litellm-master-key",
                base_url="http://litellm-proxy:4000",
            )
            assert provider is mock_provider

    def test_litellm_provider_registered_in_gateway_classes(self):
        """Test that LiteLLM provider is registered in gateway classes."""
        from titan_cli.ai.providers.litellm import LiteLLMProvider

        assert "openai_compatible" in get_gateway_classes()
        assert get_gateway_classes()["openai_compatible"] == LiteLLMProvider

    def test_litellm_provider_generate(self):
        """Test generate method with LiteLLM provider."""
        ai_config = AIConfig(
            default_connection="gateway",
            connections={
                "gateway": AIProviderConfig(
                    name="Gateway",
                    kind=AIConnectionKind.GATEWAY,
                    gateway_type="openai_compatible",
                    default_model="test-model",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-key"

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.LiteLLMProvider") as mock_provider_class:
            mock_provider = Mock()
            mock_response = Mock()
            mock_response.content = "Generated text"
            mock_provider.generate.return_value = mock_response
            mock_provider_class.return_value = mock_provider

            from titan_cli.ai.models import AIMessage

            response = client.generate([AIMessage(role="user", content="Hello")])

            assert mock_provider.generate.called
            assert response.content == "Generated text"

    def test_litellm_provider_generate_omits_default_sampling_params(self):
        """Test AIClient does not inject default max_tokens/temperature for gateways."""
        ai_config = AIConfig(
            default_connection="gateway",
            connections={
                "gateway": AIProviderConfig(
                    name="Gateway",
                    kind=AIConnectionKind.GATEWAY,
                    gateway_type="openai_compatible",
                    default_model="test-model",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-key"

        client = AIClient(ai_config, mock_secrets)

        with patch("titan_cli.ai.client.LiteLLMProvider") as mock_provider_class:
            mock_provider = Mock()
            mock_response = Mock()
            mock_response.content = "Generated text"
            mock_provider.generate.return_value = mock_response
            mock_provider_class.return_value = mock_provider

            from titan_cli.ai.models import AIMessage

            client.generate([AIMessage(role="user", content="Hello")])

            request_arg = mock_provider.generate.call_args.args[0]
            assert request_arg.max_tokens is None
            assert request_arg.temperature is None

    def test_litellm_provider_missing_dependency_shows_install_command(self):
        """Test missing LiteLLM dependency surfaces an install command."""
        ai_config = AIConfig(
            default_connection="gateway",
            connections={
                "gateway": AIProviderConfig(
                    name="Gateway",
                    kind=AIConnectionKind.GATEWAY,
                    gateway_type="openai_compatible",
                    default_model="test-model",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-key"

        client = AIClient(ai_config, mock_secrets)

        with patch(
            "titan_cli.ai.client.LiteLLMProvider",
            side_effect=ImportError("No module named 'openai'"),
        ):
            with pytest.raises(AIConfigurationError, match="Install with:"):
                _ = client.provider
