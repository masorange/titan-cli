from unittest.mock import Mock

from titan_cli.utils import autoupdate


def test_update_core_reports_verified_version_after_pipx_upgrade(mocker):
    """Report the externally verified version when pipx upgrade succeeds."""
    newer_version = "999.0.0"
    mock_run = mocker.patch("titan_cli.utils.autoupdate.subprocess.run")
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    mocker.patch(
        "titan_cli.utils.autoupdate.get_installed_version",
        return_value=newer_version,
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
        "titan_cli.utils.autoupdate.get_installed_version",
        return_value=autoupdate.__version__,
    )

    result = autoupdate.update_core()

    assert result["success"] is False
    assert result["installed_version"] == autoupdate.__version__
    assert result["error"] == (
        f"Installed version remains at {autoupdate.__version__}; update did not apply"
    )


def test_update_core_succeeds_when_target_version_is_installed(mocker):
    """Accept an update only when the visible installed version reaches target."""
    target_version = "999.0.0"
    mock_run = mocker.patch("titan_cli.utils.autoupdate.subprocess.run")
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    mocker.patch(
        "titan_cli.utils.autoupdate.get_installed_version",
        return_value=target_version,
    )

    result = autoupdate.update_core(target_version=target_version)

    assert result["success"] is True
    assert result["method"] == "pipx"
    assert result["installed_version"] == target_version


def test_update_core_fails_when_installed_version_is_below_target(mocker):
    """Reject partial upgrades that do not reach the requested latest version."""
    installed_version = "999.0.0"
    target_version = "999.0.1"
    mock_run = mocker.patch("titan_cli.utils.autoupdate.subprocess.run")
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    mocker.patch(
        "titan_cli.utils.autoupdate.get_installed_version",
        return_value=installed_version,
    )

    result = autoupdate.update_core(target_version=target_version)

    assert result["success"] is False
    assert result["installed_version"] == installed_version
    assert result["error"] == (
        f"Installed version is {installed_version}; expected at least {target_version}"
    )


def test_is_newer_installed_version_requires_higher_semver():
    """Only a strictly newer installed version should count as a successful update."""
    assert autoupdate._is_newer_installed_version("999.0.0") is True
    assert autoupdate._is_newer_installed_version(autoupdate.__version__) is False


def test_meets_target_version_requires_target_or_higher():
    """Target validation should not accept lower installed versions."""
    assert autoupdate.meets_target_version("999.0.1", "999.0.0") is True
    assert autoupdate.meets_target_version("999.0.0", "999.0.0") is True
    assert autoupdate.meets_target_version("999.0.0", "999.0.1") is False


def test_get_active_titan_version_parses_version_command(mocker):
    """Read the version from the titan executable currently visible on PATH."""
    mocker.patch("titan_cli.utils.autoupdate.shutil.which", return_value="/bin/titan")
    mocker.patch(
        "titan_cli.utils.autoupdate.subprocess.run",
        return_value=Mock(returncode=0, stdout="Titan CLI v999.0.0\n", stderr=""),
    )

    assert autoupdate._get_active_titan_version() == "999.0.0"
