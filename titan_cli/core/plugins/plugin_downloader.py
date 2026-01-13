"""
Plugin downloader for GitHub-based plugin marketplace.

Downloads and installs plugins from the Titan plugin registry on GitHub.
"""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from .exceptions import PluginDownloadError, PluginInstallError


class PluginDownloader:
    """
    Downloads and installs plugins from GitHub marketplace.

    Registry URL: https://raw.githubusercontent.com/masmovil/titan-cli/master/registry.json
    """

    # GitHub repository configuration
    REGISTRY_REPO = "masmovil/titan-cli"
    REGISTRY_BRANCH = "feat/plugin-marketplace-system"  # TODO: Change to "master" after merge
    REGISTRY_URL = f"https://raw.githubusercontent.com/{REGISTRY_REPO}/{REGISTRY_BRANCH}/registry.json"

    def __init__(self, registry_url: Optional[str] = None, plugins_dir: Optional[Path] = None):
        """
        Initialize plugin downloader.

        Args:
            registry_url: Custom registry URL (defaults to official)
            plugins_dir: Custom plugins directory (defaults to .titan/plugins in current dir)
        """
        self.registry_url = registry_url or self.REGISTRY_URL

        # Use project-level plugin directory by default
        if plugins_dir is not None:
            self.plugins_dir = plugins_dir
        else:
            # Default to current working directory's .titan/plugins
            self.plugins_dir = Path.cwd() / ".titan" / "plugins"

        self._registry_cache: Optional[Dict[str, Any]] = None

    def fetch_registry(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch plugin registry from GitHub.

        Args:
            force_refresh: Force refresh cache

        Returns:
            Registry dictionary with plugin metadata

        Raises:
            PluginDownloadError: If registry cannot be fetched
        """
        if self._registry_cache and not force_refresh:
            return self._registry_cache

        try:
            with urlopen(self.registry_url, timeout=10) as response:
                if response.status != 200:
                    raise PluginDownloadError(
                        f"Failed to fetch registry: HTTP {response.status}"
                    )

                content = response.read().decode('utf-8')
                self._registry_cache = json.loads(content)
                return self._registry_cache

        except HTTPError as e:
            raise PluginDownloadError(
                f"HTTP error fetching registry: {e.code} {e.reason}"
            ) from e
        except URLError as e:
            raise PluginDownloadError(
                f"Network error fetching registry: {e.reason}"
            ) from e
        except json.JSONDecodeError as e:
            raise PluginDownloadError(
                f"Invalid registry JSON: {e}"
            ) from e
        except Exception as e:
            raise PluginDownloadError(
                f"Unexpected error fetching registry: {e}"
            ) from e

    def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get plugin information from registry.

        Args:
            plugin_name: Name of the plugin (e.g., "git", "github")

        Returns:
            Plugin metadata dictionary

        Raises:
            PluginDownloadError: If plugin not found in registry
        """
        registry = self.fetch_registry()

        if "plugins" not in registry:
            raise PluginDownloadError("Invalid registry format: missing 'plugins' key")

        plugins = registry["plugins"]

        if plugin_name not in plugins:
            available = ", ".join(plugins.keys())
            raise PluginDownloadError(
                f"Plugin '{plugin_name}' not found in registry. "
                f"Available plugins: {available}"
            )

        return plugins[plugin_name]

    def download_plugin(
        self,
        plugin_name: str,
        version: Optional[str] = None
    ) -> Path:
        """
        Download plugin from GitHub to temporary directory.

        Args:
            plugin_name: Name of the plugin
            version: Specific version (defaults to latest)

        Returns:
            Path to downloaded plugin directory

        Raises:
            PluginDownloadError: If download fails
        """
        plugin_info = self.get_plugin_info(plugin_name)

        # Determine version
        target_version = version or plugin_info.get("latest_version", "main")

        # Build download URL
        source_path = plugin_info.get("source")
        if not source_path:
            raise PluginDownloadError(
                f"Plugin '{plugin_name}' has no source path in registry"
            )

        # Download entire repository as ZIP
        zip_url = (
            f"https://github.com/{self.REGISTRY_REPO}/archive/refs/heads/{self.REGISTRY_BRANCH}.zip"
        )

        try:
            # Create temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix=f"titan-plugin-{plugin_name}-"))

            # Download ZIP
            zip_path = temp_dir / "repo.zip"
            with urlopen(zip_url, timeout=30) as response:
                if response.status != 200:
                    raise PluginDownloadError(
                        f"Failed to download plugin: HTTP {response.status}"
                    )

                zip_path.write_bytes(response.read())

            # Extract ZIP
            extract_dir = temp_dir / "extracted"
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # Find plugin directory in extracted content
            # Structure: titan-plugins-{branch}/{source_path}
            repo_dir = extract_dir / f"titan-plugins-{self.REGISTRY_BRANCH}"
            plugin_dir = repo_dir / source_path

            if not plugin_dir.exists():
                raise PluginDownloadError(
                    f"Plugin directory not found: {source_path}"
                )

            return plugin_dir

        except HTTPError as e:
            raise PluginDownloadError(
                f"HTTP error downloading plugin: {e.code} {e.reason}"
            ) from e
        except URLError as e:
            raise PluginDownloadError(
                f"Network error downloading plugin: {e.reason}"
            ) from e
        except zipfile.BadZipFile as e:
            raise PluginDownloadError(
                f"Invalid ZIP file: {e}"
            ) from e
        except Exception as e:
            raise PluginDownloadError(
                f"Unexpected error downloading plugin: {e}"
            ) from e

    def install_plugin(
        self,
        plugin_name: str,
        version: Optional[str] = None,
        force: bool = False
    ) -> Path:
        """
        Download and install plugin to local plugins directory.

        Args:
            plugin_name: Name of the plugin
            version: Specific version (defaults to latest)
            force: Force reinstall if already installed

        Returns:
            Path to installed plugin directory

        Raises:
            PluginInstallError: If installation fails
        """
        # Check if already installed
        install_path = self.plugins_dir / plugin_name

        if install_path.exists() and not force:
            raise PluginInstallError(
                f"Plugin '{plugin_name}' is already installed. "
                f"Use force=True to reinstall."
            )

        try:
            # Download plugin
            plugin_dir = self.download_plugin(plugin_name, version)

            # Create plugins directory if needed
            self.plugins_dir.mkdir(parents=True, exist_ok=True)

            # Remove existing installation if force
            if install_path.exists():
                shutil.rmtree(install_path)

            # Copy plugin to install directory
            shutil.copytree(plugin_dir, install_path)

            # Clean up temp directory
            temp_dir = plugin_dir.parent.parent  # temp_dir/extracted/repo_dir
            if temp_dir.exists() and temp_dir.name.startswith("titan-plugin-"):
                shutil.rmtree(temp_dir)

            return install_path

        except PluginDownloadError as e:
            raise PluginInstallError(
                f"Failed to download plugin '{plugin_name}': {e}"
            ) from e
        except Exception as e:
            raise PluginInstallError(
                f"Failed to install plugin '{plugin_name}': {e}"
            ) from e

    def uninstall_plugin(self, plugin_name: str) -> None:
        """
        Uninstall plugin from local plugins directory.

        Args:
            plugin_name: Name of the plugin

        Raises:
            PluginInstallError: If uninstallation fails
        """
        install_path = self.plugins_dir / plugin_name

        if not install_path.exists():
            raise PluginInstallError(
                f"Plugin '{plugin_name}' is not installed"
            )

        try:
            shutil.rmtree(install_path)
        except Exception as e:
            raise PluginInstallError(
                f"Failed to uninstall plugin '{plugin_name}': {e}"
            ) from e

    def list_installed(self) -> list[str]:
        """
        List installed plugins from local directory.

        Returns:
            List of installed plugin names
        """
        if not self.plugins_dir.exists():
            return []

        installed = []
        for item in self.plugins_dir.iterdir():
            if item.is_dir() and (item / "plugin.json").exists():
                installed.append(item.name)

        return sorted(installed)

    def get_installed_version(self, plugin_name: str) -> Optional[str]:
        """
        Get version of installed plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Version string or None if not installed
        """
        install_path = self.plugins_dir / plugin_name / "plugin.json"

        if not install_path.exists():
            return None

        try:
            with open(install_path) as f:
                metadata = json.load(f)
                return metadata.get("version")
        except Exception:
            return None
