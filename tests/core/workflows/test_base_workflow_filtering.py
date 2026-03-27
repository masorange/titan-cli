"""
Tests for base workflow filtering in WorkflowRegistry.

Covers:
- _normalize_extends_ref: all supported reference formats
- _filter_base_workflows: filtering logic
- discover() integration: both flat and directory-based naming patterns
"""
import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock

from titan_cli.core.workflows.workflow_registry import WorkflowRegistry
from titan_cli.core.workflows.workflow_sources import WorkflowInfo
from titan_cli.core.plugins.plugin_registry import PluginRegistry
from titan_cli.core.workflows.project_step_source import ProjectStepSource


# --- Fixtures ---

@pytest.fixture
def mock_project_root(tmp_path: Path):
    return tmp_path


@pytest.fixture
def mock_plugin_registry():
    registry = MagicMock(spec=PluginRegistry)
    registry.list_installed.return_value = []
    registry.get_plugin.return_value = None
    registry._plugins = {}
    return registry


@pytest.fixture
def mock_project_step_source(mock_project_root):
    return ProjectStepSource(mock_project_root)


@pytest.fixture
def registry(mock_project_root, mock_plugin_registry, mock_project_step_source):
    return WorkflowRegistry(
        project_root=mock_project_root,
        plugin_registry=mock_plugin_registry,
        project_step_source=mock_project_step_source,
    )


@pytest.fixture
def workflows_dir(mock_project_root):
    d = mock_project_root / ".titan" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_project_workflow(workflows_dir: Path, name: str, config: dict) -> Path:
    path = workflows_dir / f"{name}.yaml"
    path.write_text(yaml.dump(config))
    return path


# --- Tests for _normalize_extends_ref ---

class TestNormalizeExtendsRef:

    def test_simple_name(self, registry):
        assert registry._normalize_extends_ref("release-notes") == "release-notes"

    def test_relative_path(self, registry):
        assert registry._normalize_extends_ref("common/release-notes") == "common/release-notes"

    def test_plugin_prefix_simple(self, registry):
        # "plugin:git/commit-ai" -> "commit-ai"
        assert registry._normalize_extends_ref("plugin:git/commit-ai") == "commit-ai"

    def test_plugin_prefix_with_subdir(self, registry):
        # "plugin:myplugin/common/release-notes" -> "common/release-notes"
        assert registry._normalize_extends_ref("plugin:myplugin/common/release-notes") == "common/release-notes"

    def test_source_qualifier_no_subpath(self, registry):
        # "system:quick-commit" (no subpath after plugin name) -> "quick-commit"
        assert registry._normalize_extends_ref("system:quick-commit") == "quick-commit"

    def test_slash_without_colon_is_unchanged(self, registry):
        # "system/quick-commit" without ":" is a plain relative path, returned as-is
        assert registry._normalize_extends_ref("system/quick-commit") == "system/quick-commit"

    def test_deep_subdir(self, registry):
        # "plugin:myplugin/a/b/c" -> "a/b/c"
        assert registry._normalize_extends_ref("plugin:myplugin/a/b/c") == "a/b/c"


# --- Tests for _filter_base_workflows ---

def make_workflow_info(name: str, extends_ref: str = None) -> WorkflowInfo:
    return WorkflowInfo(
        name=name,
        description="desc",
        source="project",
        path=Path(f"/fake/{name}.yaml"),
        extends_ref=extends_ref,
    )


