from pathlib import Path

import tomli_w

from titan_cli.core.plugins.local_sources import get_local_plugin_validation_error


def test_validate_local_plugin_repo_rejects_missing_directory(tmp_path: Path):
    missing_path = tmp_path / "missing-plugin"

    error = get_local_plugin_validation_error(missing_path, "github")

    assert error == "The selected path does not exist or is not a directory."


def test_validate_local_plugin_repo_requires_pyproject(tmp_path: Path):
    repo_path = tmp_path / "plugin-repo"
    repo_path.mkdir()

    error = get_local_plugin_validation_error(repo_path, "github")

    assert error == "The selected path does not contain a pyproject.toml file."


def test_validate_local_plugin_repo_requires_titan_entry_points(tmp_path: Path):
    repo_path = tmp_path / "plugin-repo"
    repo_path.mkdir()

    with open(repo_path / "pyproject.toml", "wb") as f:
        tomli_w.dump(
            {
                "project": {
                    "name": "example-plugin",
                    "version": "0.1.0",
                }
            },
            f,
        )

    error = get_local_plugin_validation_error(repo_path, "github")

    assert error == "This repository does not declare any 'titan.plugins' entry points."


def test_validate_local_plugin_repo_requires_selected_plugin_name(tmp_path: Path):
    repo_path = tmp_path / "plugin-repo"
    repo_path.mkdir()

    with open(repo_path / "pyproject.toml", "wb") as f:
        tomli_w.dump(
            {
                "project": {
                    "name": "example-plugin",
                    "version": "0.1.0",
                    "entry-points": {
                        "titan.plugins": {
                            "jira": "example.plugin:JiraPlugin",
                        }
                    },
                }
            },
            f,
        )

    error = get_local_plugin_validation_error(repo_path, "github")

    assert error == "This repository does not provide the 'github' plugin. Available plugins: jira"


def test_validate_local_plugin_repo_accepts_matching_plugin(tmp_path: Path):
    repo_path = tmp_path / "plugin-repo"
    repo_path.mkdir()

    with open(repo_path / "pyproject.toml", "wb") as f:
        tomli_w.dump(
            {
                "project": {
                    "name": "example-plugin",
                    "version": "0.1.0",
                    "entry-points": {
                        "titan.plugins": {
                            "github": "example.plugin:GitHubPlugin",
                        }
                    },
                }
            },
            f,
        )

    error = get_local_plugin_validation_error(repo_path, "github")

    assert error is None
