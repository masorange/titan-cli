"""Tests for AIClient integration with custom provider."""

import pytest
from unittest.mock import Mock, patch

from titan_cli.ai.client import AIClient
from titan_cli.ai.exceptions import AIConfigurationError
from titan_cli.core.models import AIConfig, AIProviderConfig
from titan_cli.core.secrets import SecretManager


class TestAIClientCustomProvider:
    """Test suite for AIClient with custom provider."""

    def test_custom_provider_with_api_key(self):
        """Test custom provider initialization with API key."""
        # Mock configuration
        ai_config = AIConfig(
            default="custom-llm",
            providers={
                "custom-llm": AIProviderConfig(
                    name="Custom LLM",
                    type="individual",
                    provider="custom",
                    model="llama-2-7b",
                    base_url="http://localhost:4000",
                )
            },
        )

        # Mock secrets
        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-api-key"

        # Create client
        client = AIClient(ai_config, mock_secrets)

        # Get provider (triggers lazy loading)
        with patch("titan_cli.ai.client.CustomProvider") as mock_custom_class:
            mock_provider = Mock()
            mock_custom_class.return_value = mock_provider

            provider = client.provider

            # Verify CustomProvider was instantiated with correct params
            mock_custom_class.assert_called_once_with(
                model="llama-2-7b",
                api_key="test-api-key",
                base_url="http://localhost:4000",
            )
            # Verify the returned provider is the mocked one
            assert provider is mock_provider

    def test_custom_provider_without_api_key(self):
        """Test custom provider initialization without API key (allowed)."""
        # Mock configuration
        ai_config = AIConfig(
            default="local-llm",
            providers={
                "local-llm": AIProviderConfig(
                    name="Local LLM",
                    type="individual",
                    provider="custom",
                    model="mistral-7b",
                    base_url="http://localhost:8000",
                )
            },
        )

        # Mock secrets (returns None - no API key)
        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = None

        # Create client (should not raise error)
        client = AIClient(ai_config, mock_secrets)

        # Get provider
        with patch("titan_cli.ai.client.CustomProvider") as mock_custom_class:
            mock_provider = Mock()
            mock_custom_class.return_value = mock_provider

            provider = client.provider

            # Verify CustomProvider was instantiated WITHOUT api_key
            mock_custom_class.assert_called_once_with(
                model="mistral-7b",
                base_url="http://localhost:8000",
            )
            # Verify the returned provider is the mocked one
            assert provider is mock_provider

    def test_custom_provider_missing_base_url(self):
        """Test custom provider fails without base_url."""
        # Mock configuration WITHOUT base_url
        ai_config = AIConfig(
            default="bad-custom",
            providers={
                "bad-custom": AIProviderConfig(
                    name="Bad Custom",
                    type="individual",
                    provider="custom",
                    model="llama-2-7b",
                    # base_url missing!
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = None

        client = AIClient(ai_config, mock_secrets)

        # Should raise configuration error
        with pytest.raises(
            AIConfigurationError, match="base_url is required for custom provider"
        ):
            _ = client.provider

    def test_custom_provider_with_litellm_url(self):
        """Test custom provider with LiteLLM proxy URL."""
        ai_config = AIConfig(
            default="litellm",
            providers={
                "litellm": AIProviderConfig(
                    name="LiteLLM Proxy",
                    type="corporate",
                    provider="custom",
                    model="gpt-3.5-turbo",
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

            # Verify correct instantiation
            mock_custom_class.assert_called_once_with(
                model="gpt-3.5-turbo",
                api_key="litellm-master-key",
                base_url="http://litellm-proxy:4000",
            )
            # Verify the returned provider is the mocked one
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
            default="custom",
            providers={
                "custom": AIProviderConfig(
                    name="Custom",
                    type="individual",
                    provider="custom",
                    model="test-model",
                    base_url="http://localhost:4000",
                )
            },
        )

        mock_secrets = Mock(spec=SecretManager)
        mock_secrets.get.return_value = "test-key"

        client = AIClient(ai_config, mock_secrets)

        # Mock the provider's generate method
        with patch("titan_cli.ai.client.CustomProvider") as mock_custom_class:
            mock_provider = Mock()
            mock_response = Mock()
            mock_response.content = "Generated text"
            mock_provider.generate.return_value = mock_response
            mock_custom_class.return_value = mock_provider

            # Call generate
            from titan_cli.ai.models import AIMessage

            response = client.generate(
                [AIMessage(role="user", content="Hello")]
            )

            # Verify provider's generate was called
            assert mock_provider.generate.called
            assert response.content == "Generated text"
