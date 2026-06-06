"""Verify migration tools use OdbcAdapter by default (cross-platform support).

These tests ensure the extract_schema and transfer_data MCP tools instantiate
OdbcAdapter rather than WinComAdapter when no existing pooled connection is
available.  The migration service itself is stubbed — we only assert the
adapter class that gets wired in.

Note: we import through ms_access_mcp.mcp.server (not .migration directly)
to avoid a circular import triggered during module initialization.
"""
from unittest.mock import MagicMock


class _FakeAdapter:
    def connect(self, database_path: str) -> bool:
        return True

    def disconnect(self) -> None:
        pass


def test_extract_schema_uses_odbc_when_no_pooled_connection(monkeypatch):
    """extract_schema falls back to OdbcAdapter, not WinComAdapter, when no pool hit."""
    from ms_access_mcp.mcp.server import extract_schema as extract_schema_tool

    # Stub connection_service to return no pooled connection
    fake_connection_service = MagicMock()
    fake_connection_service.list.return_value = {}
    fake_connection_service.is_connected.return_value = False
    monkeypatch.setitem(extract_schema_tool.__globals__, "connection_service", fake_connection_service)

    # Stub migration_service
    class _FakeSchema:
        @staticmethod
        def model_dump() -> dict:
            return {"tables": []}

    fake_migration_service = MagicMock()
    fake_migration_service.extract_schema.return_value = _FakeSchema()
    monkeypatch.setitem(extract_schema_tool.__globals__, "migration_service", fake_migration_service)

    # Patch OdbcAdapter so we can track calls
    monkeypatch.setitem(extract_schema_tool.__globals__, "OdbcAdapter", _FakeAdapter)

    result = extract_schema_tool("/tmp/test.accdb")

    assert result["success"] is True
    assert result["reused_connection"] is False


def test_transfer_data_uses_odbc_when_no_pooled_connection(monkeypatch):
    """transfer_data falls back to OdbcAdapter, not WinComAdapter, when no pool hit."""
    from ms_access_mcp.mcp.server import transfer_data as transfer_data_tool

    # Stub connection_service
    fake_connection_service = MagicMock()
    fake_connection_service.list.return_value = {}
    fake_connection_service.is_connected.return_value = False
    monkeypatch.setitem(transfer_data_tool.__globals__, "connection_service", fake_connection_service)

    # Stub migration_service
    class _FakeSchema:
        @staticmethod
        def model_dump() -> dict:
            return {"tables": []}

    fake_migration_service = MagicMock()
    fake_migration_service.extract_schema.return_value = _FakeSchema()
    fake_migration_service.transfer_data.return_value = {"success": True, "job_id": "test-job"}
    monkeypatch.setitem(transfer_data_tool.__globals__, "migration_service", fake_migration_service)

    # Patch OdbcAdapter
    monkeypatch.setitem(transfer_data_tool.__globals__, "OdbcAdapter", _FakeAdapter)

    result = transfer_data_tool(
        "postgres",
        "conn-string",
        "/tmp/test.accdb",
    )

    assert result["success"] is True
    fake_migration_service.transfer_data.assert_called_once()


def test_extract_schema_reuses_pooled_adapter(monkeypatch):
    """extract_schema reuses an existing pooled adapter instead of creating a new one."""
    from ms_access_mcp.mcp.server import extract_schema as extract_schema_tool

    pooled_adapter = MagicMock()
    pooled_adapter.is_connected.return_value = True

    # Stub connection_service to return a pooled connection
    fake_connection_service = MagicMock()
    fake_connection_service.list.return_value = {
        "default": MagicMock(adapter=pooled_adapter, db_path="/tmp/test.accdb")
    }
    fake_connection_service.is_connected.return_value = True
    monkeypatch.setitem(extract_schema_tool.__globals__, "connection_service", fake_connection_service)

    # Stub migration_service
    class _FakeSchema:
        @staticmethod
        def model_dump() -> dict:
            return {"tables": []}

    fake_migration_service = MagicMock()
    fake_migration_service.extract_schema.return_value = _FakeSchema()
    monkeypatch.setitem(extract_schema_tool.__globals__, "migration_service", fake_migration_service)

    # Track whether OdbcAdapter is called
    calls = []

    def _track_odbc():
        calls.append("called")
        return _FakeAdapter()

    monkeypatch.setitem(extract_schema_tool.__globals__, "OdbcAdapter", _track_odbc)

    result = extract_schema_tool("/tmp/test.accdb")

    assert result["success"] is True
    assert result["reused_connection"] is True
    assert calls == [], "OdbcAdapter should not be called when pooled connection exists"


def test_transfer_data_reuses_pooled_adapter(monkeypatch):
    """transfer_data reuses an existing pooled adapter instead of creating a new one."""
    from ms_access_mcp.mcp.server import transfer_data as transfer_data_tool

    pooled_adapter = MagicMock()
    pooled_adapter.is_connected.return_value = True

    # Stub connection_service
    fake_connection_service = MagicMock()
    fake_connection_service.list.return_value = {
        "default": MagicMock(adapter=pooled_adapter, db_path="/tmp/test.accdb")
    }
    fake_connection_service.is_connected.return_value = True
    monkeypatch.setitem(transfer_data_tool.__globals__, "connection_service", fake_connection_service)

    # Stub migration_service
    class _FakeSchema:
        @staticmethod
        def model_dump() -> dict:
            return {"tables": []}

    fake_migration_service = MagicMock()
    fake_migration_service.extract_schema.return_value = _FakeSchema()
    fake_migration_service.transfer_data.return_value = {"success": True, "job_id": "test-job"}
    monkeypatch.setitem(transfer_data_tool.__globals__, "migration_service", fake_migration_service)

    # Track whether OdbcAdapter is called
    calls = []

    def _track_odbc():
        calls.append("called")
        return _FakeAdapter()

    monkeypatch.setitem(transfer_data_tool.__globals__, "OdbcAdapter", _track_odbc)

    result = transfer_data_tool(
        "postgres",
        "conn-string",
        "/tmp/test.accdb",
    )

    assert result["success"] is True
    assert calls == [], "OdbcAdapter should not be called when pooled connection exists"
