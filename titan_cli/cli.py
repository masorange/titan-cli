"""
Titan CLI - Main CLI application

Combines all tool commands into a single CLI interface.
"""
from contextlib import redirect_stdout
from dataclasses import asdict, is_dataclass
from datetime import datetime
import json
import os
import sys
from typing import Any, Optional

import typer

from titan_cli.application.models.requests import StartWorkflowRequest
from titan_cli.application.services.project_inspection_service import (
    ProjectInspectionService,
)
from titan_cli.application.services.workflow_service import WorkflowService
from titan_cli import __version__
from titan_cli.core.config import TitanConfig
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

headless_app = typer.Typer(
    name="headless",
    help="Machine-readable runtime commands for native clients and automation.",
)
headless_workflows_app = typer.Typer(
    name="workflows",
    help="Discover and describe workflows.",
)
headless_runs_app = typer.Typer(
    name="runs",
    help="Start and inspect workflow runs.",
)
headless_project_app = typer.Typer(
    name="project",
    help="Inspect and configure Titan projects.",
)
headless_ai_app = typer.Typer(
    name="ai",
    help="Inspect and configure Titan AI connections.",
)
headless_app.add_typer(headless_workflows_app, name="workflows")
headless_app.add_typer(headless_runs_app, name="runs")
headless_app.add_typer(headless_project_app, name="project")
headless_app.add_typer(headless_ai_app, name="ai")
app.add_typer(headless_app, name="headless")


# --- Helper function for version retrieval ---
def get_version() -> str:
    """Retrieves the package version."""
    return __version__


def _workflow_service() -> WorkflowService:
    """Build the workflow service used by headless CLI commands."""
    return WorkflowService(config=TitanConfig())


def _project_inspection_service() -> ProjectInspectionService:
    """Build the project inspection service used by headless CLI commands."""
    return ProjectInspectionService(config=TitanConfig())


def _ai_config() -> TitanConfig:
    """Build a lightweight config object for headless AI settings."""
    return TitanConfig(skip_plugin_init=True)


def _ai_connections_payload(config: TitanConfig) -> dict[str, object]:
    """Return AI connection settings in a stable native-client shape."""
    ai_config = config.get_ai_connections_config()
    default_connection = ai_config.get("default_connection")
    connections = []

    for connection_id, connection_data in sorted(
        ai_config.get("connections", {}).items()
    ):
        connections.append(
            {
                "id": connection_id,
                **connection_data,
                "is_default": connection_id == default_connection,
            }
        )

    return {
        "default_connection": default_connection,
        "connections": connections,
    }


def _popular_direct_models(provider: str | None) -> list[dict[str, object]]:
    """Return curated model suggestions for direct providers."""
    suggestions = {
        "anthropic": [
            "claude-sonnet-4-5",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ],
        "openai": [
            "gpt-5",
            "gpt-5-mini",
            "gpt-4.1",
        ],
        "gemini": [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
    }
    return [
        {"id": model, "name": model, "owned_by": provider, "source": "suggested"}
        for model in suggestions.get(provider or "", [])
    ]


def _ai_models_payload(config: TitanConfig, connection_id: str) -> dict[str, object]:
    """Return available or suggested models for an AI connection."""
    ai_config = config.config.ai
    if not ai_config or connection_id not in ai_config.connections:
        raise ValueError(f"AI connection '{connection_id}' not found.")

    connection = ai_config.connections[connection_id]
    connection_type = getattr(connection.connection_type, "value", connection.connection_type)

    if connection_type == "gateway":
        from titan_cli.ai.litellm_client import LiteLLMClient

        api_key = config.secrets.get(f"{connection_id}_api_key")
        models = LiteLLMClient(
            base_url=connection.base_url,
            api_key=api_key,
        ).list_models()
        items = [
            {
                "id": model.id,
                "name": model.name,
                "owned_by": model.owned_by,
                "source": "gateway",
            }
            for model in models
        ]
    else:
        provider = getattr(connection.provider, "value", connection.provider)
        items = _popular_direct_models(provider)

    return {
        "connection_id": connection_id,
        "default_model": connection.default_model,
        "items": items,
    }


def to_jsonable(value: Any) -> Any:
    """Convert Titan objects to JSON-safe values for headless output."""
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def _echo_payload(payload: object, as_json: bool) -> None:
    """Print command output in JSON or compact human form."""
    jsonable = to_jsonable(payload)
    if as_json:
        typer.echo(json.dumps(jsonable))
        return

    if isinstance(jsonable, dict):
        typer.echo(json.dumps(jsonable, indent=2))
        return

    typer.echo(jsonable)


def _parse_json_object(raw_value: Optional[str], option_name: str) -> dict[str, object]:
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


def _parse_json_array(raw_value: Optional[str], option_name: str) -> list[object]:
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


def _fail_headless_command(exc: Exception, as_json: bool) -> None:
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


def _run_headless_operation(operation):
    """Run a headless operation while keeping stdout reserved for JSON output."""
    with redirect_stdout(sys.stderr):
        return operation()


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

    # Headless runtime commands are consumed by native clients. They must keep
    # stdout clean so the response remains parseable JSON.
    if ctx.invoked_subcommand == "headless":
        ctx.ensure_object(dict)
        ctx.obj["devtools"] = devtools
        return

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


@headless_workflows_app.command("list")
def list_workflows(
    project_path: Optional[str] = typer.Option(
        None,
        "--project-path",
        help="Project directory used to resolve project workflows and plugin config.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Print a machine-readable JSON response.",
    ),
):
    """List workflows without launching the TUI or HTTP backend."""
    try:
        workflows = _run_headless_operation(
            lambda: _workflow_service().list_workflows(project_path=project_path)
        )
        _echo_payload({"items": workflows}, as_json=output_json)
    except Exception as exc:
        _fail_headless_command(exc, as_json=output_json)


@headless_workflows_app.command("describe")
def describe_workflow(
    workflow_name: str = typer.Argument(..., help="Workflow name to describe."),
    project_path: Optional[str] = typer.Option(
        None,
        "--project-path",
        help="Project directory used to resolve project workflows and plugin config.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Print a machine-readable JSON response.",
    ),
):
    """Describe a resolved workflow, including inherited and hook steps."""
    try:
        workflow = _run_headless_operation(
            lambda: _workflow_service().describe_workflow(
                workflow_name=workflow_name,
                project_path=project_path,
            )
        )
        if workflow is None:
            raise typer.BadParameter(f"Workflow '{workflow_name}' not found")
        _echo_payload(workflow, as_json=output_json)
    except typer.BadParameter:
        raise
    except Exception as exc:
        _fail_headless_command(exc, as_json=output_json)


@headless_runs_app.command("start")
def start_run(
    workflow_name: str = typer.Argument(..., help="Workflow name to run."),
    project_path: Optional[str] = typer.Option(
        None,
        "--project-path",
        help="Project directory used to resolve project workflows and plugin config.",
    ),
    params_json: Optional[str] = typer.Option(
        None,
        "--params-json",
        help="JSON object merged into the workflow context.",
    ),
    prompt_responses_json: Optional[str] = typer.Option(
        None,
        "--prompt-responses-json",
        help="JSON array of pre-seeded prompt responses for headless execution.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Print a machine-readable JSON response.",
    ),
):
    """Run a workflow synchronously without launching the TUI or HTTP backend."""
    try:
        request = StartWorkflowRequest(
            workflow_name=workflow_name,
            params=_parse_json_object(params_json, "--params-json"),
            prompt_responses=_parse_json_array(
                prompt_responses_json,
                "--prompt-responses-json",
            ),
            project_path=project_path,
            interaction_mode="headless",
        )
        response = _run_headless_operation(
            lambda: _workflow_service().start_workflow(request)
        )
        _echo_payload(response, as_json=output_json)
    except typer.BadParameter:
        raise
    except Exception as exc:
        _fail_headless_command(exc, as_json=output_json)


@headless_project_app.command("inspect")
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
        inspection = _run_headless_operation(
            lambda: _project_inspection_service().inspect_project(
                project_path=project_path,
            )
        )
        _echo_payload(inspection, as_json=output_json)
    except Exception as exc:
        _fail_headless_command(exc, as_json=output_json)


@headless_ai_app.command("list")
def list_ai_connections(
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Print a machine-readable JSON response.",
    ),
):
    """List configured AI connections without launching the TUI."""
    try:
        config = _run_headless_operation(_ai_config)
        _echo_payload(_ai_connections_payload(config), as_json=output_json)
    except Exception as exc:
        _fail_headless_command(exc, as_json=output_json)


