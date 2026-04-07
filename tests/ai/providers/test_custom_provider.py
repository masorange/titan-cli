"""Tests for Custom AI Provider (OpenAI-compatible)."""

import pytest
from unittest.mock import Mock, patch
from openai import AuthenticationError, RateLimitError, APIError

from titan_cli.ai.providers.custom import CustomProvider
from titan_cli.ai.models import AIMessage, AIRequest
from titan_cli.ai.exceptions import (
    AIProviderAuthenticationError,
    AIProviderRateLimitError,
    AIProviderAPIError,
)


class TestCustomProvider:
    """Test suite for CustomProvider."""

    def test_init_with_valid_params(self):
        """Test initialization with valid parameters."""
        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="test-key",
        )

        assert provider._base_url == "http://localhost:4000"
        assert provider._model == "gpt-3.5-turbo"
        assert provider._client.base_url == "http://localhost:4000"

    def test_init_without_api_key(self):
        """Test initialization without API key (some endpoints don't need auth)."""
        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="llama-2-7b",
        )

        assert provider._base_url == "http://localhost:4000"
        assert provider._model == "llama-2-7b"
        # Should use placeholder key
        assert provider._client.api_key == "sk-placeholder"

    def test_init_missing_base_url(self):
        """Test initialization fails without base_url."""
        with pytest.raises(ValueError, match="base_url is required"):
            CustomProvider(
                base_url="",
                model="gpt-3.5-turbo",
            )

    def test_init_missing_model(self):
        """Test initialization fails without model."""
        with pytest.raises(ValueError, match="model is required"):
            CustomProvider(
                base_url="http://localhost:4000",
                model="",
            )

    def test_name_property(self):
        """Test provider name includes base URL."""
        provider = CustomProvider(
            base_url="http://llm.company.com",
            model="custom-model",
        )

        assert "http://llm.company.com" in provider.name

    @patch("titan_cli.ai.providers.custom.OpenAI")
    def test_generate_success(self, mock_openai_class):
        """Test successful generation."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock response
        mock_choice = Mock()
        mock_choice.message.content = "Generated response"
        mock_choice.finish_reason = "stop"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-3.5-turbo"
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.return_value = mock_response

        # Create provider
        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        # Make request
        request = AIRequest(
            messages=[AIMessage(role="user", content="Hello")],
            max_tokens=100,
            temperature=0.7,
        )

        response = provider.generate(request)

        # Verify
        assert response.content == "Generated response"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20
        assert response.finish_reason == "stop"

    @patch("titan_cli.ai.providers.custom.OpenAI")
    def test_generate_authentication_error(self, mock_openai_class):
        """Test handling of authentication errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = AuthenticationError(
            "Invalid API key",
            response=Mock(),
            body=None,
        )

        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        request = AIRequest(
            messages=[AIMessage(role="user", content="Hello")]
        )

        with pytest.raises(AIProviderAuthenticationError, match="Authentication failed"):
            provider.generate(request)

    @patch("titan_cli.ai.providers.custom.OpenAI")
    def test_generate_rate_limit_error(self, mock_openai_class):
        """Test handling of rate limit errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded",
            response=Mock(),
            body=None,
        )

        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        request = AIRequest(
            messages=[AIMessage(role="user", content="Hello")]
        )

        with pytest.raises(AIProviderRateLimitError, match="Rate limit exceeded"):
            provider.generate(request)

    @patch("titan_cli.ai.providers.custom.OpenAI")
    def test_generate_api_error(self, mock_openai_class):
        """Test handling of general API errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = APIError(
            "Server error",
            request=Mock(),
            body=None,
        )

        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        request = AIRequest(
            messages=[AIMessage(role="user", content="Hello")]
        )

        with pytest.raises(AIProviderAPIError, match="API error"):
            provider.generate(request)

    @patch("titan_cli.ai.providers.custom.OpenAI")
    def test_validate_api_key_success(self, mock_openai_class):
        """Test successful API key validation."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock successful minimal request
        mock_choice = Mock()
        mock_choice.message.content = "test"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="test-key",
        )

        assert provider.validate_api_key() is True

    @patch("titan_cli.ai.providers.custom.OpenAI")
    def test_validate_api_key_failure(self, mock_openai_class):
        """Test failed API key validation."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = AuthenticationError(
            "Invalid API key",
            response=Mock(),
            body=None,
        )

        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="bad-key",
        )

        assert provider.validate_api_key() is False

    @patch("titan_cli.ai.providers.custom.OpenAI")
    def test_validate_api_key_other_error_returns_true(self, mock_openai_class):
        """Test that non-auth errors in validation still return True (endpoint reachable)."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Simulate rate limit - means auth passed but hit rate limit
        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit",
            response=Mock(),
            body=None,
        )

        provider = CustomProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="test-key",
        )

        # Other errors mean auth is OK, endpoint is reachable
        assert provider.validate_api_key() is True
