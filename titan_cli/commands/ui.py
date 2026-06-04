"""Local web UI command adapter."""

from __future__ import annotations

import threading
import time
import webbrowser

import typer
import uvicorn

from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.ui_web.app import create_app


def build_app(container: TitanRuntimeContainer) -> typer.Typer:
    """Build the local web UI command group."""
    app = typer.Typer(
        name="ui",
        help="Launch the local browser-based Titan UI.",
    )

    @app.callback(invoke_without_command=True)
    def launch_ui(
        ctx: typer.Context,
        host: str = typer.Option("127.0.0.1", help="Host interface for the local UI server."),
        port: int = typer.Option(8765, help="Port for the local UI server."),
        no_open_browser: bool = typer.Option(
            False,
            "--no-open-browser",
            help="Start the local UI server without opening a browser window.",
        ),
    ) -> None:
        """Start the local Titan UI backend and serve the minimal web shell."""
        if ctx.invoked_subcommand is not None:
            return

        app_instance = create_app(container)
        server = uvicorn.Server(
            uvicorn.Config(
                app_instance,
                host=host,
                port=port,
                log_level="info",
            )
        )

        if not no_open_browser:
            browser_thread = threading.Thread(
                target=_open_browser_when_ready,
                args=(host, port),
                daemon=True,
            )
            browser_thread.start()

        server.run()

    return app


def _open_browser_when_ready(host: str, port: int) -> None:
    """Open a browser shortly after the local server starts."""
    time.sleep(0.8)
    webbrowser.open(f"http://{host}:{port}")
