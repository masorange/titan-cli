# tests/core/test_plugin_registry.py
import pytest
from unittest.mock import MagicMock, patch
from typing import List, Optional
from titan_cli.core.plugin_registry import PluginRegistry
from titan_cli.core.errors import PluginLoadError, PluginError
from titan_cli.core.plugin_base import TitanPlugin
from titan_cli.core.config import TitanConfig
from titan_cli.core.secrets import SecretManager


# A proper mock class to represent a loaded plugin
class MockPlugin(TitanPlugin):
    def __init__(self, name: str, dependencies: Optional[List[str]] = None):
        self._name = name
        self._dependencies = dependencies if dependencies is not None else []
        self._initialized = False
        self.received_config = None
        self.received_secrets = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Description for {self._name}"

    @property
    def dependencies(self) -> list[str]:
        return self._dependencies

    def initialize(self, config: TitanConfig, secrets: SecretManager) -> None:
        self._initialized = True
        self.received_config = config
        self.received_secrets = secrets

    def is_available(self) -> bool:
        return True

class MockDependentPlugin(MockPlugin):
    def __init__(self, name: str, dependencies: Optional[List[str]] = None):
        # Default dependency is 'plugin_one' to match the tests
        super().__init__(name, dependencies or ["plugin_one"])


def test_plugin_registry_discovery_success(mocker):
    """
    Test that PluginRegistry successfully discovers and loads plugins.
    """
    mock_ep1 = MagicMock()
    mock_ep1.name = "plugin_one"
    mock_ep1.load.return_value = MockPlugin

    mock_ep2 = MagicMock()
    mock_ep2.name = "plugin_two"
    mock_ep2.load.return_value = MockPlugin

    mocker.patch(
        "titan_cli.core.plugin_registry.entry_points",
        return_value=[mock_ep1, mock_ep2]
    )

    registry = PluginRegistry()
    
    installed_plugins = registry.list_installed()
    assert len(installed_plugins) == 2
    assert "plugin_one" in installed_plugins
    assert "plugin_two" in installed_plugins

    plugin_instance = registry.get_plugin("plugin_one")
    assert isinstance(plugin_instance, MockPlugin)
    assert plugin_instance.name == "plugin_one"


def test_plugin_registry_handles_load_failure(mocker, capsys):
    """
    Test that PluginRegistry gracefully handles a plugin that fails to load or is invalid.
    """
    class InvalidPlugin: # Does not inherit from TitanPlugin
        pass

    mock_ep1 = MagicMock()
    mock_ep1.name = "plugin_good"
    mock_ep1.load.return_value = MockPlugin

    mock_ep_bad_import = MagicMock()
    mock_ep_bad_import.name = "plugin_bad_import"
    mock_ep_bad_import.load.side_effect = ImportError("Something went wrong during import")

    mock_ep_bad_type = MagicMock()
    mock_ep_bad_type.name = "plugin_bad_type"
    mock_ep_bad_type.load.return_value = InvalidPlugin

    mocker.patch(
        "titan_cli.core.plugin_registry.entry_points",
        return_value=[mock_ep1, mock_ep_bad_import, mock_ep_bad_type]
    )

    registry = PluginRegistry()

    installed_plugins = registry.list_installed()
    assert len(installed_plugins) == 1
    assert "plugin_good" in installed_plugins
    assert "plugin_bad_import" not in installed_plugins
    assert "plugin_bad_type" not in installed_plugins

    captured = capsys.readouterr()
    output = captured.err + captured.out
    
    # Check that a warning was printed for the bad plugin
    assert "Warning: Failed to load plugin 'plugin_bad_import': Something went wrong during import" in output
    assert "Warning: Failed to load plugin 'plugin_bad_type': Plugin class must inherit from TitanPlugin" in output


def test_plugin_registry_dependency_resolution(mocker):
    """
    Test that plugins are initialized in correct dependency order.
    """
    mock_ep_p1 = MagicMock()
    mock_ep_p1.name = "plugin_one"
    mock_ep_p1.load.return_value = MockPlugin

    mock_ep_p2 = MagicMock()
    mock_ep_p2.name = "plugin_two"
    mock_ep_p2.load.return_value = MockDependentPlugin # depends on plugin_one

    mocker.patch(
        "titan_cli.core.plugin_registry.entry_points",
        return_value=[mock_ep_p2, mock_ep_p1] # Load dependent first to test sorting
    )

    registry = PluginRegistry()
    mock_config = MagicMock(spec=TitanConfig)
    mock_secrets = MagicMock(spec=SecretManager)

    registry.initialize_plugins(mock_config, mock_secrets)

    plugin_one = registry.get_plugin("plugin_one")
    plugin_two = registry.get_plugin("plugin_two")

    assert plugin_one._initialized
    assert plugin_two._initialized


def test_plugin_registry_unresolved_dependency(mocker):
    """
    Test that PluginRegistry raises an error for unresolved dependencies.
    """
    mock_ep_dep = MagicMock()
    mock_ep_dep.name = "plugin_dependent"
    mock_ep_dep.load.return_value = MockDependentPlugin # depends on non-existent plugin

    mocker.patch(
        "titan_cli.core.plugin_registry.entry_points",
        return_value=[mock_ep_dep]
    )

    registry = PluginRegistry()
    mock_config = MagicMock(spec=TitanConfig)
    mock_secrets = MagicMock(spec=SecretManager)

    # Now expects 'plugin_one' as the missing dependency
    with pytest.raises(PluginError, match="Plugin 'plugin_dependent' has an unresolved dependency: 'plugin_one'"):
        registry.initialize_plugins(mock_config, mock_secrets)


def test_plugin_registry_plugin_initialization_context(mocker):
    """
    Test that config and secrets are passed correctly to plugin initialize method.
    """
    mock_ep = MagicMock()
    mock_ep.name = "test_plugin"
    mock_ep.load.return_value = MockPlugin

    mocker.patch(
        "titan_cli.core.plugin_registry.entry_points",
        return_value=[mock_ep]
    )

    registry = PluginRegistry()
    mock_config = MagicMock(spec=TitanConfig)
    mock_secrets = MagicMock(spec=SecretManager)

    registry.initialize_plugins(mock_config, mock_secrets)

    plugin_instance = registry.get_plugin("test_plugin")
    assert plugin_instance.received_config is mock_config
    assert plugin_instance.received_secrets is mock_secrets

