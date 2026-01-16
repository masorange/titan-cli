"""
Client for fetching and managing the Titan Plugin Marketplace registry.

Handles dynamic discovery of plugins from GitHub marketplace repository,
with local caching and version compatibility validation.
"""

import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from packaging import version as pkg_version
from pydantic import ValidationError

from .marketplace_models import PluginInfo, MarketplaceRegistry
from ..errors import TitanError


# Configuration
MARKETPLACE_REPO_URL = "https://github.com/masmovil/titan-marketplace"
MARKETPLACE_REGISTRY_RAW_URL = (
    "https://raw.githubusercontent.com/masmovil/titan-marketplace/main/registry.json"
)
MARKETPLACE_CACHE_DIR = Path.home() / ".titan" / ".cache"
MARKETPLACE_CACHE_FILE = MARKETPLACE_CACHE_DIR / "registry.json"
MARKETPLACE_CACHE_TTL = 3600  # 1 hour in seconds


class MarketplaceClientError(TitanError):
    """Error fetching from marketplace"""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(self.message)


class MarketplaceClient:
    """Client for interacting with the Titan Plugin Marketplace"""

    def __init__(self, cache_dir: Optional[Path] = None, cache_ttl: int = MARKETPLACE_CACHE_TTL):
        """
        Initialize marketplace client.

        Args:
            cache_dir: Directory for caching registry (defaults to ~/.titan/.cache)
            cache_ttl: Cache time-to-live in seconds (defaults to 1 hour)
        """
        self.cache_dir = cache_dir or MARKETPLACE_CACHE_DIR
        self.cache_ttl = cache_ttl
        self.cache_file = self.cache_dir / "registry.json"
        self._registry: Optional[MarketplaceRegistry] = None

    def fetch_registry(self, force_refresh: bool = False) -> MarketplaceRegistry:
        """
        Fetch the marketplace registry from GitHub.

        Attempts to use cache first, then falls back to remote fetch.
        If remote fetch fails, uses stale cache as last resort.

        Args:
            force_refresh: Skip cache and fetch from remote

        Returns:
            MarketplaceRegistry object (may be empty if all methods fail)

        Raises:
            MarketplaceClientError: If validation fails on valid registry data
        """
        # Try fresh cache first (unless force_refresh)
        if not force_refresh:
            cached = self._try_load_cache()
            if cached is not None:
                self._registry = cached
                return cached

        # Try remote fetch
        try:
            registry_data = self._fetch_from_github()
            self._registry = MarketplaceRegistry(**registry_data)
            self._save_cache(registry_data)
            return self._registry
        except MarketplaceClientError:
            # Remote fetch failed - try stale cache as fallback
            stale_cache = self._try_load_cache(ignore_ttl=True)
            if stale_cache is not None:
                self._registry = stale_cache
                return stale_cache
            raise
        except ValidationError as e:
            raise MarketplaceClientError(
                f"Invalid registry format from marketplace: {e}",
                original_exception=e
            )
        except Exception as e:
            # Unknown error - try stale cache as fallback
            stale_cache = self._try_load_cache(ignore_ttl=True)
            if stale_cache is not None:
                self._registry = stale_cache
                return stale_cache
            raise MarketplaceClientError(
                f"Failed to fetch marketplace registry: {e}",
                original_exception=e
            )

    def get_available_plugins(self, force_refresh: bool = False) -> List[PluginInfo]:
        """
        Get list of available plugins from marketplace.

        Args:
            force_refresh: Force fresh fetch from remote

        Returns:
            List of PluginInfo objects
        """
        try:
            registry = self.fetch_registry(force_refresh=force_refresh)
            return list(registry.plugins.values())
        except MarketplaceClientError:
            # Return empty list on error instead of failing
            return []

    def get_plugin_info(self, plugin_id: str, force_refresh: bool = False) -> Optional[PluginInfo]:
        """
        Get specific plugin information.

        Args:
            plugin_id: Plugin ID (e.g., 'git', 'github')
            force_refresh: Force fresh fetch from remote

        Returns:
            PluginInfo if found, None otherwise
        """
        try:
            registry = self.fetch_registry(force_refresh=force_refresh)
            return registry.plugins.get(plugin_id)
        except MarketplaceClientError:
            return None

    def check_compatibility(
        self, plugin_info: PluginInfo, titan_version: str
    ) -> bool:
        """
        Check if plugin is compatible with given Titan version.

        Args:
            plugin_info: Plugin metadata
            titan_version: Titan CLI version (e.g., '1.0.0')

        Returns:
            True if compatible, False otherwise
        """
        try:
            current = pkg_version.parse(titan_version)
            min_required = pkg_version.parse(plugin_info.min_titan_version)

            # Check minimum version
            if current < min_required:
                return False

            # Check maximum version if specified
            if plugin_info.max_titan_version:
                max_allowed = pkg_version.parse(plugin_info.max_titan_version)
                if current > max_allowed:
                    return False

            return True
        except Exception:
            # If version parsing fails, assume incompatible
            return False

    def check_dependencies(
        self,
        plugin_id: str,
        available_plugins: Optional[List[PluginInfo]] = None
    ) -> Dict[str, Any]:
        """
        Check if all dependencies of a plugin are available.

        Args:
            plugin_id: Plugin ID to check
            available_plugins: List of available plugins (auto-fetches if None)

        Returns:
            Dict with keys:
            - 'satisfied': bool - True if all dependencies are available
            - 'missing': list[str] - Missing plugin IDs
            - 'plugin_info': PluginInfo - Info about the plugin
        """
        if available_plugins is None:
            available_plugins = self.get_available_plugins()

        available_ids = {p.id for p in available_plugins}
        plugin_info = None

        # Find the plugin
        for p in available_plugins:
            if p.id == plugin_id:
                plugin_info = p
                break

        if plugin_info is None:
            return {
                "satisfied": False,
                "missing": [plugin_id],
                "plugin_info": None
            }

        # Check dependencies
        missing = []
        for dep_id in plugin_info.dependencies:
            if dep_id not in available_ids:
                missing.append(dep_id)

        return {
            "satisfied": len(missing) == 0,
            "missing": missing,
            "plugin_info": plugin_info
        }

    # Private methods

    def _fetch_from_github(self) -> Dict[str, Any]:
        """
        Fetch registry.json from GitHub marketplace repository.

        Returns:
            Parsed JSON registry data

        Raises:
            Exception: Network or parsing errors
        """
        try:
            response = requests.get(
                MARKETPLACE_REGISTRY_RAW_URL,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise MarketplaceClientError(
                f"Failed to fetch from {MARKETPLACE_REGISTRY_RAW_URL}: {e}",
                original_exception=e
            )
        except json.JSONDecodeError as e:
            raise MarketplaceClientError(
                f"Invalid JSON in marketplace registry: {e}",
                original_exception=e
            )

    def _try_load_cache(self, ignore_ttl: bool = False) -> Optional[MarketplaceRegistry]:
        """
        Try to load registry from local cache.

        Args:
            ignore_ttl: If True, load cache even if expired (stale cache fallback)

        Returns:
            MarketplaceRegistry if cache exists and is valid, None otherwise
        """
        if not self.cache_file.exists():
            return None

        try:
            # Check cache age (unless ignore_ttl)
            if not ignore_ttl:
                cache_age = datetime.now().timestamp() - self.cache_file.stat().st_mtime
                if cache_age > self.cache_ttl:
                    return None

            # Load and validate cache
            with open(self.cache_file) as f:
                data = json.load(f)

            return MarketplaceRegistry(**data)
        except Exception:
            # If anything fails, return None (will retry remote fetch)
            return None

    def _save_cache(self, registry_data: Dict[str, Any]) -> None:
        """
        Save registry data to local cache.

        Args:
            registry_data: Registry dictionary to cache
        """
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(registry_data, f, indent=2)
        except Exception:
            # Silently fail - cache is optional
            pass
