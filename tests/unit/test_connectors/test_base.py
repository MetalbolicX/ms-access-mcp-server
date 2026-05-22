from ms_access_mcp.connectors.base import TargetConnector, ConnectionStatus
from typing import Any


class DummyConnector(TargetConnector):
    target_type: str = "postgresql"

    def connect(self, connection_string: str) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def create_table(self, schema: Any) -> bool:
        return True

    def insert_rows(self, table: str, rows: list[dict]) -> int:
        return len(rows)

    def rollback_table(self, table: str) -> None:
        pass


def test_target_connector_protocol():
    conn = DummyConnector()
    assert isinstance(conn, TargetConnector)
    assert conn.target_type == "postgresql"


def test_connection_status():
    status = ConnectionStatus(connected=True, server_version="14.0")
    assert status.connected is True