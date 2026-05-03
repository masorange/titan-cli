"""Headless plugin management commands."""

import typer

from titan_cli.commands.headless.common import (
    fail_headless_command,
    parse_json_object,
    run_headless_operation,
)
from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.runtime.output import output_presenter


def build_app(container: TitanRuntimeContainer) -> typer.Typer:
    """Build plugin headless commands."""
    app = typer.Typer(name="plugins", help="Inspect and configure Titan plugins.")

    @app.command("list")
    def list_plugins(
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """List installed and enabled plugins."""
        try:
            payload = run_headless_operation(
                lambda: {
                    "installed": container.plugin_service().list_plugins(),
                    "enabled": container.plugin_service().list_enabled_plugins(),
                }
            )
            output_presenter(output_json).write(payload)
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("available")
    def list_available_plugins(
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """List curated plugins available for guided installation."""
        try:
            items = run_headless_operation(
                lambda: container.plugin_service().list_available_plugins()
            )
            output_presenter(output_json).write({"items": items})
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("schema")
    def get_plugin_schema(
        plugin_name: str = typer.Argument(..., help="Plugin name."),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Return the configuration schema exposed by a plugin."""
        try:
            schema = run_headless_operation(
                lambda: container.plugin_service().get_config_schema(plugin_name)
            )
            output_presenter(output_json).write(
                {"plugin_name": plugin_name, "schema": schema}
            )
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("set-enabled")
    def set_plugin_enabled(
        plugin_name: str = typer.Argument(..., help="Plugin name."),
        enabled: bool = typer.Argument(..., help="Whether the plugin is enabled."),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Enable or disable a plugin for the current project."""
        try:
            result = run_headless_operation(
                lambda: container.plugin_service().set_enabled(plugin_name, enabled)
            )
            output_presenter(output_json).write(result)
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("configure")
    def configure_plugin(
        plugin_name: str = typer.Argument(..., help="Plugin name."),
        config_json: str = typer.Option(
            ...,
            "--config-json",
            help="JSON object with plugin configuration values.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Configure a plugin for the current project."""
        try:
            config_values = parse_json_object(config_json, "--config-json")
            result = run_headless_operation(
                lambda: container.plugin_service().configure_plugin(
                    plugin_name,
                    config_values,
                )
            )
            output_presenter(output_json).write(result)
        except typer.BadParameter:
            raise
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("set-dev-source")
    def set_plugin_dev_source(
        plugin_name: str = typer.Argument(..., help="Plugin name."),
        path: str = typer.Option(
            ...,
            "--path",
            help="Absolute or user-relative path to a local plugin checkout.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Use a local development source for a community plugin."""
        try:
            result = run_headless_operation(
                lambda: container.plugin_service().set_dev_source(plugin_name, path)
            )
            output_presenter(output_json).write(result)
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("clear-dev-source")
    def clear_plugin_dev_source(
        plugin_name: str = typer.Argument(..., help="Plugin name."),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Remove a local development source override for a community plugin."""
        try:
            result = run_headless_operation(
                lambda: container.plugin_service().clear_dev_source(plugin_name)
            )
            output_presenter(output_json).write(result)
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    return app
