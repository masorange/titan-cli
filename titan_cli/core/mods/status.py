"""What became of every mod Titan found: loaded, switched off, or failed."""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

LOADED = "loaded"
DISABLED = "disabled"
FAILED = "failed"


@dataclass(frozen=True)
class ModStatus:
    name: str
    state: str  # LOADED, DISABLED or FAILED
    # The reason it failed; only for FAILED.
    error: Optional[str] = None


SOURCE_ORDER = ("titan", "plugin", "project", "user", "dev")


def source_kind(source: str) -> str:
    """"plugin:github" -> "plugin"."""
    return source.split(":", 1)[0]


@dataclass(frozen=True)
class ModEntry:
    """One mod as the Mods screen lists it: what it is, what became of it, what is saved."""

    manifest: Any
    status: ModStatus
    # What the config says now.
    enabled: bool
    sections: Dict[str, bool]

    @property
    def name(self) -> str:
        return self.manifest.name


def mod_entries(found: Mapping[str, Any], statuses: Mapping[str, ModStatus], mods_config: Mapping[str, Mapping[str, Any]]) -> List[ModEntry]:
    """Every mod found, widest source first, then by name."""
    from .sections import resolve_sections

    entries = []
    for name, manifest in found.items():
        config = mods_config.get(name, {})
        entries.append(
            ModEntry(
                manifest=manifest,
                status=statuses.get(name, ModStatus(name, LOADED)),
                enabled=config.get("enabled", True) is not False,
                sections=resolve_sections(manifest.sections, config.get("sections", {}))[0],
            )
        )

    def order(e: ModEntry):
        kind = source_kind(e.manifest.source)
        return (SOURCE_ORDER.index(kind) if kind in SOURCE_ORDER else len(SOURCE_ORDER), e.name)

    return sorted(entries, key=order)
