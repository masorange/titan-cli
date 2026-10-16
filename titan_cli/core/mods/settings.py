"""Writes a mod's `[mods.<name>]` settings to the user's own global config.

Unlike a plugin - a fact of the repo the team shares via the project's own
`.titan/config.toml` - which mod is on and which of its sections you want is personal:
whether you like to see the merge queue is not something a teammate's commit should
decide for you. So a switch here lands in `~/.titan/config.toml`, scoped to the active
project under the same `project_sources.<key>` block a plugin's `dev_local` override and
a favorite workflow already use (`core/config.py`), never in the project's own file.
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence

import tomli_w
import tomllib

from titan_cli.core.errors import ConfigWriteError
from titan_cli.core.utils import project_source_scope_key


def set_mod_setting(
    mod: str,
    path: Sequence[str],
    value: Any,
    project_root: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> None:
    """Set `[project_sources.<key>.mods.<mod>.<path...>] = value` in the user's global config."""
    from .loader import USER_CONFIG
    from .loader import project_root as active_project_root

    target = config_path or USER_CONFIG
    try:
        data = tomllib.loads(target.read_text())
    except FileNotFoundError:
        data = {}
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigWriteError(file_path=str(target), original_exception=e)

    root = (project_root or active_project_root() or Path.cwd()).resolve()
    project_table = _table(_table(data, "project_sources"), project_source_scope_key(root))
    project_table["project_path"] = str(root)
    node = _table(_table(project_table, "mods"), mod)
    *parents, last = path
    for key in parents:
        node = _table(node, key)
    node[last] = value

    try:
        _write_atomically(target, tomli_w.dumps(data))
    except (OSError, TypeError, ValueError) as e:
        raise ConfigWriteError(file_path=str(target), original_exception=e)


def _table(parent: dict, key: str) -> dict:
    """`parent[key]` as a table, replacing a value of another shape the setting cannot live in."""
    node = parent.get(key)
    if not isinstance(node, dict):
        node = parent[key] = {}
    return node


def _write_atomically(target: Path, text: str) -> None:
    """Replace `target` in one step: a crash mid-write must not truncate the user's config."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_mod_enabled(
    mod: str, enabled: bool, project_root: Optional[Path] = None, config_path: Optional[Path] = None
) -> None:
    set_mod_setting(mod, ("enabled",), enabled, project_root, config_path)


def set_mod_section(
    mod: str, section: str, enabled: bool, project_root: Optional[Path] = None, config_path: Optional[Path] = None
) -> None:
    set_mod_setting(mod, ("sections", section), enabled, project_root, config_path)
