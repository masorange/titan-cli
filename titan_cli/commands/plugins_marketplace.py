"""
Plugin marketplace commands for discovering and installing plugins from GitHub.
"""

import typer
from typing import Optional
from titan_cli.core.plugins.plugin_downloader import PluginDownloader
from titan_cli.core.plugins.plugin_validator import PluginValidator
from titan_cli.core.plugins.exceptions import PluginDownloadError, PluginInstallError, PluginValidationError
from titan_cli.core.config import TitanConfig
from titan_cli.ui.components.typography import TextRenderer
from titan_cli.ui.components.panel import PanelRenderer
from titan_cli.ui.components.table import TableRenderer
from titan_cli.messages import msg


def install_plugin_from_marketplace(
    name: str,
    version: Optional[str] = None,
    force: bool = False
) -> None:
    """
    Install plugin from GitHub marketplace.

    Args:
        name: Plugin name (e.g., "git", "github", "jira")
        version: Specific version (defaults to latest)
        force: Force reinstall if already installed
    """
    text = TextRenderer()
    panel = PanelRenderer()

    text.info(f"Installing plugin: {name}")
    text.line()

    try:
        # Initialize downloader and validator
        downloader = PluginDownloader()
        validator = PluginValidator()

        # Fetch plugin info
        text.body("Fetching plugin information from registry...")
        plugin_info = downloader.get_plugin_info(name)

        # Display plugin info
        display_name = plugin_info.get("display_name", name)
        description = plugin_info.get("description", "No description")
        category = plugin_info.get("category", "unknown")
        verified = plugin_info.get("verified", False)

        text.styled_text(
            ("Plugin: ", "bold"),
            (display_name, "cyan"),
            (" ", "default"),
            ("⭐ Verified" if verified else "⚠️  Community", "green" if verified else "yellow")
        )
        text.body(description, style="dim")
        text.line()

        # Check dependencies
        dependencies = plugin_info.get("dependencies", [])
        if dependencies:
            text.body(f"Dependencies: {', '.join(dependencies)}", style="dim")

            # Validate dependencies are installed
            config = TitanConfig()
            installed = config.registry.list_installed()
            missing = [dep for dep in dependencies if dep not in installed]

            if missing:
                text.error(f"Missing dependencies: {', '.join(missing)}")
                text.body("Please install dependencies first:")
                for dep in missing:
                    text.body(f"  titan plugins install {dep}")
                raise typer.Exit(1)

        # Download and install
        text.body("Downloading plugin from GitHub...")
        install_path = downloader.install_plugin(name, version, force)

        # Validate plugin
        text.body("Validating plugin...")
        metadata = validator.validate_plugin(install_path)

        # Success
        text.line()
        text.success(f"✅ Plugin '{display_name}' installed successfully!")
        text.body(f"Location: {install_path}", style="dim")
        text.line()
        text.body("Plugin will be loaded on next 'titan' command")

    except PluginDownloadError as e:
        text.line()
        text.error(f"❌ Download failed: {e}")
        panel.print(str(e), panel_type="error", title="Download Error")
        raise typer.Exit(1)

    except PluginInstallError as e:
        text.line()
        text.error(f"❌ Installation failed: {e}")
        panel.print(str(e), panel_type="error", title="Installation Error")
        raise typer.Exit(1)

    except PluginValidationError as e:
        text.line()
        text.error(f"❌ Validation failed: {e}")
        panel.print(str(e), panel_type="error", title="Validation Error")
        raise typer.Exit(1)

    except Exception as e:
        text.line()
        text.error(f"❌ Unexpected error: {e}")
        panel.print(str(e), panel_type="error", title="Error")
        raise typer.Exit(1)


