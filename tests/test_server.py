"""Unit tests for the Sure MCP HTTP application."""

import importlib

from starlette.testclient import TestClient


def load_server(monkeypatch, *, auth_token: str | None = None):
    """Load the server with deterministic deployment settings."""
    monkeypatch.setenv("PORT", "8000")
    monkeypatch.setenv("MCP_PATH", "/mcp")
    if auth_token is None:
        monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    else:
        monkeypatch.setenv("MCP_AUTH_TOKEN", auth_token)

    import sure_mcp_server.server as server

    return importlib.reload(server)


def test_http_defaults(monkeypatch):
    server = load_server(monkeypatch)

    assert server.mcp.settings.host == "0.0.0.0"
    assert server.mcp.settings.port == 8000
    assert server.mcp.settings.streamable_http_path == "/mcp"
    assert server.mcp.settings.json_response is True
    assert server.mcp.settings.stateless_http is True


def test_health_endpoint_is_public(monkeypatch):
    server = load_server(monkeypatch, auth_token="secret")

    with TestClient(server.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "sure-mcp-server"}


def test_mcp_endpoint_requires_configured_bearer_token(monkeypatch):
    server = load_server(monkeypatch, auth_token="secret")

    with TestClient(server.app) as client:
        response = client.post("/mcp", json={})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_mcp_endpoint_accepts_configured_bearer_token(monkeypatch):
    server = load_server(monkeypatch, auth_token="secret")

    with TestClient(server.app) as client:
        response = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer secret",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "Sure MCP Server"
