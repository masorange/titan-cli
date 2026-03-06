import subprocess
from pathlib import Path
from typing import Optional


def find_git_root() -> Optional[Path]:
    """
    Find the root of the current git repository.

    Returns:
        Path to the git root directory, or None if not in a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def find_project_root() -> Path:
    """
    Determine the project root directory.

    Uses the git root if inside a git repository, otherwise falls back to the
    current working directory.

    Returns:
        Path to the project root.
    """
    return find_git_root() or Path.cwd()
