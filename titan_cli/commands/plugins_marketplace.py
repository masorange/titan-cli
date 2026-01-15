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

    text.info(msg.Plugins.INSTALLING_PLUGIN.format(name=name))
    text.line()

    try:
        # Get current project path from config
        config = TitanConfig()
        plugins_path = config.active_project_path if config.active_project_path else config.project_root

        # Initialize downloader and validator with project-specific plugin directory
        downloader = PluginDownloader(plugins_dir=plugins_path / ".titan" / "plugins")
        validator = PluginValidator()

        # Fetch plugin info
        text.body(msg.Plugins.INSTALL_FETCHING_INFO)
        plugin_info = downloader.get_plugin_info(name)

        # Display plugin info
        display_name = plugin_info.get("display_name", name)
        description = plugin_info.get("description", "No description")
        verified = plugin_info.get("verified", False)

        text.styled_text(
            ("Plugin: ", "bold"),
            (display_name, "cyan"),
            (" ", "default"),
            (msg.Plugins.PLUGIN_VERIFIED if verified else msg.Plugins.PLUGIN_COMMUNITY, "green" if verified else "yellow")
        )
        text.body(description, style="dim")
        text.line()

        # Check dependencies
        dependencies = plugin_info.get("dependencies", [])
        if dependencies:
            text.body(msg.Plugins.DEPENDENCIES_LABEL.format(dependencies=', '.join(dependencies)), style="dim")

            # Validate dependencies are installed
            installed = config.registry.list_installed()
            missing = [dep for dep in dependencies if dep not in installed]

            if missing:
                text.error(msg.Plugins.DEPENDENCIES_MISSING.format(missing=', '.join(missing)))
                text.body(msg.Plugins.DEPENDENCIES_INSTALL_FIRST)
                for dep in missing:
                    text.body(msg.Plugins.DEPENDENCY_INSTALL_CMD.format(dep=dep))
                raise typer.Exit(1)

        # Download and install
        text.body(msg.Plugins.INSTALL_DOWNLOADING)
        install_path = downloader.install_plugin(name, version, force)

        # Validate plugin
        text.body(msg.Plugins.INSTALL_VALIDATING)
        metadata = validator.validate_plugin(install_path)

        # Configure plugin if schema is present
        if 'configSchema' in metadata:
            text.line()
            text.info(msg.Plugins.CONFIG_REQUIRED)
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
                    text.success(msg.Plugins.CONFIG_SUCCESS)

            except KeyboardInterrupt:
                text.line()
                text.warning(msg.Plugins.CONFIG_SKIPPED)
                text.body(msg.Plugins.CONFIG_CMD_HINT.format(name=name), style="dim")
            except Exception as e:
                text.line()
                text.error(msg.Plugins.CONFIG_ERROR.format(error=e))
                text.warning(msg.Plugins.CONFIG_INSTALL_BUT_NOT_CONFIGURED)
                text.body(msg.Plugins.CONFIG_CMD_HINT.format(name=name), style="dim")

        # Success
        text.line()
        text.success(msg.Plugins.INSTALL_SUCCESS.format(display_name=display_name))
        text.body(msg.Plugins.INSTALL_LOCATION.format(path=install_path), style="dim")
        text.line()
        text.body(msg.Plugins.INSTALL_NEXT_LOAD)

    except PluginDownloadError as e:
        text.line()
        text.error(msg.Plugins.DOWNLOAD_FAILED.format(error=e))
        panel.print(str(e), panel_type="error", title=msg.Plugins.ERROR_DOWNLOAD)
        raise typer.Exit(1)

    except PluginInstallError as e:
        text.line()
        text.error(msg.Plugins.INSTALL_FAILED.format(error=e))
        panel.print(str(e), panel_type="error", title=msg.Plugins.ERROR_INSTALL)
        raise typer.Exit(1)

    except PluginValidationError as e:
        text.line()
        text.error(msg.Plugins.VALIDATION_FAILED.format(error=e))
        panel.print(str(e), panel_type="error", title=msg.Plugins.ERROR_VALIDATION)
        raise typer.Exit(1)

    except Exception as e:
        text.line()
        text.error(msg.Plugins.UNEXPECTED_ERROR.format(error=e))
        panel.print(str(e), panel_type="error", title=msg.Plugins.ERROR_GENERIC)
        raise typer.Exit(1)


