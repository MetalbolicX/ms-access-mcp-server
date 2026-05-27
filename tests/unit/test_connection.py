"""Tests for mcp/connection.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


class TestConnectAccess:
    """Tests for connect_access tool."""

    def test_connect_access_returns_success_when_service_connect_succeeds(self):
        """connect_access should return success when connection_service.connect succeeds."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = True
        mock_conn.current_database = "test.accdb"
        with patch.dict(server.connect_access.__globals__, connection_service=mock_conn):
            result = server.connect_access("test.accdb")
            assert result["success"] is True
            assert result["connected"] is True
            mock_conn.connect.assert_called_once()

    def test_connect_access_returns_failure_when_service_connect_fails(self):
        """connect_access should return failure when connection_service.connect fails."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = False
        with patch.dict(server.connect_access.__globals__, connection_service=mock_conn):
            result = server.connect_access("test.accdb")
            assert result["success"] is False
            assert result["connected"] is False

    def test_connect_access_sets_adapter_on_schema_and_com_services(self):
        """connect_access should set adapter on schema_service and com_automation_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = True
        mock_schema = MagicMock()
        mock_com = MagicMock()
        with patch.dict(server.connect_access.__globals__, connection_service=mock_conn, schema_service=mock_schema, com_automation_service=mock_com):
            result = server.connect_access("test.accdb", use_com=True)
            assert result["success"] is True
            mock_schema.set_adapter.assert_called_once()
            mock_com.set_adapter.assert_called_once()


class TestDisconnectAccess:
    """Tests for disconnect_access tool."""

    def test_disconnect_access_returns_true(self):
        """disconnect_access should always return success."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.disconnect_access.__globals__, connection_service=mock_conn):
            result = server.disconnect_access()
            assert result["success"] is True
            mock_conn.disconnect.assert_called_once()


class TestIsConnected:
    """Tests for is_connected tool."""

    def test_is_connected_returns_true_when_connected(self):
        """is_connected should return True when connection_service is connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.current_database = "/path/to/db.accdb"
        with patch.dict(server.is_connected.__globals__, connection_service=mock_conn):
            result = server.is_connected()
            assert result["connected"] is True
            assert result["database"] == "/path/to/db.accdb"

    def test_is_connected_returns_false_when_disconnected(self):
        """is_connected should return False when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.current_database = None
        with patch.dict(server.is_connected.__globals__, connection_service=mock_conn):
            result = server.is_connected()
            assert result["connected"] is False
