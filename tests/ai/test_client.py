import pytest
from unittest.mock import MagicMock

from titan_cli.ai.client import AIClient
from titan_cli.ai.exceptions import AIConfigurationError
from titan_cli.core.models import (
    AIConfig,
    AIConnectionConfig,
    AIConnectionType,
    AIProviderConfig,
)


@pytest.fixture
def mock_ai_config_single_connection():
    """Returns an AIConfig with one connection and it as default."""
    return AIConfig(
        default_connection="test_connection",
        connections={
            "test_connection": AIProviderConfig(
                name="Test Connection",
                connection_type=AIConnectionType.DIRECT_PROVIDER,
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
                connection_type=AIConnectionType.DIRECT_PROVIDER,
                provider="gemini",
                default_model="gemini-pro",
            ),
            "secondary_anthropic": AIProviderConfig(
                name="Secondary Anthropic",
                connection_type=AIConnectionType.DIRECT_PROVIDER,
                provider="anthropic",
                default_model="claude-3",
            ),
        },
    )


@pytest.fixture
def mock_provider_factory():
    """A provider factory stand-in; construction details are not under test here."""
    return MagicMock(return_value=MagicMock())


def test_aiclient_init_specific_connection(
    mock_ai_config_multiple_connections, mock_provider_factory
):
    """Test AIClient initializes with a specific connection_id."""
    client = AIClient(
        ai_config=mock_ai_config_multiple_connections,
        provider_factory=mock_provider_factory,
        connection_id="secondary_anthropic",
    )
    current_connection_cfg = client.ai_config.connections.get(client.connection_id)
    assert current_connection_cfg.name == "Secondary Anthropic"
    assert current_connection_cfg.provider == "anthropic"


def test_aiclient_init_default_connection(
    mock_ai_config_multiple_connections, mock_provider_factory
):
    """Test AIClient initializes with the default connection when no connection_id is given."""
    client = AIClient(
        ai_config=mock_ai_config_multiple_connections,
        provider_factory=mock_provider_factory,
    )
    current_connection_cfg = client.ai_config.connections.get(client.connection_id)
    assert current_connection_cfg.name == "Default Gemini"
    assert current_connection_cfg.provider == "gemini"


def test_aiclient_init_fallback_default_not_exist_fails():
    """
    A default connection that does not exist is reported when something tries to use it,
    not when the config loads - loading must never be what stops Titan from starting.
    """
    ai_config = AIConfig(
        default_connection="non_existent",
        connections={
            "some_connection": AIProviderConfig(
                name="Some Connection",
                connection_type=AIConnectionType.DIRECT_PROVIDER,
                provider="openai",
                default_model="gpt-3.5",
            )
        },
    )

    with pytest.raises(AIConfigurationError):
        AIClient(ai_config, MagicMock())


def test_aiclient_init_invalid_connection_id_is_refused_by_name(
    mock_ai_config_multiple_connections, mock_provider_factory
):
    """
    Asking for a connection that does not exist must say so, not quietly answer with a
    different one - the prompts would go somewhere the user never chose, unnoticed.
    """
    with pytest.raises(AIConfigurationError, match="non_existent_connection"):
        AIClient(
            ai_config=mock_ai_config_multiple_connections,
            provider_factory=mock_provider_factory,
            connection_id="non_existent_connection",
        )


def test_aiclient_no_connections_configured():
    """Test AIClient raises AIConfigurationError if no connections are configured."""
    ai_config_no_connections = AIConfig(connections={})
    with pytest.raises(AIConfigurationError, match="No AI connections configured."):
        AIClient(
            ai_config=ai_config_no_connections,
            provider_factory=MagicMock(),
        )


class TestModelOverride:
    """
    A client may run a connection on a different model without touching stored config.

    This is how a task's pinned model and a session override reach a remote provider.
    The mechanism is deliberately small: `create_ai_provider` already takes the model
    from the connection config it is handed, so a copy carrying another one is the whole
    change - no provider and no `generate()` signature is involved.
    """

    @staticmethod
    def _config():
        return AIConfig(
            default_connection="work",
            connections={
                "work": AIConnectionConfig(
                    name="Work gateway",
                    connection_type="gateway",
                    gateway_backend="openai_compatible",
                    base_url="https://gateway.example/v1",
                    default_model="gpt-5",
                )
            },
        )

    def test_the_override_reaches_the_factory(self):
        seen = {}

        def factory(connection_id, connection_cfg):
            seen["model"] = connection_cfg.default_model
            return object()

        AIClient(self._config(), factory, connection_id="work", model="gpt-5-mini").provider

        assert seen["model"] == "gpt-5-mini"

    def test_without_an_override_the_connections_own_model_is_used(self):
        seen = {}

        def factory(connection_id, connection_cfg):
            seen["model"] = connection_cfg.default_model
            return object()

        AIClient(self._config(), factory, connection_id="work").provider

        assert seen["model"] == "gpt-5"

    def test_the_stored_connection_is_never_mutated(self):
        """The same AIConfig is shared with the rest of the session."""
        config = self._config()

        AIClient(config, lambda cid, cfg: object(), connection_id="work", model="gpt-5-mini").provider

        assert config.connections["work"].default_model == "gpt-5"