def uninstall_plugin_from_marketplace(name: str) -> None:
    """
    Uninstall plugin from local plugins directory.

    Args:
        name: Plugin name
    """
    text = TextRenderer()
    panel = PanelRenderer()

    text.info(msg.Plugins.UNINSTALLING_PLUGIN.format(name=name))
    text.line()

    try:
        # Get current project path from config
        config = TitanConfig()
        plugins_path = config.active_project_path if config.active_project_path else config.project_root

        # Initialize downloader with project-specific plugin directory
        downloader = PluginDownloader(plugins_dir=plugins_path / ".titan" / "plugins")

        # Check if installed
        installed = downloader.list_installed()
        if name not in installed:
            text.warning(msg.Plugins.UNINSTALL_NOT_INSTALLED.format(name=name))
            raise typer.Exit(1)

        # Uninstall
        downloader.uninstall_plugin(name)

        # Success
        text.success(msg.Plugins.UNINSTALL_SUCCESS.format(name=name))
        text.body(msg.Plugins.UNINSTALL_NEXT_LOAD)

    except PluginInstallError as e:
        text.line()
        text.error(msg.Plugins.UNINSTALL_FAILED.format(error=e))
        panel.print(str(e), panel_type="error", title=msg.Plugins.ERROR_UNINSTALL)
        raise typer.Exit(1)

    except Exception as e:
        text.line()
        text.error(msg.Plugins.UNEXPECTED_ERROR.format(error=e))
        panel.print(str(e), panel_type="error", title=msg.Plugins.ERROR_GENERIC)
        raise typer.Exit(1)


def discover_plugins() -> None:
    """Browse plugin marketplace with interactive selection and installation."""
    text = TextRenderer()
    panel = PanelRenderer()
    prompts = PromptsRenderer()

    text.title(msg.Plugins.MARKETPLACE_TITLE)
    text.line()

    try:
        # Get current project path from config
        config = TitanConfig()
        plugins_path = config.active_project_path if config.active_project_path else config.project_root

        # Initialize downloader with project-specific plugin directory
        downloader = PluginDownloader(plugins_dir=plugins_path / ".titan" / "plugins")

        # Fetch registry
        text.body(msg.Plugins.MARKETPLACE_FETCHING_REGISTRY, style="dim")
        registry = downloader.fetch_registry()

        if "plugins" not in registry:
            text.error(msg.Plugins.MARKETPLACE_INVALID_REGISTRY)
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
            status_badge = msg.Plugins.PLUGIN_ALREADY_INSTALLED if is_installed else ""
            verified_badge = "⭐" if verified else ""

            label = f"{display_name} (v{version})"
            if verified_badge:
                label = f"{verified_badge} {label}"
            if status_badge:
                label = f"{label} {status_badge}"

            item = MenuItem(
                label=label,
                description=description,
                action=name
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
            text.warning(msg.Plugins.MARKETPLACE_NO_PLUGINS)
            return

        # Show interactive menu
        text.line()
        menu = Menu(
            title=msg.Plugins.MARKETPLACE_SELECT_PROMPT,
            emoji="📦",
            categories=categories
        )

        selected = prompts.ask_menu(menu, allow_quit=True)

        if not selected:
            text.line()
            text.body(msg.Plugins.MARKETPLACE_CLOSED, style="dim")
            return

        # Install selected plugin
        plugin_name = selected.action
        text.line()

        # Check if already installed
        if plugin_name in installed:
            text.warning(msg.Plugins.REINSTALL_ALREADY_INSTALLED.format(name=plugin_name))
            if prompts.ask_confirm(question=msg.Plugins.REINSTALL_CONFIRM):
                install_plugin_from_marketplace(plugin_name, force=True)
            return

        # Install new plugin (configuration wizard runs automatically during installation)
        install_plugin_from_marketplace(plugin_name)

    except PluginDownloadError as e:
        text.line()
        text.error(msg.Plugins.MARKETPLACE_FETCH_ERROR.format(error=e))
        panel.print(str(e), panel_type="error", title=msg.Plugins.ERROR_DOWNLOAD)
        raise typer.Exit(1)

    except Exception as e:
        text.line()
        text.error(msg.Plugins.UNEXPECTED_ERROR.format(error=e))
        panel.print(str(e), panel_type="error", title=msg.Plugins.ERROR_GENERIC)
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
        text.info(msg.Plugins.UPDATING_ALL_PLUGINS)

        # Get current project path from config
        config = TitanConfig()
        plugins_path = config.active_project_path if config.active_project_path else config.project_root

        # Initialize downloader with project-specific plugin directory
        downloader = PluginDownloader(plugins_dir=plugins_path / ".titan" / "plugins")
        installed = downloader.list_installed()

        if not installed:
            text.warning(msg.Plugins.UPDATE_NO_PLUGINS)
            return

        for plugin_name in installed:
            text.line()
            text.body(msg.Plugins.UPDATE_CHECKING.format(name=plugin_name))
            install_plugin_from_marketplace(plugin_name, force=True)

    else:
        text.info(msg.Plugins.UPDATING_PLUGIN.format(name=name))
        install_plugin_from_marketplace(name, force=True)
