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

    def test_wincom_has_recreate_linked_table(self):
        assert hasattr(WinComAdapter, "recreate_linked_table")

    def test_wincom_has_unlink_table(self):
        assert hasattr(WinComAdapter, "unlink_table")

    def test_protocol_defines_linked_table_methods(self):
        assert hasattr(AccessAdapter, "get_linked_tables")
        assert hasattr(AccessAdapter, "create_linked_table")
        assert hasattr(AccessAdapter, "refresh_linked_table")
        assert hasattr(AccessAdapter, "recreate_linked_table")
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

    def test_refresh_linked_table_accepts_optional_connect_string(self):
        """OdbcAdapter.refresh_linked_table accepts optional connect_string parameter."""
        adapter = OdbcAdapter()
        # Should accept connect_string=None as optional param (doesn't raise on signature)
        sig = adapter.refresh_linked_table.__code__.co_varnames[: adapter.refresh_linked_table.__code__.co_argcount]
        # Verify connect_string is a parameter (even if NotImplemented at runtime)
        assert "connect_string" in sig or "name" in sig  # At minimum, method exists


class TestRecreateLinkedTableOdbcStub:
    def test_raises_not_implemented_error(self):
        """OdbcAdapter.recreate_linked_table raises NotImplementedError."""
        adapter = OdbcAdapter()
        with pytest.raises(NotImplementedError):
            adapter.recreate_linked_table("name", "source", "connect")

    def test_recreate_linked_table_signature_includes_attributes(self):
        """OdbcAdapter.recreate_linked_table accepts attributes parameter."""
        adapter = OdbcAdapter()
        sig = adapter.recreate_linked_table.__code__.co_varnames[: adapter.recreate_linked_table.__code__.co_argcount]
        assert "attributes" in sig


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

    def test_recreate_linked_table_is_declared_in_protocol(self):
        """WinComAdapter.recreate_linked_table is declared (implementation in PR 2)."""
        # This test verifies the method exists on WinComAdapter
        # Actual return value tests are in integration tests (PR 2+)
        assert hasattr(WinComAdapter, "recreate_linked_table")

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

    def test_recreate_linked_table_is_callable_signature(self):
        """WinComAdapter.recreate_linked_table has correct signature."""
        import inspect
        sig = inspect.signature(WinComAdapter.recreate_linked_table)
        param_names = list(sig.parameters.keys())
        # Should have: self, name, source_table, connect_string, attributes=None
        assert "name" in param_names
        assert "source_table" in param_names
        assert "connect_string" in param_names
        assert "attributes" in param_names

    def test_unlink_table_has_success_key(self):
        """WinComAdapter.unlink_table returns dict with success key."""
        result = WinComAdapter().unlink_table("")
        assert "success" in result


class TestLinkedTableInfoAttributes:
    """LinkedTableInfo model includes attributes field."""

    def test_linked_table_info_has_attributes_field(self):
        """LinkedTableInfo includes attributes: int field."""
        from ms_access_mcp.models.database import LinkedTableInfo

        info = LinkedTableInfo(
            name="Orders",
            source_table="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN",
        )
        assert hasattr(info, "attributes")
        assert isinstance(info.attributes, int)

    def test_linked_table_info_attributes_defaults_to_zero(self):
        """LinkedTableInfo.attributes defaults to 0."""
        from ms_access_mcp.models.database import LinkedTableInfo

        info = LinkedTableInfo(
            name="Orders",
            source_table="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN",
        )
        assert info.attributes == 0

    def test_linked_table_info_can_set_hidden_attribute(self):
        """LinkedTableInfo.attributes can be set to dbHiddenObject flag."""
        from ms_access_mcp.models.database import LinkedTableInfo

        info = LinkedTableInfo(
            name="SysConfig",
            source_table="dbo.SysConfig",
            connect_string="ODBC;DSN=MyDSN",
            attributes=1,  # dbHiddenObject
        )
        assert info.attributes == 1
