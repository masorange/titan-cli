"""
Plugin manifest for App Store Connect.

Defines plugin metadata, status, and exports steps for Titan CLI.
"""

from typing import Dict, Any, Optional
from pathlib import Path
from titan_cli.core.plugins.plugin_base import TitanPlugin
from .credentials import CredentialsManager

# Plugin metadata
PLUGIN_NAME = "appstore"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "Interact with Apple's App Store Connect API"


class AppStorePlugin(TitanPlugin):
    """
    App Store Connect Plugin for Titan CLI.

    Entry point class that Titan uses to discover and load the plugin.
    """

    def __init__(self):
        """Initialize the plugin."""
        self._client = None

    @property
    def name(self) -> str:
        """Plugin unique identifier."""
        return PLUGIN_NAME

    @property
    def version(self) -> str:
        """Plugin version."""
        return PLUGIN_VERSION

    @property
    def description(self) -> str:
        """Plugin description."""
        return PLUGIN_DESCRIPTION

    @property
    def dependencies(self) -> list[str]:
        """Plugin dependencies (none)."""
        return []

    def initialize(self, config: Any, secrets: Any) -> None:
        """
        Initialize plugin with configuration and secrets.

        Args:
            config: TitanConfig instance
            secrets: SecretManager instance
        """
        # Initialize client if credentials are configured
        plugin_config = self._get_plugin_config(config)
        if plugin_config:
            self._client = self._create_client(plugin_config)

    def _get_plugin_config(self, config: Any) -> dict:
        """
        Extract plugin-specific configuration.

        Args:
            config: TitanConfig instance

        Returns:
            Plugin config dict (empty if not configured)
        """
        if not config or not hasattr(config, 'config'):
            return {}

        if "appstore" not in config.config.plugins:
            return {}

        plugin_entry = config.config.plugins["appstore"]
        return plugin_entry.config if hasattr(plugin_entry, 'config') else {}

    def is_configured(self) -> bool:
        """
        Check if plugin is configured.

        Returns:
            True if credentials are configured and valid
        """
        return CredentialsManager.is_configured()

    def is_available(self) -> bool:
        """
        Check if plugin is available/configured.

        Returns:
            True if plugin can be used
        """
        return self.is_configured()

    def get_status(self) -> Dict[str, Any]:
        """
        Get plugin status information.

        Returns:
            Dictionary with plugin status details
        """
        issuer_id, key_id, p8_path = CredentialsManager.get_client_credentials()

        status = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "configured": key_id is not None,
            "enabled": True,
        }

        if key_id:
            status["key_id"] = key_id
            status["issuer_id"] = issuer_id or "(Individual Key)"
            status["private_key_path"] = p8_path

        return status

    def get_plugin_info(self) -> Dict[str, Any]:
        """
        Return plugin metadata for Titan CLI discovery.

        Returns:
            Dictionary with plugin information
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "configured": self.is_configured(),
        }

    def get_steps(self) -> Dict[str, Any]:
        """
        Return available steps for this plugin.

        Uses lazy imports to avoid loading steps until needed.

        Note: setup_wizard_step is not exposed as it's embedded inside
        check_and_setup_step and runs automatically when needed.

        Returns:
            Dictionary mapping step names to step functions
        """
        from .steps import (
            check_and_setup_step,
            select_app_step,
            prompt_version_step,
            create_version_step,
            show_whats_new_preview,
            select_build_per_brand,
            submit_for_review,
            generate_submission_report,
            fetch_versions_step,
            request_analytics_step,
            request_analytics_single_version_step,
            fetch_metrics_step,
            analyze_metrics_step,
            generate_analytics_report,
            ai_insights_step,
            executive_dashboard_step,
            check_product_report_dependencies_step,
            select_product_report_version_step,
            product_report_step,
            export_product_report_pdf_step,
            analyze_single_version_step,
            fetch_production_version_step,
            analyze_version_with_comparison_step,
            debug_sales_reports_step,
            display_active_versions_health,
        )

        return {
            "check_and_setup_step": check_and_setup_step,
            "select_app_step": select_app_step,
            "prompt_version_step": prompt_version_step,
            "create_version_step": create_version_step,
            "show_whats_new_preview": show_whats_new_preview,
            "select_build_per_brand": select_build_per_brand,
            "submit_for_review": submit_for_review,
            "generate_submission_report": generate_submission_report,
            "fetch_versions_step": fetch_versions_step,
            "request_analytics_step": request_analytics_step,
            "request_analytics_single_version_step": request_analytics_single_version_step,
            "fetch_metrics_step": fetch_metrics_step,
            "analyze_metrics_step": analyze_metrics_step,
            "generate_analytics_report": generate_analytics_report,
            "ai_insights_step": ai_insights_step,
            "executive_dashboard_step": executive_dashboard_step,
            "check_product_report_dependencies_step": check_product_report_dependencies_step,
            "select_product_report_version_step": select_product_report_version_step,
            "product_report_step": product_report_step,
            "export_product_report_pdf_step": export_product_report_pdf_step,
            "analyze_single_version_step": analyze_single_version_step,
            "fetch_production_version_step": fetch_production_version_step,
            "analyze_version_with_comparison_step": analyze_version_with_comparison_step,
            "debug_sales_reports_step": debug_sales_reports_step,
            "display_active_versions_health": display_active_versions_health,
        }

    @property
    def workflows_path(self) -> Optional[Path]:
        """
        Return path to workflows directory.

        Returns:
            Path to workflows directory
        """
        plugin_dir = Path(__file__).parent.parent
        return plugin_dir / "workflows"

    def get_client(self) -> Optional[Any]:
        """
        Get the main client instance for this plugin.

        Returns:
            AppStoreConnectClient instance or None
        """
        return self._client

    def _create_client(self, config: Dict[str, Any]):
        """
        Build AppStoreConnectClient from plugin config.

        Internal method to create client instance.

        Args:
            config: Configuration dictionary with credentials

        Returns:
            AppStoreConnectClient instance or None if credentials invalid
        """
        from .clients.appstore_client import AppStoreConnectClient

        issuer_id = config.get("issuer_id")
        key_id = config.get("key_id")
        private_key_path = config.get("private_key_path")

        if not all([key_id, private_key_path]):
            return None

        key_path = Path(str(private_key_path)).expanduser()
        if not key_path.exists():
            return None

        return AppStoreConnectClient(
            key_id=key_id,
            issuer_id=issuer_id,
            private_key_content=key_path.read_text()
        )

    # Backward compatibility methods
    def get_workflows_dir(self) -> str:
        """Get workflows directory (backward compatibility)."""
        return str(self.workflows_path) if self.workflows_path else ""

    def create_client(self, config: Dict[str, Any]):
        """Create client instance (backward compatibility)."""
        return self._create_client(config)


# Backward compatibility functions
def is_configured() -> bool:
    """Check if plugin is configured (backward compatibility)."""
    return CredentialsManager.is_configured()


def get_status() -> Dict[str, Any]:
    """Get plugin status (backward compatibility)."""
    plugin = AppStorePlugin()
    return plugin.get_status()


# Export plugin class and metadata
__all__ = [
    "AppStorePlugin",
    "PLUGIN_NAME",
    "PLUGIN_VERSION",
    "PLUGIN_DESCRIPTION",
    "is_configured",
    "get_status",
]
