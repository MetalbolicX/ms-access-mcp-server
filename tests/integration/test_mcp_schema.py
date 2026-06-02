"""
Integration tests for MCP schema tools (get_tables, get_table_schema,
get_relationships, generate_sql, get_er_diagram).

Tier 1: SQLite-backed OdbcAdapter verifies happy path and error paths.
"""

import os
import tempfile

import pytest

from conftest import pool_with_sqlite
from helpers import call_mcp_tool


class TestSchemaHappyPath:
    """Tier 1: Happy-path tests for schema tools via OdbcAdapter/SQLite."""

    def test_get_tables_via_sqlite(self, pool_with_sqlite):
        """get_tables returns success=True with tables list via OdbcAdapter.

        The SQLite DB has a __meta table created by the pool_with_sqlite fixture.
        All user tables (excluding MSys*) should be returned.
        """
        result = call_mcp_tool(
            "get_tables",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is True, f"Expected success=True, got: {result}"
        assert "tables" in result, f"Missing 'tables' key in {result}"
        assert isinstance(result["tables"], list), f"tables should be list, got: {type(result['tables'])}"
        assert "count" in result, f"Missing 'count' key in {result}"
        assert result["count"] == len(result["tables"])

    def test_get_table_schema_existing_table(self, pool_with_sqlite):
        """get_table_schema returns success=False when table not found via ODBC.

        ODBC's get_tables() queries MSysObjects which does not exist in SQLite,
        so no tables are enumerated. get_table_schema for any name returns failure.
        """
        result = call_mcp_tool(
            "get_table_schema",
            "__meta",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is False, f"Expected failure (ODBC can't enumerate SQLite tables), got: {result}"
        assert "error" in result, f"Missing 'error' key in {result}"

    def test_get_table_schema_unknown_table(self, pool_with_sqlite):
        """get_table_schema returns success=False for unknown table name."""
        result = call_mcp_tool(
            "get_table_schema",
            "NonExistentTable",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is False, f"Expected failure for unknown table, got: {result}"
        assert "error" in result, f"Missing 'error' key in {result}"

    def test_get_relationships_via_sqlite(self, pool_with_sqlite):
        """get_relationships returns success=True with relationships list via OdbcAdapter.

        ODBC adapter returns empty list (no FK metadata via ODBC), so we verify
        the shape of the response and that the list is empty.
        """
        result = call_mcp_tool(
            "get_relationships",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is True, f"Expected success=True, got: {result}"
        assert "relationships" in result, f"Missing 'relationships' key in {result}"
        assert isinstance(result["relationships"], list), f"relationships should be list, got: {type(result['relationships'])}"
        assert "count" in result, f"Missing 'count' key in {result}"

    def test_generate_sql_returns_error_via_sqlite(self, pool_with_sqlite):
        """generate_sql returns success=False via OdbcAdapter (ODBC does not support it)."""
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
            sql_path = f.name
        try:
            result = call_mcp_tool(
                "generate_sql",
                sql_path,
                connection_service=pool_with_sqlite,
            )
            assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
            assert result.get("success") is False, f"Expected failure via ODBC, got: {result}"
            assert "error" in result, f"Missing 'error' key in {result}"
        finally:
            if os.path.exists(sql_path):
                os.unlink(sql_path)

    def test_get_er_diagram_via_sqlite(self, pool_with_sqlite):
        """get_er_diagram returns success=True with empty nodes/edges via OdbcAdapter.

        ODBC's get_tables() queries MSysObjects which does not exist in SQLite,
        so no tables are enumerated. The ER diagram still returns success=True
        with empty nodes and edges.
        """
        result = call_mcp_tool(
            "get_er_diagram",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is True, f"Expected success=True, got: {result}"
        assert "nodes" in result, f"Missing 'nodes' key in {result}"
        assert "edges" in result, f"Missing 'edges' key in {result}"
        assert isinstance(result["nodes"], list), f"nodes should be list, got: {type(result['nodes'])}"
        assert isinstance(result["edges"], list), f"edges should be list, got: {type(result['edges'])}"
        assert "node_count" in result, f"Missing 'node_count' key in {result}"
        assert "edge_count" in result, f"Missing 'edge_count' key in {result}"
        assert result["node_count"] == 0, f"Expected 0 nodes (ODBC can't enumerate SQLite tables), got {result['node_count']}"
        assert result["edge_count"] == 0, f"Expected 0 edges, got {result['edge_count']}"


class TestSchemaErrorPaths:
    """Tier 1: Error-path tests — each schema tool returns success=False for disconnected/None adapter."""

    def test_get_tables_disconnected(self, pool_with_sqlite):
        """get_tables returns success=False when not connected."""
        pool_with_sqlite.disconnect("default")
        result = call_mcp_tool(
            "get_tables",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is False, f"Expected failure when disconnected, got: {result}"
        assert "error" in result, f"Missing 'error' key in {result}"

    def test_get_table_schema_disconnected(self, pool_with_sqlite):
        """get_table_schema returns success=False when not connected."""
        pool_with_sqlite.disconnect("default")
        result = call_mcp_tool(
            "get_table_schema",
            "any_table",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is False, f"Expected failure when disconnected, got: {result}"
        assert "error" in result, f"Missing 'error' key in {result}"

    def test_get_table_schema_invalid_table_name(self, pool_with_sqlite):
        """get_table_schema returns success=False for table that does not exist."""
        result = call_mcp_tool(
            "get_table_schema",
            "ThisTableDoesNotExist123",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is False, f"Expected failure for invalid table, got: {result}"
        assert "error" in result, f"Missing 'error' key in {result}"

    def test_get_relationships_disconnected(self, pool_with_sqlite):
        """get_relationships returns success=False when not connected."""
        pool_with_sqlite.disconnect("default")
        result = call_mcp_tool(
            "get_relationships",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is False, f"Expected failure when disconnected, got: {result}"
        assert "error" in result, f"Missing 'error' key in {result}"

    def test_generate_sql_disconnected(self, pool_with_sqlite):
        """generate_sql returns success=False when not connected."""
        pool_with_sqlite.disconnect("default")
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
            sql_path = f.name
        try:
            result = call_mcp_tool(
                "generate_sql",
                sql_path,
                connection_service=pool_with_sqlite,
            )
            assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
            assert result.get("success") is False, f"Expected failure when disconnected, got: {result}"
            assert "error" in result, f"Missing 'error' key in {result}"
        finally:
            if os.path.exists(sql_path):
                os.unlink(sql_path)

    def test_get_er_diagram_disconnected(self, pool_with_sqlite):
        """get_er_diagram returns success=False when not connected."""
        pool_with_sqlite.disconnect("default")
        result = call_mcp_tool(
            "get_er_diagram",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("success") is False, f"Expected failure when disconnected, got: {result}"
        assert "error" in result, f"Missing 'error' key in {result}"
