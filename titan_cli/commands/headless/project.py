"""Headless project inspection commands."""

from typing import Optional

import typer

from titan_cli.commands.headless.common import (
    fail_headless_command,
    run_headless_operation,
)
from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.runtime.output import output_presenter


def build_app(container: TitanRuntimeContainer) -> typer.Typer:
    """Build project headless commands."""
    app = typer.Typer(name="project", help="Inspect and configure Titan projects.")

    @app.command("inspect")
    def inspect_project(
        project_path: Optional[str] = typer.Option(
            None,
            "--project-path",
            help="Project directory used to resolve project config, plugins, and workflows.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Inspect a Titan project without launching the TUI or HTTP backend."""
        try:
            inspection = run_headless_operation(
                lambda: container.project_inspection_service().inspect_project(
                    project_path=project_path,
                )
            )
            output_presenter(output_json).write(inspection)
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    return app

