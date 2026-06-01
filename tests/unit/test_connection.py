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


class TestConnectAccessWithName:
    """Tests for connect_access tool with name parameter."""

    def test_connect_access_with_name_param(self):
        """connect_access with name parameter should include name in response."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = True
        mock_schema = MagicMock()
        mock_com = MagicMock()
        with patch.dict(server.connect_access.__globals__, connection_service=mock_conn, schema_service=mock_schema, com_automation_service=mock_com):
            result = server.connect_access("test.accdb", use_com=False, name="prod")
            assert result["name"] == "prod"

    def test_connect_access_name_in_response(self):
        """connect_access response should contain name key."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = True
        with patch.dict(server.connect_access.__globals__, connection_service=mock_conn):
            result = server.connect_access("test.accdb", name="prod")
            assert "name" in result


class TestDisconnectAccessWithName:
    """Tests for disconnect_access tool with name parameter."""

    def test_disconnect_access_with_name_param(self):
        """disconnect_access should call disconnect with the given name."""
        mock_conn = MagicMock()
        with patch.dict(server.disconnect_access.__globals__, connection_service=mock_conn):
            result = server.disconnect_access("prod")
            mock_conn.disconnect.assert_called_once_with("prod")
            assert result["success"] is True

    def test_disconnect_access_unknown_name_returns_error(self):
        """disconnect_access with unknown name should return error."""
        mock_conn = MagicMock()
        mock_conn.disconnect.side_effect = KeyError("not found")
        with patch.dict(server.disconnect_access.__globals__, connection_service=mock_conn):
            result = server.disconnect_access("unknown")
            assert result["success"] is False


class TestNewConnectionTools:
    """Tests for new connection management tools."""

    def test_list_connections_returns_structure(self):
        """list_connections should return dict with connections key."""
        mock_conn = MagicMock()
        mock_state = MagicMock()
        mock_state.db_path = "/path/to/db.accdb"
        mock_state.adapter_type = "odbc"
        mock_state.adapter.is_connected.return_value = True
        mock_conn.list.return_value = {"default": mock_state}
        mock_conn.get_active.return_value = "default"
        with patch.dict(server.list_connections.__globals__, connection_service=mock_conn):
            result = server.list_connections()
            assert "connections" in result
            assert "success" in result

    def test_set_active_connection_calls_service(self):
        """set_active_connection should call connection_service.set_active."""
        mock_conn = MagicMock()
        with patch.dict(server.set_active_connection.__globals__, connection_service=mock_conn):
            result = server.set_active_connection("prod")
            mock_conn.set_active.assert_called_once_with("prod")
            assert result["success"] is True

    def test_set_active_connection_unknown_returns_error(self):
        """set_active_connection with unknown name should return error."""
        mock_conn = MagicMock()
        mock_conn.set_active.side_effect = KeyError("not found")
        with patch.dict(server.set_active_connection.__globals__, connection_service=mock_conn):
            result = server.set_active_connection("unknown")
            assert result["success"] is False

    def test_get_active_connection_returns_name(self):
        """get_active_connection should return the active connection name."""
        mock_conn = MagicMock()
        mock_conn.get_active.return_value = "default"
        with patch.dict(server.get_active_connection.__globals__, connection_service=mock_conn):
            result = server.get_active_connection()
            assert result["active"] == "default"

    def test_is_connected_with_connection_name(self):
        """is_connected should pass connection_name to connection_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.current_database = "/path/to/db.accdb"
        with patch.dict(server.is_connected.__globals__, connection_service=mock_conn):
            result = server.is_connected(connection_name="prod")
            mock_conn.is_connected.assert_called_once_with("prod")
            assert result["connected"] is True
