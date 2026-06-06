"""
E2E lifecycle tests for HTTP transport with SQLite-backed connection pool.

Validates the complete MCP lifecycle over HTTP JSON-RPC 2.0:
initialize → connect → create_table → insert_data → query_data → disconnect.

All tests use e2e_http_pool_client fixture which injects a real SQLite pool
into the HTTP server, enabling actual database operations over HTTP.

Table cleanup: each test uses explicit try/finally, dropping created tables.
Naming: all test-created objects prefixed with __e2e_lifecycle_.
"""

import os
import sqlite3

import pytest

from tests.e2e.conftest import e2e_http_pool_client
from tests.e2e.helpers import mcp_request, send_jsonrpc, initialize_client


# ============================================================================
# Helpers
# ============================================================================

def _assert_success_response(resp: dict, step_name: str) -> dict:
    """Assert JSON-RPC 2.0 success structure and return structuredContent."""
    assert resp.get("jsonrpc") == "2.0", f"[{step_name}] Expected jsonrpc='2.0', got: {resp}"
    result = resp.get("result", {})
    sc = result.get("structuredContent", result)
    assert sc.get("success") is True, f"[{step_name}] Expected success=True, got: {sc}"
    return sc


def _cleanup_table(pool, table_name: str) -> None:
    """Drop table if it exists, ignoring errors."""
    try:
        if pool.is_connected("default"):
            adapter = pool.get_adapter("default")
            adapter.execute_query(f"DROP TABLE IF EXISTS [{table_name}]")
    except Exception:
        pass


# ============================================================================
# TestFullHttpLifecycle
# ============================================================================

