"""
Workflow Filter Service

Service for filtering and grouping workflows by plugin.
"""
from typing import Dict, List, Set

from .workflow_sources import WorkflowInfo


class WorkflowFilterService:
    """Service for filtering and grouping workflows."""

    @staticmethod
    def detect_plugin_name(wf_info: WorkflowInfo) -> str:
        """
        Detect the actual plugin name for a workflow.

        This method intelligently detects which plugin a workflow belongs to,
        even for project/user workflows that use plugin steps.

        Args:
            wf_info: WorkflowInfo object to analyze

        Returns:
            Plugin name in capitalized form (e.g., "Github", "Jira", "Custom")

        Examples:
            Plugin workflow: "plugin:github" -> "Github"
            Project workflow using GitHub steps -> "Github"
            Project workflow using Jira steps -> "Jira"
            Project workflow with no plugins -> "Custom"
        """
        # If it's already from a plugin, extract the name
        if wf_info.source.startswith("plugin:"):
            plugin_name = wf_info.source.split(":", 1)[1]
            return plugin_name.capitalize()

        # For project/user workflows, check which plugin they use
        if wf_info.source in ["project", "user"]:
            if wf_info.required_plugins:
                # Use the first required plugin (most workflows use only one)
                primary_plugin = sorted(wf_info.required_plugins)[0]
                return primary_plugin.capitalize()
            else:
                # No plugin dependencies, it's a custom workflow
                return "Custom"

        # Fallback for other sources
        return wf_info.source.capitalize()

    @staticmethod
    def group_by_plugin(workflows: List[WorkflowInfo]) -> Dict[str, List[WorkflowInfo]]:
        """
        Group workflows by their associated plugin.

        Analyzes each workflow to determine its plugin and creates a mapping
        from plugin names to lists of workflows.

        Args:
            workflows: List of WorkflowInfo objects to group

        Returns:
            Dictionary mapping plugin names to lists of workflows

        Example:
            {
                "Github": [workflow1, workflow2],
                "Jira": [workflow3],
                "Custom": [workflow4]
            }
        """
        plugin_map: Dict[str, List[WorkflowInfo]] = {}

        for wf_info in workflows:
            plugin_name = WorkflowFilterService.detect_plugin_name(wf_info)

            if plugin_name not in plugin_map:
                plugin_map[plugin_name] = []
            plugin_map[plugin_name].append(wf_info)

        return plugin_map

    @staticmethod
    def get_unique_plugin_names(workflows: List[WorkflowInfo]) -> Set[str]:
        """
        Get all unique plugin names from a list of workflows.

        Args:
            workflows: List of WorkflowInfo objects

        Returns:
            Set of unique plugin names
        """
        plugin_names = set()
        for wf_info in workflows:
            plugin_name = WorkflowFilterService.detect_plugin_name(wf_info)
            plugin_names.add(plugin_name)
        return plugin_names

    @staticmethod
    def filter_by_plugin(workflows: List[WorkflowInfo], plugin_name: str) -> List[WorkflowInfo]:
        """
        Filter workflows by plugin name.

        Args:
            workflows: List of WorkflowInfo objects to filter
            plugin_name: Plugin name to filter by (e.g., "Github")

        Returns:
            List of workflows that belong to the specified plugin
        """
        return [
            wf for wf in workflows
            if WorkflowFilterService.detect_plugin_name(wf) == plugin_name
        ]

    @staticmethod
    def remove_duplicates(workflows: List[WorkflowInfo]) -> List[WorkflowInfo]:
        """
        Remove duplicate workflows by name, keeping first occurrence.

        Args:
            workflows: List of WorkflowInfo objects that may contain duplicates

        Returns:
            List of unique workflows (by name)
        """
        seen = set()
        unique_workflows = []

        for wf in workflows:
            if wf.name not in seen:
                seen.add(wf.name)
                unique_workflows.append(wf)

        return unique_workflows
