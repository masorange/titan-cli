"""
YAML validation tests for release notes workflow.
"""

import pytest
import yaml
from pathlib import Path


class TestReleaseNotesWorkflowValidation:
    """Validate release notes workflow YAML configurations."""

    @pytest.fixture
    def plugin_workflow_file(self):
        """Get plugin workflow file."""
        return Path("plugins/titan-plugin-jira/titan_plugin_jira/workflows/generate-release-notes.yaml")

    @pytest.fixture
    def example_workflow_files(self):
        """Get example workflow files."""
        return [
            Path("examples/ragnarok-ios-release-notes-workflow.yaml"),
            Path("examples/ragnarok-android-release-notes-workflow.yaml"),
        ]

    def test_plugin_workflow_valid_yaml(self, plugin_workflow_file):
        """Test that plugin workflow is valid YAML."""
        assert plugin_workflow_file.exists(), f"Workflow file not found: {plugin_workflow_file}"

        with open(plugin_workflow_file) as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {plugin_workflow_file}: {e}")

    def test_plugin_workflow_has_required_fields(self, plugin_workflow_file):
        """Test that plugin workflow has all required fields."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        required_fields = ["name", "description", "steps"]
        for field in required_fields:
            assert field in config, f"Missing required field: {field}"

    def test_plugin_workflow_steps_have_required_fields(self, plugin_workflow_file):
        """Test that all steps have required fields."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        required_step_fields = ["id", "name"]

        for step in config.get("steps", []):
            for field in required_step_fields:
                assert field in step, \
                    f"Step missing required field '{field}': {step.get('id', 'unknown')}"

            # Either plugin+step OR command+use_shell
            has_plugin_step = "plugin" in step and "step" in step
            has_command = "command" in step
            assert has_plugin_step or has_command, \
                f"Step must have either (plugin+step) or command: {step['id']}"

    def test_plugin_workflow_step_ids_unique(self, plugin_workflow_file):
        """Test that step IDs are unique."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        step_ids = [step["id"] for step in config.get("steps", [])]
        duplicates = [id for id in step_ids if step_ids.count(id) > 1]

        assert len(step_ids) == len(set(step_ids)), \
            f"Duplicate step IDs found: {duplicates}"

    def test_plugin_workflow_dependencies_valid(self, plugin_workflow_file):
        """Test that step dependencies reference valid outputs."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        # Build set of available outputs (step IDs + workflow params + known step outputs)
        available_outputs = set()

        # Add workflow params
        for param_name in config.get("params", {}).keys():
            available_outputs.add(param_name)

        # Known step outputs (implicit from step implementations)
        step_outputs = {
            "list_versions": ["versions"],
            "search_issues": ["issues", "issue_count"],
            "generate_release_notes": ["release_notes"],
            "save_release_notes_file": ["file_path"],
            "ensure_release_branch": ["release_branch", "branch_created"],
            "create_git_commit": ["commit_hash"],
            "create_git_push": ["pr_head_branch"],
            "prepare_commit_pr_data": ["commit_message", "pr_title", "pr_body", "pr_head_branch"],
            "prompt_select_version": ["fix_version"],
            "normalize_version": ["fix_version"],
            "prompt_platform": ["platform"],
        }

        # Process steps in order
        for step in config.get("steps", []):
            step_id = step["id"]
            step_name = step.get("step", "")

            # Add this step's ID as available output
            available_outputs.add(step_id)

            # Add known outputs from this step
            if step_name in step_outputs:
                available_outputs.update(step_outputs[step_name])

            # Check requires references
            requires = step.get("requires", [])
            for req in requires:
                assert req in available_outputs, \
                    f"Step '{step_id}' requires '{req}' which is not available. " \
                    f"Available: {available_outputs}"

    def test_plugin_workflow_parameter_references_valid(self, plugin_workflow_file):
        """Test that ${param} references are defined."""
        import re

        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)
            content = f.read()

        # Find all ${variable} references in file
        param_refs = re.findall(r'\$\{(\w+)\}', content)

        # Get available params
        workflow_params = set(config.get("params", {}).keys())

        # Build available outputs from steps
        available_outputs = set()
        for step in config.get("steps", []):
            available_outputs.add(step["id"])

        # Check each reference is defined
        for ref in param_refs:
            assert ref in workflow_params or ref in available_outputs, \
                f"Parameter reference ${{{ref}}} not defined in workflow"

    def test_example_workflows_valid_yaml(self, example_workflow_files):
        """Test that all example workflows are valid YAML."""
        for workflow_file in example_workflow_files:
            if not workflow_file.exists():
                pytest.skip(f"Example file not found: {workflow_file}")

            with open(workflow_file) as f:
                try:
                    yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {workflow_file}: {e}")

    def test_example_workflows_have_required_fields(self, example_workflow_files):
        """Test that example workflows have required fields."""
        for workflow_file in example_workflow_files:
            if not workflow_file.exists():
                continue

            with open(workflow_file) as f:
                config = yaml.safe_load(f)

            required_fields = ["name", "description", "steps"]
            for field in required_fields:
                assert field in config, \
                    f"{workflow_file.name} missing field: {field}"

    def test_workflow_uses_correct_plugins(self, plugin_workflow_file):
        """Test that workflow only uses valid plugins."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        valid_plugins = ["jira", "git", "github"]

        for step in config.get("steps", []):
            if "plugin" in step:
                plugin_name = step["plugin"]
                assert plugin_name in valid_plugins, \
                    f"Step '{step['id']}' uses invalid plugin: {plugin_name}"

    def test_workflow_has_descriptive_step_names(self, plugin_workflow_file):
        """Test that all steps have descriptive names."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        for step in config.get("steps", []):
            name = step.get("name", "")
            assert len(name) > 0, f"Step '{step['id']}' has empty name"
            assert len(name) >= 5, \
                f"Step '{step['id']}' name too short: '{name}'"

    def test_workflow_params_have_defaults_or_prompts(self, plugin_workflow_file):
        """Test that workflow params either have defaults or will be prompted."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        params = config.get("params", {})

        # Check that important params have sensible defaults
        if "project_key" in params:
            assert params["project_key"], "project_key should have default value"

    def test_workflow_step_order_logical(self, plugin_workflow_file):
        """Test that steps are in logical order."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        steps = config.get("steps", [])
        step_ids = [step["id"] for step in steps]

        # Ensure branch creation happens before commit
        if "ensure_branch" in step_ids and "commit_changes" in step_ids:
            ensure_idx = step_ids.index("ensure_branch")
            commit_idx = step_ids.index("commit_changes")
            assert ensure_idx < commit_idx, \
                "ensure_branch must come before commit_changes"

        # Ensure commit happens before push
        if "commit_changes" in step_ids and "push_branch" in step_ids:
            commit_idx = step_ids.index("commit_changes")
            push_idx = step_ids.index("push_branch")
            assert commit_idx < push_idx, \
                "commit_changes must come before push_branch"

        # Ensure push happens before PR
        if "push_branch" in step_ids and "create_pr" in step_ids:
            push_idx = step_ids.index("push_branch")
            pr_idx = step_ids.index("create_pr")
            assert push_idx < pr_idx, \
                "push_branch must come before create_pr"

    def test_workflow_has_hitl_confirmation_steps(self, plugin_workflow_file):
        """Test that workflow includes human confirmation where appropriate."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        step_ids = [step["id"] for step in config.get("steps", [])]

        # Should have some confirmation step for release notes
        # (either confirm_notes or user selection of version)
        has_confirmation = any(
            "confirm" in step_id or "select" in step_id or "prompt" in step_id
            for step_id in step_ids
        )

        assert has_confirmation, \
            "Workflow should include user confirmation or selection steps"

    def test_workflow_creates_pr_data_before_pr(self, plugin_workflow_file):
        """Test that PR data is prepared before creating PR."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        steps = config.get("steps", [])
        step_ids = [step["id"] for step in steps]

        if "create_pr" in step_ids:
            pr_idx = step_ids.index("create_pr")

            # There should be a prepare_data step before create_pr
            prepare_found = False
            for i in range(pr_idx):
                step = steps[i]
                if "prepare" in step["id"] and "pr" in step.get("step", ""):
                    prepare_found = True
                    break

            assert prepare_found or "pr_title" in step_ids or "prepare_data" in step_ids, \
                "PR data should be prepared before create_pr step"

    def test_workflow_normalizes_version_format(self, plugin_workflow_file):
        """Test that workflow includes version normalization step."""
        with open(plugin_workflow_file) as f:
            config = yaml.safe_load(f)

        steps = config.get("steps", [])

        # Should have normalize_version step
        has_normalize = any(
            step.get("step") == "normalize_version"
            for step in steps
        )

        assert has_normalize, \
            "Workflow should normalize version format (YY.W.B)"
