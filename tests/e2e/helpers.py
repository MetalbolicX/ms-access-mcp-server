"""
E2E workflow helpers — custom assertions and HTTP transport helpers.

call_mcp_tool is exposed via conftest.py and can be imported from there.
Tests should use: from tests.e2e.conftest import call_mcp_tool
"""

from pathlib import Path
from typing import Any


# ============================================================================
# HTTP Transport Helpers
# ============================================================================

def mcp_request(method: str, params: dict[str, Any] | None = None, req_id: int | str = 1) -> dict[str, Any]:
    """Build an MCP JSON-RPC 2.0 request dict."""
    return {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": req_id,
    }


def send_jsonrpc(client, request: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    """POST a JSON-RPC request to the MCP HTTP endpoint."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = client.post("/mcp/", json=request, headers=headers)
    return response.json()


def initialize_client(client, token: str) -> None:
    """Send MCP initialize handshake."""
    init_req = mcp_request(
        method="initialize",
        params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "e2e-test-client", "version": "1.0"},
        },
        req_id=1,
    )
    send_jsonrpc(client, init_req, token=token)


# ============================================================================
# Assertion Helpers
# ============================================================================

def assert_file_exists(file_path: str) -> None:
    """Assert that a file exists at the given path."""
    assert Path(file_path).exists(), f"Expected file to exist: {file_path}"


def assert_file_not_empty(file_path: str) -> None:
    """Assert that a file exists and has non-zero size."""
    path = Path(file_path)
    assert path.exists(), f"Expected file to exist: {file_path}"
    assert path.stat().st_size > 0, f"Expected non-empty file: {file_path}"


def assert_workflow_result(result: dict, expected_success: bool = True) -> None:
    """Assert basic workflow success structure."""
    assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
    assert result.get("success") is expected_success, \
        f"Expected success={expected_success}, got: {result}"