"""Writes a mod's `[mods.<name>]` settings to the user's own global config.

Unlike a plugin - a fact of the repo the team shares via the project's own
`.titan/config.toml` - which mod is on and which of its sections you want is personal:
whether you like to see the merge queue is not something a teammate's commit should
decide for you. So a switch here lands in `~/.titan/config.toml`, scoped to the active
project under the same `project_sources.<key>` block a plugin's `dev_local` override and
a favorite workflow already use (`core/config.py`), never in the project's own file.
"""

from pathlib import Path
from typing import Any, Optional, Sequence

import tomli_w
import tomllib

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

    root = (project_root or active_project_root() or Path.cwd()).resolve()
    project_table = data.setdefault("project_sources", {}).setdefault(project_source_scope_key(root), {})
    project_table["project_path"] = str(root)
    node = project_table.setdefault("mods", {}).setdefault(mod, {})
    *parents, last = path
    for key in parents:
        node = node.setdefault(key, {})
    node[last] = value

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(tomli_w.dumps(data))


def set_mod_enabled(
    mod: str, enabled: bool, project_root: Optional[Path] = None, config_path: Optional[Path] = None
) -> None:
    set_mod_setting(mod, ("enabled",), enabled, project_root, config_path)


def set_mod_section(
    mod: str, section: str, enabled: bool, project_root: Optional[Path] = None, config_path: Optional[Path] = None
) -> None:
    set_mod_setting(mod, ("sections", section), enabled, project_root, config_path)
