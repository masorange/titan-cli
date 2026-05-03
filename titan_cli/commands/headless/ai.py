"""Headless AI configuration commands."""

import os

import typer

from titan_cli.commands.headless.common import (
    fail_headless_command,
    parse_json_object,
    run_headless_operation,
)
from titan_cli.core.config import TitanConfig
from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.runtime.output import output_presenter


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


def build_app(container: TitanRuntimeContainer) -> typer.Typer:
    """Build AI headless commands."""
    app = typer.Typer(name="ai", help="Inspect and configure Titan AI connections.")

    @app.command("list")
    def list_ai_connections(
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """List configured AI connections without launching the TUI."""
        try:
            config = run_headless_operation(container.ai_config)
            output_presenter(output_json).write(_ai_connections_payload(config))
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("upsert")
    def upsert_ai_connection(
        connection_id: str = typer.Argument(..., help="Stable AI connection ID."),
        connection_json: str = typer.Option(
            ...,
            "--connection-json",
            help="JSON object with AI connection settings.",
        ),
        api_key: str | None = typer.Option(
            None,
            "--api-key",
            help="Optional API key stored in Titan's user secret store.",
        ),
        api_key_env: str | None = typer.Option(
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
            connection_data = parse_json_object(connection_json, "--connection-json")
            config = run_headless_operation(container.ai_config)
            run_headless_operation(
                lambda: config.upsert_ai_connection(connection_id, connection_data)
            )
            secret_value = api_key
            if not secret_value and api_key_env:
                secret_value = os.getenv(api_key_env)

            if secret_value:
                run_headless_operation(
                    lambda: config.secrets.set(
                        f"{connection_id}_api_key",
                        secret_value,
                        scope="user",
                    )
                )
            output_presenter(output_json).write(_ai_connections_payload(config))
        except typer.BadParameter:
            raise
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("set-default")
    def set_default_ai_connection(
        connection_id: str = typer.Argument(
            ...,
            help="AI connection ID to use by default.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Set the default AI connection used by Titan workflows."""
        try:
            config = run_headless_operation(container.ai_config)
            run_headless_operation(
                lambda: config.set_default_ai_connection(connection_id)
            )
            output_presenter(output_json).write(_ai_connections_payload(config))
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("models")
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
            config = run_headless_operation(container.ai_config)
            payload = run_headless_operation(
                lambda: _ai_models_payload(config, connection_id)
            )
            output_presenter(output_json).write(payload)
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    return app

