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
from titan_cli.core.logging import setup_logging, get_logger


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
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output (INFO level logs)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug mode (DEBUG level logs with detailed output)",
    ),
):
    """Titan CLI - Main entry point"""
    # Setup logging FIRST (before any other operations)
    setup_logging(verbose=verbose, debug=debug)
    logger = get_logger("titan.cli")

    logger.debug("cli_invoked", command=ctx.invoked_subcommand, verbose=verbose, debug=debug)

    if ctx.invoked_subcommand is None:
        # Check for updates BEFORE launching TUI
        try:
            logger.debug("checking_for_updates")
            update_info = check_for_updates()
            if update_info["update_available"]:
                current = update_info["current_version"]
                latest = update_info["latest_version"]

                logger.info("update_available", current=current, latest=latest)

                typer.echo(f"🔔 Update available: v{current} → v{latest}")
                typer.echo()

                # Ask user if they want to update
                if typer.confirm("Would you like to update now?", default=True):
                    typer.echo("⏳ Updating Titan CLI...")
                    typer.echo()
                    logger.info("update_initiated")
                    result = perform_update()

                    if result["success"]:
                        installed_version = result.get("installed_version", latest)
                        logger.info("update_successful", version=installed_version, method=result['method'])
                        typer.echo(f"✅ Successfully updated to v{installed_version} using {result['method']}")
                        typer.echo("🔄 Relaunching Titan with new version...")
                        typer.echo()

                        # Relaunch titan
                        # Use 'titan' command directly (works for both pipx and pip)
                        subprocess.run(
                            ["titan"] + sys.argv[1:],
                            shell=False,
                            check=False
                        )
                        sys.exit(0)
                    else:
                        logger.error("update_failed", error=result['error'])
                        typer.echo(f"❌ Update failed: {result['error']}")
                        typer.echo("   Please try manually: pipx upgrade titan-cli")
                        typer.echo()
                        # Continue to TUI even if update fails
                else:
                    logger.info("update_skipped")
                    typer.echo("⏭  Skipping update. Run 'pipx upgrade titan-cli' to update later.")
                    typer.echo()
        except (typer.Exit, SystemExit):
            raise
        except Exception as e:
            # Log update check failures but don't show to user
            logger.warning("update_check_failed", error=str(e))
            pass

        # Launch TUI (only if no update or update was declined/failed)
        launch_tui(debug=debug)


@app.command()
def version():
    """Show Titan CLI version."""
    cli_version = get_version()
    typer.echo(msg.CLI.VERSION.format(version=cli_version))


@app.command()
def tui(
    ctx: typer.Context,
):
    """Launch Titan in TUI mode (Textual interface)."""
    # Get debug flag from parent context (main callback)
    debug = ctx.parent.params.get("debug", False) if ctx.parent else False
    launch_tui(debug=debug)
