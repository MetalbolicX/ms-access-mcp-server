"""
E2E tests for real server transport lifecycle — streamable-HTTP and real uvicorn server.

Tier 1 (TestStreamableHttpTransport): Fast, isolated tests using Starlette TestClient.
Tier 3 (TestRealServerTransport): Thread-based uvicorn server with real HTTP client.
"""

import socket
import tempfile
import threading
import time

import pytest
import uvicorn
from starlette.testclient import TestClient

from ms_access_mcp.mcp import server as server_module
from tests.e2e.helpers import initialize_client, mcp_request, send_jsonrpc


class TestStreamableHttpTransport:
    """Tier 1: Streamable-HTTP transport lifecycle via TestClient."""

    def test_streamable_initialize_and_list(self, e2e_streamable_client):
        """Initialize streamable-HTTP client and list available tools."""
        client = e2e_streamable_client
        token = "test-e2e-api-key-12345"

        initialize_client(client, token)

        resp = send_jsonrpc(client, mcp_request("tools/list", {}, req_id=2), token=token)
        assert resp.get("jsonrpc") == "2.0"
        tools = resp.get("result", {}).get("tools", [])
        assert len(tools) > 0

    def test_streamable_diagnose_environment(self, e2e_streamable_client):
        """Call diagnose_environment over streamable-HTTP transport."""
        client = e2e_streamable_client
        token = "test-e2e-api-key-12345"

        initialize_client(client, token)

        resp = send_jsonrpc(
            client,
            mcp_request("tools/call", {"name": "diagnose_environment", "arguments": {}}, req_id=3),
            token=token,
        )
        assert resp.get("jsonrpc") == "2.0"
        result = resp.get("result", {})
        sc = result.get("structuredContent", result)
        assert sc.get("success") is True


class TestRealServerTransport:
    """Tier 3: Real uvicorn server with multi-step lifecycle via httpx."""

    def test_real_server_multi_tool_workflow(self, monkeypatch):
        """Start real uvicorn server, run initialize → tools/list → tools/call, verify clean shutdown."""
        import httpx

        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        # Configure server env
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "test-e2e-api-key-12345")
        monkeypatch.setenv("ACCESS_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("ACCESS_MCP_PORT", str(port))
        monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", tempfile.gettempdir())

        server_module._config = None
        server_module._path_guard = None
        server_module._auth_middleware = None
        server_module._init_http_config()

        app = server_module.mcp.http_app(json_response=True)
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        # Wait for server to be ready
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("Server failed to start within 5 seconds")

        try:
            token = "test-e2e-api-key-12345"

            # Step 1: initialize
            init_resp = httpx.post(
                f"http://127.0.0.1:{port}/mcp/",
                json=mcp_request(
                    method="initialize",
                    params={
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "real-server-e2e", "version": "1.0"},
                    },
                ),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                follow_redirects=True,
                timeout=10,
            )
            assert init_resp.status_code == 200, f"Initialize returned {init_resp.status_code}"
            init_data = init_resp.json()
            assert init_data.get("jsonrpc") == "2.0"
            assert "result" in init_data

            # Capture session ID (stateful streamable-http)
            session_id = init_resp.headers.get("mcp-session-id")
            assert session_id is not None, "Initialize must return mcp-session-id header"

            # Step 2: tools/list
            list_resp = httpx.post(
                f"http://127.0.0.1:{port}/mcp/",
                json=mcp_request("tools/list", {}, req_id=2),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                    "mcp-session-id": session_id,
                },
                follow_redirects=True,
                timeout=10,
            )
            assert list_resp.status_code == 200, f"tools/list returned {list_resp.status_code}"
            list_data = list_resp.json()
            assert list_data.get("jsonrpc") == "2.0"
            tools = list_data.get("result", {}).get("tools", [])
            assert len(tools) > 0, "Expected at least one tool"

            # Step 3: tools/call diagnose_environment
            diag_resp = httpx.post(
                f"http://127.0.0.1:{port}/mcp/",
                json=mcp_request(
                    "tools/call",
                    {"name": "diagnose_environment", "arguments": {}},
                    req_id=3,
                ),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                    "mcp-session-id": session_id,
                },
                follow_redirects=True,
                timeout=10,
            )
            assert diag_resp.status_code == 200, f"tools/call returned {diag_resp.status_code}"
            diag_data = diag_resp.json()
            assert diag_data.get("jsonrpc") == "2.0"
            result = diag_data.get("result", {})
            # Either isError is False, or structuredContent.success is True
            is_error = result.get("isError", False)
            sc = result.get("structuredContent", {})
            assert is_error is False or sc.get("success") is True, f"Expected success, got: {result}"

        finally:
            # Clean shutdown
            server.should_exit = True
            thread.join(timeout=10)