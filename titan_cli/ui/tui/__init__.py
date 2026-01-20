"""
Titan TUI Module

Textual-based Terminal User Interface for Titan CLI.
"""
from .app import TitanApp

__all__ = ["TitanApp"]


def launch_tui():
    """
    Launch the Titan TUI application.

    This is the main entry point for running Titan in TUI mode.

    Flow:
    1. Check if global config exists (~/.titan/config.toml)
       - If NO: Launch global setup wizard
       - If YES: Continue
    2. Check if project config exists (./.titan/config.toml)
       - If NO: Launch project setup wizard
       - If YES: Continue to main menu
    """
    from pathlib import Path
    from titan_cli.core.config import TitanConfig
    from titan_cli.core.plugins.plugin_registry import PluginRegistry
    from .screens import GlobalSetupWizardScreen, ProjectSetupWizardScreen, MainMenuScreen

    # Check if global config exists
    global_config_path = TitanConfig.GLOBAL_CONFIG

    if not global_config_path.exists():
        # First-time setup: Launch global setup wizard
        plugin_registry = PluginRegistry()
        config = TitanConfig(registry=plugin_registry)

        # We'll create a special wrapper screen that handles the wizard flow
        from .screens.base import BaseScreen
        from textual.app import ComposeResult
        from textual.containers import Container

        class WizardFlowScreen(BaseScreen):
            """Temporary screen to manage wizard flow."""

            def __init__(self, config, *args, **kwargs):
                super().__init__(config, title="Setup", show_back=False, *args, **kwargs)

            def compose_content(self) -> ComposeResult:
                # This won't be used, we push wizard immediately
                yield Container()

            def on_mount(self) -> None:
                """Push the global wizard on mount."""
                def on_project_wizard_complete(_=None):
                    """After project wizard completes, show main menu."""
                    # Reload project config without resetting plugins
                    from titan_cli.core.secrets import SecretManager
                    from titan_cli.core.models import TitanConfigModel

                    self.config.project_config_path = Path.cwd() / ".titan" / "config.toml"
                    self.config.project_config = self.config._load_toml(self.config.project_config_path)

                    # Merge configs and update
                    merged = self.config._merge_configs(self.config.global_config, self.config.project_config)
                    self.config.config = TitanConfigModel(**merged)

                    # Update secrets manager to use current project
                    self.config.secrets = SecretManager(project_path=Path.cwd())

                    # Initialize only the configured plugins (without reset)
                    self.config.registry.initialize_plugins(config=self.config, secrets=self.config.secrets)

                    # Pop all screens except the base one, then push main menu
                    # WizardFlowScreen is still there, so we need to pop it too
                    # Stack after project wizard completes: [WizardFlowScreen]
                    # We want: [MainMenuScreen]
                    self.app.pop_screen()  # Remove WizardFlowScreen
                    self.app.push_screen(MainMenuScreen(self.config))

                def on_global_wizard_complete(_=None):
                    """After global wizard completes, check for project config."""
                    # Reload global config
                    self.config.global_config = self.config._load_toml(self.config._global_config_path)

                    # Check if project config exists
                    project_config_path = Path.cwd() / ".titan" / "config.toml"

                    if not project_config_path.exists():
                        # Launch project setup wizard with callback to show main menu
                        self.app.push_screen(
                            ProjectSetupWizardScreen(self.config, Path.cwd()),
                            on_project_wizard_complete
                        )
                    else:
                        # Project is configured, reload configs without resetting plugins
                        from titan_cli.core.secrets import SecretManager
                        from titan_cli.core.models import TitanConfigModel

                        self.config.project_config_path = project_config_path
                        self.config.project_config = self.config._load_toml(self.config.project_config_path)

                        # Merge configs and update
                        merged = self.config._merge_configs(self.config.global_config, self.config.project_config)
                        self.config.config = TitanConfigModel(**merged)

                        # Update secrets manager to use current project
                        self.config.secrets = SecretManager(project_path=Path.cwd())

                        # Initialize plugins with new config
                        self.config.registry.initialize_plugins(config=self.config, secrets=self.config.secrets)

                        # Stack: [WizardFlowScreen]
                        # We want: [MainMenuScreen]
                        self.app.pop_screen()  # Remove WizardFlowScreen
                        self.app.push_screen(MainMenuScreen(self.config))

                # Push global wizard
                self.app.push_screen(GlobalSetupWizardScreen(self.config), on_global_wizard_complete)

        # Create app with the flow screen
        app = TitanApp(config=config, initial_screen=WizardFlowScreen(config))
        app.run()
        return

    # Global config exists, initialize normally
    plugin_registry = PluginRegistry()
    config = TitanConfig(registry=plugin_registry)

    # Check if project config exists in current directory
    project_config_path = Path.cwd() / ".titan" / "config.toml"

    if not project_config_path.exists():
        # Project not configured: Launch project setup wizard
        # Create a wrapper screen similar to global wizard flow
        from .screens.base import BaseScreen
        from textual.app import ComposeResult
        from textual.containers import Container

        class ProjectWizardFlowScreen(BaseScreen):
            """Temporary screen to manage project wizard flow."""

            def __init__(self, config, *args, **kwargs):
                super().__init__(config, title="Project Setup", show_back=False, *args, **kwargs)

            def compose_content(self) -> ComposeResult:
                # This won't be used, we push wizard immediately
                yield Container()

            def on_mount(self) -> None:
                """Push the project wizard on mount."""
                def on_project_wizard_complete(_=None):
                    """After project wizard completes, show main menu."""
                    # Reload project config without resetting plugins
                    from pathlib import Path
                    from titan_cli.core.secrets import SecretManager
                    from titan_cli.core.models import TitanConfigModel

                    self.config.project_config_path = Path.cwd() / ".titan" / "config.toml"
                    self.config.project_config = self.config._load_toml(self.config.project_config_path)

                    # Merge configs and update
                    merged = self.config._merge_configs(self.config.global_config, self.config.project_config)
                    self.config.config = TitanConfigModel(**merged)

                    # Update secrets manager to use current project
                    self.config.secrets = SecretManager(project_path=Path.cwd())

                    # Initialize only the configured plugins (without reset)
                    self.config.registry.initialize_plugins(config=self.config, secrets=self.config.secrets)

                    # Pop this flow screen and show main menu
                    self.app.pop_screen()  # Remove ProjectWizardFlowScreen
                    self.app.push_screen(MainMenuScreen(self.config))

                # Push project wizard
                self.app.push_screen(
                    ProjectSetupWizardScreen(self.config, Path.cwd()),
                    on_project_wizard_complete
                )

        # Create app with the flow screen
        app = TitanApp(config=config, initial_screen=ProjectWizardFlowScreen(config))
        app.run()
        return

    # Both global and project configs exist: Run normally
    app = TitanApp(config=config)
    app.run()