class TestFilterBaseWorkflows:

    def test_no_extends_keeps_all(self, registry):
        workflows = [
            make_workflow_info("wf-a"),
            make_workflow_info("wf-b"),
        ]
        result = registry._filter_base_workflows(workflows)
        assert [w.name for w in result] == ["wf-a", "wf-b"]

    def test_flat_naming_hides_base(self, registry):
        """Flat naming: "release-notes" is extended by "release-notes-android"."""
        workflows = [
            make_workflow_info("release-notes"),
            make_workflow_info("release-notes-android", extends_ref="release-notes"),
        ]
        result = registry._filter_base_workflows(workflows)
        names = [w.name for w in result]
        assert "release-notes-android" in names
        assert "release-notes" not in names

    def test_directory_naming_hides_base(self, registry):
        """Directory naming: "common/release-notes" extended by "android/release-notes"."""
        workflows = [
            make_workflow_info("common/release-notes"),
            make_workflow_info("android/release-notes", extends_ref="common/release-notes"),
        ]
        result = registry._filter_base_workflows(workflows)
        names = [w.name for w in result]
        assert "android/release-notes" in names
        assert "common/release-notes" not in names

    def test_plugin_prefix_reference_hides_base(self, registry):
        """Plugin prefix: extends "plugin:myplugin/common/release-notes" hides "common/release-notes"."""
        workflows = [
            make_workflow_info("common/release-notes"),
            make_workflow_info("android/release-notes",
                               extends_ref="plugin:myplugin/common/release-notes"),
        ]
        result = registry._filter_base_workflows(workflows)
        names = [w.name for w in result]
        assert "android/release-notes" in names
        assert "common/release-notes" not in names

    def test_multiple_children_hide_single_base(self, registry):
        """Multiple platforms extending the same base — base must be hidden."""
        workflows = [
            make_workflow_info("common/release-notes"),
            make_workflow_info("android/release-notes",
                               extends_ref="plugin:myplugin/common/release-notes"),
            make_workflow_info("ios/release-notes",
                               extends_ref="plugin:myplugin/common/release-notes"),
        ]
        result = registry._filter_base_workflows(workflows)
        names = [w.name for w in result]
        assert "android/release-notes" in names
        assert "ios/release-notes" in names
        assert "common/release-notes" not in names

    def test_unrelated_workflows_are_kept(self, registry):
        """Unrelated workflows are not affected by base filtering."""
        workflows = [
            make_workflow_info("common/release-notes"),
            make_workflow_info("android/release-notes",
                               extends_ref="plugin:myplugin/common/release-notes"),
            make_workflow_info("commit-ai"),
            make_workflow_info("play-store-release"),
        ]
        result = registry._filter_base_workflows(workflows)
        names = [w.name for w in result]
        assert "commit-ai" in names
        assert "play-store-release" in names
        assert "android/release-notes" in names
        assert "common/release-notes" not in names

    def test_child_is_also_base_of_another(self, registry):
        """A workflow that extends another AND is extended by a third: keeps the middle, hides the root."""
        workflows = [
            make_workflow_info("base"),
            make_workflow_info("middle", extends_ref="base"),
            make_workflow_info("child", extends_ref="middle"),
        ]
        result = registry._filter_base_workflows(workflows)
        names = [w.name for w in result]
        # "base" is hidden because "middle" extends it
        # "middle" is hidden because "child" extends it
        # "child" is shown
        assert "child" in names
        assert "middle" not in names
        assert "base" not in names

    def test_same_name_extends_plugin_keeps_project_workflow(self, registry):
        """Project 'commit-ai' extending plugin:git/commit-ai must NOT be hidden.

        Two workflows (project and plugin variant) both extend plugin:git/commit-ai.
        Normalised, that resolves to 'commit-ai'. The project workflow is named
        'commit-ai' — it must NOT be filtered out because the extender name equals
        the normalised base name.
        """
        workflows = [
            make_workflow_info("commit-ai", extends_ref="plugin:git/commit-ai"),
            make_workflow_info("android/commit-ai", extends_ref="plugin:git/commit-ai"),
        ]
        result = registry._filter_base_workflows(workflows)
        names = [w.name for w in result]
        assert "commit-ai" in names
        assert "android/commit-ai" in names


# --- Integration tests via discover() ---

class TestDiscoverFiltersBaseWorkflows:

    def test_flat_naming_discover(self, registry, workflows_dir):
        """discover() hides base when using flat naming."""
        create_project_workflow(workflows_dir, "release-notes", {
            "name": "Release Notes",
            "description": "Base",
            "steps": [{"id": "s1", "command": "echo base"}],
        })
        create_project_workflow(workflows_dir, "release-notes-android", {
            "name": "Release Notes Android",
            "description": "Android",
            "extends": "release-notes",
            "steps": [],
        })

        names = [w.name for w in registry.discover()]
        assert "release-notes-android" in names
        assert "release-notes" not in names

    def test_directory_naming_discover(self, mock_project_root, mock_plugin_registry, mock_project_step_source, tmp_path):
        """discover() hides base when using directory-based naming inside a plugin."""
        plugin_workflows_dir = tmp_path / "plugin_workflows"
        (plugin_workflows_dir / "common").mkdir(parents=True)
        (plugin_workflows_dir / "android").mkdir(parents=True)

        (plugin_workflows_dir / "common" / "release-notes.yaml").write_text(yaml.dump({
            "name": "Release Notes",
            "description": "Base workflow",
            "hooks": ["create_notes_files"],
            "steps": [{"id": "s1", "command": "echo base"}],
        }))
        (plugin_workflows_dir / "android" / "release-notes.yaml").write_text(yaml.dump({
            "name": "Release Notes Android",
            "description": "Android extension",
            "extends": "plugin:myplugin/common/release-notes",
            "hooks": {
                "create_notes_files": [{"id": "create", "command": "echo android"}]
            },
        }))

        mock_plugin = MagicMock()
        mock_plugin.name = "myplugin"
        mock_plugin.workflows_path = plugin_workflows_dir
        mock_plugin.filter_workflows = lambda wfs, cfg: wfs

        mock_plugin_registry.list_installed.return_value = ["myplugin"]
        mock_plugin_registry.get_plugin.return_value = mock_plugin
        mock_plugin_registry._plugins = {"myplugin": mock_plugin}

        reg = WorkflowRegistry(
            project_root=mock_project_root,
            plugin_registry=mock_plugin_registry,
            project_step_source=mock_project_step_source,
        )

        names = [w.name for w in reg.discover()]
        assert "android/release-notes" in names
        assert "common/release-notes" not in names

    def test_discover_keeps_standalone_workflows(self, registry, workflows_dir):
        """discover() does not filter workflows that nobody extends."""
        create_project_workflow(workflows_dir, "commit-ai", {
            "name": "Commit AI",
            "description": "Standalone",
            "steps": [{"id": "s1", "command": "echo hi"}],
        })
        create_project_workflow(workflows_dir, "play-store-release", {
            "name": "Play Store Release",
            "description": "Standalone",
            "steps": [{"id": "s1", "command": "echo hi"}],
        })

        names = [w.name for w in registry.discover()]
        assert "commit-ai" in names
        assert "play-store-release" in names
