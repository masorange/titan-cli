from unittest.mock import Mock

from titan_cli.utils import autoupdate


def test_update_core_prefers_runtime_version_after_pipx_upgrade(mocker):
    """Report the version from the updated runtime when pipx upgrade succeeds."""
    newer_version = "999.0.0"
    mock_run = mocker.patch("titan_cli.utils.autoupdate.subprocess.run")
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    mocker.patch(
        "titan_cli.utils.autoupdate._get_installed_version_runtime",
        return_value=newer_version,
    )
    mocker.patch(
        "titan_cli.utils.autoupdate._get_installed_version_pipx",
        return_value=autoupdate.__version__,
    )

    result = autoupdate.update_core()

    assert result["success"] is True
    assert result["method"] == "pipx"
    assert result["installed_version"] == newer_version


def test_update_core_fails_when_version_does_not_change_after_pipx_upgrade(mocker):
    """Avoid reporting success when pipx leaves Titan on the current version."""
    mock_run = mocker.patch("titan_cli.utils.autoupdate.subprocess.run")
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    mocker.patch(
        "titan_cli.utils.autoupdate._get_installed_version_runtime",
        return_value=autoupdate.__version__,
    )
    mocker.patch(
        "titan_cli.utils.autoupdate._get_installed_version_pipx",
        return_value=None,
    )

    result = autoupdate.update_core()

    assert result["success"] is False
    assert result["installed_version"] is None
    assert result["error"] == (
        f"Installed version remains at {autoupdate.__version__}; update did not apply"
    )


def test_is_newer_installed_version_requires_higher_semver():
    """Only a strictly newer installed version should count as a successful update."""
    assert autoupdate._is_newer_installed_version("999.0.0") is True
    assert autoupdate._is_newer_installed_version(autoupdate.__version__) is False
