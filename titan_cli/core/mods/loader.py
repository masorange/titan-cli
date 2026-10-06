"""
Finds, configures and loads mods.

A mod is a folder holding `mod.toml` (what it is, what it needs, which events
and slots it uses, its option defaults) and `mod.py` (`register(on, options)`).
Titan reads the manifest without executing anything, so a mod can be listed,
explained and switched off before its code ever runs.

Sources, later overriding earlier by name:

    plugin mods   each enabled plugin's `mods_path`
    user mods     ~/.titan/mods/<name>/

Project mods (`<repo>/.titan/mods/`) are deliberately not read: they would run
at start-up straight from a cloned repo, so they wait for a consent flow.

A user mod is enabled by being there; `[mods.<name>] enabled = false` in
`~/.titan/config.toml` turns any mod off, and `[mods.<name>.options]`
overrides the manifest's option defaults.

Mods are trusted, in-process code: nothing here sandboxes them. A mod that
fails to parse, import or register is logged and left out; it never stops
Titan from starting.
"""

import importlib.util
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from titan_cli.core.logging import get_logger

from .bus import ModBus

logger = get_logger(__name__)

MANIFEST = "mod.toml"
ENTRYPOINT = "mod.py"
USER_MODS = Path.home() / ".titan" / "mods"
USER_CONFIG = Path.home() / ".titan" / "config.toml"


@dataclass(frozen=True)
class ModManifest:
    name: str
    version: str
    description: str
    source: str  # "user" or "plugin:<name>"
    folder: Path
    requires_plugins: Tuple[str, ...] = ()
    events: Tuple[str, ...] = ()
    slots: Tuple[str, ...] = ()
    options: Dict[str, Any] = field(default_factory=dict)

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
    if name != folder.name:
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
    )


def discover_mods(sources: List[Tuple[str, Path]]) -> Dict[str, ModManifest]:
    """Every mod folder under each `(source, root)`, later sources overriding earlier by name."""
    found: Dict[str, ModManifest] = {}
    for source, root in sources:
        if not root.is_dir():
            continue
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            if not (folder / MANIFEST).is_file():
                continue
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


def mod_sources(plugin_mod_paths: Dict[str, Path], user_root: Optional[Path] = None) -> List[Tuple[str, Path]]:
    sources = [(f"plugin:{plugin}", path) for plugin, path in sorted(plugin_mod_paths.items())]
    sources.append(("user", user_root or USER_MODS))
    return sources


def read_mods_config(config_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """The `[mods.*]` tables of the user config, or nothing."""
    try:
        return tomllib.loads((config_path or USER_CONFIG).read_text()).get("mods", {})
    except (OSError, tomllib.TOMLDecodeError):
        return {}


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
            spec = importlib.util.spec_from_file_location(f"titan_mod_{name}", manifest.entrypoint)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot import {manifest.entrypoint}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            register = getattr(module, "register", None)
            if not callable(register):
                raise AttributeError(f"{manifest.entrypoint} defines no register(on, options)")
            register(bus.on_for(name), options)
        except Exception:
            logger.exception("mod_load_failed", mod=name, path=str(manifest.folder))
            continue
        loaded.append(name)
        logger.info("mod_loaded", mod=name, source=manifest.source, version=manifest.version)
    return loaded


def build_mod_bus(plugin_mod_paths: Optional[Dict[str, Path]] = None) -> ModBus:
    bus = ModBus()
    load_mods(bus, discover_mods(mod_sources(plugin_mod_paths or {})), read_mods_config())
    return bus
