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
from typing import Any, Optional


class RemoteConfigValueType(str, Enum):
    """Supported Firebase Remote Config parameter value types."""

    BOOLEAN = "BOOLEAN"
    JSON = "JSON"
    NUMBER = "NUMBER"
    STRING = "STRING"
    UNKNOWN = "UNKNOWN"


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

    return RemoteConfigValueType.__members__.get(
        normalized,
        RemoteConfigValueType.UNKNOWN,
    )


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
            raise RemoteConfigValueError(
                f"'{stripped}' is not a number."
            ) from exc
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


def format_value_for_display(
    raw_value: Optional[str],
    value_type: RemoteConfigValueType,
    *,
    max_length: int = 60,
) -> str:
    """Render a value for a table cell, truncating long JSON and strings."""
    if raw_value is None:
        return "—"

    collapsed = " ".join(raw_value.split())
    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[: max_length - 1]}…"
