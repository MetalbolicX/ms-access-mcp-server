import pytest
from unittest.mock import MagicMock
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.base import AccessAdapter


class TestLinkedTableProtocol:
    def test_wincom_has_get_linked_tables(self):
        assert hasattr(WinComAdapter, "get_linked_tables")

    def test_wincom_has_create_linked_table(self):
        assert hasattr(WinComAdapter, "create_linked_table")

    def test_wincom_has_refresh_linked_table(self):
        assert hasattr(WinComAdapter, "refresh_linked_table")

    def test_wincom_has_unlink_table(self):
        assert hasattr(WinComAdapter, "unlink_table")

    def test_protocol_defines_linked_table_methods(self):
        assert hasattr(AccessAdapter, "get_linked_tables")
        assert hasattr(AccessAdapter, "create_linked_table")
        assert hasattr(AccessAdapter, "refresh_linked_table")
        assert hasattr(AccessAdapter, "unlink_table")


class TestGetLinkedTablesOdbcStub:
    def test_returns_error_not_connected(self):
        """OdbcAdapter.get_linked_tables returns error when not connected."""
        adapter = OdbcAdapter()
        result = adapter.get_linked_tables()
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]

    def test_returns_error_connected(self):
        """OdbcAdapter.get_linked_tables returns error even when connected."""
        adapter = OdbcAdapter()
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"
        result = adapter.get_linked_tables()
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]


class TestCreateLinkedTableOdbcStub:
    def test_returns_error_not_connected(self):
        """OdbcAdapter.create_linked_table returns error when not connected."""
        adapter = OdbcAdapter()
        result = adapter.create_linked_table("name", "source", "connect")
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]

    def test_returns_error_connected(self):
        """OdbcAdapter.create_linked_table returns error even when connected."""
        adapter = OdbcAdapter()
        adapter._conn = MagicMock()
        result = adapter.create_linked_table("name", "source", "connect")
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]


class TestRefreshLinkedTableOdbcStub:
    def test_returns_error_not_connected(self):
        """OdbcAdapter.refresh_linked_table returns error when not connected."""
        adapter = OdbcAdapter()
        result = adapter.refresh_linked_table("name")
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]

    def test_returns_error_connected(self):
        """OdbcAdapter.refresh_linked_table returns error even when connected."""
        adapter = OdbcAdapter()
        adapter._conn = MagicMock()
        result = adapter.refresh_linked_table("name")
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]


class TestUnlinkTableOdbcStub:
    def test_returns_error_not_connected(self):
        """OdbcAdapter.unlink_table returns error when not connected."""
        adapter = OdbcAdapter()
        result = adapter.unlink_table("name")
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]

    def test_returns_error_connected(self):
        """OdbcAdapter.unlink_table returns error even when connected."""
        adapter = OdbcAdapter()
        adapter._conn = MagicMock()
        result = adapter.unlink_table("name")
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]


class TestWinComLinkedTablesReturnTypes:
    def test_get_linked_tables_returns_dict(self):
        """WinComAdapter.get_linked_tables returns a dict."""
        adapter = WinComAdapter()
        type_name = adapter.get_linked_tables().__class__.__name__
        assert type_name == "dict"

    def test_create_linked_table_returns_dict(self):
        """WinComAdapter.create_linked_table returns a dict."""
        adapter = WinComAdapter()
        type_name = adapter.create_linked_table("", "", "").__class__.__name__
        assert type_name == "dict"

    def test_refresh_linked_table_returns_dict(self):
        """WinComAdapter.refresh_linked_table returns a dict."""
        adapter = WinComAdapter()
        type_name = adapter.refresh_linked_table("").__class__.__name__
        assert type_name == "dict"

    def test_unlink_table_returns_dict(self):
        """WinComAdapter.unlink_table returns a dict."""
        adapter = WinComAdapter()
        type_name = adapter.unlink_table("").__class__.__name__
        assert type_name == "dict"

    def test_get_linked_tables_has_success_key(self):
        """WinComAdapter.get_linked_tables returns dict with success key."""
        result = WinComAdapter().get_linked_tables()
        assert "success" in result

    def test_create_linked_table_has_success_key(self):
        """WinComAdapter.create_linked_table returns dict with success key."""
        result = WinComAdapter().create_linked_table("", "", "")
        assert "success" in result

    def test_refresh_linked_table_has_success_key(self):
        """WinComAdapter.refresh_linked_table returns dict with success key."""
        result = WinComAdapter().refresh_linked_table("")
        assert "success" in result

    def test_unlink_table_has_success_key(self):
        """WinComAdapter.unlink_table returns dict with success key."""
        result = WinComAdapter().unlink_table("")
        assert "success" in result
