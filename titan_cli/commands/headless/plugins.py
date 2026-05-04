"""Headless plugin management commands."""

from typing import Optional

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
        project_path: Optional[str] = typer.Option(
            None,
            "--project-path",
            help="Project directory used to resolve project config and plugin state.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """List installed, enabled, and inspected plugins."""
        try:
            payload = run_headless_operation(
                lambda: _build_plugin_list_payload(container, project_path)
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

    @app.command("preview-source")
    def preview_plugin_source(
        source: str = typer.Option(
            ...,
            "--source",
            help="Repository URL with version suffix, e.g. https://github.com/org/plugin@v1.0.0.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Preview a stable community plugin source before installation."""
        try:
            preview = run_headless_operation(
                lambda: container.plugin_service().preview_stable_source(source)
            )
            output_presenter(output_json).write(preview)
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("install")
    def install_plugin_source(
        source: str = typer.Option(
            ...,
            "--source",
            help="Repository URL with version suffix, e.g. https://github.com/org/plugin@v1.0.0.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Install and pin a stable community plugin source."""
        try:
            result = run_headless_operation(
                lambda: container.plugin_service().install_stable_source(source)
            )
            output_presenter(output_json).write(result)
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


def _build_plugin_list_payload(
    container: TitanRuntimeContainer,
    project_path: Optional[str],
) -> dict[str, object]:
    """Build a backward-compatible plugin list payload for native clients."""
    inspection = container.project_inspection_service().inspect_project(
        project_path=project_path,
    )
    return {
        "installed": [
            plugin.name for plugin in inspection.plugins if plugin.installed
        ],
        "enabled": [
            plugin.name for plugin in inspection.plugins if plugin.enabled
        ],
        "items": inspection.plugins,
        "diagnostics": inspection.diagnostics,
    }
