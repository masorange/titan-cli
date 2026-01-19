"""
Tests for WorkflowFilterService

Unit tests for workflow filtering and grouping logic.
"""
from pathlib import Path

from titan_cli.core.workflows.workflow_filter_service import WorkflowFilterService
from titan_cli.core.workflows.workflow_sources import WorkflowInfo


class TestWorkflowFilterService:
    """Test suite for WorkflowFilterService."""

    def test_detect_plugin_name_from_plugin_source(self):
        """Test detecting plugin name from plugin: source."""
        wf = WorkflowInfo(
            name="test-workflow",
            source="plugin:github",
            description="Test workflow",
            path=Path("/path/to/workflow.yaml"),
            required_plugins=set()
        )

        result = WorkflowFilterService.detect_plugin_name(wf)
        assert result == "Github"

    def test_detect_plugin_name_from_project_with_required_plugins(self):
        """Test detecting plugin name from project workflow with required plugins."""
        wf = WorkflowInfo(
            name="test-workflow",
            source="project",
            description="Test workflow",
            path=Path("/path/to/workflow.yaml"),
            required_plugins={"github", "jira"}
        )

        result = WorkflowFilterService.detect_plugin_name(wf)
        # Should return first in sorted order
        assert result == "Github"

    def test_detect_plugin_name_from_project_without_plugins(self):
        """Test detecting plugin name from project workflow without plugins."""
        wf = WorkflowInfo(
            name="test-workflow",
            source="project",
            description="Test workflow",
            path=Path("/path/to/workflow.yaml"),
            required_plugins=set()
        )

        result = WorkflowFilterService.detect_plugin_name(wf)
        assert result == "Custom"

    def test_detect_plugin_name_from_user_source(self):
        """Test detecting plugin name from user workflow."""
        wf = WorkflowInfo(
            name="test-workflow",
            source="user",
            description="Test workflow",
            path=Path("/path/to/workflow.yaml"),
            required_plugins={"jira"}
        )

        result = WorkflowFilterService.detect_plugin_name(wf)
        assert result == "Jira"

    def test_group_by_plugin(self):
        """Test grouping workflows by plugin."""
        workflows = [
            WorkflowInfo(
                name="github-workflow",
                source="plugin:github",
                description="GitHub workflow",
                path=Path("/path/1.yaml"),
                required_plugins=set()
            ),
            WorkflowInfo(
                name="jira-workflow",
                source="plugin:jira",
                description="Jira workflow",
                path=Path("/path/2.yaml"),
                required_plugins=set()
            ),
            WorkflowInfo(
                name="project-github-workflow",
                source="project",
                description="Project workflow",
                path=Path("/path/3.yaml"),
                required_plugins={"github"}
            ),
        ]

        result = WorkflowFilterService.group_by_plugin(workflows)

        assert "Github" in result
        assert "Jira" in result
        assert len(result["Github"]) == 2  # Plugin + project workflow
        assert len(result["Jira"]) == 1

    def test_get_unique_plugin_names(self):
        """Test getting unique plugin names."""
        workflows = [
            WorkflowInfo(
                name="workflow1",
                source="plugin:github",
                description="Test",
                path=Path("/path/1.yaml"),
                required_plugins=set()
            ),
            WorkflowInfo(
                name="workflow2",
                source="plugin:github",
                description="Test",
                path=Path("/path/2.yaml"),
                required_plugins=set()
            ),
            WorkflowInfo(
                name="workflow3",
                source="plugin:jira",
                description="Test",
                path=Path("/path/3.yaml"),
                required_plugins=set()
            ),
        ]

        result = WorkflowFilterService.get_unique_plugin_names(workflows)

        assert result == {"Github", "Jira"}

    def test_filter_by_plugin(self):
        """Test filtering workflows by plugin name."""
        workflows = [
            WorkflowInfo(
                name="github-workflow",
                source="plugin:github",
                description="GitHub workflow",
                path=Path("/path/1.yaml"),
                required_plugins=set()
            ),
            WorkflowInfo(
                name="jira-workflow",
                source="plugin:jira",
                description="Jira workflow",
                path=Path("/path/2.yaml"),
                required_plugins=set()
            ),
        ]

        result = WorkflowFilterService.filter_by_plugin(workflows, "Github")

        assert len(result) == 1
        assert result[0].name == "github-workflow"

    def test_remove_duplicates(self):
        """Test removing duplicate workflows by name."""
        workflows = [
            WorkflowInfo(
                name="duplicate-workflow",
                source="plugin:github",
                description="First",
                path=Path("/path/1.yaml"),
                required_plugins=set()
            ),
            WorkflowInfo(
                name="duplicate-workflow",
                source="project",
                description="Second",
                path=Path("/path/2.yaml"),
                required_plugins=set()
            ),
            WorkflowInfo(
                name="unique-workflow",
                source="plugin:jira",
                description="Unique",
                path=Path("/path/3.yaml"),
                required_plugins=set()
            ),
        ]

        result = WorkflowFilterService.remove_duplicates(workflows)

        assert len(result) == 2
        assert result[0].name == "duplicate-workflow"
        assert result[0].source == "plugin:github"  # First occurrence kept
        assert result[1].name == "unique-workflow"

    def test_detect_plugin_name_fallback(self):
        """Test fallback for unknown source types."""
        wf = WorkflowInfo(
            name="test-workflow",
            source="unknown-source",
            description="Test workflow",
            path=Path("/path/to/workflow.yaml"),
            required_plugins=set()
        )

        result = WorkflowFilterService.detect_plugin_name(wf)
        assert result == "Unknown-source"
