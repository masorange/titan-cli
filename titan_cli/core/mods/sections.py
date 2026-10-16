"""
Mod sections: parts of one mod the user can switch on or off one by one.

A mod declares them in `mod.toml`:

    [sections.queue]
    title = "Merge queue"
    description = "Your place in the merge queue."
    default = true

The user turns one off in `[mods.<name>.sections]` of `~/.titan/config.toml`
(`queue = false`). The mod receives the result as `options["sections"]`, a
`{name: bool}` for every section it declares, and decides what a switched-off
section stops doing (polling, drawing). Titan only keeps the switches.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple


@dataclass(frozen=True)
class SectionSpec:
    name: str
    title: str = ""
    description: str = ""
    default: bool = True


def parse_section_specs(table: Mapping[str, Any]) -> Dict[str, SectionSpec]:
    """Build the specs from the manifest's `[sections]` table. Raises ValueError when malformed."""
    specs: Dict[str, SectionSpec] = {}
    for name, raw in table.items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"section '{name}' must be a table, e.g. [sections.{name}]")
        unknown = set(raw) - {"title", "description", "default"}
        if unknown:
            raise ValueError(f"section '{name}': unknown key(s) {sorted(unknown)}")
        default = raw.get("default", True)
        if not isinstance(default, bool):
            raise ValueError(f"section '{name}': default must be true or false, got {default!r}")
        specs[name] = SectionSpec(
            name=name,
            title=str(raw.get("title", name)),
            description=str(raw.get("description", "")),
            default=default,
        )
    return specs


def resolve_sections(
    specs: Mapping[str, SectionSpec], overrides: Mapping[str, Any]
) -> Tuple[Dict[str, bool], List[Tuple[str, str]]]:
    """Defaults overridden by the user's switches. Returns (switches, [(section, reason)] dropped)."""
    switches = {name: spec.default for name, spec in specs.items()}
    dropped: List[Tuple[str, str]] = []
    for name, value in overrides.items():
        if name not in specs:
            dropped.append((name, "not declared in mod.toml"))
        elif not isinstance(value, bool):
            dropped.append((name, f"expected true or false, got {value!r}"))
        else:
            switches[name] = value
    return switches, dropped
