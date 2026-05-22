import pytest
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter


class TestWinComAdapterRelationshipsNotConnected:
    """Test get_relationships returns empty when not connected."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_get_relationships_returns_empty_when_not_connected(self):
        assert self.adapter.get_relationships() == []


class TestOdbcAdapterRelationships:
    """Test OdbcAdapter.get_relationships returns empty (ODBC doesn't support relations)."""

    def setup_method(self):
        self.adapter = OdbcAdapter()

    def test_get_relationships_returns_empty(self):
        assert self.adapter.get_relationships() == []

    def test_get_relationships_when_not_connected(self):
        # Even when connected, ODBC can't get relationships
        assert self.adapter.get_relationships() == []


class TestSchemaServiceRelationships:
    """Test SchemaService.get_relationships delegates properly."""

    def test_schema_service_delegates_to_adapter(self):
        from ms_access_mcp.services.schema import SchemaService
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter()
        service = SchemaService(adapter)
        # Not connected → empty list
        assert service.get_relationships() == []
