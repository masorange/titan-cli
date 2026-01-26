"""
Titan TUI Screens

Screen components for different views in the Titan TUI.
"""
from .base import BaseScreen
from .main_menu import MainMenuScreen
from .workflows import WorkflowsScreen
from .workflow_execution import WorkflowExecutionScreen
from .global_setup_wizard import GlobalSetupWizardScreen
from .project_setup_wizard import ProjectSetupWizardScreen
from .plugin_config_wizard import PluginConfigWizardScreen

__all__ = [
    "BaseScreen",
    "MainMenuScreen",
    "WorkflowsScreen",
    "WorkflowExecutionScreen",
    "GlobalSetupWizardScreen",
    "ProjectSetupWizardScreen",
    "PluginConfigWizardScreen",
]
