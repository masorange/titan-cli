"""Local web UI command adapter."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
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
        dev: bool = typer.Option(False, "--dev", help="Run the web UI with the Vite dev server and hot reload."),
        frontend_port: int = typer.Option(5173, help="Frontend dev server port when using --dev."),
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
        server = _create_server(app_instance, host=host, port=port)

        if dev:
            _run_dev_mode(
                server=server,
                host=host,
                backend_port=port,
                frontend_port=frontend_port,
                no_open_browser=no_open_browser,
            )
            return

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


def _create_server(app_instance, *, host: str, port: int) -> uvicorn.Server:
    return uvicorn.Server(
        uvicorn.Config(
            app_instance,
            host=host,
            port=port,
            log_level="info",
        )
    )


def _run_dev_mode(
    *,
    server: uvicorn.Server,
    host: str,
    backend_port: int,
    frontend_port: int,
    no_open_browser: bool,
) -> None:
    """Run backend locally and frontend through Vite for hot reload."""
    frontend_dir = Path(__file__).resolve().parents[2] / "web_ui"
    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        raise typer.BadParameter(f"web_ui frontend not found at {frontend_dir}")

    backend_thread = threading.Thread(target=server.run, daemon=True)
    backend_thread.start()

    if not no_open_browser:
        browser_thread = threading.Thread(
            target=_open_browser_when_ready,
            args=(host, frontend_port),
            daemon=True,
        )
        browser_thread.start()

    command = [
        "pnpm",
        "dev",
        "--host",
        host,
        "--port",
        str(frontend_port),
    ]
    env = {
        **dict(os.environ),
        "COREPACK_ENABLE_STRICT": "0",
        "VITE_TITAN_BACKEND_TARGET": f"http://{host}:{backend_port}",
    }

    try:
        completed = subprocess.run(command, cwd=frontend_dir, env=env, check=False)
        if completed.returncode != 0:
            raise typer.Exit(completed.returncode)
    finally:
        server.should_exit = True
        backend_thread.join(timeout=5)
