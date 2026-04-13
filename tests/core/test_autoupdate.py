from unittest.mock import Mock

from titan_cli.utils import autoupdate


def test_update_core_prefers_runtime_version_after_pipx_upgrade(mocker):
    """Report the version from the updated runtime when pipx upgrade succeeds."""
    mock_run = mocker.patch("titan_cli.utils.autoupdate.subprocess.run")
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    mocker.patch(
        "titan_cli.utils.autoupdate._get_installed_version_runtime",
        return_value="0.3.0",
    )
    mocker.patch(
        "titan_cli.utils.autoupdate._get_installed_version_pipx",
        return_value="0.2.0",
    )

    result = autoupdate.update_core()

    assert result["success"] is True
    assert result["method"] == "pipx"
    assert result["installed_version"] == "0.3.0"
