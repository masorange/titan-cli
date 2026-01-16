"""
Tests for MarketplaceClient and marketplace integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import requests

from titan_cli.core.plugins.marketplace_client import (
    MarketplaceClient,
    MarketplaceClientError
)
from titan_cli.core.plugins.marketplace_models import PluginInfo, MarketplaceRegistry


class TestMarketplaceModels:
    """Test Pydantic models for marketplace data"""

    def test_plugin_info_creation(self):
        """Test creating a valid PluginInfo"""
        plugin = PluginInfo(
            id="git",
            name="Git Plugin",
            package="titan-plugin-git",
            version="1.0.0",
            description="Git operations",
            author="Titan Team",
            min_titan_version="1.0.0"
        )

        assert plugin.id == "git"
        assert plugin.version == "1.0.0"
        assert plugin.min_titan_version == "1.0.0"
        assert plugin.dependencies == []

    def test_plugin_info_with_dependencies(self):
        """Test PluginInfo with dependencies"""
        plugin = PluginInfo(
            id="github",
            name="GitHub Plugin",
            package="titan-plugin-github",
            version="1.0.0",
            description="GitHub integration",
            author="Titan Team",
            dependencies=["git"]
        )

        assert "git" in plugin.dependencies

    def test_marketplace_registry_creation(self):
        """Test creating a complete MarketplaceRegistry"""
        registry = MarketplaceRegistry(
            version="1.0.0",
            last_updated="2026-01-15T10:00:00Z",
            plugins={
                "git": PluginInfo(
                    id="git",
                    name="Git Plugin",
                    package="titan-plugin-git",
                    version="1.0.0",
                    description="Git operations",
                    author="Titan Team"
                )
            }
        )

        assert registry.version == "1.0.0"
        assert "git" in registry.plugins


class TestMarketplaceClient:
    """Test MarketplaceClient functionality"""

    @patch("titan_cli.core.plugins.marketplace_client.requests.get")
    def test_fetch_registry_success(self, mock_get):
        """Test successful registry fetch from GitHub"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "version": "1.0.0",
            "last_updated": "2026-01-15T10:00:00Z",
            "plugins": {
                "git": {
                    "id": "git",
                    "name": "Git Plugin",
                    "package": "titan-plugin-git",
                    "version": "1.0.0",
                    "description": "Git operations",
                    "author": "Titan Team",
                    "min_titan_version": "1.0.0",
                    "dependencies": [],
                    "python_dependencies": [],
                    "keywords": [],
                    "homepage": None,
                    "repository": None
                }
            }
        }
        mock_get.return_value = mock_response

        client = MarketplaceClient()
        registry = client.fetch_registry(force_refresh=True)

        assert registry.version == "1.0.0"
        assert "git" in registry.plugins
        mock_get.assert_called_once()

    @patch("titan_cli.core.plugins.marketplace_client.requests.get")
    def test_fetch_registry_network_error(self, mock_get):
        """Test handling network errors (raises when no stale cache available)"""
        mock_get.side_effect = requests.ConnectionError("Network error")

        # Create client with non-existent cache directory to ensure no stale cache
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MarketplaceClient(cache_dir=Path(tmpdir) / "no_cache")
            with pytest.raises(MarketplaceClientError):
                client.fetch_registry(force_refresh=True)

    @patch("titan_cli.core.plugins.marketplace_client.requests.get")
    def test_fetch_registry_invalid_json(self, mock_get):
        """Test handling invalid JSON response (raises when no stale cache available)"""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_get.return_value = mock_response

        # Create client with non-existent cache directory to ensure no stale cache
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MarketplaceClient(cache_dir=Path(tmpdir) / "no_cache")
            with pytest.raises(MarketplaceClientError):
                client.fetch_registry(force_refresh=True)

    @patch("titan_cli.core.plugins.marketplace_client.requests.get")
    def test_fetch_registry_stale_cache_fallback(self, mock_get):
        """Test using stale cache when remote fetch fails"""
        import tempfile
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"

            # Create client with 1-second TTL for quick expiry
            client = MarketplaceClient(cache_dir=cache_dir, cache_ttl=1)

            # First fetch - succeeds and caches
            mock_response_1 = Mock()
            mock_response_1.json.return_value = {
                "version": "1.0.0",
                "last_updated": "2026-01-15T10:00:00Z",
                "plugins": {
                    "git": {
                        "id": "git",
                        "name": "Git Plugin",
                        "package": "titan-plugin-git",
                        "version": "1.0.0",
                        "description": "Git operations",
                        "author": "Titan Team",
                        "min_titan_version": "1.0.0"
                    }
                }
            }
            mock_get.return_value = mock_response_1
            registry_1 = client.fetch_registry(force_refresh=True)
            assert "git" in registry_1.plugins

            # Wait for cache to expire
            time.sleep(2)

            # Second fetch - network error, should use stale cache
            mock_get.side_effect = requests.ConnectionError("Network error")
            registry_2 = client.fetch_registry(force_refresh=True)

            # Should return stale cache instead of raising
            assert "git" in registry_2.plugins
            assert registry_2.version == "1.0.0"

    @patch("titan_cli.core.plugins.marketplace_client.requests.get")
    def test_get_available_plugins(self, mock_get):
        """Test getting list of available plugins"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "version": "1.0.0",
            "last_updated": "2026-01-15T10:00:00Z",
            "plugins": {
                "git": {
                    "id": "git",
                    "name": "Git Plugin",
                    "package": "titan-plugin-git",
                    "version": "1.0.0",
                    "description": "Git operations",
                    "author": "Titan Team",
                    "min_titan_version": "1.0.0",
                    "dependencies": [],
                    "python_dependencies": [],
                    "keywords": [],
                    "homepage": None,
                    "repository": None
                }
            }
        }
        mock_get.return_value = mock_response

        client = MarketplaceClient()
        plugins = client.get_available_plugins(force_refresh=True)

        assert len(plugins) == 1
        assert plugins[0].id == "git"

    @patch("titan_cli.core.plugins.marketplace_client.requests.get")
    def test_get_specific_plugin(self, mock_get):
        """Test getting specific plugin info"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "version": "1.0.0",
            "last_updated": "2026-01-15T10:00:00Z",
            "plugins": {
                "git": {
                    "id": "git",
                    "name": "Git Plugin",
                    "package": "titan-plugin-git",
                    "version": "1.0.0",
                    "description": "Git operations",
                    "author": "Titan Team",
                    "min_titan_version": "1.0.0",
                    "dependencies": [],
                    "python_dependencies": [],
                    "keywords": [],
                    "homepage": None,
                    "repository": None
                }
            }
        }
        mock_get.return_value = mock_response

        client = MarketplaceClient()
        plugin = client.get_plugin_info("git", force_refresh=True)

        assert plugin is not None
        assert plugin.id == "git"

    def test_check_compatibility_compatible(self):
        """Test compatibility check for compatible plugin"""
        plugin = PluginInfo(
            id="git",
            name="Git Plugin",
            package="titan-plugin-git",
            version="1.0.0",
            description="Git operations",
            author="Titan Team",
            min_titan_version="1.0.0"
        )

        client = MarketplaceClient()
        assert client.check_compatibility(plugin, "1.0.0") is True
        assert client.check_compatibility(plugin, "1.5.0") is True
        assert client.check_compatibility(plugin, "2.0.0") is True

    def test_check_compatibility_not_compatible(self):
        """Test compatibility check for incompatible plugin"""
        plugin = PluginInfo(
            id="git",
            name="Git Plugin",
            package="titan-plugin-git",
            version="1.0.0",
            description="Git operations",
            author="Titan Team",
            min_titan_version="2.0.0"
        )

        client = MarketplaceClient()
        assert client.check_compatibility(plugin, "1.0.0") is False
        assert client.check_compatibility(plugin, "1.5.0") is False

    def test_check_compatibility_with_max_version(self):
        """Test compatibility check with max version constraint"""
        plugin = PluginInfo(
            id="git",
            name="Git Plugin",
            package="titan-plugin-git",
            version="1.0.0",
            description="Git operations",
            author="Titan Team",
            min_titan_version="1.0.0",
            max_titan_version="2.0.0"
        )

        client = MarketplaceClient()
        assert client.check_compatibility(plugin, "1.0.0") is True
        assert client.check_compatibility(plugin, "1.5.0") is True
        assert client.check_compatibility(plugin, "2.0.0") is False
        assert client.check_compatibility(plugin, "2.1.0") is False

    def test_check_dependencies_all_met(self):
        """Test dependency check when all are available"""
        plugins = [
            PluginInfo(
                id="git",
                name="Git Plugin",
                package="titan-plugin-git",
                version="1.0.0",
                description="Git operations",
                author="Titan Team"
            ),
            PluginInfo(
                id="github",
                name="GitHub Plugin",
                package="titan-plugin-github",
                version="1.0.0",
                description="GitHub integration",
                author="Titan Team",
                dependencies=["git"]
            )
        ]

        client = MarketplaceClient()
        result = client.check_dependencies("github", available_plugins=plugins)

        assert result["satisfied"] is True
        assert result["missing"] == []

    def test_check_dependencies_missing(self):
        """Test dependency check when dependencies are missing"""
        plugins = [
            PluginInfo(
                id="github",
                name="GitHub Plugin",
                package="titan-plugin-github",
                version="1.0.0",
                description="GitHub integration",
                author="Titan Team",
                dependencies=["git"]  # git not available
            )
        ]

        client = MarketplaceClient()
        result = client.check_dependencies("github", available_plugins=plugins)

        assert result["satisfied"] is False
        assert "git" in result["missing"]

    @patch("titan_cli.core.plugins.marketplace_client.requests.get")
    def test_cache_registry_locally(self, mock_get, tmp_path):
        """Test that registry is cached locally"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "version": "1.0.0",
            "last_updated": "2026-01-15T10:00:00Z",
            "plugins": {}
        }
        mock_get.return_value = mock_response

        client = MarketplaceClient(cache_dir=tmp_path)

        # First fetch
        registry1 = client.fetch_registry(force_refresh=True)

        # Cache file should exist
        cache_file = tmp_path / "registry.json"
        assert cache_file.exists()

        # Second fetch without force_refresh should use cache
        client.fetch_registry(force_refresh=False)

        # Network call should have been made once (for first fetch)
        assert mock_get.call_count == 1
