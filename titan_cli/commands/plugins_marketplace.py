"""
Plugin marketplace commands for discovering and installing plugins from GitHub.
"""

import typer
from typing import Optional
from titan_cli.core.plugins.plugin_downloader import PluginDownloader
from titan_cli.core.plugins.plugin_validator import PluginValidator
from titan_cli.core.plugins.config_schema_renderer import ConfigSchemaRenderer
from titan_cli.core.plugins.exceptions import PluginDownloadError, PluginInstallError, PluginValidationError
from titan_cli.core.config import TitanConfig
from titan_cli.ui.components.typography import TextRenderer
from titan_cli.ui.components.panel import PanelRenderer
from titan_cli.ui.components.table import TableRenderer
from titan_cli.ui.views.prompts import PromptsRenderer
from titan_cli.ui.views.menu_components import Menu, MenuItem, MenuCategory
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
        # Get current project path from config
        config = TitanConfig()
        plugins_path = config._active_project_path if config._active_project_path else config._project_root

        # Initialize downloader and validator with project-specific plugin directory
        downloader = PluginDownloader(plugins_dir=plugins_path / ".titan" / "plugins")
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

        # Configure plugin if schema is present
        if 'configSchema' in metadata:
            text.line()
            text.info("📝 Plugin requires configuration")
            text.line()

            try:
                schema_renderer = ConfigSchemaRenderer()
                plugin_config = schema_renderer.render_config_wizard(
                    schema=metadata['configSchema'],
                    plugin_name=name
                )

                # Save non-secret config to titan config
                if plugin_config:
                    config.set_plugin_config(name, plugin_config)
                    text.line()
                    text.success("Configuration saved successfully!")

            except KeyboardInterrupt:
                text.line()
                text.warning("Configuration skipped - you can configure later with:")
                text.body(f"  titan plugins configure {name}", style="dim")
            except Exception as e:
                text.line()
                text.error(f"Configuration error: {e}")
                text.warning("Plugin installed but not configured")
                text.body(f"  titan plugins configure {name}", style="dim")

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
        # Get current project path from config
        config = TitanConfig()
        plugins_path = config._active_project_path if config._active_project_path else config._project_root

        # Initialize downloader with project-specific plugin directory
        downloader = PluginDownloader(plugins_dir=plugins_path / ".titan" / "plugins")

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
    """Browse plugin marketplace with interactive selection and installation."""
    text = TextRenderer()
    panel = PanelRenderer()
    prompts = PromptsRenderer()

    text.title("📦 Titan Plugin Marketplace")
    text.line()

    try:
        # Get current project path from config
        config = TitanConfig()
        plugins_path = config._active_project_path if config._active_project_path else config._project_root

        # Initialize downloader with project-specific plugin directory
        downloader = PluginDownloader(plugins_dir=plugins_path / ".titan" / "plugins")

        # Fetch registry
        text.body("Fetching plugin registry from GitHub...", style="dim")
        registry = downloader.fetch_registry()

        if "plugins" not in registry:
            text.error("Invalid registry format")
            raise typer.Exit(1)

        plugins = registry["plugins"]
        installed = downloader.list_installed()

        # Group by category
        official_items = []
        community_items = []

        for name, info in plugins.items():
            category = info.get("category", "community")
            is_installed = name in installed

            display_name = info.get("display_name", name)
            version = info.get("latest_version", "unknown")
            description = info.get("description", "")
            verified = info.get("verified", False)

            # Build label with status indicators
            status_badge = "✅ Installed" if is_installed else ""
            verified_badge = "⭐" if verified else ""

            label = f"{display_name} (v{version})"
            if verified_badge:
                label = f"{verified_badge} {label}"
            if status_badge:
                label = f"{label} {status_badge}"

            item = MenuItem(
                label=label,
                description=description,
                value=name
            )

            if category == "official":
                official_items.append(item)
            else:
                community_items.append(item)

        # Build menu categories
        categories = []
        if official_items:
            categories.append(
                MenuCategory(
                    name="Official Plugins",
                    emoji="⭐",
                    items=official_items
                )
            )
        if community_items:
            categories.append(
                MenuCategory(
                    name="Community Plugins",
                    emoji="👥",
                    items=community_items
                )
            )

        if not categories:
            text.warning("No plugins available in marketplace")
            return

        # Show interactive menu
        text.line()
        menu = Menu(
            title="Select a plugin to install (or 'q' to quit)",
            emoji="📦",
            categories=categories
        )

        selected = prompts.ask_menu(menu, allow_quit=True)

        if not selected:
            text.line()
            text.body("Marketplace closed", style="dim")
            return

        # Install selected plugin
        plugin_name = selected.value
        text.line()

        # Check if already installed
        if plugin_name in installed:
            text.warning(f"Plugin '{plugin_name}' is already installed")
            if prompts.ask_confirm("Reinstall?"):
                install_plugin_from_marketplace(plugin_name, force=True)
            return

        # Install new plugin
        install_plugin_from_marketplace(plugin_name)

        # Ask about configuration
        text.line()
        if prompts.ask_confirm("Configure plugin now?"):
            text.info("Opening plugin configuration...")
            # TODO: Trigger configuration wizard
            # For now, just show hint
            text.body("Run: titan config edit", style="dim")

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

        # Get current project path from config
        config = TitanConfig()
        plugins_path = config._active_project_path if config._active_project_path else config._project_root

        # Initialize downloader with project-specific plugin directory
        downloader = PluginDownloader(plugins_dir=plugins_path / ".titan" / "plugins")
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
