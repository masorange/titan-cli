"""
Titan CLI - Main CLI application

Combines all tool commands into a single CLI interface.
"""
import subprocess
import sys
import typer

from titan_cli import __version__
from titan_cli.messages import msg
from titan_cli.ui.tui import launch_tui
from titan_cli.utils.autoupdate import check_for_updates, perform_update



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
        # Check for updates BEFORE launching TUI
        try:
            update_info = check_for_updates()
            if update_info["update_available"]:
                current = update_info["current_version"]
                latest = update_info["latest_version"]

                typer.echo(f"🔔 Update available: v{current} → v{latest}")
                typer.echo()

                # Ask user if they want to update
                if typer.confirm("Would you like to update now?", default=True):
                    typer.echo("⏳ Updating Titan CLI...")
                    typer.echo()
                    result = perform_update()

                    if result["success"]:
                        typer.echo(f"✅ Successfully updated to v{latest} using {result['method']}")
                        typer.echo("🔄 Relaunching Titan with new version...")
                        typer.echo()

                        # Relaunch titan using subprocess
                        # Note: sys.executable and sys.argv are controlled by the Python runtime,
                        # not user input, so this is safe from command injection
                        subprocess.run(
                            [sys.executable, "-m", "titan_cli.cli"] + sys.argv[1:],
                            shell=False,  # Explicitly disable shell to prevent injection
                            check=False   # Don't raise on non-zero exit
                        )
                        raise typer.Exit(0)
                    else:
                        typer.echo(f"❌ Update failed: {result['error']}")
                        typer.echo("   Please try manually: pipx upgrade titan-cli")
                        typer.echo()
                        # Continue to TUI even if update fails
                else:
                    typer.echo("⏭  Skipping update. Run 'pipx upgrade titan-cli' to update later.")
                    typer.echo()
        except Exception:
            # Silently ignore update check failures
            pass

        # Launch TUI (only if no update or update was declined/failed)
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
