"""
Projects Subcommand Module

This module contains the 'projects' command, which discovers and lists
Titan projects in the configured project root.
"""

import typer
from pathlib import Path

from ..core.discovery import discover_projects
from ..ui.components.typography import TextRenderer
from ..ui.components.spacer import SpacerRenderer
from ..ui.components.table import TableRenderer

projects_app = typer.Typer(name="projects", help="Discover and manage Titan projects.")

@projects_app.callback()
def projects_callback():
    """Discover and manage Titan projects."""
    pass # No default action, subcommands will be implemented here


@projects_app.command("list")
def list_projects(directory: Path = typer.Argument(None, help="Directory to scan for projects (default: current directory)")):
    """
    List discovered Titan projects in a directory.
    Categorizes projects as configured (with .titan/config.toml)
    and unconfigured (git repos without .titan/config.toml).
    """
    text = TextRenderer()
    spacer = SpacerRenderer()
    table_renderer = TableRenderer()

    text.title("Project Discovery")
    spacer.line()

    # Use current directory if no directory specified
    project_root = directory if directory else Path.cwd()

    if not project_root.is_dir():
        text.error(f"Directory does not exist: {project_root}")
        raise typer.Exit(1)

    text.body(f"Scanning for projects in: [primary]{project_root}[/primary]")
    spacer.line()

    configured_projects, unconfigured_projects = discover_projects(str(project_root))

    # Display Configured Projects
    text.success("Configured Projects:")
    if configured_projects:
        headers = ["Project Name", "Path"]
        rows = []
        for p in configured_projects:
            try:
                rel_path = str(p.relative_to(project_root))
            except ValueError:
                rel_path = str(p) # Fallback to absolute path
            rows.append([p.name, rel_path])
        table_renderer.print_table(headers=headers, rows=rows, show_lines=True)
    else:
        text.body("No configured Titan projects found.")
    spacer.line()

    # Display Unconfigured Projects
    text.warning("Unconfigured Git Projects (candidates for 'titan init'):")
    if unconfigured_projects:
        headers = ["Project Name", "Path"]
        rows = []
        for p in unconfigured_projects:
            try:
                rel_path = str(p.relative_to(project_root))
            except ValueError:
                rel_path = str(p) # Fallback to absolute path
            rows.append([p.name, rel_path])
        table_renderer.print_table(headers=headers, rows=rows, show_lines=True)
    else:
        text.body("No unconfigured Git projects found.")
    spacer.line()

    text.info("To initialize an unconfigured project, navigate to its directory and run 'titan init'.")
