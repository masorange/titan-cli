# titan_cli/core/workflows/__init__.py
"""
Workflow management system.

Similar to plugins system, but for workflows:
- WorkflowRegistry: Discover and manage workflows
- WorkflowSource: Load from multiple sources (project, user, system, plugins)
"""

from .workflow_registry import WorkflowRegistry, ParsedWorkflow
from .workflow_sources import WorkflowInfo
from .workflow_exceptions import WorkflowNotFoundError, WorkflowExecutionError
from .project_step_source import ProjectStepSource, UserStepSource
from .ai_usage_discovery import AIUsageDiscoveryService, DiscoveredAIStep, DiscoveredWorkflowAIUsage
from .quick_launch_service import QuickLaunchService, QuickLaunchSlot, DEFAULT_SLOT_COUNT

__all__ = [
    "WorkflowRegistry",
    "WorkflowInfo",
    "QuickLaunchService",
    "QuickLaunchSlot",
    "DEFAULT_SLOT_COUNT",
    "ParsedWorkflow",
    "WorkflowNotFoundError",
    "WorkflowExecutionError",
    "ProjectStepSource",
    "UserStepSource",
    "AIUsageDiscoveryService",
    "DiscoveredAIStep",
    "DiscoveredWorkflowAIUsage",
]
