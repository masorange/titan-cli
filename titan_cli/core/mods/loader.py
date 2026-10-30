"""
Finds, configures and loads mods.

A mod is a folder holding `mod.toml` (what it is, what it needs, which events
and slots it uses, its typed options) and `mod.py` (`register(on, options)`).
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

A mod is enabled by being there; `[mods.<name>] enabled = false` in the user's
`~/.titan/config.toml` turns any mod off everywhere, for every project, and its
`[mods.<name>.sections]` switches its sections one by one, the same way. Whether that
holds for one project in particular is the user's own choice there, kept in the same
file under `project_sources.<key>.mods.<name>` (`core/mods/settings.py`): personal, like
a favorite workflow or a plugin's `dev_local` override, never written to the project's
own `.titan/config.toml` - unlike a plugin, which project a mod runs in is not a fact
the project gets to assert about anyone else running Titan there. `[mods.<name>.options]`
overrides the manifest's option defaults (see `options.py`), not scoped per project.
`dirs` is therefore not a mod name.

A mod hooks only the events its manifest lists: hooking another fails its
register, so what Titan shows before running a mod is all it can hook.

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
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence, Tuple

from titan_cli.core.logging import get_logger
from titan_cli.core.utils import project_source_scope_key

from .bus import ModBus
from .options import OptionSpec, parse_option_specs, resolve_options
from .sections import SectionSpec, parse_section_specs, resolve_sections
from .status import DISABLED, FAILED, LOADED, ModStatus

logger = get_logger(__name__)

TITAN_WORKSPACES = Path(__file__).resolve().parents[2] / "workspaces"
USER_WORKSPACES = Path.home() / ".titan" / "workspaces"
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
class Kind:
    """
    What differs between the things this loader finds: a mod and a workspace are the same
    shape (a folder with a manifest and an entry point, many sources, one config table) under
    other names. `MODS` is what every function below defaults to.
    """

    noun: str  # "mod" or "workspace": the manifest's table and the word in logs and errors
    manifest: str
    entrypoint: str
    package_prefix: str
    config_table: str  # `[<table>.<name>]` in the user's config, and `project_sources.<key>.<table>`
    dirs_env: str
    # Folders under Titan, a project's `.titan/` and the user's `~/.titan/`. `titan_root` and
    # `user_dir` are read when used, not held, so a test can point the module's constant elsewhere.
    titan_root_name: str
    project_dir: Path
    user_dir_name: str
    # What the bus puts before a name for Titan's host (see `ModBus`), and where its store lives
    host_prefix: str = ""
    store_dir: str = ""
    register_args: str = "on, options"  # for the error of an entry point with no `register`

    @property
    def titan_root(self) -> Path:
        return globals()[self.titan_root_name]

    @property
    def user_dir(self) -> Path:
        return globals()[self.user_dir_name]


MODS = Kind(
    noun="mod",
    manifest=MANIFEST,
    entrypoint=ENTRYPOINT,
    package_prefix=PACKAGE_PREFIX,
    config_table="mods",
    dirs_env=MOD_DIRS_ENV,
    titan_root_name="TITAN_MODS",
    project_dir=PROJECT_MODS,
    user_dir_name="USER_MODS",
)

WORKSPACES = Kind(
    noun="workspace",
    manifest="workspace.toml",
    entrypoint="workspace.py",
    package_prefix="titan_workspace_",
    config_table="workspaces",
    dirs_env="TITAN_WORKSPACE_DIRS",
    titan_root_name="TITAN_WORKSPACES",
    project_dir=Path(".titan") / "workspaces",
    user_dir_name="USER_WORKSPACES",
    host_prefix="workspace.",
    store_dir="workspaces",
    register_args="w, on, options",
)


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
    options: Dict[str, OptionSpec] = field(default_factory=dict)
    # Parts of the mod the user can switch on or off one by one.
    sections: Dict[str, SectionSpec] = field(default_factory=dict)
    # The label of the routing task `mods.<name>` its `m.ai` calls run under, when it
    # uses AI: the AI screen lists the task with it, so it can be pinned there too.
    ai_task: Optional[str] = None
    # The label of the task `mods.<name>.assist`, which decides what a help button
    # (`ai_assist_button`) opens; separate from `ai_task` because it can be an
    # interactive CLI, which a one-shot `m.ai.complete` could never run.
    ai_assist_task: Optional[str] = None
    # What the side panel's rail shows for the mod's pane: one character or emoji.
    icon: Optional[str] = None
    # The file `register` is in, which is the kind's (`mod.py`, `workspace.py`).
    entry_file: str = ENTRYPOINT

    @property
    def entrypoint(self) -> Path:
        return self.folder / self.entry_file


def read_manifest(folder: Path, source: str, kind: Kind = MODS) -> ModManifest:
    """Parse `<folder>/mod.toml` (`workspace.toml` for a workspace). Raises ValueError when it is missing or malformed."""
    path = folder / kind.manifest
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ValueError(f"{path}: {e}") from e

    mod = data.get(kind.noun, {})
    if not isinstance(mod, dict):
        raise ValueError(f"{path}: [{kind.noun}] must be a table")
    name = mod.get("name") or folder.name
    if not isinstance(name, str):
        raise ValueError(f"{path}: name must be a string")
    for key in ("requires_plugins", "events", "slots"):
        value = mod.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"{path}: {key} must be a list of strings")
    for key in ("options", "sections"):
        if not isinstance(data.get(key, {}), dict):
            raise ValueError(f"{path}: [{key}] must be a table")
    if not VALID_NAME.fullmatch(name):
        raise ValueError(f"{path}: name '{name}' must be letters, digits, '_' or '-', up to 64")
    if name == DIRS_KEY:
        raise ValueError(f"{path}: '{DIRS_KEY}' is reserved in [{kind.config_table}] and cannot name a {kind.noun}")
    # Under a mods root the folder is the name; a dev folder is a checkout named freely.
    if source != DEV and name != folder.name:
        raise ValueError(f"{path}: name '{name}' does not match its folder '{folder.name}'")
    try:
        options = parse_option_specs(data.get("options", {}))
        sections = parse_section_specs(data.get("sections", {}))
    except ValueError as e:
        raise ValueError(f"{path}: {e}") from e
    return ModManifest(
        name=name,
        version=str(mod.get("version", "0.0.0")),
        description=mod.get("description", ""),
        source=source,
        folder=folder,
        requires_plugins=tuple(mod.get("requires_plugins", [])),
        events=tuple(mod.get("events", [])),
        slots=tuple(mod.get("slots", [])),
        options=options,
        sections=sections,
        ai_task=mod.get("ai_task") or None,
        ai_assist_task=mod.get("ai_assist_task") or None,
        icon=mod.get("icon") or None,
        entry_file=kind.entrypoint,
    )


def discover_mods(sources: List[Tuple[str, Path]], kind: Kind = MODS) -> Dict[str, ModManifest]:
    """
    Every mod under each `(source, root)`, later sources overriding earlier by name.

    A root holds one mod per subfolder, except a "dev" root, which is the mod folder itself.
    """
    found: Dict[str, ModManifest] = {}
    for source, root in sources:
        if source == DEV:
            if not (root / kind.manifest).is_file():
                logger.warning(f"{kind.noun}_dir_without_{kind.noun}", path=str(root))
                continue
            folders = [root]
        elif root.is_dir():
            folders = sorted(p for p in root.iterdir() if p.is_dir() and (p / kind.manifest).is_file())
        else:
            continue
        for folder in folders:
            try:
                manifest = read_manifest(folder, source, kind)
            except Exception:  # a bad manifest of any shape must not stop Titan starting
                logger.exception(f"{kind.noun}_manifest_invalid", path=str(folder))
                continue
            if not manifest.entrypoint.is_file():
                logger.warning(f"{kind.noun}_entrypoint_missing", mod=manifest.name, path=str(folder))
                continue
            if manifest.name in found:
                logger.warning(
                    f"{kind.noun}_overrides_{kind.noun}",
                    mod=manifest.name,
                    source=manifest.source,
                    replaces=found[manifest.name].source,
                    path=str(folder),
                )
            found[manifest.name] = manifest
    return found


def mod_sources(
    plugin_mod_paths: Dict[str, Path],
    project_root: Optional[Path] = None,
    user_root: Optional[Path] = None,
    titan_root: Optional[Path] = None,
    dev_dirs: Sequence[Path] = (),
    kind: Kind = MODS,
) -> List[Tuple[str, Path]]:
    """Every place mods live, in override order (see the module docstring)."""
    sources = [("titan", titan_root or kind.titan_root)]
    sources += [(f"plugin:{plugin}", path) for plugin, path in sorted(plugin_mod_paths.items())]
    if project_root is not None:
        sources.append(("project", project_root / kind.project_dir))
    sources.append(("user", user_root or kind.user_dir))
    sources += [(DEV, folder) for folder in dev_dirs]
    return sources


def project_root() -> Optional[Path]:
    """The project Titan runs in (git root, else the working directory)."""
    from titan_cli.core.utils import find_project_root

    try:
        return Path(find_project_root())
    except Exception:
        return None


def _read_config(config_path: Optional[Path]) -> Dict[str, Any]:
    try:
        return tomllib.loads((config_path or USER_CONFIG).read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _read_mods_table(config_path: Optional[Path], kind: Kind = MODS) -> Dict[str, Any]:
    mods = _read_config(config_path).get(kind.config_table, {})
    return mods if isinstance(mods, dict) else {}


def read_mods_config(
    config_path: Optional[Path] = None, project_root_path: Optional[Path] = None, kind: Kind = MODS
) -> Dict[str, Dict[str, Any]]:
    """
    The `[mods.<name>]` tables as they apply here: the background default (the same file's
    top-level `[mods.<name>]`, which applies to every project) overridden by the user's own
    choice for this one project, kept in the same file under
    `project_sources.<key>.mods.<name>` (`core/mods/settings.py`).

    The project-scoped override decides `enabled` and each of `sections`; options and `dirs`
    are the background default only, not scoped per project.
    """
    data = _read_config(config_path)
    mods = data.get(kind.config_table, {})
    config: Dict[str, Dict[str, Any]] = {}
    for name, table in (mods.items() if isinstance(mods, dict) else ()):
        if name == DIRS_KEY:
            continue
        if not isinstance(table, dict):
            logger.warning("mod_config_invalid", mod=name, reason="not a table")
            continue
        entry = dict(table)
        for key in ("options", "sections"):
            if key in entry and not isinstance(entry[key], dict):
                logger.warning("mod_config_invalid", mod=name, key=key, reason="not a table")
                entry[key] = {}
        config[name] = entry
    root = project_root_path if project_root_path is not None else project_root()
    if root is None:
        return config
    scoped = data.get("project_sources", {})
    scoped = scoped.get(project_source_scope_key(root), {}) if isinstance(scoped, dict) else {}
    scoped_mods = scoped.get(kind.config_table, {}) if isinstance(scoped, dict) else {}
    if not isinstance(scoped_mods, dict):
        return config
    for name, table in scoped_mods.items():
        if not isinstance(table, dict):
            continue
        mine = config.setdefault(name, {})
        if isinstance(table.get("enabled"), bool):
            mine["enabled"] = table["enabled"]
        if isinstance(table.get("sections"), dict):
            mine["sections"] = {**mine.get("sections", {}), **table["sections"]}
    return config


def mod_dirs(
    cli_dirs: Sequence[str] = (),
    config_path: Optional[Path] = None,
    environ: Optional[Mapping[str, str]] = None,
    kind: Kind = MODS,
) -> List[Path]:
    """
    The extra mod folders: `[mods] dirs`, then TITAN_MOD_DIRS, then `--mod-dir`.

    The most explicit comes last, so it wins when two folders hold a mod of the same name.
    """
    configured = _read_mods_table(config_path, kind).get(DIRS_KEY, [])
    if not isinstance(configured, list) or not all(isinstance(d, str) for d in configured):
        logger.warning("mod_dirs_config_invalid", value=repr(configured))
        configured = []
    env = (os.environ if environ is None else environ).get(kind.dirs_env, "")
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


def import_mod(folder: Path, name: Optional[str] = None, kind: Kind = MODS) -> ModuleType:
    """
    Import a mod's folder as the package `titan_mod_<name>`, `mod.py` being its `__init__`.

    `name` defaults to the folder's. Whatever the mod imported before, under that package, is
    dropped first; when the import fails nothing of it stays in `sys.modules`. A mod's own
    tests use this to import it exactly as Titan does.
    """
    package = kind.package_prefix + (name or folder.name)
    _forget_modules(package)
    spec = importlib.util.spec_from_file_location(
        package, folder / kind.entrypoint, submodule_search_locations=[str(folder)]
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {folder / kind.entrypoint}")
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
    *,
    enabled_plugins: Optional[Collection[str]] = None,
    kind: Kind = MODS,
) -> List[str]:
    """
    Import each enabled mod and run its `register`. Returns the names that loaded.

    With `enabled_plugins`, a mod whose `requires_plugins` are not all among them fails
    unimported; None means the set is unknown and nothing is checked.
    """
    mods_config = mods_config or {}
    if enabled_plugins is not None:
        bus.enabled_plugins = frozenset(enabled_plugins)
    loaded: List[str] = []
    for name, manifest in mods.items():
        bus.found[name] = manifest
        if _load_one(bus, name, manifest, mods_config.get(name, {}), bus.enabled_plugins, kind):
            loaded.append(name)
    return loaded


def reload_mod(
    bus: ModBus,
    name: str,
    mods_config: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    enabled_plugins: Optional[Collection[str]] = None,
    kind: Kind = MODS,
) -> str:
    """
    Unload one mod and load it again with the current config, as if Titan had just started
    with it: switch it on or off, or apply changed options and sections.

    Re-reads its `mod.toml` and re-imports its code. Everything the old copy registered
    (hooks, timers, keys, panes, badges, its dock tile) goes; a thread it left running
    can no longer reach Titan, and what it keeps in `m.state` is lost (`m.store` stays).
    Call it on the UI thread. Returns the mod's new state: loaded, disabled or failed.
    `enabled_plugins` defaults to the set the bus was loaded with.
    """
    if enabled_plugins is None:
        enabled_plugins = bus.enabled_plugins
    previous = bus.found.get(name)
    if previous is None:
        raise KeyError(f"no mod named '{name}'")
    bus.unload(name)
    try:
        manifest = read_manifest(previous.folder, previous.source, kind)
    except Exception as e:
        bus.statuses[name] = ModStatus(name, FAILED, error=str(e))
        logger.error("mod_reload_failed", mod=name, reason=str(e))
        return FAILED
    bus.found[name] = manifest
    if _load_one(bus, name, manifest, (mods_config or {}).get(name, {}), enabled_plugins, kind):
        # The mod missed Titan's own `app.start`: give it one of its own.
        if kind is not MODS:
            bus.start(name)
        elif bus.started is not None:
            bus.dispatch("app.start", bus.started, lambda e: None, mod=name)
    return bus.statuses[name].state


def _load_one(
    bus: ModBus,
    name: str,
    manifest: ModManifest,
    config: Dict[str, Any],
    enabled_plugins: Optional[Collection[str]] = None,
    kind: Kind = MODS,
) -> bool:
    if config.get("enabled", True) is False:
        logger.info(f"{kind.noun}_disabled", mod=name, source=manifest.source)
        bus.statuses[name] = ModStatus(name, DISABLED)
        return False
    if enabled_plugins is not None:
        missing = set(manifest.requires_plugins) - set(enabled_plugins)
        if missing:
            logger.warning(f"{kind.noun}_plugins_missing", mod=name, missing=sorted(missing))
            bus.statuses[name] = ModStatus(
                name, FAILED, error=f"needs plugin(s) not enabled: {', '.join(sorted(missing))}"
            )
            return False
    options, dropped = resolve_options(manifest.options, config.get("options", {}))
    for option, _reason in dropped:
        # The reason quotes the offending value, which may be a secret typed into a
        # string option: log which option was dropped, never what was in it.
        logger.warning(f"{kind.noun}_option_dropped", mod=name, option=option)
    options["sections"], dropped = resolve_sections(manifest.sections, config.get("sections", {}))
    for section, reason in dropped:
        logger.warning(f"{kind.noun}_section_dropped", mod=name, section=section, reason=reason)
    try:
        module = import_mod(manifest.folder, name, kind)
        register = getattr(module, "register", None)
        if not callable(register):
            raise AttributeError(f"{manifest.entrypoint} defines no register({kind.register_args})")
        # A mod gets `on` to hook events; a workspace its own handle (`w`, the same `ModAPI`) and `on`.
        on = bus.on_for(name, manifest.events)
        register(on, options) if kind is MODS else register(bus.api(name), on, options)
    except (Exception, SystemExit) as e:  # a mod calling sys.exit() must not stop Titan starting
        bus.statuses[name] = ModStatus(name, FAILED, error=f"{type(e).__name__}: {e}")
        # All or nothing: hooks a register() added before failing would run
        # for a mod that is reported as not loaded, and its modules would linger.
        bus.unload(name)
        _forget_modules(kind.package_prefix + name)
        logger.exception(f"{kind.noun}_load_failed", mod=name, path=str(manifest.folder))
        return False
    bus.sections[name] = options["sections"]
    bus.statuses[name] = ModStatus(name, LOADED)
    bus.manifests[name] = manifest
    logger.info(f"{kind.noun}_loaded", mod=name, source=manifest.source, version=manifest.version)
    return True


def build_mod_bus(
    plugin_mod_paths: Optional[Dict[str, Path]] = None,
    cli_mod_dirs: Sequence[str] = (),
    enabled_plugins: Optional[Collection[str]] = None,
    kind: Kind = MODS,
) -> ModBus:
    """The bus of every `kind` found and loaded: mods by default, `WORKSPACES` for the workspaces."""
    bus = ModBus(prefix=kind.host_prefix, store_dir=kind.store_dir)
    sources = mod_sources(plugin_mod_paths or {}, project_root(), dev_dirs=mod_dirs(cli_mod_dirs, kind=kind), kind=kind)
    load_mods(bus, discover_mods(sources, kind), read_mods_config(kind=kind), enabled_plugins=enabled_plugins, kind=kind)
    return bus
