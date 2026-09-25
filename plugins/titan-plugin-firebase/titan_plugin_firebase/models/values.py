"""
Remote Config value typing: inference, parsing, and serialization.

Remote Config stores every value as a string. The declared `valueType` on a
parameter tells the console how to render it, but it is absent on older
parameters, so a value's effective type is the declared one when present and
an inferred one otherwise.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Iterable, Optional


class RemoteConfigValueInputMode(str, Enum):
    """How Titan should ask for or render an editable Remote Config value."""

    BOOLEAN_CHOICE = "boolean_choice"
    MULTILINE_JSON = "multiline_json"
    NUMBER_TEXT = "number_text"
    STRING_TEXT = "string_text"
    UNKNOWN_TEXT = "unknown_text"


class RemoteConfigValueSource(str, Enum):
    """Firebase union field used by one Remote Config parameter value."""

    LITERAL = "value"
    IN_APP_DEFAULT = "useInAppDefault"
    PERSONALIZATION = "personalizationValue"
    EXPERIMENT = "experimentValue"
    ROLLOUT = "rolloutValue"
    UNKNOWN = "unknown"

    @property
    def display_label(self) -> str:
        """Short user-facing source label."""
        return _VALUE_SOURCE_SPECS[self]["label"]

    @property
    def is_titan_editable(self) -> bool:
        """Whether Titan may replace this value with a literal string safely."""
        return self in {
            RemoteConfigValueSource.LITERAL,
            RemoteConfigValueSource.IN_APP_DEFAULT,
        }

    @property
    def is_firebase_managed(self) -> bool:
        """Whether Firebase owns this value through another Remote Config feature."""
        return self in {
            RemoteConfigValueSource.PERSONALIZATION,
            RemoteConfigValueSource.EXPERIMENT,
            RemoteConfigValueSource.ROLLOUT,
        }


class RemoteConfigValueType(str, Enum):
    """Supported Firebase Remote Config parameter value types."""

    BOOLEAN = "BOOLEAN"
    JSON = "JSON"
    NUMBER = "NUMBER"
    STRING = "STRING"
    UNKNOWN = "UNKNOWN"

    @property
    def display_label(self) -> str:
        """Short user-facing type label."""
        return _VALUE_TYPE_SPECS[self]["label"]

    @property
    def prompt_hint(self) -> str:
        """Short hint used by text prompts."""
        return _VALUE_TYPE_SPECS[self]["hint"]

    @property
    def input_mode(self) -> RemoteConfigValueInputMode:
        """How this type should be edited in Titan."""
        return _VALUE_TYPE_SPECS[self]["input_mode"]

    @property
    def is_known(self) -> bool:
        """Whether this is a supported known Remote Config type."""
        return self != RemoteConfigValueType.UNKNOWN

    @property
    def is_structured(self) -> bool:
        """Whether this type carries structured data."""
        return self == RemoteConfigValueType.JSON

    @property
    def supports_multiline_input(self) -> bool:
        """Whether editing this type should use a multiline control."""
        return self.input_mode == RemoteConfigValueInputMode.MULTILINE_JSON

    @property
    def preserves_whitespace(self) -> bool:
        """Whether leading/trailing whitespace is semantically meaningful."""
        return self in {RemoteConfigValueType.STRING, RemoteConfigValueType.UNKNOWN}


_VALUE_TYPE_SPECS: dict[RemoteConfigValueType, dict[str, Any]] = {
    RemoteConfigValueType.BOOLEAN: {
        "label": "Bool",
        "hint": "booleano",
        "input_mode": RemoteConfigValueInputMode.BOOLEAN_CHOICE,
    },
    RemoteConfigValueType.JSON: {
        "label": "JSON",
        "hint": "JSON",
        "input_mode": RemoteConfigValueInputMode.MULTILINE_JSON,
    },
    RemoteConfigValueType.NUMBER: {
        "label": "Number",
        "hint": "número",
        "input_mode": RemoteConfigValueInputMode.NUMBER_TEXT,
    },
    RemoteConfigValueType.STRING: {
        "label": "String",
        "hint": "texto",
        "input_mode": RemoteConfigValueInputMode.STRING_TEXT,
    },
    RemoteConfigValueType.UNKNOWN: {
        "label": "Unknown",
        "hint": "texto sin tipo declarado",
        "input_mode": RemoteConfigValueInputMode.UNKNOWN_TEXT,
    },
}

_VALUE_SOURCE_SPECS: dict[RemoteConfigValueSource, dict[str, str]] = {
    RemoteConfigValueSource.LITERAL: {"label": "Literal"},
    RemoteConfigValueSource.IN_APP_DEFAULT: {"label": "In-app default"},
    RemoteConfigValueSource.PERSONALIZATION: {"label": "Personalization"},
    RemoteConfigValueSource.EXPERIMENT: {"label": "Experiment"},
    RemoteConfigValueSource.ROLLOUT: {"label": "Rollout"},
    RemoteConfigValueSource.UNKNOWN: {"label": "Unknown"},
}

_VALUE_TYPE_ALIASES = {
    "BOOL": RemoteConfigValueType.BOOLEAN,
    "BOOLEAN": RemoteConfigValueType.BOOLEAN,
    "JSON": RemoteConfigValueType.JSON,
    "NUMBER": RemoteConfigValueType.NUMBER,
    "NUMERIC": RemoteConfigValueType.NUMBER,
    "STRING": RemoteConfigValueType.STRING,
    "STR": RemoteConfigValueType.STRING,
    "TEXT": RemoteConfigValueType.STRING,
    "UNKNOWN": RemoteConfigValueType.UNKNOWN,
}

_VALUE_SOURCE_ALIASES = {
    "EXPERIMENT": RemoteConfigValueSource.EXPERIMENT,
    "EXPERIMENTVALUE": RemoteConfigValueSource.EXPERIMENT,
    "INAPPDEFAULT": RemoteConfigValueSource.IN_APP_DEFAULT,
    "LITERAL": RemoteConfigValueSource.LITERAL,
    "PERSONALIZATION": RemoteConfigValueSource.PERSONALIZATION,
    "PERSONALIZATIONVALUE": RemoteConfigValueSource.PERSONALIZATION,
    "ROLLOUT": RemoteConfigValueSource.ROLLOUT,
    "ROLLOUTVALUE": RemoteConfigValueSource.ROLLOUT,
    "UNKNOWN": RemoteConfigValueSource.UNKNOWN,
    "USEINAPPDEFAULT": RemoteConfigValueSource.IN_APP_DEFAULT,
    "VALUE": RemoteConfigValueSource.LITERAL,
}


class RemoteConfigValueError(ValueError):
    """Raised when a user-supplied value does not match its declared type."""


def normalize_value_type(value: Any) -> RemoteConfigValueType:
    """Normalize an unknown or absent Firebase value type name."""
    if isinstance(value, RemoteConfigValueType):
        return value
    if value is None:
        return RemoteConfigValueType.UNKNOWN

    normalized = str(value).strip().upper()
    if not normalized:
        return RemoteConfigValueType.UNKNOWN

    return _VALUE_TYPE_ALIASES.get(normalized, RemoteConfigValueType.UNKNOWN)


def normalize_value_source(value: Any) -> RemoteConfigValueSource:
    """Normalize an unknown Firebase Remote Config value union field name."""
    if isinstance(value, RemoteConfigValueSource):
        return value
    if value is None:
        return RemoteConfigValueSource.UNKNOWN

    normalized = (
        str(value).strip().replace("_", "").replace("-", "").replace(" ", "").upper()
    )
    if not normalized:
        return RemoteConfigValueSource.UNKNOWN

    return _VALUE_SOURCE_ALIASES.get(normalized, RemoteConfigValueSource.UNKNOWN)


def infer_value_type(value: Optional[str]) -> RemoteConfigValueType:
    """Infer a value type from a raw Remote Config string."""
    if value is None:
        return RemoteConfigValueType.UNKNOWN

    stripped = value.strip()
    if not stripped:
        return RemoteConfigValueType.STRING

    if stripped.lower() in {"true", "false"}:
        return RemoteConfigValueType.BOOLEAN

    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
        except ValueError:
            return RemoteConfigValueType.STRING
        if isinstance(parsed, (dict, list)):
            return RemoteConfigValueType.JSON

    try:
        float(stripped)
    except ValueError:
        return RemoteConfigValueType.STRING

    return RemoteConfigValueType.NUMBER


def parse_value(
    value: Optional[str],
    value_type: RemoteConfigValueType,
) -> Any:
    """Parse a raw Remote Config value according to its effective type."""
    if value is None:
        return None

    stripped = value.strip()
    if value_type == RemoteConfigValueType.BOOLEAN:
        lowered = stripped.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return value

    if value_type == RemoteConfigValueType.JSON:
        try:
            return json.loads(stripped)
        except ValueError:
            return value

    if value_type == RemoteConfigValueType.NUMBER:
        try:
            parsed = float(stripped)
        except ValueError:
            return value
        if parsed.is_integer() and "." not in stripped and "e" not in stripped.lower():
            return int(parsed)
        return parsed

    return value


def serialize_value(value: str, value_type: RemoteConfigValueType) -> str:
    """
    Validate user input and return the exact string Remote Config must store.

    Firebase only accepts the lowercase literals "true"/"false" for booleans;
    "True", "1" and "0" are explicitly documented as wrong, so they are
    normalized here rather than silently published as strings.

    Raises:
        RemoteConfigValueError: If the input cannot represent the given type.
    """
    if value is None:
        raise RemoteConfigValueError("A value is required.")

    stripped = value.strip()

    if value_type == RemoteConfigValueType.BOOLEAN:
        lowered = stripped.lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return "true"
        if lowered in {"false", "0", "no", "n", "off"}:
            return "false"
        raise RemoteConfigValueError(
            f"'{stripped}' is not a boolean. Use true or false."
        )

    if value_type == RemoteConfigValueType.NUMBER:
        try:
            float(stripped)
        except ValueError as exc:
            raise RemoteConfigValueError(f"'{stripped}' is not a number.") from exc
        return stripped

    if value_type == RemoteConfigValueType.JSON:
        try:
            parsed = json.loads(stripped)
        except ValueError as exc:
            raise RemoteConfigValueError(f"Invalid JSON: {exc}") from exc
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)

    # STRING and UNKNOWN are stored verbatim: leading and trailing whitespace
    # can be meaningful in a string parameter, so the raw input is kept.
    return value


def display_value_type(value_type: Any) -> str:
    """Return Titan's compact display label for a value type."""
    return normalize_value_type(value_type).display_label


def display_value_types(value_types: Iterable[Any]) -> list[str]:
    """Return compact display labels for several value types."""
    return [display_value_type(value_type) for value_type in value_types]


def format_value_for_display(
    raw_value: Optional[str],
    value_type: RemoteConfigValueType,
    *,
    max_length: int = 60,
) -> str:
    """Render a value for a table cell, truncating long JSON and strings."""
    if raw_value is None:
        return "—"

    if value_type == RemoteConfigValueType.JSON:
        parsed = parse_value(raw_value, value_type)
        if isinstance(parsed, (dict, list)):
            collapsed = json.dumps(
                parsed,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            collapsed = " ".join(raw_value.split())
    elif value_type == RemoteConfigValueType.BOOLEAN:
        parsed = parse_value(raw_value, value_type)
        collapsed = str(parsed).lower() if isinstance(parsed, bool) else raw_value
    elif value_type == RemoteConfigValueType.NUMBER:
        collapsed = raw_value.strip()
    else:
        collapsed = " ".join(raw_value.split())

    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[: max_length - 1]}…"
