from typer.testing import CliRunner

from titan_cli.cli import app


def test_cli_update_does_not_launch_tui_after_successful_update(mocker):
    """A successful update should exit and ask the user to rerun Titan."""
    runner = CliRunner()
    mocker.patch(
        "titan_cli.cli.check_for_updates",
        return_value={
            "update_available": True,
            "current_version": "999.0.0",
            "latest_version": "999.0.1",
            "is_dev_install": False,
            "error": None,
        },
    )
    update_core = mocker.patch(
        "titan_cli.cli.update_core",
        return_value={
            "success": True,
            "method": "pipx",
            "installed_version": "999.0.1",
            "error": None,
        },
    )
    mocker.patch(
        "titan_cli.cli.update_plugins",
        return_value={"success": True, "skipped": False, "error": None},
    )
    mocker.patch("titan_cli.cli.get_installed_version", return_value="999.0.1")
    launch_tui = mocker.patch("titan_cli.cli.launch_tui")

    result = runner.invoke(app, input="Y\n")

    assert result.exit_code == 0
    update_core.assert_called_once_with(target_version="999.0.1")
    launch_tui.assert_not_called()
    assert "Please run `titan` again" in result.output


def test_cli_update_fails_when_final_version_check_fails(mocker):
    """Do not report success if plugins leave Titan below the target version."""
    runner = CliRunner()
    mocker.patch(
        "titan_cli.cli.check_for_updates",
        return_value={
            "update_available": True,
            "current_version": "999.0.0",
            "latest_version": "999.0.2",
            "is_dev_install": False,
            "error": None,
        },
    )
    mocker.patch(
        "titan_cli.cli.update_core",
        return_value={
            "success": True,
            "method": "pipx",
            "installed_version": "999.0.2",
            "error": None,
        },
    )
    mocker.patch(
        "titan_cli.cli.update_plugins",
        return_value={"success": True, "skipped": False, "error": None},
    )
    mocker.patch("titan_cli.cli.get_installed_version", return_value="999.0.1")
    launch_tui = mocker.patch("titan_cli.cli.launch_tui")

    result = runner.invoke(app, input="Y\n")

    assert result.exit_code == 1
    launch_tui.assert_not_called()
    assert "Failed to verify Titan CLI after plugin update" in result.output
    assert "expected at least 999.0.2" in result.output
