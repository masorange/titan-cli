# plugins/titan-plugin-git/titan_plugin_git/plugin.py
import shutil
from titan_cli.core.plugin_base import TitanPlugin
from titan_cli.core.config import TitanConfig # Needed for type hinting
from titan_cli.core.secrets import SecretManager # Needed for type hinting
from .clients.git_client import GitClient, GitClientError
from .messages import msg # Import the messages module

class GitPlugin(TitanPlugin):
    """
    Titan CLI Plugin for Git operations.
    Provides a GitClient for interacting with the Git CLI.
    """

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return "Provides core Git CLI functionalities."

    @property
    def dependencies(self) -> list[str]:
        return []

    def initialize(self, config: TitanConfig, secrets: SecretManager) -> None:
        """
        Initialize with configuration.
        
        Reads config from:
            config.config.plugins["git"].config
        """
        # Get plugin-specific configuration
        plugin_config = self._get_plugin_config(config)

        # Extract values with defaults
        main_branch = plugin_config.get("main_branch", "main")
        default_remote = plugin_config.get("default_remote", "origin")
        protected_branches = plugin_config.get("protected_branches", ["main"])

        # Initialize client with configuration
        self._client = GitClient(
            main_branch=main_branch,
            default_remote=default_remote,
            protected_branches=protected_branches
        )

    def _get_plugin_config(self, config: TitanConfig) -> dict:
        """
        Extract plugin-specific configuration.
        
        Args:
            config: TitanConfig instance
        
        Returns:
            Plugin config dict (empty if not configured)
        """
        if "git" not in config.config.plugins:
            return {}

        plugin_entry = config.config.plugins["git"]
        return plugin_entry.config if hasattr(plugin_entry, 'config') else {}

    def get_config_schema(self) -> dict:
        """
        Return JSON schema for plugin configuration.
        
        Returns:
            JSON schema dict
        """
        from titan_cli.core.plugins.models import GitPluginConfig
        return GitPluginConfig.model_json_schema()


    def is_available(self) -> bool:
        """
        Checks if the Git CLI is installed and available.
        """
        # Leverage the GitClient's own check
        return shutil.which("git") is not None and hasattr(self, '_client') and self._client is not None

    def get_client(self) -> GitClient:
        """
        Returns the initialized GitClient instance.
        """
        if not hasattr(self, '_client') or self._client is None:
            raise GitClientError(msg.Plugin.git_client_not_available)
        return self._client

    def get_steps(self) -> dict:
        """
        Returns a dictionary of available workflow steps.
        """
        from .steps.status_step import get_git_status_step
        from .steps.commit_step import create_git_commit_step
        return {
            "get_status": get_git_status_step,
            "create_commit": create_git_commit_step,
        }
