"""Writes a mod's `[mods.<name>]` settings to the project's `.titan/config.toml`.

Like plugins, a mod is switched on or off per project: the file is the project's, so the
change holds there and nowhere else. The user's `~/.titan/config.toml` stays the
background for every project and is edited by hand.
"""

from pathlib import Path
from typing import Any, Optional, Sequence

import tomli_w
import tomllib


class NoProjectConfig(Exception):
    """There is no `.titan/config.toml` to write: Titan is not set up for this project."""


def set_mod_setting(mod: str, path: Sequence[str], value: Any, config_path: Optional[Path] = None) -> None:
    """Set `[mods.<mod>.<path...>] = value` in the project's config, keeping the rest of it."""
    from .loader import project_config_file

    target = config_path or project_config_file()
    if target is None or not target.exists():
        raise NoProjectConfig("No project configuration found")
    data = tomllib.loads(target.read_text())
    node = data.setdefault("mods", {}).setdefault(mod, {})
    *parents, last = path
    for key in parents:
        node = node.setdefault(key, {})
    node[last] = value
    target.write_text(tomli_w.dumps(data))


def set_mod_enabled(mod: str, enabled: bool, config_path: Optional[Path] = None) -> None:
    set_mod_setting(mod, ("enabled",), enabled, config_path)


def set_mod_section(mod: str, section: str, enabled: bool, config_path: Optional[Path] = None) -> None:
    set_mod_setting(mod, ("sections", section), enabled, config_path)
