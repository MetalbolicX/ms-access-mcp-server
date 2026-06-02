"""
Integration tests for MCP tools using ConnectionPool with SQLite-backed adapters.

Validates that MCP tool functions correctly use connection_name to route
to the right adapter in the pool, without requiring Windows or MS Access.
"""

import sys
import pytest
from unittest.mock import MagicMock

from ms_access_mcp.services.connection import ConnectionPool, ConnectionState
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.mcp import server as server_module

from conftest import pool_with_sqlite, pool_with_two_adapters, sqlite_db
from helpers import call_mcp_tool


# ---- Tests ---------------------------------------------------------------------

class TestSaveQueryTool:
    """save_query tool with real SQLite-backed pool and mock adapters."""

    def test_save_query_creates_new_when_no_existing(self, pool_with_sqlite):
        """save_query with overwrite=False creates new query when get_queries returns empty."""
        # Patch get_queries to return empty and create_query to succeed
        adapter = pool_with_sqlite.get_adapter("default")
        adapter.get_queries = MagicMock(return_value=[])
        adapter.create_query = MagicMock(return_value={"success": True})

        result = call_mcp_tool(
            "save_query",
            "TestQuery", "SELECT 1 AS test",
            overwrite=False,
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is True
        assert result["action"] == "created"
        assert result["query"] == "TestQuery"

    def test_save_query_rejects_existing_without_overwrite(self, pool_with_sqlite):
        """save_query with overwrite=False errors if query exists."""
        adapter = pool_with_sqlite.get_adapter("default")
        mock_query = MagicMock()
        mock_query.name = "DupQuery"
        adapter.get_queries = MagicMock(return_value=[mock_query])

        result = call_mcp_tool(
            "save_query",
            "DupQuery", "SELECT 2",
            overwrite=False,
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False
        assert "already exists" in result["error"]

    def test_save_query_overwrites_existing(self, pool_with_sqlite):
        """save_query with overwrite=True updates existing query."""
        adapter = pool_with_sqlite.get_adapter("default")
        mock_query = MagicMock()
        mock_query.name = "UpdQuery"
        adapter.get_queries = MagicMock(return_value=[mock_query])
        adapter.set_query_sql = MagicMock(return_value={"success": True})

        result = call_mcp_tool(
            "save_query",
            "UpdQuery", "SELECT 2 AS num",
            overwrite=True,
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is True
        assert result["action"] == "updated"

    def test_save_query_uses_connection_name(self, pool_with_two_adapters):
        """save_query uses the adapter for the specified connection_name."""
        prod_adapter = pool_with_two_adapters.get_adapter("prod")
        prod_adapter.get_queries = MagicMock(return_value=[])
        prod_adapter.create_query = MagicMock(return_value={"success": True})

        result = call_mcp_tool(
            "save_query",
            "ProdQuery", "SELECT name FROM __meta",
            overwrite=False, connection_name="prod",
            connection_service=pool_with_two_adapters,
        )
        if not result["success"]:
            print("FAILURE:", result.get("error", "unknown"))
        assert result["success"] is True
        assert result["query"] == "ProdQuery"
        prod_adapter.create_query.assert_called_once_with("ProdQuery", "SELECT name FROM __meta")


class TestVbaListProceduresTool:
    """vba_list_procedures tool with real pool."""

    def test_vba_list_procedures_returns_proper_structure(self, pool_with_sqlite):
        """vba_list_procedures via OdbcAdapter returns None -> tool returns success=True with procedures list."""
        result = call_mcp_tool(
            "vba_list_procedures",
            "Module1",
            connection_service=pool_with_sqlite,
        )
        # OdbcAdapter.vba_list_procedures returns None, tool treats None as empty list
        assert result["success"] is True
        assert result["module"] == "Module1"
        assert "procedures" in result


class TestVbaGetProcedureTool:
    """vba_get_procedure tool with real pool."""

    def test_vba_get_procedure_returns_not_found(self, pool_with_sqlite):
        """vba_get_procedure returns error via OdbcAdapter when procedure not found."""
        result = call_mcp_tool(
            "vba_get_procedure",
            "Module1", "NonExistent",
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestVbaReplaceProcedureTool:
    """vba_replace_procedure tool with real pool."""

    def test_vba_replace_procedure_returns_failure(self, pool_with_sqlite):
        """vba_replace_procedure returns error via OdbcAdapter when not WinCom."""
        result = call_mcp_tool(
            "vba_replace_procedure",
            "Module1", "Proc1", "Sub Proc1()\nEnd Sub",
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False


class TestListConnectionsTool:
    """list_connections from connection.py MCP tool."""

    def test_list_connections_returns_correct_structure(self, pool_with_sqlite, sqlite_db):
        """list_connections returns database/adapter_type for each connection."""
        result = call_mcp_tool(
            "list_connections",
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is True
        assert "default" in result["connections"]
        conn_info = result["connections"]["default"]
        assert "database" in conn_info
        assert conn_info["database"] == sqlite_db
        assert "adapter_type" in conn_info
        assert conn_info["adapter_type"] == "odbc"

    def test_list_connections_with_multiple(self, pool_with_two_adapters):
        """list_connections returns all named connections."""
        result = call_mcp_tool(
            "list_connections",
            connection_service=pool_with_two_adapters,
        )
        assert result["success"] is True
        assert "prod" in result["connections"]
        assert "dev" in result["connections"]


class TestGetSystemTablesTool:
    """get_system_tables with real pool."""

    def test_get_system_tables_returns_list(self, pool_with_sqlite):
        """get_system_tables via OdbcAdapter returns a list result."""
        result = call_mcp_tool(
            "get_system_tables",
            connection_name="default",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "system_tables" in result
        assert isinstance(result["system_tables"], list)


class TestDiagnoseEnvironmentTool:
    """diagnose_environment tool with real pool."""

    def test_diagnose_environment_returns_info(self, pool_with_sqlite):
        """diagnose_environment returns diagnostic info dict."""
        result = call_mcp_tool(
            "diagnose_environment",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "diagnostics" in result
        assert "platform" in result["diagnostics"]


class TestRecoverAccessTool:
    """recover_access tool with real pool."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_recover_access_not_supported_on_linux(self, pool_with_sqlite):
        """recover_access returns success=False on non-Windows."""
        result = call_mcp_tool(
            "recover_access",
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False
        assert "Not supported" in result["error"]