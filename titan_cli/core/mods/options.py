"""
Typed mod options.

A mod declares each option in `mod.toml` as a table under `[options]`:

    [options.shown]
    type = "int"
    title = "Issues shown"
    description = "How many issues the card lists."
    default = 10
    min = 1
    max = 50

`type` is one of string, int, float, bool, list (of strings) or choice (which also takes
`values`).
`default` is required, so a mod always finds every option it declares. The user
overrides values in `[mods.<name>.options]` of `~/.titan/config.toml`; a value that
does not fit its declaration, or an option the manifest never declared, is dropped
and reported, never handed to the mod.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

# `options["sections"]` carries the mod's section switches (see sections.py).
RESERVED = "sections"
TYPES = ("string", "int", "float", "bool", "list", "choice")
_SPEC_KEYS = {"type", "title", "description", "default", "values", "min", "max"}


@dataclass(frozen=True)
class OptionSpec:
    name: str
    type: str
    default: Any
    title: str = ""
    description: str = ""
    values: Tuple[Any, ...] = ()
    min: Optional[float] = None
    max: Optional[float] = None

    def coerce(self, value: Any) -> Any:
        """The value as this option's type. Raises ValueError saying why it does not fit."""
        if self.type == "string":
            if not isinstance(value, str):
                raise ValueError(f"expected a string, got {value!r}")
            return value
        if self.type == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"expected true or false, got {value!r}")
            return value
        if self.type == "list":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(f"expected a list of strings, got {value!r}")
            return list(value)
        if self.type == "choice":
            if value not in self.values:
                raise ValueError(f"{value!r} is not one of {list(self.values)}")
            return value
        # int / float: a bool is an int in Python, but never a number here.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"expected a number, got {value!r}")
        if self.type == "int" and not isinstance(value, int):
            raise ValueError(f"expected a whole number, got {value!r}")
        if self.min is not None and value < self.min:
            raise ValueError(f"{value!r} is below the minimum {self.min}")
        if self.max is not None and value > self.max:
            raise ValueError(f"{value!r} is above the maximum {self.max}")
        return float(value) if self.type == "float" else value


def parse_option_specs(table: Mapping[str, Any]) -> Dict[str, OptionSpec]:
    """Build the specs from the manifest's `[options]` table. Raises ValueError when malformed."""
    specs: Dict[str, OptionSpec] = {}
    for name, raw in table.items():
        if name == RESERVED:
            raise ValueError(f"option name '{RESERVED}' is reserved for the mod's section switches")
        if not isinstance(raw, Mapping):
            raise ValueError(f"option '{name}' must be a table with a type and a default, e.g. [options.{name}]")
        unknown = set(raw) - _SPEC_KEYS
        if unknown:
            raise ValueError(f"option '{name}': unknown key(s) {sorted(unknown)}")
        kind = raw.get("type")
        if kind not in TYPES:
            raise ValueError(f"option '{name}': type must be one of {list(TYPES)}, got {kind!r}")
        if "default" not in raw:
            raise ValueError(f"option '{name}': default is required")
        values = tuple(raw.get("values", ()))
        if kind == "choice" and not values:
            raise ValueError(f"option '{name}': a choice needs a non-empty values list")
        if kind != "choice" and values:
            raise ValueError(f"option '{name}': values only applies to type 'choice'")
        if kind not in ("int", "float") and ("min" in raw or "max" in raw):
            raise ValueError(f"option '{name}': min and max only apply to int and float")
        spec = OptionSpec(
            name=name,
            type=kind,
            default=raw["default"],
            title=str(raw.get("title", "")),
            description=str(raw.get("description", "")),
            values=values,
            min=raw.get("min"),
            max=raw.get("max"),
        )
        try:
            default = spec.coerce(spec.default)
        except ValueError as e:
            raise ValueError(f"option '{name}': default {e}") from e
        specs[name] = OptionSpec(**{**spec.__dict__, "default": default})
    return specs


def resolve_options(
    specs: Mapping[str, OptionSpec], overrides: Mapping[str, Any]
) -> Tuple[Dict[str, Any], List[Tuple[str, str]]]:
    """Defaults overridden by the user's values. Returns (values, [(option, reason)] dropped)."""
    values = {name: spec.default for name, spec in specs.items()}
    dropped: List[Tuple[str, str]] = []
    for name, value in overrides.items():
        spec = specs.get(name)
        if spec is None:
            dropped.append((name, "not declared in mod.toml"))
            continue
        try:
            values[name] = spec.coerce(value)
        except ValueError as e:
            dropped.append((name, str(e)))
    return values, dropped
