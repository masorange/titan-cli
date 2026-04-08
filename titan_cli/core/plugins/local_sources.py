"""
Local plugin source helpers.
"""

from pathlib import Path

import tomli


def get_local_plugin_validation_error(repo_path: Path, plugin_name: str) -> str | None:
    """Validate that a local repository exposes the selected Titan plugin."""
    if not repo_path.exists() or not repo_path.is_dir():
        return "The selected path does not exist or is not a directory."

    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        return "The selected path does not contain a pyproject.toml file."

    try:
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomli.load(f)
    except Exception as e:
        return f"Could not read pyproject.toml: {e}"

    entry_points = (
        pyproject_data.get("project", {})
        .get("entry-points", {})
        .get("titan.plugins", {})
    )
    if not entry_points:
        return "This repository does not declare any 'titan.plugins' entry points."

    if plugin_name not in entry_points:
        available = ", ".join(sorted(entry_points.keys()))
        return (
            f"This repository does not provide the '{plugin_name}' plugin."
            + (f" Available plugins: {available}" if available else "")
        )

    return None
