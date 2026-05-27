from ms_access_mcp.connectors.base import (
    TargetConnector,
    ConnectionStatus,
    ConnectorCapabilities,
)
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

    def table_exists(self, table_name: str) -> bool:
        return False

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            supports_linked_insert_select=True,
            supports_checksum=True,
            supports_sampling=True,
            preferred_batch_size=500,
        )

    def get_row_count(self, table: str) -> int:
        return 10

    def get_checksum(self, table: str, columns: list[str]) -> str | None:
        return f"{table}:{','.join(columns)}"

    def sample_rows(self, table: str, columns: list[str], limit: int, offset: int = 0) -> list[dict]:
        return [{col: f"sample-{idx}" for col in columns} for idx in range(offset, offset + limit)]

    def linked_transfer(self, source_adapter: Any, source_table: str, target_table: str) -> int:
        return 25


def test_target_connector_protocol():
    conn = DummyConnector()
    assert isinstance(conn, TargetConnector)
    assert conn.target_type == "postgresql"


def test_connection_status():
    status = ConnectionStatus(connected=True, server_version="14.0")
    assert status.connected is True


def test_connector_capabilities_defaults():
    capabilities = ConnectorCapabilities(
        supports_linked_insert_select=False,
        supports_checksum=True,
        supports_sampling=False,
    )

    assert capabilities.preferred_batch_size == 1000
    assert capabilities.supports_checksum is True


def test_target_connector_contract_includes_verification_and_linked_transfer_methods():
    conn = DummyConnector()

    assert conn.get_capabilities().supports_linked_insert_select is True
    assert conn.get_row_count("Customers") == 10
    assert conn.get_checksum("Customers", ["ID", "Name"]) == "Customers:ID,Name"
    sample = conn.sample_rows("Customers", ["ID"], limit=2)
    assert sample == [{"ID": "sample-0"}, {"ID": "sample-1"}]
    assert conn.linked_transfer(source_adapter=None, source_table="Customers", target_table="Customers") == 25
