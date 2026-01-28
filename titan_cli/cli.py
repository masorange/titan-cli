"""
Titan CLI - Main CLI application

Combines all tool commands into a single CLI interface.
"""
import typer
import importlib.metadata

from titan_cli.messages import msg
from titan_cli.ui.tui import launch_tui



# Main Typer Application
app = typer.Typer(
    name=msg.CLI.APP_NAME,
    help=msg.CLI.APP_DESCRIPTION,
    invoke_without_command=True,
    no_args_is_help=False,
)


# --- Helper function for version retrieval ---
def get_version() -> str:
    """Retrieves the package version from pyproject.toml."""
    return importlib.metadata.version("titan-cli")


@app.callback()
def main(ctx: typer.Context):
    """Titan CLI - Main entry point"""
    if ctx.invoked_subcommand is None:
        # Launch TUI by default
        launch_tui()


@app.command()
def version():
    """Show Titan CLI version."""
    cli_version = get_version()
    typer.echo(msg.CLI.VERSION.format(version=cli_version))


@app.command()
def tui():
    """Launch Titan in TUI mode (Textual interface)."""
    launch_tui()
