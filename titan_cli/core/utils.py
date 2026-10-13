import hashlib
import re
import subprocess
from pathlib import Path
from typing import Optional

from titan_cli.core.logging import get_logger

logger = get_logger(__name__)


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
            git_root = Path(result.stdout.strip())
            logger.debug("git_root_found", path=str(git_root))
            return git_root
    except Exception:
        logger.debug("git_not_available")
    logger.debug("git_root_not_found")
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


def project_source_scope_key(project_path: Path) -> str:
    """
    The `project_sources` key a project's personal, per-machine state is filed under in
    the global `~/.titan/config.toml`: a plugin's `dev_local` override, favorite workflows,
    a mod's enabled flag and section switches (`core/config.py`, `core/mods/settings.py`).

    Keyed by the resolved path, not just the name: moving the repo on disk loses the
    entry rather than one project silently inheriting another's state because they share
    a folder name.
    """
    resolved = project_path.resolve()
    safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", resolved.name).strip("_").lower() or "project"
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:8]
    return f"p_{safe_name}_{digest}"
