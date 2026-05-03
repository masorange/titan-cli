"""Headless command tree composition."""

import typer

from titan_cli.commands.headless import ai, project, runs, workflows
from titan_cli.runtime.container import TitanRuntimeContainer


def build_app(container: TitanRuntimeContainer) -> typer.Typer:
    """Build the root headless command group."""
    app = typer.Typer(
        name="headless",
        help="Machine-readable runtime commands for native clients and automation.",
    )
    app.add_typer(workflows.build_app(container), name="workflows")
    app.add_typer(runs.build_app(container), name="runs")
    app.add_typer(project.build_app(container), name="project")
    app.add_typer(ai.build_app(container), name="ai")
    return app

