from fastapi.testclient import TestClient

from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.ui_web.app import create_app


def test_ui_shell_served() -> None:
    client = TestClient(create_app(TitanRuntimeContainer()))

    response = client.get("/")

    assert response.status_code == 200
    assert "Titan UI" in response.text
    assert '<div id="root"></div>' in response.text


def test_open_session_websocket() -> None:
    client = TestClient(create_app(TitanRuntimeContainer()))

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "open_session", "payload": {}})
        response = websocket.receive_json()

    assert response["type"] == "session_opened"
    assert response["payload"]["adapter"] == "local_web"
    assert response["payload"]["transport"] == "websocket"
    assert response["payload"]["session_id"].startswith("session-")
