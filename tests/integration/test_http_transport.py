"""
Integration tests for HTTP transport with auth middleware.

Uses Starlette TestClient to test MCP HTTP endpoints without real ports.
Tests auth middleware behavior, error handling, transport modes, and server startup.
"""

import json
import os
import pathlib
import socket
import tempfile
import threading
import time
from typing import Any

import pytest
from starlette.testclient import TestClient

from ms_access_mcp.mcp import server as server_module


# ---- Test fixtures ------------------------------------------------------------

@pytest.fixture(scope="class")
def api_key():
    """Shared valid API key for all tests in this class."""
    return "test-api-key-12345"


@pytest.fixture(scope="class")
def valid_env(api_key):
    """Environment variables with a valid API key and temp dir as allowed directory."""
    return {
        "ACCESS_MCP_API_KEY": api_key,
        "ACCESS_MCP_HOST": "127.0.0.1",
        "ACCESS_MCP_PORT": "8000",
        "ACCESS_MCP_ALLOWED_DIRS": tempfile.gettempdir(),
    }


@pytest.fixture
def app(valid_env, monkeypatch):
    """Starlette TestClient wrapping mcp.http_app(), authorized."""
    for key, value in valid_env.items():
        monkeypatch.setenv(key, value)

    server_module._config = None
    server_module._path_guard = None
    server_module._auth_middleware = None

    server_module._init_http_config()
    return server_module.mcp.http_app(json_response=True, stateless_http=True)


