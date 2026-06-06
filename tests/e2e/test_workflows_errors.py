"""
E2E workflow error tests — negative scenarios for pool and HTTP transport layers.

Validates that the MCP server returns structured `success: false` payloads
with meaningful error messages instead of raising unhandled exceptions.

All tests follow TDD strict mode: write tests first, implement, verify.
"""

import pytest

from tests.e2e.conftest import e2e_pool, empty_pool, e2e_http_client, call_mcp_tool
from tests.e2e.helpers import mcp_request, send_jsonrpc, initialize_client, assert_workflow_result


# ============================================================================
# TestRecoveryPoolErrors — Tier 1: direct pool/tool errors
# ============================================================================

class TestRecoveryPoolErrors:
    """Pool-level error recovery — operations on empty pool or invalid references."""

    def test_disconnect_without_connection(self, empty_pool):
        """disconnect_access('default') on empty pool returns without raising."""
        pool = empty_pool

        # Must not raise — pool gracefully handles disconnect on non-existent connection
        pool.disconnect("default")

        # Pool must remain usable after the no-op disconnect
        assert not pool.is_connected("default")

    def test_query_without_connection(self, empty_pool):
        """query_data on empty pool returns success=false with 'Not connected to database'."""
        result = call_mcp_tool(
            "query_data",
            "SELECT 1",
            connection_service=empty_pool,
        )
        assert_workflow_result(result, expected_success=False)
        assert "Not connected to database" in result.get("error", "")

    def test_create_table_without_connection(self, empty_pool):
        """create_table on empty pool returns success=false with 'Not connected to database'."""
        result = call_mcp_tool(
            "create_table",
            "__e2e_test_err",
            [{"name": "id", "type": "Long Integer"}],
            connection_service=empty_pool,
        )
        assert_workflow_result(result, expected_success=False)
        assert "Not connected to database" in result.get("error", "")

    def test_invalid_sql_query(self, e2e_pool):
        """Querying a nonexistent table returns success=false with table-not-found message."""
        result = call_mcp_tool(
            "query_data",
            "SELECT * FROM nonexistent_table_xyz_123",
            connection_service=e2e_pool,
        )
        assert_workflow_result(result, expected_success=False)
        error_msg = result.get("error", "")
        assert "nonexistent" in error_msg.lower() or "not found" in error_msg.lower()

    def test_insert_nonexistent_table(self, e2e_pool):
        """insert_data to nonexistent table returns success=false."""
        result = call_mcp_tool(
            "insert_data",
            "nonexistent_table_xyz",
            [{"col": "val"}],
            connection_service=e2e_pool,
        )
        assert_workflow_result(result, expected_success=False)
        error_msg = result.get("error", "")
        assert "nonexistent" in error_msg.lower() or "not found" in error_msg.lower() or "no such table" in error_msg.lower()

    def test_schema_nonexistent_table(self, e2e_pool):
        """get_table_schema for nonexistent table returns success=false."""
        result = call_mcp_tool(
            "get_table_schema",
            "nonexistent_table_xyz",
            connection_service=e2e_pool,
        )
        assert_workflow_result(result, expected_success=False)
        error_msg = result.get("error", "")
        assert "nonexistent" in error_msg.lower() or "not found" in error_msg.lower() or "no such table" in error_msg.lower()

    def test_set_active_invalid(self, e2e_pool):
        """set_active_connection to nonexistent name returns success=false."""
        result = call_mcp_tool(
            "set_active_connection",
            "nonexistent",
            connection_service=e2e_pool,
        )
        assert_workflow_result(result, expected_success=False)
        error_msg = result.get("error", "")
        assert "nonexistent" in error_msg.lower() or "not found" in error_msg.lower() or "Connection" in error_msg


# ============================================================================
# TestRecoveryHttpErrors — Tier 2: HTTP transport / JSON-RPC errors
# ============================================================================

class TestRecoveryHttpErrors:
    """HTTP transport error recovery — missing initialize and unknown tools."""

    @pytest.mark.xfail(
        strict=False,
        reason="FastMCP stateless_http=True does not enforce initialize handshake",
    )
    def test_tool_call_without_initialize(self, e2e_http_client):
        """Calling a tool before initialize should return JSON-RPC error.

        Current limitation: FastMCP stateless_http=True mode does not
        enforce the initialize handshake before accepting tool calls.
        The test documents the spec requirement — marked xfail until
        the server enforces this MCP protocol requirement.
        """
        client = e2e_http_client
        token = "test-e2e-api-key-12345"

        # Send tools/call WITHOUT prior initialize
        req = mcp_request(
            method="tools/call",
            params={
                "name": "diagnose_environment",
                "arguments": {},
            },
            req_id=1,
        )
        resp = send_jsonrpc(client, req, token=token)

        # Must be a valid JSON-RPC error response (not HTTP 500)
        assert resp.get("jsonrpc") == "2.0"
        assert "error" in resp, f"Expected JSON-RPC error, got: {resp}"

    def test_nonexistent_tool_call(self, e2e_http_client):
        """Calling a nonexistent tool returns isError=true."""
        client = e2e_http_client
        token = "test-e2e-api-key-12345"

        # Initialize first
        initialize_client(client, token)

        # Call nonexistent tool
        req = mcp_request(
            method="tools/call",
            params={
                "name": "nonexistent_tool_xyz",
                "arguments": {},
            },
            req_id=2,
        )
        resp = send_jsonrpc(client, req, token=token)

        assert resp.get("jsonrpc") == "2.0"
        result = resp.get("result", {})
        assert result.get("isError") is True, f"Expected isError=True, got: {result}"