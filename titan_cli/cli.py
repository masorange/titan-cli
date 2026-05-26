"""
Titan CLI - Main CLI application

Combines all tool commands into a single CLI interface.
"""
import os
import sys
import typer

from titan_cli import __version__
from titan_cli.messages import msg
from titan_cli.ui.tui import launch_tui
from titan_cli.utils.autoupdate import (
    check_for_updates,
    get_installed_version,
    meets_target_version,
    update_core,
    update_plugins,
)
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
    devtools: bool = typer.Option(
        False,
        "--devtools",
        help="Enable Textual devtools (visual debugging for TUI, requires 'textual console' in another terminal)",
    ),
):
    """Titan CLI - Main entry point"""
    # Auto-enable debug if running as titan-dev (detected via TITAN_ENV set by the script)
    if os.getenv("TITAN_ENV") == "development":
        debug = True

    # Setup logging FIRST (before any other operations)
    setup_logging(verbose=verbose, debug=debug)
    logger = get_logger("titan.cli")

    # Store devtools flag in context for other commands
    ctx.ensure_object(dict)
    ctx.obj["devtools"] = devtools

    logger.debug("cli_invoked", command=ctx.invoked_subcommand, verbose=verbose, debug=debug, devtools=devtools)

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
                    logger.info("update_initiated")

                    # Step 1: update core
                    typer.echo("⏳ Updating Titan CLI...")
                    core_result = update_core(target_version=latest)

                    if not core_result["success"]:
                        logger.error("update_core_failed", error=core_result["error"])
                        typer.echo(f"❌ Failed to update Titan CLI: {core_result['error']}")
                        typer.echo()
                        typer.echo("   Please update manually:")
                        typer.echo("     pipx upgrade --force titan-cli")
                        typer.echo("     pipx upgrade --include-injected titan-cli")
                        sys.exit(1)

                    installed_version = core_result.get("installed_version", latest)
                    logger.info("update_core_successful", version=installed_version, method=core_result["method"])
                    typer.echo(f"✅ Titan CLI updated to v{installed_version}")

                    # Step 2: update plugins
                    typer.echo("⏳ Updating plugins...")
                    plugins_result = update_plugins()

                    if not plugins_result["success"]:
                        logger.error("update_plugins_failed", error=plugins_result["error"])
                        typer.echo(f"❌ Failed to update plugins: {plugins_result['error']}")
                        typer.echo()
                        typer.echo("   Please run manually:")
                        typer.echo("     pipx upgrade --include-injected titan-cli")
                        sys.exit(1)

                    if not plugins_result.get("skipped"):
                        typer.echo("✅ Plugins updated")

                    final_version = get_installed_version()
                    if not final_version or not meets_target_version(final_version, latest):
                        logger.error(
                            "update_final_version_check_failed",
                            expected=latest,
                            installed=final_version,
                        )
                        typer.echo(
                            "❌ Failed to verify Titan CLI after plugin update: "
                            f"installed version is {final_version or 'unknown'}, "
                            f"expected at least {latest}"
                        )
                        typer.echo()
                        typer.echo("   Please update manually:")
                        typer.echo("     pipx upgrade --force titan-cli")
                        typer.echo("     pipx upgrade --include-injected titan-cli")
                        sys.exit(1)

                    logger.info("update_successful", version=final_version)
                    typer.echo()
                    typer.echo(
                        "✅ Update complete. Please run `titan` again to use "
                        f"v{final_version}."
                    )
                    sys.exit(0)
                else:
                    logger.info("update_skipped")
                    typer.echo()
                    typer.echo("   Please update manually:")
                    typer.echo("     pipx upgrade --force titan-cli")
                    typer.echo("     pipx upgrade --include-injected titan-cli")
                    sys.exit(1)
        except (typer.Exit, SystemExit):
            raise
        except Exception as e:
            # Log update check failures but don't show to user
            logger.warning("update_check_failed", error=str(e))
            pass

        # Launch TUI (only if no update or update was declined/failed)
        launch_tui(debug=debug, devtools=devtools)


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
    # Get debug and devtools flags from parent context (main callback)
    debug = ctx.parent.params.get("debug", False) if ctx.parent else False
    devtools = ctx.parent.obj.get("devtools", False) if ctx.parent and ctx.parent.obj else False
    launch_tui(debug=debug, devtools=devtools)