def uninstall_plugin_from_marketplace(name: str) -> None:
    """
    Uninstall plugin from local plugins directory.

    Args:
        name: Plugin name
    """
    text = TextRenderer()
    panel = PanelRenderer()

    text.info(f"Uninstalling plugin: {name}")
    text.line()

    try:
        downloader = PluginDownloader()

        # Check if installed
        installed = downloader.list_installed()
        if name not in installed:
            text.warning(f"Plugin '{name}' is not installed")
            raise typer.Exit(1)

        # Uninstall
        downloader.uninstall_plugin(name)

        # Success
        text.success(f"✅ Plugin '{name}' uninstalled successfully!")
        text.body("Plugin will be removed on next 'titan' command")

    except PluginInstallError as e:
        text.line()
        text.error(f"❌ Uninstallation failed: {e}")
        panel.print(str(e), panel_type="error", title="Uninstall Error")
        raise typer.Exit(1)

    except Exception as e:
        text.line()
        text.error(f"❌ Unexpected error: {e}")
        panel.print(str(e), panel_type="error", title="Error")
        raise typer.Exit(1)


def discover_plugins() -> None:
    """Browse plugin marketplace and show available plugins."""
    text = TextRenderer()
    panel = PanelRenderer()
    table_renderer = TableRenderer()

    text.title("📦 Titan Plugin Marketplace")
    text.line()

    try:
        downloader = PluginDownloader()
        config = TitanConfig()

        # Fetch registry
        text.body("Fetching plugin registry from GitHub...", style="dim")
        registry = downloader.fetch_registry()

        if "plugins" not in registry:
            text.error("Invalid registry format")
            raise typer.Exit(1)

        plugins = registry["plugins"]
        installed = downloader.list_installed()

        # Group by category
        official = []
        community = []

        for name, info in plugins.items():
            category = info.get("category", "community")
            is_installed = name in installed

            plugin_data = {
                "name": name,
                "display_name": info.get("display_name", name),
                "description": info.get("description", ""),
                "version": info.get("latest_version", "unknown"),
                "verified": info.get("verified", False),
                "installed": is_installed
            }

            if category == "official":
                official.append(plugin_data)
            else:
                community.append(plugin_data)

        # Display official plugins
        if official:
            text.subtitle("Official Plugins")
            text.line()

            for p in official:
                status = "✅ Installed" if p["installed"] else ""
                verified = "⭐ Verified" if p["verified"] else ""

                text.styled_text(
                    (f"{p['display_name']}", "bold cyan"),
                    (f" (v{p['version']})", "dim"),
                    (f" {verified}", "green"),
                    (f" {status}", "green")
                )
                text.body(f"  {p['description']}", style="dim")
                text.line()

        # Display community plugins
        if community:
            text.subtitle("Community Plugins")
            text.line()

            for p in community:
                status = "✅ Installed" if p["installed"] else ""
                verified = "⭐ Verified" if p["verified"] else "⚠️  Community"

                text.styled_text(
                    (f"{p['display_name']}", "bold cyan"),
                    (f" (v{p['version']})", "dim"),
                    (f" {verified}", "yellow"),
                    (f" {status}", "green")
                )
                text.body(f"  {p['description']}", style="dim")
                text.line()

        # Instructions
        text.line()
        text.body("To install a plugin:", style="bold")
        text.body("  titan plugins install <name>")
        text.line()
        text.body("Example:", style="bold")
        text.body("  titan plugins install git")

    except PluginDownloadError as e:
        text.line()
        text.error(f"❌ Failed to fetch marketplace: {e}")
        panel.print(str(e), panel_type="error", title="Marketplace Error")
        raise typer.Exit(1)

    except Exception as e:
        text.line()
        text.error(f"❌ Unexpected error: {e}")
        panel.print(str(e), panel_type="error", title="Error")
        raise typer.Exit(1)


def update_plugin(name: str, all_plugins: bool = False) -> None:
    """
    Update installed plugin to latest version.

    Args:
        name: Plugin name to update
        all_plugins: Update all installed plugins
    """
    text = TextRenderer()

    if all_plugins:
        text.info("Updating all installed plugins...")
        downloader = PluginDownloader()
        installed = downloader.list_installed()

        if not installed:
            text.warning("No plugins installed")
            return

        for plugin_name in installed:
            text.line()
            text.body(f"Updating {plugin_name}...")
            install_plugin_from_marketplace(plugin_name, force=True)

    else:
        text.info(f"Updating plugin: {name}")
        install_plugin_from_marketplace(name, force=True)
