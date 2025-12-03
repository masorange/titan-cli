"""
Base interface for Titan plugins.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable


class TitanPlugin(ABC):
    """
    Base class for all Titan plugins.
    
    Plugins extend Titan CLI with:
    - Service clients (Git, GitHub, Jira, etc.)
    - Workflow steps (atomic operations)
    
    Example:
        class GitPlugin(TitanPlugin):
            @property
            def name(self) -> str:
                return "git"
            
            def get_client(self):
                return GitClient()
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Plugin unique identifier.
        
        Returns:
            Plugin name (e.g., "git", "github", "jira")
        """
        pass

    @property
    def version(self) -> str:
        """Plugin version (default: "0.0.0")"""
        return "0.0.0"

    @property
    def description(self) -> str:
        """Plugin description (default: empty)"""
        return ""

    @property
    def dependencies(self) -> list[str]:
        """
        Other plugins this plugin depends on.
        
        Returns:
            List of plugin names (e.g., ["git"] for GitHub plugin)
        """
        return []

    def initialize(self, config: Any, secrets: Any) -> None:
        """
        Initialize plugin with configuration and secrets.
        
        Called once when plugin is loaded by PluginRegistry.
        
        Args:
            config: TitanConfig instance
            secrets: SecretManager instance
        """
        pass

    def get_client(self) -> Optional[Any]:
        """
        Get the main client instance for this plugin.
        
        This client will be injected into WorkflowContext.
        
        Returns:
            Client instance or None
        """
        return None

    def get_steps(self) -> Dict[str, Callable]:
        """
        Get workflow steps provided by this plugin.
        
        Returns:
            Dict mapping step name to step function
        """
        return {}

    def is_available(self) -> bool:
        """
        Check if plugin is available/configured.
        
        Returns:
            True if plugin can be used
        """
        return True