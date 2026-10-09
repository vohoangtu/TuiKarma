import pytest
from starlette.testclient import TestClient
from tuikarma.web.server import app, manager


def test_web_server_root_and_static_assets():
    """Verify web server serves index.html, styles.css and app.js."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "TUIKarma" in response.text
    assert "Fluent 2 Mica UI" in response.text

    css_res = client.get("/static/styles.css")
    assert css_res.status_code == 200
    assert "--fluent-bg-canvas" in css_res.text

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200
    assert "TUIKarmaWebClient" in js_res.text


def test_web_server_status_and_pipelines_api():
    """Verify /api/status and /api/pipelines REST endpoints."""
    client = TestClient(app)

    status_res = client.get("/api/status")
    assert status_res.status_code == 200
    data = status_res.json()
    assert "status" in data
    assert "agents" in data
    assert "Supervisor" in data["agents"]
    assert "Coder" in data["agents"]

    pipes_res = client.get("/api/pipelines")
    assert pipes_res.status_code == 200
    pipes = pipes_res.json()
    assert isinstance(pipes, list)
    assert len(pipes) >= 3
    pipe_names = [p["name"] for p in pipes]
    assert any("Dynamic" in name or "Parallel" in name for name in pipe_names)


def test_web_server_hitl_commands():
    """Verify /api/hitl/command endpoint handles various actions."""
    client = TestClient(app)

    # Test PAUSE / RESUME
    pause_res = client.post("/api/hitl/command", json={"action": "PAUSE"})
    assert pause_res.status_code == 200
    assert pause_res.json()["action"] == "PAUSE"
    assert manager.topology.is_paused is True

    resume_res = client.post("/api/hitl/command", json={"action": "RESUME"})
    assert resume_res.status_code == 200
    assert resume_res.json()["action"] == "RESUME"
    assert manager.topology.is_paused is False

    # Test APPROVE
    appr_res = client.post("/api/hitl/command", json={"action": "APPROVE", "payload": "Approved via Web UI"})
    assert appr_res.status_code == 200
    assert appr_res.json()["action"] == "APPROVE"


def test_web_server_sandbox_api():
    """Verify /api/sandbox/files endpoint."""
    client = TestClient(app)
    files_res = client.get("/api/sandbox/files")
    assert files_res.status_code == 200
    assert isinstance(files_res.json(), list)


def test_web_server_websocket_connection():
    """Verify client can connect to WebSocket endpoint and receive initial state."""
    client = TestClient(app)
    with client.websocket_connect("/api/ws") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "INITIAL_STATE"
        assert "status" in data["data"]
