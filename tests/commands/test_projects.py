# tests/commands/test_projects.py
from typer.testing import CliRunner

from titan_cli.cli import app

runner = CliRunner()

def test_projects_list_no_root_config(monkeypatch, tmp_path):
    """
    Test that 'titan projects list' works with current directory.

    Note: Updated for new per-project configuration architecture.
    The command now uses current directory instead of global project_root.
    """
    # Create a temporary directory for testing
    test_dir = tmp_path / "test_projects"
    test_dir.mkdir()

    # Change to test directory
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(test_dir)

        # Run the 'projects list' command (should work even with no projects)
        result = runner.invoke(app, ["projects", "list"])

        # Should succeed (exit code 0) even if no projects found
        assert result.exit_code == 0
        assert "Project Discovery" in result.stdout

    finally:
        os.chdir(original_cwd)