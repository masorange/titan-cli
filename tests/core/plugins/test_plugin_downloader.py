"""
Tests for PluginDownloader module.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from titan_cli.core.plugins.plugin_downloader import PluginDownloader
from titan_cli.core.plugins.exceptions import (
    PluginDownloadError,
    PluginInstallError
)


@pytest.fixture
def temp_plugins_dir(tmp_path):
    """Create temporary plugins directory."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True)
    return plugins_dir


@pytest.fixture
def downloader(temp_plugins_dir):
    """Create PluginDownloader with temporary directory."""
    return PluginDownloader(plugins_dir=temp_plugins_dir)


@pytest.fixture
def sample_registry():
    """Sample plugin registry data."""
    return {
        "version": "1.0.0",
        "plugins": {
            "git": {
                "display_name": "Git Plugin",
                "description": "Git operations client",
                "category": "official",
                "verified": True,
                "latest_version": "1.0.0",
                "source": "plugins/titan-plugin-git",
                "dependencies": [],
                "python_dependencies": ["gitpython>=3.1.0"]
            },
            "github": {
                "display_name": "GitHub Plugin",
                "description": "GitHub integration",
                "category": "official",
                "verified": True,
                "latest_version": "1.0.0",
                "source": "plugins/titan-plugin-github",
                "dependencies": ["git"],
                "python_dependencies": ["PyGithub>=2.0.0"]
            }
        }
    }


class TestPluginDownloader:
    """Tests for PluginDownloader class."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        downloader = PluginDownloader()
        assert downloader.plugins_dir == Path.home() / ".titan" / "plugins"
        assert downloader.registry_url == downloader.REGISTRY_URL

    def test_init_with_custom_paths(self, temp_plugins_dir):
        """Test initialization with custom paths."""
        custom_url = "https://example.com/registry.json"
        downloader = PluginDownloader(registry_url=custom_url, plugins_dir=temp_plugins_dir)

        assert downloader.plugins_dir == temp_plugins_dir
        assert downloader.registry_url == custom_url

    @patch("titan_cli.core.plugins.plugin_downloader.urlopen")
    def test_fetch_registry_success(self, mock_urlopen, downloader, sample_registry):
        """Test successful registry fetch."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(sample_registry).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        registry = downloader.fetch_registry()

        assert registry == sample_registry
        assert "plugins" in registry
        assert "git" in registry["plugins"]

    @patch("titan_cli.core.plugins.plugin_downloader.urlopen")
    def test_fetch_registry_cached(self, mock_urlopen, downloader, sample_registry):
        """Test that registry is cached after first fetch."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(sample_registry).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # First call - should hit network
        registry1 = downloader.fetch_registry()
        assert mock_urlopen.call_count == 1

        # Second call - should use cache
        registry2 = downloader.fetch_registry()
        assert mock_urlopen.call_count == 1
        assert registry1 == registry2

    @patch("titan_cli.core.plugins.plugin_downloader.urlopen")
    def test_fetch_registry_force_refresh(self, mock_urlopen, downloader, sample_registry):
        """Test that force_refresh bypasses cache."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(sample_registry).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # First call
        downloader.fetch_registry()
        assert mock_urlopen.call_count == 1

        # Force refresh - should hit network again
        downloader.fetch_registry(force_refresh=True)
        assert mock_urlopen.call_count == 2

    @patch("titan_cli.core.plugins.plugin_downloader.urlopen")
    def test_fetch_registry_network_error(self, mock_urlopen, downloader):
        """Test registry fetch with network error."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network error")

        with pytest.raises(PluginDownloadError) as exc_info:
            downloader.fetch_registry()

        assert "Network error" in str(exc_info.value)

    @patch("titan_cli.core.plugins.plugin_downloader.urlopen")
    def test_get_plugin_info_success(self, mock_urlopen, downloader, sample_registry):
        """Test successful plugin info retrieval."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(sample_registry).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        info = downloader.get_plugin_info("git")

        assert info["display_name"] == "Git Plugin"
        assert info["category"] == "official"
        assert info["verified"] is True

    @patch("titan_cli.core.plugins.plugin_downloader.urlopen")
    def test_get_plugin_info_not_found(self, mock_urlopen, downloader, sample_registry):
        """Test plugin info for non-existent plugin."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(sample_registry).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(PluginDownloadError) as exc_info:
            downloader.get_plugin_info("nonexistent")

        assert "not found in registry" in str(exc_info.value)

    def test_list_installed_empty(self, downloader):
        """Test list_installed with no plugins."""
        installed = downloader.list_installed()
        assert installed == []

    def test_list_installed_with_plugins(self, temp_plugins_dir):
        """Test list_installed with some plugins installed."""
        # Create downloader with existing plugins_dir
        downloader = PluginDownloader(plugins_dir=temp_plugins_dir)

        # Create plugin directories with plugin.json
        git_dir = temp_plugins_dir / "git"
        git_dir.mkdir()
        (git_dir / "plugin.json").write_text('{"name": "git"}')

        github_dir = temp_plugins_dir / "github"
        github_dir.mkdir()
        (github_dir / "plugin.json").write_text('{"name": "github"}')

        # Should be ignored (not a directory)
        (temp_plugins_dir / "not_a_plugin.txt").touch()

        installed = downloader.list_installed()

        assert len(installed) == 2
        assert "git" in installed
        assert "github" in installed

    def test_uninstall_plugin_success(self, downloader, temp_plugins_dir):
        """Test successful plugin uninstallation."""
        # Create installed plugin
        plugin_dir = temp_plugins_dir / "git"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").touch()

        downloader.uninstall_plugin("git")

        assert not plugin_dir.exists()

    def test_uninstall_plugin_not_installed(self, downloader):
        """Test uninstalling plugin that's not installed."""
        with pytest.raises(PluginInstallError) as exc_info:
            downloader.uninstall_plugin("nonexistent")

        assert "not installed" in str(exc_info.value)
