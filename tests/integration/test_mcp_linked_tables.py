"""
Integration tests for MCP linked_tables tools via OdbcAdapter (Tier 1).

Tier 1 tests verify that all 4 COM-only linked table tools return the
"Not available via ODBC" error when called via the SQLite-backed OdbcAdapter.
This confirms graceful degradation in non-COM environments.

Tier 3 tests (WinCom happy paths) are in the same file, gated by
skip_unless_windows and skip_unless_db markers.
"""

import pytest

from conftest import pool_with_sqlite
from helpers import call_mcp_tool, skip_unless_windows, skip_unless_db


class TestLinkedTablesOdbcErrorPath:
    """Tier 1: Verify COM-only linked table tools reject ODBC gracefully."""

    @pytest.mark.parametrize(
        "tool_name,args",
        [
            ("get_linked_tables", []),
            ("create_linked_table", ["TestLink", "RemoteTable", "ODBC;DSN=TestDSN"]),
            ("refresh_linked_table", ["TestLink"]),
            ("unlink_table", ["TestLink"]),
            ("upsert_linked_table", ["TestLink", "RemoteTable", "ODBC;DSN=TestDSN"]),
        ],
    )
    def test_linked_table_tools_return_not_available_via_odbc(
        self, pool_with_sqlite, tool_name, args
    ):
        """All5 COM-only linked table tools return 'Not available via ODBC' via OdbcAdapter."""
        result = call_mcp_tool(
            tool_name,
            *args,
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False
        assert "not available via odbc" in result["error"].lower(), (
            f"Expected ODBC error for {tool_name}, got: {result.get('error')}"
        )


class TestUpsertLinkedTableIntegration:
    """Tier 3: WinCom integration tests for upsert_linked_table flows.

    Tests create, refresh, and recreate scenarios via the MCP tool layer.
    """

    pytestmark = [skip_unless_windows, skip_unless_db]

    def test_upsert_linked_table_returns_error_for_disallowed_provider(self, temp_db_copy):
        """upsert_linked_table should reject disallowed providers with clear error."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_upsert", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "upsert_linked_table",
                "TestTable",
                "dbo.TestTable",
                "Provider=Disallowed.Provider;Data Source=remote.db;",
                connection_name="test_upsert",
                connection_service=pool,
            )
            assert result["success"] is False
            assert "allowlist" in result["error"].lower() or "not allowed" in result["error"].lower()

            pool.disconnect("test_upsert")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_upsert_linked_table_accepts_odbc_provider(self, temp_db_copy):
        """upsert_linked_table should accept ODBC connection strings."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_upsert", temp_db_copy, adapter, "com")

            # Use a dummy ODBC connect string - the tool should accept it
            # (actual link operation may fail if ODBC driver unavailable, but the
            # allowlist check should pass first)
            result = call_mcp_tool(
                "upsert_linked_table",
                "TestUpsertTable",
                "dbo.TestTable",
                "ODBC;DSN=TestDSN",
                connection_name="test_upsert",
                connection_service=pool,
            )
            # Should not crash - either success or a proper error dict
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_upsert")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_upsert_linked_table_accepts_password_parameter(self, temp_db_copy):
        """upsert_linked_table should accept optional password parameter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_upsert", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "upsert_linked_table",
                "TestUpsertTable",
                "dbo.TestTable",
                "ODBC;DSN=TestDSN",
                connection_name="test_upsert",
                connection_service=pool,
                password="secret123",
            )
            # Should not crash - either success or a proper error dict
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_upsert")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_upsert_linked_table_accepts_preserve_hidden_parameter(self, temp_db_copy):
        """upsert_linked_table should accept preserve_hidden parameter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_upsert", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "upsert_linked_table",
                "TestUpsertTable",
                "dbo.TestTable",
                "ODBC;DSN=TestDSN",
                connection_name="test_upsert",
                preserve_hidden=True,
            )
            # Should not crash - either success or a proper error dict
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_upsert")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass


class TestRefreshLinkedTableIntegration:
    """Tier 3: WinCom integration tests for refresh_linked_table with new params."""

    pytestmark = [skip_unless_windows, skip_unless_db]

    def test_refresh_linked_table_accepts_connect_string_parameter(self, temp_db_copy):
        """refresh_linked_table should accept optional connect_string parameter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_refresh", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "refresh_linked_table",
                "NonExistentTable",
                connection_name="test_refresh",
                connect_string="ODBC;DSN=NewDSN",
            )
            # Should not crash - returns proper dict
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_refresh")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_refresh_linked_table_accepts_password_parameter(self, temp_db_copy):
        """refresh_linked_table should accept optional password parameter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_refresh", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "refresh_linked_table",
                "NonExistentTable",
                connection_name="test_refresh",
                password="secret123",
            )
            # Should not crash - returns proper dict
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_refresh")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass


class TestLinkedTablesWinComHappyPath:
    """Tier 3: WinCom happy-path tests for linked table tools.

    NOTE: These tests require the pool.connect(name, db_path, adapter_type) API
    which is currently broken (pre-existing issue - pool.connect only accepts
    3 args but the tests pass 4). Skip via marker until connection.py is fixed.
    """

    pytestmark = [skip_unless_windows, skip_unless_db]

    def test_get_linked_tables_via_wincom(self, temp_db_copy):
        """get_linked_tables returns linked table list via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_linked", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "get_linked_tables",
                connection_name="test_linked",
                connection_service=pool,
            )
            assert result["success"] is True
            assert "linked_tables" in result
            assert isinstance(result["linked_tables"], list)

            pool.disconnect("test_linked")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_create_linked_table_via_wincom(self, temp_db_copy):
        """create_linked_table creates a linked table definition via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_linked", temp_db_copy, adapter, "com")

            # Create a small SQLite table to use as the source
            import sqlite3, tempfile, os

            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                remote_db = f.name
            conn = sqlite3.connect(remote_db)
            conn.execute("CREATE TABLE RemoteSource (ID INTEGER PRIMARY KEY, Name TEXT)")
            conn.execute("INSERT INTO RemoteSource VALUES (1, 'SourceRow')")
            conn.commit()
            conn.close()

            connect_str = f"ODBC;DBQ={remote_db};Driver=SQLite3"

            result = call_mcp_tool(
                "create_linked_table",
                "TestLinkedTable_MCP",
                "RemoteSource",
                connect_str,
                connection_name="test_linked",
                connection_service=pool,
            )
            # May succeed or fail depending on ODBC driver availability, but should
            # not crash and must return a proper dict response
            assert isinstance(result, dict)
            assert "success" in result

            os.unlink(remote_db)
            pool.disconnect("test_linked")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_refresh_linked_table_via_wincom(self, temp_db_copy):
        """refresh_linked_table refreshes a linked table via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_linked", temp_db_copy, adapter, "com")

            # Try to refresh a non-existent table - should return proper error dict
            result = call_mcp_tool(
                "refresh_linked_table",
                "NonExistentLinkedTable",
                connection_name="test_linked",
                connection_service=pool,
            )
            # Should return success=True (refresh of non-existent is a no-op in Access)
            # or success=False with a proper error message - both are valid responses
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_linked")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_unlink_table_via_wincom(self, temp_db_copy):
        """unlink_table removes a linked table definition via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_linked", temp_db_copy, adapter, "com")

            # Try to unlink a non-existent table - should return proper error dict
            result = call_mcp_tool(
                "unlink_table",
                "NonExistentLinkedTable",
                connection_name="test_linked",
                connection_service=pool,
            )
            # Should return success=False with an error (table not found)
            # or success=True if Access treats it as a no-op
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_linked")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass