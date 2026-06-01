"""Tests for ConnectionService alias identity."""
from ms_access_mcp.services.connection import ConnectionService, ConnectionPool
from ms_access_mcp.mcp import server


class TestConnectionServiceAlias:
    def test_connection_service_is_connectionpool(self):
        assert ConnectionService is ConnectionPool

    def test_connection_service_has_get_adapter(self):
        assert hasattr(server.connection_service, "get_adapter")

    def test_connection_service_has_list(self):
        assert hasattr(server.connection_service, "list")

    def test_connection_service_has_is_connected(self):
        assert hasattr(server.connection_service, "is_connected")

    def test_connection_service_has_recover_access(self):
        assert hasattr(server.connection_service, "recover_access")
