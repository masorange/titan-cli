"""Tests for LiteLLM/OpenAI-compatible provider."""

import pytest
from unittest.mock import Mock, patch

pytest.importorskip("openai")

from openai import AuthenticationError, RateLimitError, APIError

from titan_cli.ai.providers.litellm import LiteLLMProvider
from titan_cli.ai.models import AIMessage, AIRequest
from titan_cli.ai.exceptions import (
    AIProviderAuthenticationError,
    AIProviderRateLimitError,
    AIProviderAPIError,
)


class TestLiteLLMProvider:
    """Test suite for LiteLLMProvider."""

    def test_init_with_valid_params(self):
        """Test initialization with valid parameters."""
        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="test-key",
        )

        assert provider._base_url == "http://localhost:4000/v1"
        assert provider._model == "gpt-3.5-turbo"
        assert str(provider._client.base_url) == "http://localhost:4000/v1/"

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_init_configures_http2_client(self, mock_openai_class):
        """Test initialization injects an HTTP/2-capable client."""
        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="test-key",
        )

        assert provider._http_client is not None
        assert provider._http_client._transport._pool._http2 is True
        mock_openai_class.assert_called_once_with(
            base_url="http://localhost:4000/v1",
            api_key="test-key",
            http_client=provider._http_client,
        )

    def test_init_without_api_key(self):
        """Test initialization without API key (some endpoints don't need auth)."""
        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="llama-2-7b",
        )

        assert provider._base_url == "http://localhost:4000/v1"
        assert provider._model == "llama-2-7b"
        assert provider._client.api_key == "sk-placeholder"

    def test_init_preserves_existing_path(self):
        """Test initialization preserves explicit API paths."""
        provider = LiteLLMProvider(
            base_url="https://llm.company.com/api/openai",
            model="gpt-3.5-turbo",
        )

        assert provider._base_url == "https://llm.company.com/api/openai"

    def test_init_missing_base_url(self):
        """Test initialization fails without base_url."""
        with pytest.raises(ValueError, match="base_url is required"):
            LiteLLMProvider(
                base_url="",
                model="gpt-3.5-turbo",
            )

    def test_init_missing_model(self):
        """Test initialization fails without model."""
        with pytest.raises(ValueError, match="model is required"):
            LiteLLMProvider(
                base_url="http://localhost:4000",
                model="",
            )

    def test_name_property(self):
        """Test provider name includes base URL."""
        provider = LiteLLMProvider(
            base_url="http://llm.company.com",
            model="custom-model",
        )

        assert "http://llm.company.com" in provider.name

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_generate_success(self, mock_openai_class):
        """Test successful generation."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        first_choice = Mock()
        first_choice.delta.content = "Generated "
        first_choice.finish_reason = None
        first_chunk = Mock()
        first_chunk.choices = [first_choice]
        first_chunk.model = "gpt-3.5-turbo"
        first_chunk.usage = None

        second_choice = Mock()
        second_choice.delta.content = "response"
        second_choice.finish_reason = "stop"
        second_chunk = Mock()
        second_chunk.choices = [second_choice]
        second_chunk.model = "gpt-3.5-turbo"
        second_chunk.usage = None

        usage_chunk = Mock()
        usage_chunk.choices = []
        usage_chunk.model = "gpt-3.5-turbo"
        usage_chunk.usage = Mock(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

        mock_client.chat.completions.create.return_value = [
            first_chunk,
            second_chunk,
            usage_chunk,
        ]

        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        request = AIRequest(
            messages=[AIMessage(role="user", content="Hello")],
            max_tokens=100,
            temperature=0.7,
        )

        response = provider.generate(request)

        assert response.content == "Generated response"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20
        assert response.finish_reason == "stop"
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=100,
            temperature=0.7,
            stream=True,
        )

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_generate_includes_optional_params_when_provided(self, mock_openai_class):
        """Test provider only sends optional params when explicitly provided."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        chunk_choice = Mock()
        chunk_choice.delta.content = "ok"
        chunk_choice.finish_reason = "stop"
        chunk = Mock()
        chunk.choices = [chunk_choice]
        chunk.model = "gpt-3.5-turbo"
        chunk.usage = None
        mock_client.chat.completions.create.return_value = [chunk]

        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        request = AIRequest(
            messages=[AIMessage(role="user", content="Hello")],
            max_tokens=100,
            temperature=0.7,
        )

        provider.generate(request)

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=100,
            temperature=0.7,
            stream=True,
        )

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_generate_authentication_error(self, mock_openai_class):
        """Test handling of authentication errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = AuthenticationError(
            "Invalid API key",
            response=Mock(),
            body=None,
        )

        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        request = AIRequest(messages=[AIMessage(role="user", content="Hello")])

        with pytest.raises(AIProviderAuthenticationError, match="Authentication failed"):
            provider.generate(request)

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_generate_rate_limit_error(self, mock_openai_class):
        """Test handling of rate limit errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded",
            response=Mock(),
            body=None,
        )

        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        request = AIRequest(messages=[AIMessage(role="user", content="Hello")])

        with pytest.raises(AIProviderRateLimitError, match="Rate limit exceeded"):
            provider.generate(request)

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_generate_api_error(self, mock_openai_class):
        """Test handling of general API errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = APIError(
            "Server error",
            request=Mock(),
            body=None,
        )

        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
        )

        request = AIRequest(messages=[AIMessage(role="user", content="Hello")])

        with pytest.raises(AIProviderAPIError, match="API error"):
            provider.generate(request)

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_validate_api_key_success(self, mock_openai_class):
        """Test successful API key validation."""
        mock_client = Mock()
        test_client = Mock()
        mock_openai_class.side_effect = [mock_client, test_client]

        mock_choice = Mock()
        mock_choice.delta.content = "test"
        mock_choice.finish_reason = "stop"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-3.5-turbo"
        mock_response.usage = None
        test_client.chat.completions.create.return_value = [mock_response]

        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="test-key",
        )

        assert provider.validate_api_key() is True
        assert mock_openai_class.call_args_list[-1].kwargs["http_client"] is not None

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_validate_api_key_failure(self, mock_openai_class):
        """Test failed API key validation."""
        mock_client = Mock()
        test_client = Mock()
        mock_openai_class.side_effect = [mock_client, test_client]

        test_client.chat.completions.create.side_effect = AuthenticationError(
            "Invalid API key",
            response=Mock(),
            body=None,
        )

        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="bad-key",
        )

        assert provider.validate_api_key() is False

    @patch("titan_cli.ai.providers.litellm.OpenAI")
    def test_validate_api_key_other_error_returns_true(self, mock_openai_class):
        """Test that non-auth errors in validation still return True."""
        mock_client = Mock()
        test_client = Mock()
        mock_openai_class.side_effect = [mock_client, test_client]

        test_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit",
            response=Mock(),
            body=None,
        )

        provider = LiteLLMProvider(
            base_url="http://localhost:4000",
            model="gpt-3.5-turbo",
            api_key="test-key",
        )

        assert provider.validate_api_key() is True