@headless_ai_app.command("upsert")
def upsert_ai_connection(
    connection_id: str = typer.Argument(..., help="Stable AI connection ID."),
    connection_json: str = typer.Option(
        ...,
        "--connection-json",
        help="JSON object with AI connection settings.",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="Optional API key stored in Titan's user secret store.",
    ),
    api_key_env: Optional[str] = typer.Option(
        None,
        "--api-key-env",
        help="Optional environment variable containing the API key to store.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Print a machine-readable JSON response.",
    ),
):
    """Create or update an AI connection for native clients."""
    try:
        connection_data = _parse_json_object(connection_json, "--connection-json")
        config = _run_headless_operation(_ai_config)
        _run_headless_operation(
            lambda: config.upsert_ai_connection(connection_id, connection_data)
        )
        secret_value = api_key
        if not secret_value and api_key_env:
            secret_value = os.getenv(api_key_env)

        if secret_value:
            _run_headless_operation(
                lambda: config.secrets.set(
                    f"{connection_id}_api_key",
                    secret_value,
                    scope="user",
                )
            )
        _echo_payload(_ai_connections_payload(config), as_json=output_json)
    except typer.BadParameter:
        raise
    except Exception as exc:
        _fail_headless_command(exc, as_json=output_json)


@headless_ai_app.command("set-default")
def set_default_ai_connection(
    connection_id: str = typer.Argument(..., help="AI connection ID to use by default."),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Print a machine-readable JSON response.",
    ),
):
    """Set the default AI connection used by Titan workflows."""
    try:
        config = _run_headless_operation(_ai_config)
        _run_headless_operation(lambda: config.set_default_ai_connection(connection_id))
        _echo_payload(_ai_connections_payload(config), as_json=output_json)
    except Exception as exc:
        _fail_headless_command(exc, as_json=output_json)


@headless_ai_app.command("models")
def list_ai_models(
    connection_id: str = typer.Argument(..., help="AI connection ID."),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Print a machine-readable JSON response.",
    ),
):
    """List available models for a configured AI connection."""
    try:
        config = _run_headless_operation(_ai_config)
        payload = _run_headless_operation(
            lambda: _ai_models_payload(config, connection_id)
        )
        _echo_payload(payload, as_json=output_json)
    except Exception as exc:
        _fail_headless_command(exc, as_json=output_json)


@app.command()
def tui(
    ctx: typer.Context,
):
    """Launch Titan in TUI mode (Textual interface)."""
    # Get debug and devtools flags from parent context (main callback)
    debug = ctx.parent.params.get("debug", False) if ctx.parent else False
    devtools = ctx.parent.obj.get("devtools", False) if ctx.parent and ctx.parent.obj else False
    launch_tui(debug=debug, devtools=devtools)
