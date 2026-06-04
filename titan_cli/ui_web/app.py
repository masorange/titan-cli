"""FastAPI application for the local Titan web adapter."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.ui_web.session_manager import BrowserSessionManager


STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(container: TitanRuntimeContainer) -> FastAPI:
    """Create the local web adapter application."""
    app = FastAPI(title="Titan UI", docs_url=None, redoc_url=None)
    session_manager = BrowserSessionManager()

    app.state.container = container
    app.state.session_manager = session_manager

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(
                status_code=503,
                detail="Titan UI frontend build not found. Run 'npm install && npm run build' in web_ui/.",
            )
        return FileResponse(index_path)

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
