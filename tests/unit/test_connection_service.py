import pytest
from ms_access_mcp.services.connection import ConnectionService

def test_connection_service_initial_state():
    service = ConnectionService()
    assert service.is_connected() is False
    assert service.current_database is None

def test_connection_service_can_be_instantiated():
    service = ConnectionService()
    assert service is not None