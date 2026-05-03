"""Output presenters shared by command adapters."""

from dataclasses import asdict, is_dataclass
from datetime import datetime
import json
from typing import Any, Protocol

import typer


def to_jsonable(value: Any) -> Any:
    """Convert Titan objects to JSON-safe values for command output."""
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


class OutputPresenter(Protocol):
    """Contract for rendering command payloads."""

    def write(self, payload: object) -> None:
        """Render a payload to the command output stream."""


class JsonOutputPresenter:
    """Render payloads as compact machine-readable JSON."""

    def write(self, payload: object) -> None:
        typer.echo(json.dumps(to_jsonable(payload)))


class HumanOutputPresenter:
    """Render payloads in a readable fallback form."""

    def write(self, payload: object) -> None:
        jsonable = to_jsonable(payload)
        if isinstance(jsonable, dict):
            typer.echo(json.dumps(jsonable, indent=2))
            return

        typer.echo(jsonable)


def output_presenter(as_json: bool) -> OutputPresenter:
    """Select the output strategy once per command."""
    if as_json:
        return JsonOutputPresenter()
    return HumanOutputPresenter()

