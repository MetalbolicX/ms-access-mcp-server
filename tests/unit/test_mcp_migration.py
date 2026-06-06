from ms_access_mcp.mcp.server import transfer_data as transfer_data_tool
from ms_access_mcp.models.migration import TableTransferConfig


class _FakeAdapter:
    def connect(self, database_path: str) -> bool:
        _ = database_path
        return True

    def disconnect(self) -> None:
        return None


class _FakeMigrationService:
    def __init__(self):
        self.transfer_calls: list[dict] = []

    def extract_schema(self, adapter, database_path: str):
        _ = adapter
        _ = database_path

        class _Schema:
            @staticmethod
            def model_dump() -> dict:
                return {"source": "source.accdb", "tables": []}

        return _Schema()

    def transfer_data(
        self,
        target_type: str,
        connection_string: str,
        schema,
        adapter,
        job_id: str | None = None,
        *,
        transfer_mode: str = "auto",
        verification_mode: str = "full",
        table_overrides: dict[str, TableTransferConfig] | None = None,
        odbc_connection_string: str | None = None,
    ):
        self.transfer_calls.append(
            {
                "target_type": target_type,
                "connection_string": connection_string,
                "job_id": job_id,
                "transfer_mode": transfer_mode,
                "verification_mode": verification_mode,
                "table_overrides": table_overrides,
                "odbc_connection_string": odbc_connection_string,
            }
        )
        _ = schema
        _ = adapter
        return {"success": True, "job_id": "job-123"}


def _make_fake_selector(adapter):
    """Return a BackendSelector mock that returns the given adapter."""
    from unittest.mock import MagicMock
    selector = MagicMock()
    selector.get_adapter.return_value = adapter
    return selector


def test_mcp_transfer_data_forwards_table_overrides(monkeypatch):
    """MCP transfer_data forwards table_overrides dict to service as TableTransferConfig instances."""
    fake_service = _FakeMigrationService()
    fake_adapter = _FakeAdapter()
    fake_selector = _make_fake_selector(fake_adapter)
    monkeypatch.setitem(transfer_data_tool.__globals__, "migration_service", fake_service)
    monkeypatch.setitem(transfer_data_tool.__globals__, "BackendSelector", fake_selector)

    result = transfer_data_tool(
        "postgres",
        "conn",
        "source.accdb",
        table_overrides={"Customers": {"columns": ["Name"]}},
    )

    assert result["success"] is True
    assert len(fake_service.transfer_calls) == 1
    assert "Customers" in fake_service.transfer_calls[0]["table_overrides"]
    customer_cfg = fake_service.transfer_calls[0]["table_overrides"]["Customers"]
    assert isinstance(customer_cfg, TableTransferConfig)
    assert customer_cfg.columns == ["Name"]


def test_mcp_transfer_data_defaults_to_backward_compatible_modes(monkeypatch):
    fake_service = _FakeMigrationService()
    fake_adapter = _FakeAdapter()
    fake_selector = _make_fake_selector(fake_adapter)
    monkeypatch.setitem(transfer_data_tool.__globals__, "migration_service", fake_service)
    monkeypatch.setitem(transfer_data_tool.__globals__, "BackendSelector", fake_selector)

    result = transfer_data_tool("postgres", "conn", "source.accdb")

    assert result["success"] is True
    assert len(fake_service.transfer_calls) == 1
    assert fake_service.transfer_calls[0]["transfer_mode"] == "auto"
    assert fake_service.transfer_calls[0]["verification_mode"] == "full"


def test_mcp_transfer_data_forwards_explicit_modes(monkeypatch):
    fake_service = _FakeMigrationService()
    fake_adapter = _FakeAdapter()
    fake_selector = _make_fake_selector(fake_adapter)
    monkeypatch.setitem(transfer_data_tool.__globals__, "migration_service", fake_service)
    monkeypatch.setitem(transfer_data_tool.__globals__, "BackendSelector", fake_selector)

    result = transfer_data_tool(
        "postgres",
        "conn",
        "source.accdb",
        transfer_mode="batch",
        verification_mode="count-only",
    )

    assert result["success"] is True
    assert len(fake_service.transfer_calls) == 1
    assert fake_service.transfer_calls[0]["transfer_mode"] == "batch"
    assert fake_service.transfer_calls[0]["verification_mode"] == "count-only"


def test_mcp_transfer_data_forwards_odbc_connection_string(monkeypatch):
    """MCP transfer_data forwards odbc_connection_string to migration service unchanged."""
    fake_service = _FakeMigrationService()
    fake_adapter = _FakeAdapter()
    fake_selector = _make_fake_selector(fake_adapter)
    monkeypatch.setitem(transfer_data_tool.__globals__, "migration_service", fake_service)
    monkeypatch.setitem(transfer_data_tool.__globals__, "BackendSelector", fake_selector)

    odbc_conn_str = "DRIVER={PostgreSQL Unicode};SERVER=test;PORT=5432;DATABASE=test;UID=u;PWD=p"
    result = transfer_data_tool(
        "postgres",
        "conn",
        "source.accdb",
        odbc_connection_string=odbc_conn_str,
    )

    assert result["success"] is True
    assert len(fake_service.transfer_calls) == 1
    assert fake_service.transfer_calls[0]["odbc_connection_string"] == odbc_conn_str


def test_mcp_transfer_data_omitting_odbc_connection_string_records_none(monkeypatch):
    """MCP transfer_data with no odbc_connection_string passes None to service."""
    fake_service = _FakeMigrationService()
    fake_adapter = _FakeAdapter()
    fake_selector = _make_fake_selector(fake_adapter)
    monkeypatch.setitem(transfer_data_tool.__globals__, "migration_service", fake_service)
    monkeypatch.setitem(transfer_data_tool.__globals__, "BackendSelector", fake_selector)

    result = transfer_data_tool("postgres", "conn", "source.accdb")

    assert result["success"] is True
    assert len(fake_service.transfer_calls) == 1
    assert fake_service.transfer_calls[0]["odbc_connection_string"] is None
