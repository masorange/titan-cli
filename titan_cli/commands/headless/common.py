"""Shared helpers for headless command modules."""

from contextlib import redirect_stdout
import json
import sys
from typing import Optional

import typer


def parse_json_object(raw_value: Optional[str], option_name: str) -> dict[str, object]:
    """Parse a CLI option expected to contain a JSON object."""
    if not raw_value:
        return {}

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"{option_name} must be valid JSON: {exc.msg}"
        ) from exc

    if not isinstance(value, dict):
        raise typer.BadParameter(f"{option_name} must be a JSON object")

    return value


def parse_json_array(raw_value: Optional[str], option_name: str) -> list[object]:
    """Parse a CLI option expected to contain a JSON array."""
    if not raw_value:
        return []

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"{option_name} must be valid JSON: {exc.msg}"
        ) from exc

    if not isinstance(value, list):
        raise typer.BadParameter(f"{option_name} must be a JSON array")

    return value


def fail_headless_command(exc: Exception, as_json: bool) -> None:
    """Return stable errors for machine clients without showing tracebacks."""
    payload = {
        "error": str(exc),
        "error_type": type(exc).__name__,
    }
    if as_json:
        typer.echo(json.dumps(payload), err=True)
    else:
        typer.echo(f"{payload['error_type']}: {payload['error']}", err=True)
    raise typer.Exit(code=1)


def run_headless_operation(operation):
    """Run a headless operation while keeping stdout reserved for JSON output."""
    with redirect_stdout(sys.stderr):
        return operation()
