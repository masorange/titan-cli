"""FastAPI application for the local Titan web adapter."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import HTMLResponse

from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.ui_web.session_manager import BrowserSessionManager


def create_app(container: TitanRuntimeContainer) -> FastAPI:
    """Create the local web adapter application."""
    app = FastAPI(title="Titan UI", docs_url=None, redoc_url=None)
    session_manager = BrowserSessionManager()

    app.state.container = container
    app.state.session_manager = session_manager

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _html_shell()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")

                if message_type == "open_session":
                    session = session_manager.open_session()
                    await websocket.send_json(
                        {
                            "type": "session_opened",
                            "payload": {
                                "session_id": session.session_id,
                                "adapter": "local_web",
                                "transport": "websocket",
                            },
                        }
                    )
                    continue

                await websocket.send_json(
                    {
                        "type": "session_error",
                        "payload": {
                            "message": f"Unsupported message type: {message_type!r}",
                        },
                    }
                )
        except WebSocketDisconnect:
            return

    return app


def _html_shell() -> str:
    """Return the minimal local UI shell for the first browser session."""
    return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Titan UI</title>
    <style>
      :root {
        color-scheme: light dark;
        font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      }
      body {
        margin: 0;
        background: #f3edf6;
        color: #1f1f1f;
      }
      .page {
        max-width: 960px;
        margin: 0 auto;
        padding: 48px 24px;
      }
      .card {
        background: white;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 24px rgba(26, 26, 26, 0.12);
      }
      h1 {
        margin: 0 0 12px;
        font-size: 2rem;
      }
      p {
        margin: 0 0 12px;
        line-height: 1.5;
      }
      pre {
        margin: 0;
        padding: 16px;
        border-radius: 12px;
        background: #141414;
        color: #f5f5f5;
        overflow-x: auto;
      }
      .status {
        margin-top: 16px;
        padding: 12px 16px;
        border-radius: 12px;
        background: #f0f7ff;
        color: #124076;
      }
    </style>
  </head>
  <body>
    <main class=\"page\">
      <section class=\"card\">
        <h1>Titan UI</h1>
        <p>Local web adapter shell ready.</p>
        <p>This backend is running on your machine and is ready for the next implementation slice.</p>
        <div id=\"status\" class=\"status\">Opening local session...</div>
        <pre id=\"output\"></pre>
      </section>
    </main>
    <script>
      const statusEl = document.getElementById('status');
      const outputEl = document.getElementById('output');
      const socket = new WebSocket(`ws://${window.location.host}/ws`);

      socket.addEventListener('open', () => {
        socket.send(JSON.stringify({ type: 'open_session', payload: {} }));
      });

      socket.addEventListener('message', (event) => {
        const payload = JSON.parse(event.data);
        outputEl.textContent = JSON.stringify(payload, null, 2);
        if (payload.type === 'session_opened') {
          statusEl.textContent = `Session opened: ${payload.payload.session_id}`;
        } else if (payload.type === 'session_error') {
          statusEl.textContent = payload.payload.message;
        }
      });

      socket.addEventListener('close', () => {
        statusEl.textContent = 'Local session closed.';
      });
    </script>
  </body>
</html>
"""
