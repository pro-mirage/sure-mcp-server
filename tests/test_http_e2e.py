"""End-to-end Streamable HTTP test using the MCP client SDK."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class SureApiHandler(BaseHTTPRequestHandler):
    """Minimal Sure API stand-in for the accounts tool."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/v1/accounts":
            if self.headers.get("X-Api-Key") != "test-key":
                self.send_response(401)
                self.end_headers()
                return
            body = json.dumps(
                {"accounts": [{"id": "account-1", "name": "Cash"}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def exercise_mcp(url: str, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "get_accounts" in {tool.name for tool in tools.tools}

                result = await session.call_tool("get_accounts")
                assert result.isError is False
                assert "account-1" in result.content[0].text


def test_streamable_http_to_sure_api() -> None:
    api_server = ThreadingHTTPServer(("127.0.0.1", 0), SureApiHandler)
    api_thread = threading.Thread(target=api_server.serve_forever, daemon=True)
    api_thread.start()

    port = free_port()
    token = "e2e-secret"
    env = os.environ.copy()
    env.update(
        {
            "MCP_HOST": "127.0.0.1",
            "PORT": str(port),
            "MCP_AUTH_TOKEN": token,
            "PYTHONDONTWRITEBYTECODE": "1",
            "SURE_API_KEY": "test-key",
            "SURE_API_URL": f"http://127.0.0.1:{api_server.server_port}",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "sure_mcp_server.server"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                if (
                    httpx.get(
                        f"http://127.0.0.1:{port}/health", timeout=0.2
                    ).status_code
                    == 200
                ):
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
        else:
            output = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"MCP server did not become healthy:\n{output}")

        asyncio.run(exercise_mcp(f"http://127.0.0.1:{port}/mcp", token))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        api_server.shutdown()
        api_server.server_close()
