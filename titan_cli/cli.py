"""
Titan CLI - Main CLI application

Combines all tool commands into a single CLI interface.
"""
import typer

from titan_cli import __version__
from titan_cli.messages import msg
from titan_cli.ui.tui import launch_tui
from titan_cli.utils.autoupdate import check_for_updates, get_update_message



# Main Typer Application
app = typer.Typer(
    name=msg.CLI.APP_NAME,
    help=msg.CLI.APP_DESCRIPTION,
    invoke_without_command=True,
    no_args_is_help=False,
)


# --- Helper function for version retrieval ---
def get_version() -> str:
    """Retrieves the package version."""
    return __version__


@app.callback()
def main(ctx: typer.Context):
    """Titan CLI - Main entry point"""
    if ctx.invoked_subcommand is None:
        # Check for updates (non-blocking, silent on errors)
        try:
            update_info = check_for_updates()
            message = get_update_message(update_info)
            if message:
                typer.echo(message)
                typer.echo()  # Empty line for spacing
        except Exception:
            # Silently ignore update check failures
            pass

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
