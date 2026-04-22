from unittest.mock import Mock, patch

from titan_cli.ai.llm_tools import fetch_available_models


@patch("titan_cli.ai.llm_tools.LiteLLMClient")
def test_fetch_available_models_returns_all_models_for_openai_compatible(
    mock_litellm_client,
):
    mock_client = Mock()
    mock_litellm_client.return_value = mock_client
    mock_client.list_models.return_value = [
        Mock(id="gpt-5", owned_by="openai"),
        Mock(id="claude-sonnet-4", owned_by="anthropic"),
        Mock(id="gemini-2.5-pro", owned_by="google"),
    ]

    models = fetch_available_models(
        base_url="http://localhost:4000",
        api_key="test-key",
        provider_filter="openai_compatible",
    )

    assert [model.id for model in models] == [
        "gpt-5",
        "claude-sonnet-4",
        "gemini-2.5-pro",
    ]


@patch("titan_cli.ai.llm_tools.LiteLLMClient")
def test_fetch_available_models_filters_anthropic_models(mock_litellm_client):
    mock_client = Mock()
    mock_litellm_client.return_value = mock_client
    mock_client.list_models.return_value = [
        Mock(id="gpt-5", owned_by="openai"),
        Mock(id="claude-sonnet-4", owned_by="anthropic"),
        Mock(id="claude-opus-4", owned_by="anthropic"),
    ]

    models = fetch_available_models(
        base_url="http://localhost:4000",
        api_key="test-key",
        provider_filter="anthropic",
    )

    assert [model.id for model in models] == [
        "claude-sonnet-4",
        "claude-opus-4",
    ]


@patch("titan_cli.ai.llm_tools.LiteLLMClient")
def test_fetch_available_models_filters_gemini_models(mock_litellm_client):
    mock_client = Mock()
    mock_litellm_client.return_value = mock_client
    mock_client.list_models.return_value = [
        Mock(id="gemini-2.5-pro", owned_by="google"),
        Mock(id="gemini-2.5-flash", owned_by="google"),
        Mock(id="gpt-5", owned_by="openai"),
    ]

    models = fetch_available_models(
        base_url="http://localhost:4000",
        api_key="test-key",
        provider_filter="gemini",
    )

    assert [model.id for model in models] == [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ]


@patch("titan_cli.ai.llm_tools.LiteLLMClient")
def test_fetch_available_models_filters_openai_models(mock_litellm_client):
    mock_client = Mock()
    mock_litellm_client.return_value = mock_client
    mock_client.list_models.return_value = [
        Mock(id="gpt-5", owned_by="openai"),
        Mock(id="gpt-4.1", owned_by="openai"),
        Mock(id="claude-sonnet-4", owned_by="anthropic"),
    ]

    models = fetch_available_models(
        base_url="http://localhost:4000",
        api_key="test-key",
        provider_filter="openai",
    )

    assert [model.id for model in models] == [
        "gpt-5",
        "gpt-4.1",
        "claude-sonnet-4",
    ]