@pytest.fixture
def authorized_client(app):
    """TestClient with a valid Authorization header."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def unauthorized_client(app):
    """TestClient with no Authorization header (middleware should block)."""
    with TestClient(app) as client:
        yield client


# ---- Helper functions ---------------------------------------------------------

def mcp_request(method: str, params: dict[str, Any] | None = None, req_id: int | str = 1) -> dict[str, Any]:
    """Build an MCP JSON-RPC 2.0 request dict."""
    return {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": req_id,
    }


def send_jsonrpc(client: TestClient, request: dict[str, Any]) -> dict[str, Any]:
    """POST a JSON-RPC request to the MCP HTTP endpoint."""
    response = client.post(
        "/mcp/",
        json=request,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    return response.json()


def send_jsonrpc_with_auth(client: TestClient, request: dict[str, Any], token: str) -> dict[str, Any]:
    """POST a JSON-RPC request with an Authorization header."""
    response = client.post(
        "/mcp/",
        json=request,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    return response.json()


# ---- Auth middleware tests ----------------------------------------------------

class TestAuthMiddleware:
    """Tests for ApiKeyMiddleware behavior on the HTTP transport."""

    def test_initialize_without_auth_is_allowed(self, authorized_client):
        """MCP initialize handshake should succeed without Authorization header.

        The middleware's on_initialize allows the handshake through,
        so a client can call initialize even without a Bearer token.
        """
        request = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        response = send_jsonrpc(authorized_client, request)
        # initialize should succeed even without auth
        assert response.get("jsonrpc") == "2.0"
        assert "result" in response

    def test_initialize_with_valid_bearer_token(self, authorized_client, api_key):
        """initialize with a valid Bearer token succeeds."""
        request = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        response = send_jsonrpc_with_auth(authorized_client, request, token=api_key)
        assert response.get("jsonrpc") == "2.0"
        assert "result" in response

    def test_tool_call_without_authorization_header_is_rejected(self, authorized_client):
        """Tool calls without Authorization header are rejected with -32001.

        The middleware intercepts on_call_tool and raises McpError when
        no valid Bearer token is present.
        """
        # initialize first (required to establish MCP session)
        init_request = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        send_jsonrpc(authorized_client, init_request)

        # Now try a tool call without auth — should fail
        tool_request = mcp_request(
            method="tools/call",
            params={"name": "diagnose_environment", "arguments": {}},
            req_id=2,
        )
        response = send_jsonrpc(authorized_client, tool_request)
        # Should be an error response
        assert response.get("jsonrpc") == "2.0"
        # FastMCP 3.x wraps middleware errors in result.isError
        result = response.get("result", {})
        assert result.get("isError") is True
        content = result.get("content", [])
        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
        assert any("Unauthorized" in t for t in texts)

    def test_tool_call_with_invalid_bearer_token_is_rejected(self, authorized_client, api_key):
        """Tool calls with a wrong Bearer token are rejected with -32001."""
        # initialize first
        init_request = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        send_jsonrpc_with_auth(authorized_client, init_request, token=api_key)

        # Tool call with wrong token
        tool_request = mcp_request(
            method="tools/call",
            params={"name": "diagnose_environment", "arguments": {}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, tool_request, token="wrong-token")
        # FastMCP 3.x wraps middleware errors in result.isError
        result = response.get("result", {})
        assert result.get("isError") is True
        content = result.get("content", [])
        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
        assert any("Unauthorized" in t for t in texts)

    def test_tool_call_with_malformed_authorization_header(self, authorized_client):
        """Tool calls with non-Bearer auth headers (e.g. Basic) are rejected."""
        # initialize without auth (allowed)
        init_request = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        send_jsonrpc(authorized_client, init_request)

        # Tool call with malformed auth header
        tool_request = mcp_request(
            method="tools/call",
            params={"name": "diagnose_environment", "arguments": {}},
            req_id=2,
        )
        response = authorized_client.post(
            "/mcp/",
            json=tool_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Basic dXNlcjpwYXNz",
            },
        ).json()
        # FastMCP 3.x wraps middleware errors in result.isError
        result = response.get("result", {})
        assert result.get("isError") is True
        content = result.get("content", [])
        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
        assert any("Unauthorized" in t for t in texts)

    def test_valid_bearer_token_allows_tool_call(self, authorized_client, api_key):
        """A valid Bearer token lets the tool call through to the handler."""
        # initialize with valid token
        init_request = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        send_jsonrpc_with_auth(authorized_client, init_request, token=api_key)

        # diagnose_environment is a safe smoke test — doesn't need COM/Access
        tool_request = mcp_request(
            method="tools/call",
            params={"name": "diagnose_environment", "arguments": {}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, tool_request, token=api_key)
        # Should not be an error — tool should execute (possibly with a result or different error)
        assert response.get("jsonrpc") == "2.0"
        # Check that auth didn't reject the request
        result = response.get("result", {})
        if result.get("isError"):
            # If there's an error, it should NOT be an auth error
            content = result.get("content", [])
            texts = [c.get("text", "") for c in content if isinstance(c, dict)]
            assert not any("Unauthorized" in t for t in texts), \
                "Auth middleware incorrectly rejected valid token"


# ---- Startup configuration tests ----------------------------------------------

class TestStartupConfig:
    """Tests for server configuration initialization and failure modes."""

    def test_init_http_config_sets_config_and_path_guard(self, app, valid_env, monkeypatch):
        """_init_http_config() populates module globals from environment."""
        # Reset to force fresh init
        server_module._config = None
        server_module._path_guard = None
        server_module._auth_middleware = None

        for key, value in valid_env.items():
            monkeypatch.setenv(key, value)

        server_module._init_http_config()

        assert server_module._config is not None
        assert server_module._path_guard is not None
        assert server_module._auth_middleware is not None
        assert server_module._config.api_key == valid_env["ACCESS_MCP_API_KEY"]

    def test_init_http_config_idempotent_guard(self, app, valid_env, monkeypatch):
        """_init_http_config() returns early if already initialized (guard)."""
        # Config is already set by the class-level fixture
        original_config = server_module._config

        server_module._init_http_config()

        # Should be the same object (not re-created)
        assert server_module._config is original_config

    def test_server_startup_fails_without_api_key(self, monkeypatch):
        """Server refuses to start when ACCESS_MCP_API_KEY is not set."""
        # Clear any existing env var
        monkeypatch.delenv("ACCESS_MCP_API_KEY", raising=False)
        monkeypatch.setenv("ACCESS_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("ACCESS_MCP_PORT", "8000")

        # Reset globals
        server_module._config = None
        server_module._path_guard = None
        server_module._auth_middleware = None

        # _init_http_config should raise ValueError
        with pytest.raises(ValueError, match="ACCESS_MCP_API_KEY"):
            server_module._init_http_config()

    def test_mcp_http_app_returns_starlette_app(self, app):
        """mcp.http_app() returns a Starlette ASGI app for TestClient."""
        # The fixture already confirms this — verify the type
        from starlette.applications import Starlette
        assert isinstance(app, Starlette)


# ---- PathGuard validation tests -----------------------------------------------

class TestPathGuard:
    """Integration tests for PathGuard.validate() via connect_access tool."""

    @pytest.fixture(scope="class")
    def temp_accdb(self):
        """Create a temporary .accdb file inside the allowed temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            accdb_path = pathlib.Path(tmpdir) / "test_db.accdb"
            accdb_path.write_text("")
            yield str(accdb_path)

    def _initialize(self, client: TestClient, token: str) -> None:
        """Send MCP initialize so session is established before tool calls."""
        init_req = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        send_jsonrpc_with_auth(client, init_req, token=token)

    def test_allowed_path_succeeds(self, authorized_client, api_key, temp_accdb):
        """connect_access with a path inside allowed_dirs succeeds."""
        self._initialize(authorized_client, api_key)

        req = mcp_request(
            method="tools/call",
            params={"name": "connect_access", "arguments": {"database_path": temp_accdb}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, req, token=api_key)
        assert response.get("jsonrpc") == "2.0"
        result = response.get("result", {})
        sc = result.get("structuredContent", result)
        # Path allowed — no PathGuard error
        if "error" in sc:
            assert "not allowed" not in sc["error"].lower(), \
                f"PathGuard incorrectly rejected allowed path: {temp_accdb}"

    def test_path_outside_allowed_dir_is_rejected(self, authorized_client, api_key):
        """connect_access with a path outside allowed_dirs returns error."""
        self._initialize(authorized_client, api_key)

        # Try a path on a different drive or outside allowed_dirs
        outside_path = "C:\\Windows\\System32\\config\\test.accdb"
        req = mcp_request(
            method="tools/call",
            params={"name": "connect_access", "arguments": {"database_path": outside_path}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, req, token=api_key)
        assert response.get("jsonrpc") == "2.0"
        result = response.get("result", {})
        sc = result.get("structuredContent", result)
        assert sc.get("success") is False

    def test_path_traversal_is_rejected(self, authorized_client, api_key, temp_accdb):
        """connect_access with ../../ path traversal is rejected."""
        self._initialize(authorized_client, api_key)

        # Build a traversal path that escapes from the temp directory
        temp_path = pathlib.Path(temp_accdb)
        traversal_path = str(temp_path.parent.parent.parent / "evil.accdb")
        req = mcp_request(
            method="tools/call",
            params={"name": "connect_access", "arguments": {"database_path": traversal_path}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, req, token=api_key)
        assert response.get("jsonrpc") == "2.0"
        result = response.get("result", {})
        sc = result.get("structuredContent", result)
        assert sc.get("success") is False

    def test_unc_path_is_rejected(self, authorized_client, api_key):
        """connect_access with a UNC path (\\\\server\\share) is rejected."""
        self._initialize(authorized_client, api_key)

        unc_path = "\\\\server\\share\\test.accdb"
        req = mcp_request(
            method="tools/call",
            params={"name": "connect_access", "arguments": {"database_path": unc_path}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, req, token=api_key)
        assert response.get("jsonrpc") == "2.0"
        result = response.get("result", {})
        sc = result.get("structuredContent", result)
        assert sc.get("success") is False


# ---- Tool lifecycle tests -----------------------------------------------------

class TestToolLifecycle:
    """Integration tests for tool call lifecycle and error responses."""

    def _initialize(self, client: TestClient, token: str) -> None:
        """Send MCP initialize so session is established before tool calls."""
        init_req = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        send_jsonrpc_with_auth(client, init_req, token=token)

    def test_diagnose_environment_succeeds(self, authorized_client, api_key):
        """diagnose_environment returns a properly structured JSON-RPC response."""
        self._initialize(authorized_client, api_key)

        req = mcp_request(
            method="tools/call",
            params={"name": "diagnose_environment", "arguments": {}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, req, token=api_key)
        assert response.get("jsonrpc") == "2.0"
        assert "result" in response, f"Expected result key in response, got: {response}"
        result = response["result"]
        # Result wraps the tool output in an MCP-structured dict
        assert isinstance(result, dict)
        # The tool returns diagnostics dict with platform info
        content = result.get("content", [])
        assert isinstance(content, list)
        assert len(content) > 0, "diagnose_environment should return diagnostics content"

    def test_nonexistent_tool_returns_method_not_found(self, authorized_client, api_key):
        """Calling a non-existent tool returns isError in result."""
        self._initialize(authorized_client, api_key)

        req = mcp_request(
            method="tools/call",
            params={"name": "nonexistent_tool_xyz", "arguments": {}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, req, token=api_key)
        assert response.get("jsonrpc") == "2.0"
        result = response.get("result", {})
        assert result.get("isError") is True

    def test_connect_access_nonexistent_file_returns_error(self, authorized_client, api_key):
        """connect_access with a non-existent .accdb returns properly formatted error."""
        self._initialize(authorized_client, api_key)

        nonexistent = "C:\\nonexistent_path_12345\\nonexistent.accdb"
        req = mcp_request(
            method="tools/call",
            params={"name": "connect_access", "arguments": {"database_path": nonexistent}},
            req_id=2,
        )
        response = send_jsonrpc_with_auth(authorized_client, req, token=api_key)
        assert response.get("jsonrpc") == "2.0"
        result = response.get("result", {})
        sc = result.get("structuredContent", result)
        assert sc.get("success") is False


class TestErrorHandling:
    """Tests for HTTP-level and JSON-RPC error responses."""

    def _initialize(self, client, token):
        init_req = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            req_id=1,
        )
        send_jsonrpc_with_auth(client, init_req, token=token)

    def test_malformed_json_returns_400(self, authorized_client):
        """Sending malformed JSON body returns HTTP 400 Bad Request."""
        response = authorized_client.post(
            "/mcp/",
            content=b"this is not valid json",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        assert response.status_code == 400

    def test_missing_jsonrpc_field_returns_minus_32600(self, authorized_client):
        """JSON-RPC request without jsonrpc field returns -32600 Invalid Request."""
        request = {"method": "tools/list", "id": 1}
        response = authorized_client.post(
            "/mcp/",
            json=request,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        data = response.json()
        assert data.get("jsonrpc") == "2.0"
        error = data.get("error", {})
        # FastMCP 3.x returns -32602 for validation errors (Pydantic)
        assert error.get("code") in (-32600, -32602)

    def test_missing_id_field_returns_no_response(self, authorized_client):
        """Request without id field is treated as notification (no response body)."""
        request = {"jsonrpc": "2.0", "method": "tools/list"}
        response = authorized_client.post(
            "/mcp/",
            json=request,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        # FastMCP treats requests without id as notifications — no response body
        assert response.status_code in (200, 202)
        assert response.content == b"" or response.text == ""

    def test_wrong_http_method_returns_405(self, authorized_client):
        """HTTP GET on the MCP endpoint returns 405 Method Not Allowed."""
        response = authorized_client.get("/mcp/")
        assert response.status_code == 405

    def test_put_method_returns_405(self, authorized_client):
        """HTTP PUT on the MCP endpoint returns 405 Method Not Allowed."""
        response = authorized_client.put(
            "/mcp/",
            json={},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        assert response.status_code == 405


class TestTransportModes:
    """Tests for http, streamable-http, and sse transport modes and SSE endpoints."""

    def test_http_transport_jsonrpc(self, authorized_client):
        """Default HTTP transport accepts and processes JSON-RPC at /mcp/."""
        req = mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        )
        resp = send_jsonrpc(authorized_client, req)
        assert resp.get("jsonrpc") == "2.0"
        assert "result" in resp

    def test_http_transport_content_type(self, authorized_client):
        """HTTP transport returns application/json Content-Type with json_response=True."""
        resp = authorized_client.post(
            "/mcp/",
            json=mcp_request(
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "t", "version": "1"},
                },
            ),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        ct = resp.headers.get("content-type", "")
        assert ct.startswith("application/json"), f"Expected application/json, got {ct}"

    def test_sse_app_has_sse_route(self, valid_env, monkeypatch):
        """SSE transport app registers the /sse route."""
        for key, value in valid_env.items():
            monkeypatch.setenv(key, value)
        sse_app = server_module.mcp.http_app(transport="sse")

        route_paths = set()
        for route in sse_app.router.routes:
            if hasattr(route, "path"):
                route_paths.add(route.path)
        assert "/sse" in route_paths, f"Expected /sse route, found: {route_paths}"

    def test_sse_app_has_messages_route(self, valid_env, monkeypatch):
        """SSE transport app registers the /messages/ route."""
        for key, value in valid_env.items():
            monkeypatch.setenv(key, value)
        sse_app = server_module.mcp.http_app(transport="sse")

        route_paths = set()
        for route in sse_app.router.routes:
            if hasattr(route, "path"):
                route_paths.add(route.path)
        assert any("/messages" in p for p in route_paths), f"Expected /messages route, found: {route_paths}"

    def test_streamable_http_app_has_route(self, valid_env, monkeypatch):
        """Streamable-HTTP transport app registers the /mcp route."""
        for key, value in valid_env.items():
            monkeypatch.setenv(key, value)
        stream_app = server_module.mcp.http_app(transport="streamable-http", json_response=True)

        route_paths = set()
        for route in stream_app.router.routes:
            if hasattr(route, "path"):
                route_paths.add(route.path)
        # Both transport modes share the same path
        assert "/mcp" in route_paths or "/mcp/" in route_paths, \
            f"Expected /mcp route, found: {route_paths}"

    def test_streamable_http_accepts_jsonrpc(self, valid_env, monkeypatch, api_key):
        """Streamable-HTTP transport accepts JSON-RPC POST requests."""
        for key, value in valid_env.items():
            monkeypatch.setenv(key, value)
        server_module._config = None
        server_module._path_guard = None
        server_module._auth_middleware = None
        server_module._init_http_config()

        stream_app = server_module.mcp.http_app(transport="streamable-http", json_response=True)
        with TestClient(stream_app) as client:
            req = mcp_request(
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            )
            resp = client.post(
                "/mcp/",
                json=req,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("jsonrpc") == "2.0"
            assert "result" in data

    @pytest.mark.skip(reason="Starlette TestClient blocks on SSE streaming response; needs live server")
    def test_sse_app_returns_streaming_response(self):
        """SSE transport GET /sse returns 200 with event-stream Content-Type."""
        pass

    @pytest.mark.skip(reason="Starlette TestClient blocks on SSE streaming response; needs live server")
    def test_sse_messages_endpoint_accepts_post(self):
        """SSE transport POST /messages/ returns 200 or 202."""
        pass


class TestFullServerStartup:
    """Thread-based HTTP server smoke test and CLI import test."""

    def test_http_server_smoke(self, valid_env, monkeypatch):
        """Start uvicorn in a thread, send request, verify JSON-RPC response."""
        import uvicorn
        import httpx

        for key, value in valid_env.items():
            monkeypatch.setenv(key, value)

        server_module._config = None
        server_module._path_guard = None
        server_module._auth_middleware = None
        server_module._init_http_config()

        http_app = server_module.mcp.http_app(json_response=True)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        config = uvicorn.Config(http_app, host="127.0.0.1", port=port, log_level="error")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("Server failed to start within 5 seconds")

        try:
            init_resp = httpx.post(
                f"http://127.0.0.1:{port}/mcp/",
                json=mcp_request(
                    method="initialize",
                    params={
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "smoke-test", "version": "1.0"},
                    },
                ),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                follow_redirects=True,
                timeout=10,
            )
            assert init_resp.status_code == 200, f"Init returned {init_resp.status_code}: {init_resp.text[:300]}"
            data = init_resp.json()
            assert data.get("jsonrpc") == "2.0"
            assert "result" in data
            # Capture the session ID from response headers (stateful streamable-http)
            session_id = init_resp.headers.get("mcp-session-id")
            assert session_id is not None, "Initialize response must include mcp-session-id header"

            tool_resp = httpx.post(
                f"http://127.0.0.1:{port}/mcp/",
                json=mcp_request(
                    method="tools/call",
                    params={"name": "diagnose_environment", "arguments": {}},
                    req_id=2,
                ),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {valid_env['ACCESS_MCP_API_KEY']}",
                    "mcp-session-id": session_id,
                },
                follow_redirects=True,
                timeout=10,
            )
            assert tool_resp.status_code == 200, f"Tool call returned {tool_resp.status_code}: {tool_resp.text[:500]}"
            tool_data = tool_resp.json()
            assert tool_data.get("jsonrpc") == "2.0"
        finally:
            server.should_exit = True
            thread.join(timeout=10)

    def test_cli_module_imports(self):
        """CLI module imports without errors."""
        from ms_access_mcp.cli import main as cli_main
        assert cli_main is not None
        assert hasattr(cli_main, "app")
        assert hasattr(cli_main, "export_all")
        assert hasattr(cli_main, "compare_versioning")
        assert hasattr(cli_main, "export_vba")
