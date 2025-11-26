"""
Preview Subcommand Module

This module contains the Typer sub-application for previewing UI components.
It is imported by the main cli.py and added as a subcommand.
"""

import typer
import runpy

# Sub-application for 'preview' commands
preview_app = typer.Typer(name="preview", help="Preview UI components in isolation.")


@preview_app.command("panel")
def preview_panel():
    """
    Shows a preview of the Panel component with all its variations.
    """
    try:
        runpy.run_module("titan_cli.ui.components.__previews__.panel_preview", run_name="__main__")
    except ModuleNotFoundError:
        typer.secho("Error: Preview script not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

# You can add more preview commands here as you create more components.
# For example:
#
# @preview_app.command("banner")
# def preview_banner():
#     """Shows a preview of the Banner component."""
#     try:
#         runpy.run_module("titan_cli.ui.views.__previews__.banner_preview", run_name="__main__")
#     except ModuleNotFoundError:
#         typer.secho("Error: Preview script not found.", fg=typer.colors.RED)
#         raise typer.Exit(1)
