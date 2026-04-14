from unittest.mock import Mock, patch

from titan_cli.ai.litellm_client import LiteLLMClient


def test_normalize_base_url_adds_v1():
    assert (
        LiteLLMClient._normalize_base_url("http://localhost:4000")
        == "http://localhost:4000/v1"
    )


def test_normalize_base_url_keeps_existing_path():
    assert (
        LiteLLMClient._normalize_base_url("http://localhost:4000/v1")
        == "http://localhost:4000/v1"
    )


@patch("titan_cli.ai.litellm_client.OpenAI")
def test_list_models_returns_gateway_models(mock_openai):
    mock_client = Mock()
    mock_openai.return_value = mock_client
    mock_client.models.list.return_value = Mock(
        data=[
            Mock(id="gpt-5", owned_by="openai"),
            Mock(id="claude-sonnet-4", owned_by="anthropic"),
        ]
    )

    client = LiteLLMClient(base_url="http://localhost:4000", api_key="test")
    models = client.list_models()

    assert [model.id for model in models] == ["gpt-5", "claude-sonnet-4"]


@patch("titan_cli.ai.litellm_client.OpenAI")
def test_test_connection_without_model_uses_list_models(mock_openai):
    mock_client = Mock()
    mock_openai.return_value = mock_client
    mock_client.models.list.return_value = Mock(data=[])

    client = LiteLLMClient(base_url="http://localhost:4000", api_key="test")
    assert client.test_connection() is True
    mock_client.models.list.assert_called_once()


@patch("titan_cli.ai.litellm_client.OpenAI")
def test_test_connection_with_model_uses_chat_completion(mock_openai):
    mock_client = Mock()
    mock_openai.return_value = mock_client

    client = LiteLLMClient(base_url="http://localhost:4000", api_key="test")
    assert client.test_connection(model="gpt-5") is True
    mock_client.chat.completions.create.assert_called_once()
