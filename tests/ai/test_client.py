import pytest
from pydantic import ValidationError
from unittest.mock import MagicMock

from titan_cli.ai.client import AIClient
from titan_cli.ai.exceptions import AIConfigurationError
from titan_cli.core.models import AIConfig, AIConnectionKind, AIProviderConfig
from titan_cli.core.secrets import SecretManager


@pytest.fixture
def mock_ai_config_single_provider():
    """Returns an AIConfig with one connection and it as default."""
    return AIConfig(
        default_connection="test_provider",
        connections={
            "test_provider": AIProviderConfig(
                name="Test Provider",
                kind=AIConnectionKind.DIRECT_PROVIDER,
                provider="anthropic",
                default_model="claude-sonnet",
            )
        },
    )


@pytest.fixture
def mock_ai_config_multiple_connections():
    """Returns an AIConfig with multiple connections and a default."""
    return AIConfig(
        default_connection="default_gemini",
        connections={
            "default_gemini": AIProviderConfig(
                name="Default Gemini",
                kind=AIConnectionKind.DIRECT_PROVIDER,
                provider="gemini",
                default_model="gemini-pro",
            ),
            "secondary_anthropic": AIProviderConfig(
                name="Secondary Anthropic",
                kind=AIConnectionKind.DIRECT_PROVIDER,
                provider="anthropic",
                default_model="claude-3",
            ),
        },
    )


@pytest.fixture
def mock_secret_manager():
    """Returns a mock SecretManager."""
    sm = MagicMock(spec=SecretManager)
    sm.get.return_value = "mock_api_key"
    return sm


def test_aiclient_init_specific_provider(
    mock_ai_config_multiple_connections, mock_secret_manager
):
    """Test AIClient initializes with a specific connection_id."""
    client = AIClient(
        ai_config=mock_ai_config_multiple_connections,
        secrets=mock_secret_manager,
        connection_id="secondary_anthropic",
    )
    current_provider_cfg = client.ai_config.connections.get(client.connection_id)
    assert current_provider_cfg.name == "Secondary Anthropic"
    assert current_provider_cfg.provider == "anthropic"


def test_aiclient_init_default_provider(
    mock_ai_config_multiple_connections, mock_secret_manager
):
    """Test AIClient initializes with the default connection when no connection_id is given."""
    client = AIClient(
        ai_config=mock_ai_config_multiple_connections,
        secrets=mock_secret_manager,
    )
    current_provider_cfg = client.ai_config.connections.get(client.connection_id)
    assert current_provider_cfg.name == "Default Gemini"
    assert current_provider_cfg.provider == "gemini"


def test_aiclient_init_fallback_default_not_exist_fails():
    """Test AIConfig raises ValidationError if default connection does not exist."""
    with pytest.raises(
        ValidationError,
        match="Default connection 'non_existent' not found in configured connections.",
    ):
        AIConfig(
            default_connection="non_existent",
            connections={
                "some_provider": AIProviderConfig(
                    name="Some Provider",
                    kind=AIConnectionKind.DIRECT_PROVIDER,
                    provider="openai",
                    default_model="gpt-3.5",
                )
            },
        )


def test_aiclient_init_invalid_provider_id_falls_back(
    mock_ai_config_multiple_connections, mock_secret_manager
):
    """Test AIClient falls back to the first available connection when initializing with a non-existent connection_id."""
    client = AIClient(
        ai_config=mock_ai_config_multiple_connections,
        secrets=mock_secret_manager,
        connection_id="non_existent_connection",
    )
    first_connection_id = list(mock_ai_config_multiple_connections.connections.keys())[0]
    assert client.connection_id == first_connection_id
    assert client.connection_id in mock_ai_config_multiple_connections.connections


def test_aiclient_no_connections_configured():
    """Test AIClient raises AIConfigurationError if no connections are configured."""
    ai_config_no_providers = AIConfig(connections={})
    with pytest.raises(AIConfigurationError, match="No AI connections configured."):
        AIClient(
            ai_config=ai_config_no_providers,
            secrets=MagicMock(spec=SecretManager),
        )
