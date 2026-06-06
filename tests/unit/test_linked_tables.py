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
    def test_raises_not_implemented_error(self):
        """OdbcAdapter.get_linked_tables raises NotImplementedError."""
        adapter = OdbcAdapter()
        with pytest.raises(NotImplementedError):
            adapter.get_linked_tables()


class TestCreateLinkedTableOdbcStub:
    def test_raises_not_implemented_error(self):
        """OdbcAdapter.create_linked_table raises NotImplementedError."""
        adapter = OdbcAdapter()
        with pytest.raises(NotImplementedError):
            adapter.create_linked_table("name", "source", "connect")


class TestRefreshLinkedTableOdbcStub:
    def test_raises_not_implemented_error(self):
        """OdbcAdapter.refresh_linked_table raises NotImplementedError."""
        adapter = OdbcAdapter()
        with pytest.raises(NotImplementedError):
            adapter.refresh_linked_table("name")


class TestUnlinkTableOdbcStub:
    def test_raises_not_implemented_error(self):
        """OdbcAdapter.unlink_table raises NotImplementedError."""
        adapter = OdbcAdapter()
        with pytest.raises(NotImplementedError):
            adapter.unlink_table("name")


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
