"""
Finds, configures and loads mods.

A mod is a folder holding `mod.toml` (what it is, what it needs, which events
and slots it uses, its option defaults) and `mod.py` (`register(on, options)`).
Titan reads the manifest without executing anything, so a mod can be listed,
explained and switched off before its code ever runs.

The folder is imported as the package `titan_mod_<name>`, `mod.py` being its
`__init__`: a big mod splits into its own modules and imports them relatively
(`from .sections import prs`). The folder is never put on `sys.path`, so two
mods may each have a `sections` without one shadowing the other.

Sources, from the widest to the most personal; a later one overrides an
earlier one of the same name:

    titan mods     titan_cli/mods/<name>/       shipped with Titan, for anyone
    plugin mods    each enabled plugin's `mods_path`
    project mods   <repo root>/.titan/mods/<name>/   shared with the team
    user mods      ~/.titan/mods/<name>/        the user's own
    dev mods       extra mod folders, see below

A mod being developed lives in its own checkout, anywhere on disk. Each path
in `[mods] dirs` (user config only, never the project's), in TITAN_MOD_DIRS
(separated like PATH) and in each `--mod-dir` is one mod folder, loaded above
every other source; there the manifest's name wins over the folder's, so a
checkout called `titan-mod-x` can hold the mod `x`. A path that does not
exist or holds no mod is logged and skipped. Titan does not watch them:
editing a mod means restarting Titan.

A project mod runs from the repo as `.titan/steps` already do: committing it
is sharing it with whoever runs Titan there.

A mod is enabled by being there; `[mods.<name>] enabled = false` in
`~/.titan/config.toml` turns any mod off, and `[mods.<name>.options]`
overrides the manifest's option defaults. `dirs` is therefore not a mod name.

Mods are trusted, in-process code: nothing here sandboxes them. A mod that
fails to parse, import or register is logged and left out whole (no hook it
registered before failing stays); it never stops Titan from starting.
"""

import importlib.util
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from titan_cli.core.logging import get_logger

from .bus import ModBus

logger = get_logger(__name__)

MANIFEST = "mod.toml"
ENTRYPOINT = "mod.py"
TITAN_MODS = Path(__file__).resolve().parents[2] / "mods"
PROJECT_MODS = Path(".titan") / "mods"  # under the project root
USER_MODS = Path.home() / ".titan" / "mods"
USER_CONFIG = Path.home() / ".titan" / "config.toml"
MOD_DIRS_ENV = "TITAN_MOD_DIRS"
DIRS_KEY = "dirs"  # `[mods] dirs`: the extra mod folders, not a mod
DEV = "dev"
# Also a package name segment: a `.` would split it, so not allowed.
VALID_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
PACKAGE_PREFIX = "titan_mod_"


@dataclass(frozen=True)
class ModManifest:
    name: str
    version: str
    description: str
    source: str  # "titan", "plugin:<name>", "project", "user" or "dev"
    folder: Path
    requires_plugins: Tuple[str, ...] = ()
    events: Tuple[str, ...] = ()
    slots: Tuple[str, ...] = ()
    options: Dict[str, Any] = field(default_factory=dict)
    # The label of the routing task `mods.<name>` its `m.ai` calls run under, when it
    # uses AI: the AI screen lists the task with it, so it can be pinned there too.
    ai_task: Optional[str] = None
    # What the side panel's rail shows for the mod's pane: one character or emoji.
    icon: Optional[str] = None

    @property
    def entrypoint(self) -> Path:
        return self.folder / ENTRYPOINT


def read_manifest(folder: Path, source: str) -> ModManifest:
    """Parse `<folder>/mod.toml`. Raises ValueError when it is missing or malformed."""
    path = folder / MANIFEST
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ValueError(f"{path}: {e}") from e

    mod = data.get("mod", {})
    name = mod.get("name") or folder.name
    if not VALID_NAME.fullmatch(name):
        raise ValueError(f"{path}: name '{name}' must be letters, digits, '_' or '-', up to 64")
    if name == DIRS_KEY:
        raise ValueError(f"{path}: '{DIRS_KEY}' is reserved in [mods] and cannot name a mod")
    # Under a mods root the folder is the name; a dev folder is a checkout named freely.
    if source != DEV and name != folder.name:
        raise ValueError(f"{path}: name '{name}' does not match its folder '{folder.name}'")
    return ModManifest(
        name=name,
        version=str(mod.get("version", "0.0.0")),
        description=mod.get("description", ""),
        source=source,
        folder=folder,
        requires_plugins=tuple(mod.get("requires_plugins", [])),
        events=tuple(mod.get("events", [])),
        slots=tuple(mod.get("slots", [])),
        options=dict(data.get("options", {})),
        ai_task=mod.get("ai_task") or None,
        icon=mod.get("icon") or None,
    )


def discover_mods(sources: List[Tuple[str, Path]]) -> Dict[str, ModManifest]:
    """
    Every mod under each `(source, root)`, later sources overriding earlier by name.

    A root holds one mod per subfolder, except a "dev" root, which is the mod folder itself.
    """
    found: Dict[str, ModManifest] = {}
    for source, root in sources:
        if source == DEV:
            if not (root / MANIFEST).is_file():
                logger.warning("mod_dir_without_mod", path=str(root))
                continue
            folders = [root]
        elif root.is_dir():
            folders = sorted(p for p in root.iterdir() if p.is_dir() and (p / MANIFEST).is_file())
        else:
            continue
        for folder in folders:
            try:
                manifest = read_manifest(folder, source)
            except ValueError:
                logger.exception("mod_manifest_invalid", path=str(folder))
                continue
            if not manifest.entrypoint.is_file():
                logger.warning("mod_entrypoint_missing", mod=manifest.name, path=str(folder))
                continue
            found[manifest.name] = manifest
    return found


