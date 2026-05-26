"""Tests for direct OpenAI provider."""

from unittest.mock import Mock, patch

import pytest

pytest.importorskip("openai")

from openai import APIError, AuthenticationError, RateLimitError

from titan_cli.ai.exceptions import (
    AIProviderAPIError,
    AIProviderAuthenticationError,
    AIProviderRateLimitError,
)
from titan_cli.ai.models import AIMessage, AIRequest
from titan_cli.ai.providers.openai import OpenAIProvider


class TestOpenAIProvider:
    """Test suite for OpenAIProvider."""

    @patch("titan_cli.ai.providers.openai.OpenAI")
    def test_init_with_default_base_url(self, mock_openai):
        """Test initialization without custom base URL."""
        OpenAIProvider(api_key="test-key", model="gpt-5")

        mock_openai.assert_called_once_with(api_key="test-key")

    @patch("titan_cli.ai.providers.openai.OpenAI")
    def test_init_normalizes_custom_base_url(self, mock_openai):
        """Test initialization trims trailing slash from custom base URL."""
        OpenAIProvider(
            api_key="test-key",
            model="gpt-5",
            base_url="https://api.example.com/",
        )

        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.example.com",
        )

    @patch("titan_cli.ai.providers.openai.OpenAI")
    def test_generate_success(self, mock_openai):
        """Test successful response generation."""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        choice = Mock()
        choice.message.content = "Generated response"
        choice.finish_reason = "stop"

        response = Mock()
        response.choices = [choice]
        response.model = "gpt-5"
        response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_client.chat.completions.create.return_value = response

        provider = OpenAIProvider(api_key="test-key", model="gpt-5")
        result = provider.generate(
            AIRequest(
                messages=[AIMessage(role="user", content="Hello")],
                max_tokens=100,
                temperature=0.7,
            )
        )

        assert result.content == "Generated response"
        assert result.model == "gpt-5"
        assert result.usage == {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        }
        assert result.finish_reason == "stop"
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-5",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=100,
            temperature=0.7,
        )

    @patch("titan_cli.ai.providers.openai.OpenAI")
    def test_generate_without_usage(self, mock_openai):
        """Test generation when the SDK omits usage details."""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        choice = Mock()
        choice.message.content = "ok"
        choice.finish_reason = None

        response = Mock()
        response.choices = [choice]
        response.model = "gpt-5"
        response.usage = None
        mock_client.chat.completions.create.return_value = response

        provider = OpenAIProvider(api_key="test-key", model="gpt-5")
        result = provider.generate(
            AIRequest(messages=[AIMessage(role="user", content="Hello")])
        )

        assert result.usage == {}
        assert result.finish_reason == "stop"

    @patch("titan_cli.ai.providers.openai.OpenAI")
    def test_generate_authentication_error(self, mock_openai):
        """Test authentication errors are mapped correctly."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = AuthenticationError(
            "Invalid API key",
            response=Mock(),
            body=None,
        )

        provider = OpenAIProvider(api_key="test-key", model="gpt-5")

        with pytest.raises(AIProviderAuthenticationError, match="authentication failed"):
            provider.generate(AIRequest(messages=[AIMessage(role="user", content="Hello")]))

    @patch("titan_cli.ai.providers.openai.OpenAI")
    def test_generate_rate_limit_error(self, mock_openai):
        """Test rate limit errors are mapped correctly."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded",
            response=Mock(),
            body=None,
        )

        provider = OpenAIProvider(api_key="test-key", model="gpt-5")

        with pytest.raises(AIProviderRateLimitError, match="rate limit exceeded"):
            provider.generate(AIRequest(messages=[AIMessage(role="user", content="Hello")]))

    @patch("titan_cli.ai.providers.openai.OpenAI")
    def test_generate_api_error(self, mock_openai):
        """Test generic API errors are mapped correctly."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APIError(
            "Server error",
            request=Mock(),
            body=None,
        )

        provider = OpenAIProvider(api_key="test-key", model="gpt-5")

        with pytest.raises(AIProviderAPIError, match="OpenAI API error"):
            provider.generate(AIRequest(messages=[AIMessage(role="user", content="Hello")]))
