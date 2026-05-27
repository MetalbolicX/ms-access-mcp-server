"""Comprehensive unit tests for ConnectionService."""

import pytest
from unittest.mock import MagicMock, patch
from ms_access_mcp.services.connection import ConnectionService


def make_mock_adapter():
    a = MagicMock()
    a.connect.return_value = True
    a.disconnect.return_value = None
    a.is_connected.return_value = True
    return a


# =============================================================================
# Initial state
# =============================================================================

class TestConnectionServiceInitialState:
    def test_not_connected_by_default(self):
        assert ConnectionService().is_connected() is False

    def test_current_database_none_by_default(self):
        assert ConnectionService().current_database is None

    def test_adapter_property_is_none_by_default(self):
        assert ConnectionService().adapter is None


# =============================================================================
# connect() — wiring, state tracking, failure handling
# =============================================================================

class TestConnect:
    def test_connect_stores_adapter(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        assert service.adapter is adapter

    def test_connect_stores_database_path_on_success(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        assert service.current_database == "/tmp/db.accdb"

    def test_connect_calls_adapter_connect(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        adapter.connect.assert_called_once_with("/tmp/db.accdb")

    def test_connect_returns_adapter_result_true(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        result = service.connect("/tmp/db.accdb", adapter)
        assert result is True

    def test_connect_returns_adapter_result_false(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.connect.return_value = False
        result = service.connect("/tmp/db.accdb", adapter)
        assert result is False

    def test_connect_does_not_store_database_path_on_failure(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.connect.return_value = False
        service.connect("/tmp/db.accdb", adapter)
        assert service.current_database is None

    def test_connect_overwrites_previous_adapter(self):
        service = ConnectionService()
        a1 = make_mock_adapter()
        a2 = make_mock_adapter()
        service.connect("/tmp/db1.accdb", a1)
        service.connect("/tmp/db2.accdb", a2)
        assert service.adapter is a2
        assert service.current_database == "/tmp/db2.accdb"

    def test_constructor_accepts_adapter(self):
        adapter = make_mock_adapter()
        service = ConnectionService(adapter)
        assert service.adapter is adapter


# =============================================================================
# disconnect() — cleanup, idempotency
# =============================================================================

class TestDisconnect:
    def test_disconnect_calls_adapter_disconnect(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        service.disconnect()
        adapter.disconnect.assert_called_once()

    def test_disconnect_clears_current_database(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        service.disconnect()
        assert service.current_database is None

    def test_disconnect_calls_adapter_disconnect_but_keeps_adapter_reference(self):
        """disconnect() calls adapter.disconnect() and clears DB path but keeps adapter."""
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        service.disconnect()
        adapter.disconnect.assert_called_once()
        # Adapter reference is retained (only _current_database is cleared)
        assert service.adapter is adapter

    def test_disconnect_idempotent_no_adapter(self):
        service = ConnectionService()
        service.disconnect()  # should not raise

    def test_disconnect_idempotent_after_connect(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        service.disconnect()
        service.disconnect()  # should not raise


# =============================================================================
# is_connected() — delegates to adapter
# =============================================================================

class TestIsConnected:
    def test_is_connected_delegates_to_adapter_true(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.is_connected.return_value = True
        service.connect("/tmp/db.accdb", adapter)
        assert service.is_connected() is True
        adapter.is_connected.assert_called_once()

    def test_is_connected_delegates_to_adapter_false(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.is_connected.return_value = False
        service.connect("/tmp/db.accdb", adapter)
        assert service.is_connected() is False

    def test_is_connected_returns_false_when_no_adapter(self):
        service = ConnectionService()
        assert service.is_connected() is False


# =============================================================================
# reconnect() — disconnect + connect to new path
# =============================================================================

class TestReconnect:
    def test_reconnect_disconnects_and_reconnects_same_adapter(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.connect.return_value = True
        service.connect("/tmp/db1.accdb", adapter)
        service.reconnect("/tmp/db2.accdb")
        adapter.disconnect.assert_called_once()
        adapter.connect.assert_called_with("/tmp/db2.accdb")

    def test_reconnect_updates_current_database(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.connect.return_value = True
        service.connect("/tmp/db1.accdb", adapter)
        service.reconnect("/tmp/db2.accdb")
        assert service.current_database == "/tmp/db2.accdb"

    def test_reconnect_returns_true_on_success(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.connect.return_value = True
        service.connect("/tmp/db1.accdb", adapter)
        assert service.reconnect("/tmp/db2.accdb") is True

    def test_reconnect_returns_false_when_adapter_connect_fails(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.connect.return_value = False
        service.connect("/tmp/db1.accdb", adapter)
        assert service.reconnect("/tmp/db2.accdb") is False

    def test_reconnect_returns_false_when_no_adapter(self):
        service = ConnectionService()
        assert service.reconnect("/tmp/db2.accdb") is False

    def test_reconnect_preserves_adapter_instance(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        adapter.connect.return_value = True
        service.connect("/tmp/db1.accdb", adapter)
        service.reconnect("/tmp/db2.accdb")
        assert service.adapter is adapter


# =============================================================================
# current_database and adapter properties
# =============================================================================

class TestProperties:
    def test_current_database_returns_set_path(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/mydb.accdb", adapter)
        assert service.current_database == "/tmp/mydb.accdb"

    def test_current_database_after_disconnect_is_none(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        service.disconnect()
        assert service.current_database is None

    def test_adapter_property_returns_adapter(self):
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        assert service.adapter is adapter

    def test_adapter_property_after_disconnect_retains_reference(self):
        """After disconnect, adapter reference is retained (only DB path is cleared)."""
        service = ConnectionService()
        adapter = make_mock_adapter()
        service.connect("/tmp/db.accdb", adapter)
        service.disconnect()
        assert service.adapter is adapter