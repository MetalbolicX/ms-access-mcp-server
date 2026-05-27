"""Tests for mcp/linked_tables.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


class TestLinkedTablesConnectionGuards:
    """Tests that linked table tools check connection before executing."""

    @pytest.mark.parametrize("tool_func,args", [
        (server.get_linked_tables, ()),
        (server.create_linked_table, ("lnk", "RemoteT", "ODBC;DSN=test")),
        (server.refresh_linked_table, ("lnk",)),
        (server.unlink_table, ("lnk",)),
    ])
    def test_linked_table_tools_return_error_when_not_connected(self, tool_func, args):
        """Each linked table tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(tool_func.__globals__, connection_service=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestGetLinkedTables:
    """Tests for get_linked_tables tool."""

    def test_get_linked_tables_delegates_to_adapter(self):
        """get_linked_tables should delegate to adapter.get_linked_tables."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.get_linked_tables.return_value = {"success": True, "tables": []}
        with patch.dict(server.get_linked_tables.__globals__, connection_service=mock_conn):
            result = server.get_linked_tables()
            assert result["success"] is True
            mock_conn.adapter.get_linked_tables.assert_called_once()

    def test_get_linked_tables_returns_adapter_error(self):
        """get_linked_tables should return error on adapter failure."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.get_linked_tables.side_effect = RuntimeError("DAO error")
        with patch.dict(server.get_linked_tables.__globals__, connection_service=mock_conn):
            result = server.get_linked_tables()
            assert result["success"] is False
            assert "DAO error" in result["error"]


class TestCreateLinkedTable:
    """Tests for create_linked_table tool."""

    def test_create_linked_table_delegates_to_adapter(self):
        """create_linked_table should delegate to adapter.create_linked_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_linked_table.return_value = {"success": True}
        args = ("lnkName", "RemoteT", "ODBC;DSN=test")
        with patch.dict(server.create_linked_table.__globals__, connection_service=mock_conn):
            result = server.create_linked_table(*args)
            assert result["success"] is True
            mock_conn.adapter.create_linked_table.assert_called_once_with("lnkName", "RemoteT", "ODBC;DSN=test")

    def test_create_linked_table_returns_error_on_exception(self):
        """create_linked_table should return error on exception."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_linked_table.side_effect = RuntimeError("Link failed")
        args = ("lnkName", "RemoteT", "ODBC;DSN=bad")
        with patch.dict(server.create_linked_table.__globals__, connection_service=mock_conn):
            result = server.create_linked_table(*args)
            assert result["success"] is False
            assert "Link failed" in result["error"]


class TestRefreshLinkedTable:
    """Tests for refresh_linked_table tool."""

    def test_refresh_linked_table_delegates_to_adapter(self):
        """refresh_linked_table should delegate to adapter.refresh_linked_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.refresh_linked_table.return_value = {"success": True}
        with patch.dict(server.refresh_linked_table.__globals__, connection_service=mock_conn):
            result = server.refresh_linked_table("existing_link")
            assert result["success"] is True
            mock_conn.adapter.refresh_linked_table.assert_called_once_with("existing_link")


class TestUnlinkTable:
    """Tests for unlink_table tool."""

    def test_unlink_table_delegates_to_adapter(self):
        """unlink_table should delegate to adapter.unlink_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.unlink_table.return_value = {"success": True}
        with patch.dict(server.unlink_table.__globals__, connection_service=mock_conn):
            result = server.unlink_table("lnkName")
            assert result["success"] is True
            mock_conn.adapter.unlink_table.assert_called_once_with("lnkName")