def mod_sources(
    plugin_mod_paths: Dict[str, Path],
    project_root: Optional[Path] = None,
    user_root: Optional[Path] = None,
    titan_root: Optional[Path] = None,
    dev_dirs: Sequence[Path] = (),
) -> List[Tuple[str, Path]]:
    """Every place mods live, in override order (see the module docstring)."""
    sources = [("titan", titan_root or TITAN_MODS)]
    sources += [(f"plugin:{plugin}", path) for plugin, path in sorted(plugin_mod_paths.items())]
    if project_root is not None:
        sources.append(("project", project_root / PROJECT_MODS))
    sources.append(("user", user_root or USER_MODS))
    sources += [(DEV, folder) for folder in dev_dirs]
    return sources


def project_root() -> Optional[Path]:
    """The project Titan runs in (git root, else the working directory)."""
    from titan_cli.core.utils import find_project_root

    try:
        return Path(find_project_root())
    except Exception:
        return None


def _read_mods_table(config_path: Optional[Path]) -> Dict[str, Any]:
    try:
        return tomllib.loads((config_path or USER_CONFIG).read_text()).get("mods", {})
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def read_mods_config(config_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """The `[mods.<name>]` tables of the user config, or nothing."""
    return {name: table for name, table in _read_mods_table(config_path).items() if name != DIRS_KEY}


def mod_dirs(
    cli_dirs: Sequence[str] = (),
    config_path: Optional[Path] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> List[Path]:
    """
    The extra mod folders: `[mods] dirs`, then TITAN_MOD_DIRS, then `--mod-dir`.

    The most explicit comes last, so it wins when two folders hold a mod of the same name.
    """
    configured = _read_mods_table(config_path).get(DIRS_KEY, [])
    if not isinstance(configured, list) or not all(isinstance(d, str) for d in configured):
        logger.warning("mod_dirs_config_invalid", value=repr(configured))
        configured = []
    env = (os.environ if environ is None else environ).get(MOD_DIRS_ENV, "")
    raw = [*configured, *env.split(os.pathsep), *cli_dirs]

    folders: List[Path] = []
    for entry in raw:
        if not entry.strip():
            continue
        folder = Path(entry.strip()).expanduser().resolve()
        if folder in folders:
            folders.remove(folder)
        folders.append(folder)
    return folders


def _forget_modules(package: str) -> None:
    for module in [m for m in sys.modules if m == package or m.startswith(package + ".")]:
        del sys.modules[module]


def import_mod(folder: Path, name: Optional[str] = None) -> ModuleType:
    """
    Import a mod's folder as the package `titan_mod_<name>`, `mod.py` being its `__init__`.

    `name` defaults to the folder's. Whatever the mod imported before, under that package, is
    dropped first; when the import fails nothing of it stays in `sys.modules`. A mod's own
    tests use this to import it exactly as Titan does.
    """
    package = PACKAGE_PREFIX + (name or folder.name)
    _forget_modules(package)
    spec = importlib.util.spec_from_file_location(
        package, folder / ENTRYPOINT, submodule_search_locations=[str(folder)]
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {folder / ENTRYPOINT}")
    module = importlib.util.module_from_spec(spec)
    # Registered before running, as the import system does: relative imports look it up.
    sys.modules[package] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        _forget_modules(package)
        raise
    return module


def load_mods(
    bus: ModBus,
    mods: Dict[str, ModManifest],
    mods_config: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[str]:
    """Import each enabled mod and run its `register`. Returns the names that loaded."""
    mods_config = mods_config or {}
    loaded: List[str] = []
    for name, manifest in mods.items():
        config = mods_config.get(name, {})
        if config.get("enabled", True) is False:
            logger.info("mod_disabled", mod=name, source=manifest.source)
            continue
        options = {**manifest.options, **config.get("options", {})}
        try:
            module = import_mod(manifest.folder, name)
            register = getattr(module, "register", None)
            if not callable(register):
                raise AttributeError(f"{manifest.entrypoint} defines no register(on, options)")
            register(bus.on_for(name), options)
        except Exception:
            # All or nothing: hooks a register() added before failing would run
            # for a mod that is reported as not loaded, and its modules would linger.
            bus.forget(name)
            _forget_modules(PACKAGE_PREFIX + name)
            logger.exception("mod_load_failed", mod=name, path=str(manifest.folder))
            continue
        loaded.append(name)
        bus.manifests[name] = manifest
        logger.info("mod_loaded", mod=name, source=manifest.source, version=manifest.version)
    return loaded


def build_mod_bus(
    plugin_mod_paths: Optional[Dict[str, Path]] = None,
    cli_mod_dirs: Sequence[str] = (),
) -> ModBus:
    bus = ModBus()
    sources = mod_sources(plugin_mod_paths or {}, project_root(), dev_dirs=mod_dirs(cli_mod_dirs))
    load_mods(bus, discover_mods(sources), read_mods_config())
    return bus