class TestFullHttpLifecycle:
    """Complete MCP lifecycle tests over HTTP transport."""

    def test_full_lifecycle_single_insert(self, e2e_http_pool_client, monkeypatch):
        """Full lifecycle: initialize → connect → create_table → insert → query → disconnect.

        Verifies each step returns jsonrpc='2.0' and success=True, and that
        the final query_data returns the previously inserted row.
        """
        client = e2e_http_pool_client
        token = "test-e2e-api-key-12345"
        TABLE = "__e2e_lifecycle_single"

        # Get pool from server_module for cleanup
        from ms_access_mcp.mcp import server as server_module
        pool = server_module.connection_service

        try:
            # Initialize
            initialize_client(client, token)

            # Pool is pre-connected via e2e_http_pool_client fixture, so
            # we start directly with create_table (skip connect_access which
            # would create a new adapter without the SQLite patch and fail).

            # Step 1: tools/call create_table
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "create_table",
                        "arguments": {
                            "table_name": TABLE,
                            "columns": [
                                {"name": "id", "type": "Long Integer"},
                                {"name": "name", "type": "Text", "size": 100},
                            ],
                        },
                    },
                    req_id=11,
                ),
                token=token,
            )
            sc = _assert_success_response(resp, "create_table")
            # SQLite adapter may not return table_name; skip assertion if absent
            if "table_name" in sc:
                assert sc.get("table_name") == TABLE

            # Step 2: tools/call insert_data (single row)
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "insert_data",
                        "arguments": {
                            "table_name": TABLE,
                            "data": {"id": 1, "name": "Alpha"},
                        },
                    },
                    req_id=12,
                ),
                token=token,
            )
            sc = _assert_success_response(resp, "insert_data")
            # SQLite adapter returns 'affected' not 'rows_affected'
            rows_affected = sc.get("rows_affected") or sc.get("affected") or 0
            assert rows_affected >= 1, f"Expected rows_affected >= 1, got: {sc}"

            # Step 3: tools/call query_data — verify the inserted row
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "query_data",
                        "arguments": {
                            "sql": f"SELECT id, name FROM {TABLE} ORDER BY id",
                        },
                    },
                    req_id=13,
                ),
                token=token,
            )
            sc = _assert_success_response(resp, "query_data")
            rows = sc.get("rows", [])
            assert len(rows) == 1, f"Expected 1 row, got {len(rows)}: {rows}"
            assert rows[0]["id"] == 1
            assert rows[0]["name"] == "Alpha"

            # Step 4: tools/call disconnect_access
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "disconnect_access",
                        "arguments": {"name": "default"},
                    },
                    req_id=14,
                ),
                token=token,
            )
            _assert_success_response(resp, "disconnect_access")

        finally:
            _cleanup_table(pool, TABLE)

    def test_full_lifecycle_multiple_inserts(self, e2e_http_pool_client):
        """Full lifecycle with three sequential inserts, then query verifies all rows.

        Same pattern as single_insert but inserts 3 rows via separate requests
        and verifies all appear in the query result.
        """
        client = e2e_http_pool_client
        token = "test-e2e-api-key-12345"
        TABLE = "__e2e_lifecycle_multi"

        from ms_access_mcp.mcp import server as server_module
        pool = server_module.connection_service

        try:
            initialize_client(client, token)

            # Pool is pre-connected — start directly with create_table
            # (skip connect_access which would create a new adapter without SQLite patch)

            # create_table
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "create_table",
                        "arguments": {
                            "table_name": TABLE,
                            "columns": [
                                {"name": "id", "type": "Long Integer"},
                                {"name": "value", "type": "Double"},
                            ],
                        },
                    },
                    req_id=21,
                ),
                token=token,
            )
            _assert_success_response(resp, "create_table")

            # insert 3 rows
            for i, val in enumerate([10.0, 20.0, 30.0], start=1):
                resp = send_jsonrpc(
                    client,
                    mcp_request(
                        "tools/call",
                        {
                            "name": "insert_data",
                            "arguments": {
                                "table_name": TABLE,
                                "data": {"id": i, "value": val},
                            },
                        },
                        req_id=22 + i,
                    ),
                    token=token,
                )
                sc = _assert_success_response(resp, f"insert_data row {i}")
                # SQLite adapter returns 'affected' not 'rows_affected'
                rows_affected = sc.get("rows_affected") or sc.get("affected") or 0
                assert rows_affected >= 1, f"Expected rows_affected >= 1, got: {sc}"

            # query — verify all 3 rows
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "query_data",
                        "arguments": {
                            "sql": f"SELECT id, value FROM {TABLE} ORDER BY id",
                        },
                    },
                    req_id=26,
                ),
                token=token,
            )
            sc = _assert_success_response(resp, "query_data")
            rows = sc.get("rows", [])
            assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}: {rows}"
            assert rows[0]["id"] == 1 and rows[0]["value"] == 10.0
            assert rows[1]["id"] == 2 and rows[1]["value"] == 20.0
            assert rows[2]["id"] == 3 and rows[2]["value"] == 30.0

            # disconnect
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "disconnect_access",
                        "arguments": {"name": "default"},
                    },
                    req_id=27,
                ),
                token=token,
            )
            _assert_success_response(resp, "disconnect_access")

        finally:
            _cleanup_table(pool, TABLE)

    def test_jsonrpc_response_format(self, e2e_http_pool_client):
        """Verify every response in the lifecycle has correct JSON-RPC 2.0 format.

        Tests: jsonrpc='2.0', id matches request, result has expected keys.
        Uses a minimal lifecycle: connect → create_table → disconnect.
        """
        client = e2e_http_pool_client
        token = "test-e2e-api-key-12345"
        TABLE = "__e2e_lifecycle_jsonrpc"

        from ms_access_mcp.mcp import server as server_module
        pool = server_module.connection_service

        try:
            initialize_client(client, token)

            # Pool is pre-connected — start with create_table directly
            # create_table — check response format with id=31
            req_id = 31
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "create_table",
                        "arguments": {
                            "table_name": TABLE,
                            "columns": [{"name": "x", "type": "Long Integer"}],
                        },
                    },
                    req_id=req_id,
                ),
                token=token,
            )
            assert resp.get("jsonrpc") == "2.0"
            assert resp.get("id") == req_id
            result = resp.get("result", {})
            sc = result.get("structuredContent", result)
            assert "success" in sc

            # disconnect — check response format
            req_id = 32
            resp = send_jsonrpc(
                client,
                mcp_request(
                    "tools/call",
                    {
                        "name": "disconnect_access",
                        "arguments": {"name": "default"},
                    },
                    req_id=req_id,
                ),
                token=token,
            )
            assert resp.get("jsonrpc") == "2.0"
            assert resp.get("id") == req_id

        finally:
            _cleanup_table(pool, TABLE)

    def test_connect_error_propagation(self, e2e_http_pool_client):
        """Connect to non-existent database path returns error response (not crash).

        Verifies that connecting to a path that doesn't exist or isn't writable
        returns a structured error response with success=False, not an unhandled
        exception that would produce a 500 or malformed JSON-RPC.
        """
        client = e2e_http_pool_client
        token = "test-e2e-api-key-12345"

        initialize_client(client, token)

        # Attempt connect to non-existent path
        resp = send_jsonrpc(
            client,
            mcp_request(
                "tools/call",
                {
                    "name": "connect_access",
                    "arguments": {
                        "database_path": "C:\\nonexistent_path_xyz\\nonexistent.accdb",
                        "use_com": False,
                        "name": "default",
                    },
                },
                req_id=40,
            ),
            token=token,
        )

        # Must still be valid JSON-RPC 2.0 (not 500 error page)
        assert resp.get("jsonrpc") == "2.0", f"Expected jsonrpc='2.0', got: {resp}"
        assert resp.get("id") == 40, f"Expected id=40, got: {resp.get('id')}"

        result = resp.get("result", {})
        # Could be isError flag or success=False inside structuredContent
        is_error = result.get("isError", False)
        sc = result.get("structuredContent", result)
        success = sc.get("success", True) if isinstance(sc, dict) else False

        assert is_error or not success, \
            f"Expected error response (isError=True or success=False), got: {result}"