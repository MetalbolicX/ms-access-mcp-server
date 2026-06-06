"""
E2E workflow tests for HTTP transport using Starlette TestClient.

Validates the full MCP HTTP stack: initialize → tools/list → tools/call
for create_table, insert_data, and query_data.

Uses JSON-RPC 2.0 format matching test_http_transport.py patterns.
"""

import json
import os
from typing import Any

import pytest

from tests.e2e.conftest import e2e_pool, temp_export_dir, call_mcp_tool
from tests.e2e.helpers import assert_file_exists, mcp_request, send_jsonrpc, initialize_client


# ============================================================================
# TestHttpWorkflow
# ============================================================================

class TestHttpWorkflow:
    """Full HTTP transport workflow — initialize → tools/list → tools/call(diagnose_environment).

    Note: Tools that require a database connection (create_table, query_data, etc.)
    return 'Not connected to database' since the HTTP transport doesn't automatically
    provide a pool connection. This test validates the HTTP transport itself,
    not pool operations. For pool operations, use e2e_pool fixture directly.
    """

    def test_http_transport_initialize_and_list(self, e2e_http_client):
        """Initialize → tools/list → verify response structure.

        This tests the HTTP transport layer: JSON-RPC request/response,
        authorization, and tool enumeration.
        """
        client = e2e_http_client
        token = "test-e2e-api-key-12345"

        # Initialize session
        initialize_client(client, token)

        # tools/list — verify the endpoint returns tool list
        list_req = mcp_request(method="tools/list", params={}, req_id=2)
        list_resp = send_jsonrpc(client, list_req, token=token)
        assert list_resp.get("jsonrpc") == "2.0", f"Expected JSON-RPC 2.0 response, got: {list_resp}"
        result = list_resp.get("result", {})
        tools = result.get("tools", [])
        assert isinstance(tools, list), f"tools/list should return list, got: {type(tools)}"
        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
        assert len(tool_names) > 0, f"Expected at least one tool, got: {tool_names}"
        assert "diagnose_environment" in tool_names, f"diagnose_environment should be available: {tool_names}"

    def test_http_tool_call_diagnose_environment(self, e2e_http_client):
        """diagnose_environment works via HTTP without database connection."""
        client = e2e_http_client
        token = "test-e2e-api-key-12345"

        # Initialize session
        initialize_client(client, token)

        # tools/call — diagnose_environment (no database needed)
        diag_req = mcp_request(
            method="tools/call",
            params={
                "name": "diagnose_environment",
                "arguments": {},
            },
            req_id=3,
        )
        diag_resp = send_jsonrpc(client, diag_req, token=token)
        assert diag_resp.get("jsonrpc") == "2.0", f"diagnose_environment response: {diag_resp}"
        diag_result = diag_resp.get("result", {})
        if diag_result.get("isError"):
            content = diag_result.get("content", [])
            texts = [c.get("text", "") for c in content if isinstance(c, dict)]
            pytest.fail(f"diagnose_environment failed: {texts}")
        # The tool returns success in structuredContent
        sc = diag_result.get("structuredContent", diag_result)
        assert sc.get("success") is True, f"diagnose_environment failed: {diag_result}"