from unittest.mock import Mock, patch

from titan_cli.ai.dependencies import (
    dependencies_available,
    find_missing_modules,
    get_install_command,
    install_missing_dependencies,
)


def test_find_missing_modules_returns_empty_for_unknown_source():
    assert find_missing_modules("unknown-source") == []


@patch("titan_cli.ai.dependencies.importlib.import_module")
def test_find_missing_modules_returns_missing_modules(mock_import_module):
    def side_effect(module_name):
        if module_name == "openai":
            raise ImportError("missing")
        return Mock()

    mock_import_module.side_effect = side_effect

    missing = find_missing_modules("openai")
    assert missing == ["openai"]


@patch("titan_cli.ai.dependencies.find_missing_modules", return_value=[])
def test_dependencies_available_true_when_no_missing(mock_find_missing):
    assert dependencies_available("anthropic") is True


@patch("titan_cli.ai.dependencies.find_missing_modules", return_value=["anthropic"])
def test_dependencies_available_false_when_missing(mock_find_missing):
    assert dependencies_available("anthropic") is False


@patch("titan_cli.ai.dependencies.is_running_in_pipx", return_value=True)
def test_get_install_command_uses_pipx_when_running_in_pipx(
    mock_is_running_in_pipx,
):
    command = get_install_command("openai")
    assert command == ["pipx", "inject", "titan-cli", "openai"]


@patch("titan_cli.ai.dependencies.is_running_in_pipx", return_value=False)
def test_get_install_command_uses_pip_when_not_running_in_pipx(
    mock_is_running_in_pipx,
):
    command = get_install_command("openai")
    assert command[:3] != ["pipx", "inject", "titan-cli"]
    assert command[-1] == "openai"


def test_get_install_command_returns_none_for_unknown_source():
    assert get_install_command("unknown-source") is None


@patch("titan_cli.ai.dependencies.importlib.invalidate_caches")
@patch("titan_cli.ai.dependencies.subprocess.run")
@patch(
    "titan_cli.ai.dependencies.get_install_command",
    return_value=["pipx", "inject", "titan-cli", "openai"],
)
def test_install_missing_dependencies_runs_install_command(
    mock_get_install_command,
    mock_subprocess_run,
    mock_invalidate_caches,
):
    mock_result = Mock()
    mock_subprocess_run.return_value = mock_result

    result = install_missing_dependencies("openai")

    assert result is mock_result
    mock_subprocess_run.assert_called_once_with(
        ["pipx", "inject", "titan-cli", "openai"],
        capture_output=True,
        text=True,
    )
    mock_invalidate_caches.assert_called_once()


@patch("titan_cli.ai.dependencies.get_install_command", return_value=None)
def test_install_missing_dependencies_returns_none_when_source_unknown(
    mock_get_install_command,
):
    assert install_missing_dependencies("unknown-source") is None
