"""Verify migration tools route through BackendSelector with correct capabilities.

These tests ensure the extract_schema and transfer_data MCP tools use
BackendSelector.get_adapter() with SCHEMA_CAPS / DATA_READ_CAPS when no
pooled connection is available.  The migration service itself is stubbed —
we only assert the selector call arguments.

Note: we import through ms_access_mcp.mcp.server (not .migration directly)
to avoid a circular import triggered during module initialization.
"""
from unittest.mock import MagicMock


class _FakeAdapter:
    def connect(self, database_path: str) -> bool:
        return True

    def disconnect(self) -> None:
        pass


def test_extract_schema_uses_selector_with_schema_caps(monkeypatch):
    """extract_schema calls BackendSelector.get_adapter with SCHEMA_CAPS when no pool hit."""
    from ms_access_mcp.mcp.server import extract_schema as extract_schema_tool
    from ms_access_mcp.services.backend_selector import SCHEMA_CAPS

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

    # Capture selector calls
    selector_calls = []

    def _spy_selector(db_path, backend=None, capabilities=None):
        selector_calls.append({
            "db_path": db_path,
            "backend": backend,
            "capabilities": capabilities,
        })
        adapter = _FakeAdapter()
        return adapter

    monkeypatch.setitem(
        extract_schema_tool.__globals__,
        "BackendSelector",
        MagicMock(get_adapter=_spy_selector)
    )

    result = extract_schema_tool("/tmp/test.accdb")

    assert result["success"] is True
    assert result["reused_connection"] is False
    assert len(selector_calls) == 1, "BackendSelector.get_adapter should be called once"
    assert selector_calls[0]["capabilities"] == SCHEMA_CAPS, (
        f"extract_schema should use SCHEMA_CAPS, got {selector_calls[0]['capabilities']}"
    )


def test_transfer_data_uses_selector_with_data_read_caps(monkeypatch):
    """transfer_data calls BackendSelector.get_adapter with DATA_READ_CAPS when no pool hit."""
    from ms_access_mcp.mcp.server import transfer_data as transfer_data_tool
    from ms_access_mcp.services.backend_selector import DATA_READ_CAPS

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

    # Capture selector calls
    selector_calls = []

    def _spy_selector(db_path, backend=None, capabilities=None):
        selector_calls.append({
            "db_path": db_path,
            "backend": backend,
            "capabilities": capabilities,
        })
        return _FakeAdapter()

    monkeypatch.setitem(
        transfer_data_tool.__globals__,
        "BackendSelector",
        MagicMock(get_adapter=_spy_selector)
    )

    result = transfer_data_tool(
        "postgres",
        "conn-string",
        "/tmp/test.accdb",
    )

    assert result["success"] is True
    assert len(selector_calls) == 1, "BackendSelector.get_adapter should be called once"
    assert selector_calls[0]["capabilities"] == DATA_READ_CAPS, (
        f"transfer_data should use DATA_READ_CAPS, got {selector_calls[0]['capabilities']}"
    )


def test_extract_schema_reuses_pooled_adapter(monkeypatch):
    """extract_schema reuses an existing pooled adapter instead of calling selector."""
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

    # Track whether BackendSelector is called
    selector_called = []

    def _track_selector(db_path, backend=None, capabilities=None):
        selector_called.append("called")
        return _FakeAdapter()

    monkeypatch.setitem(
        extract_schema_tool.__globals__,
        "BackendSelector",
        MagicMock(get_adapter=_track_selector)
    )

    result = extract_schema_tool("/tmp/test.accdb")

    assert result["success"] is True
    assert result["reused_connection"] is True
    assert selector_called == [], "BackendSelector should NOT be called when pooled connection exists"


def test_transfer_data_reuses_pooled_adapter(monkeypatch):
    """transfer_data reuses an existing pooled adapter instead of calling selector."""
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

    # Track whether BackendSelector is called
    selector_called = []

    def _track_selector(db_path, backend=None, capabilities=None):
        selector_called.append("called")
        return _FakeAdapter()

    monkeypatch.setitem(
        transfer_data_tool.__globals__,
        "BackendSelector",
        MagicMock(get_adapter=_track_selector)
    )

    result = transfer_data_tool(
        "postgres",
        "conn-string",
        "/tmp/test.accdb",
    )

    assert result["success"] is True
    assert selector_called == [], "BackendSelector should NOT be called when pooled connection exists"
