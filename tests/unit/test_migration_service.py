from ms_access_mcp.services.migration import MigrationService, JobTracker
from ms_access_mcp.models.migration import ExtractedSchema, TableSchema, ColumnSchema, TableTransferConfig
import uuid
import os
import tempfile
import hashlib


class _TransferAdapter:
    def __init__(self, rows_by_table: dict[str, list[dict]]):
        self._rows_by_table = rows_by_table

    def execute_query(self, sql: str):
        table_name = sql.split("[")[1].split("]")[0]
        return list(self._rows_by_table.get(table_name, []))


class _TransferConnector:
    def __init__(self, *, supports_linked: bool, linked_error: Exception | None = None):
        from ms_access_mcp.connectors.base import ConnectorCapabilities

        self._capabilities = ConnectorCapabilities(
            supports_linked_insert_select=supports_linked,
            supports_checksum=True,
            supports_sampling=True,
            preferred_batch_size=1000,
        )
        self._linked_error = linked_error
        self.linked_calls = 0
        self.batch_calls = 0
        self._table_rows: dict[str, list[dict]] = {}

    def connect(self, connection_string: str) -> bool:
        _ = connection_string
        return True

    def disconnect(self) -> None:
        return None

    def insert_rows(self, table: str, rows: list[dict]) -> int:
        self._table_rows[table] = [dict(row) for row in rows]
        self.batch_calls += 1
        return len(rows)

    def rollback_table(self, table: str) -> None:
        _ = table
        return None

    def get_capabilities(self):
        return self._capabilities

    def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
        self.linked_calls += 1
        if self._linked_error:
            raise self._linked_error
        rows = source_adapter.execute_query(f"SELECT * FROM [{source_table}]")
        self._table_rows[target_table] = [dict(row) for row in rows]
        return len(rows)

    def get_row_count(self, table: str) -> int:
        return len(self._table_rows.get(table, []))

    def get_checksum(self, table: str, columns: list[str]) -> str | None:
        rows = self._ordered_rows(table, columns)
        payload = "||".join(
            "|".join(self._normalize_value(row.get(column)) for column in columns)
            for row in rows
        )
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def sample_rows(self, table: str, columns: list[str], limit: int, offset: int = 0) -> list[dict]:
        rows = self._ordered_rows(table, columns)
        sampled = rows[offset : offset + limit]
        return [{column: row.get(column) for column in columns} for row in sampled]

    @staticmethod
    def _normalize_value(value) -> str:
        return "<NULL>" if value is None else str(value)

    def _ordered_rows(self, table: str, columns: list[str]) -> list[dict]:
        return sorted(
            self._table_rows.get(table, []),
            key=lambda row: tuple(self._normalize_value(row.get(column)) for column in columns),
        )


class _TransferConnectorFactory:
    def __init__(self, *, supports_linked: bool, linked_error: Exception | None = None):
        self._supports_linked = supports_linked
        self._linked_error = linked_error
        self.instance: _TransferConnector | None = None

    def __call__(self):
        self.instance = _TransferConnector(
            supports_linked=self._supports_linked,
            linked_error=self._linked_error,
        )
        return self.instance


def test_transfer_data_with_column_override_filters_rows(monkeypatch):
    """transfer_data with column override should filter row dicts before insert."""
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[
            TableSchema(
                name="Customers",
                columns=[
                    ColumnSchema(name="ID", source_type="Long Integer"),
                    ColumnSchema(name="Name", source_type="Text"),
                    ColumnSchema(name="Email", source_type="Text"),
                ],
            )
        ],
    )
    adapter = _TransferAdapter(
        rows_by_table={
            "Customers": [{"ID": 1, "Name": "Alice", "Email": "alice@test.com"}]
        }
    )
    factory = _TransferConnectorFactory(supports_linked=False)
    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    overrides = {"Customers": TableTransferConfig(columns=["Name"])}
    result = service.transfer_data("postgres", "fake-conn", schema, adapter, table_overrides=overrides)

    assert result["success"] is True
    assert factory.instance is not None
    customer_rows = factory.instance._table_rows.get("Customers", [])
    assert len(customer_rows) == 1
    assert set(customer_rows[0].keys()) == {"Name"}
    assert customer_rows[0]["Name"] == "Alice"


def test_transfer_data_with_where_filter(monkeypatch):
    """transfer_data with WHERE override should build SQL with WHERE clause."""
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[
            TableSchema(name="Orders", columns=[ColumnSchema(name="OrderID", source_type="Long Integer")]),
        ],
    )
    executed_sqls = []
    class _TracingAdapter:
        def __init__(self, original):
            self._original = original
        def execute_query(self, sql):
            executed_sqls.append(sql)
            return self._original.execute_query(sql)
    adapter = _TracingAdapter(_TransferAdapter(rows_by_table={"Orders": [{"OrderID": 1}, {"OrderID": 2}]}))
    factory = _TransferConnectorFactory(supports_linked=False)
    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    overrides = {"Orders": TableTransferConfig(where="OrderID>1")}
    result = service.transfer_data("postgres", "fake-conn", schema, adapter, table_overrides=overrides)

    assert result["success"] is True
    assert any("WHERE OrderID>1" in sql for sql in executed_sqls)


def test_transfer_data_with_order_by(monkeypatch):
    """transfer_data with ORDER BY override should build SQL with ORDER BY clause."""
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[
            TableSchema(name="Products", columns=[ColumnSchema(name="Name", source_type="Text")]),
        ],
    )
    executed_sqls = []
    class _TracingAdapter:
        def __init__(self, original):
            self._original = original
        def execute_query(self, sql):
            executed_sqls.append(sql)
            return self._original.execute_query(sql)
    adapter = _TracingAdapter(_TransferAdapter(rows_by_table={"Products": [{"Name": "Beta"}, {"Name": "Alpha"}]}))
    factory = _TransferConnectorFactory(supports_linked=False)
    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    overrides = {"Products": TableTransferConfig(order_by=["Name"])}
    result = service.transfer_data("postgres", "fake-conn", schema, adapter, table_overrides=overrides)

    assert result["success"] is True
    assert any("ORDER BY Name" in sql for sql in executed_sqls)


def test_transfer_data_invalid_column_returns_error(monkeypatch):
    """transfer_data with invalid column should return success=False with error."""
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[
            TableSchema(name="Customers", columns=[ColumnSchema(name="Name", source_type="Text", allow_null=False)]),
        ],
    )
    adapter = _TransferAdapter(rows_by_table={"Customers": [{"Name": "Alice"}]})
    factory = _TransferConnectorFactory(supports_linked=False)
    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    overrides = {"Customers": TableTransferConfig(columns=["Name", "NonExistent"])}
    result = service.transfer_data("postgres", "fake-conn", schema, adapter, table_overrides=overrides)

    assert result["success"] is True
    job = service.get_job_status(result["job_id"])["job"]
    assert job["results"][0]["success"] is False
    assert "NonExistent" in job["results"][0]["error"]


def test_transfer_data_partial_override_coverage(monkeypatch):
    """Overrides only for one table; other table uses defaults."""
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[
            TableSchema(name="Customers", columns=[ColumnSchema(name="Name", source_type="Text")]),
            TableSchema(name="Orders", columns=[ColumnSchema(name="OrderID", source_type="Long Integer")]),
        ],
    )
    executed_sqls = []
    class _TracingAdapter:
        def __init__(self, original):
            self._original = original
        def execute_query(self, sql):
            executed_sqls.append(sql)
            return self._original.execute_query(sql)
    adapter = _TracingAdapter(_TransferAdapter(rows_by_table={
        "Customers": [{"Name": "Alice"}],
        "Orders": [{"OrderID": 1}],
    }))
    factory = _TransferConnectorFactory(supports_linked=False)
    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    overrides = {"Customers": TableTransferConfig(columns=["Name"])}
    result = service.transfer_data("postgres", "fake-conn", schema, adapter, table_overrides=overrides)

    assert result["success"] is True
    customer_sql = next(sql for sql in executed_sqls if "Customers" in sql)
    orders_sql = next(sql for sql in executed_sqls if "Orders" in sql)
    assert "SELECT Name FROM [Customers]" in customer_sql
    assert "SELECT * FROM [Orders]" in orders_sql


def test_transfer_data_verification_uses_effective_columns(monkeypatch):
    """transfer_data verification should use effective columns (filtered) not full schema."""
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[
            TableSchema(
                name="Customers",
                columns=[
                    ColumnSchema(name="ID", source_type="Long Integer"),
                    ColumnSchema(name="Name", source_type="Text"),
                ],
            )
        ],
    )
    adapter = _TransferAdapter(rows_by_table={"Customers": [{"ID": 1, "Name": "Alice"}]})
    factory = _TransferConnectorFactory(supports_linked=False)
    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    overrides = {"Customers": TableTransferConfig(columns=["Name"])}
    result = service.transfer_data("postgres", "fake-conn", schema, adapter, table_overrides=overrides)

    assert result["success"] is True
    job = service.get_job_status(result["job_id"])["job"]
    verification = job["results"][0]["verification"]
    assert verification["status"] == "passed"
    assert len(verification["signals"]) == 3


def test_transfer_data_no_overrides_uses_select_star(monkeypatch):
    """transfer_data with table_overrides=None preserves existing SELECT * behavior."""
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[
            TableSchema(name="Customers", columns=[ColumnSchema(name="Name", source_type="Text")]),
        ],
    )
    executed_sqls = []
    class _TracingAdapter:
        def __init__(self, original):
            self._original = original
        def execute_query(self, sql):
            executed_sqls.append(sql)
            return self._original.execute_query(sql)
    adapter = _TracingAdapter(_TransferAdapter(rows_by_table={"Customers": [{"Name": "Alice"}]}))
    factory = _TransferConnectorFactory(supports_linked=False)
    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    result = service.transfer_data("postgres", "fake-conn", schema, adapter, table_overrides=None)

    assert result["success"] is True
    assert any("SELECT * FROM [Customers]" in sql for sql in executed_sqls)


def test_validate_columns_valid():
    """_validate_columns with all valid columns should not raise."""
    MigrationService._validate_columns(["A", "B"], ["A", "B", "C"])


def test_validate_columns_invalid_raises():
    """_validate_columns with invalid column should raise ValueError naming it."""
    import pytest
    with pytest.raises(ValueError, match="X"):
        MigrationService._validate_columns(["A", "X"], ["A", "B"])


def test_resolve_override_none_returns_none_tuple():
    """_resolve_override with overrides=None returns (None, None, None)."""
    cols, where, order_by = MigrationService._resolve_override("T", None, ["A", "B"])
    assert cols is None
    assert where is None
    assert order_by is None


def test_resolve_override_table_not_in_dict_returns_none_tuple():
    """_resolve_override when table not in dict returns (None, None, None)."""
    cfg = TableTransferConfig(columns=["Name"])
    cols, where, order_by = MigrationService._resolve_override("T", {"Other": cfg}, ["A", "B"])
    assert cols is None
    assert where is None
    assert order_by is None


def test_resolve_override_applies_config():
    """_resolve_override applies the overrides config for matching table."""
    cfg = TableTransferConfig(columns=["A"], where="A>0", order_by=["A"])
    cols, where, order_by = MigrationService._resolve_override("T", {"T": cfg}, ["A", "B"])
    assert cols == ["A"]
    assert where == "A>0"
    assert order_by == ["A"]


def test_resolve_override_only_columns_returns_cols():
    """_resolve_override with only columns set returns cols list."""
    cfg = TableTransferConfig(columns=["X"])
    cols, where, order_by = MigrationService._resolve_override("T", {"T": cfg}, ["X", "Y"])
    assert cols == ["X"]
    assert where is None
    assert order_by is None


def test_build_select_star():
    """_build_select with all None params should return 'SELECT * FROM [T]'."""
    sql = MigrationService._build_select("T", None, None, None)
    assert sql == "SELECT * FROM [T]"


def test_build_select_columns():
    """_build_select with column list should return 'SELECT A, B FROM [T]'."""
    sql = MigrationService._build_select("T", ["A", "B"], None, None)
    assert sql == "SELECT A, B FROM [T]"


def test_build_select_where():
    """_build_select with WHERE clause should append it."""
    sql = MigrationService._build_select("T", None, "Active=True", None)
    assert sql == "SELECT * FROM [T] WHERE Active=True"


def test_build_select_order_by():
    """_build_select with ORDER BY should append it."""
    sql = MigrationService._build_select("T", None, None, ["X", "Y"])
    assert sql == "SELECT * FROM [T] ORDER BY X, Y"


def test_build_select_all_three():
    """_build_select with columns, WHERE, and ORDER BY combines all."""
    sql = MigrationService._build_select("T", ["A"], "A>0", ["A"])
    assert sql == "SELECT A FROM [T] WHERE A>0 ORDER BY A"


def test_table_transfer_config_all_fields_optional():
    """TableTransferConfig should have all fields optional (None by default)."""
    cfg = TableTransferConfig()
    assert cfg.columns is None
    assert cfg.where is None
    assert cfg.order_by is None


def test_table_transfer_config_roundtrip():
    """TableTransferConfig serialization round-trip should preserve values."""
    cfg = TableTransferConfig(columns=["Name", "Email"], where="Active=True", order_by=["Name"])
    dumped = cfg.model_dump()
    reconstructed = TableTransferConfig(**dumped)
    assert reconstructed.columns == ["Name", "Email"]
    assert reconstructed.where == "Active=True"
    assert reconstructed.order_by == ["Name"]


def test_extract_rows_from_query_result_handles_adapter_payload_shapes():
    rows = [{"ID": 1}]

    from_dict = MigrationService._extract_rows_from_query_result(
        {"success": True, "rows": rows, "count": 1, "columns": ["ID"]}
    )
    from_list = MigrationService._extract_rows_from_query_result(rows)
    from_failed_dict = MigrationService._extract_rows_from_query_result({"success": False, "error": "boom"})

    assert from_dict == rows
    assert from_list == rows
    assert from_failed_dict == []


def test_job_tracker_creates_job():
    """JobTracker should create a job with pending status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, ".test_jobs.json")
        tracker = JobTracker(state_file=state_file)
        job_id = str(uuid.uuid4())
        tracker.create_job(job_id, "postgres")
        job = tracker.get_job(job_id)
        assert job is not None
        assert job.id == job_id
        assert job.status == "pending"
        assert job.phase == "extract"


def test_job_tracker_updates_progress():
    """JobTracker should update job progress and current_table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, ".test_jobs.json")
        tracker = JobTracker(state_file=state_file)
        job_id = str(uuid.uuid4())
        tracker.create_job(job_id, "postgres")
        tracker.update_progress(job_id, 0.5, current_table="Customers")
        job = tracker.get_job(job_id)
        assert job.progress == 0.5
        assert job.current_table == "Customers"


def test_job_tracker_persists_to_file():
    """JobTracker should persist job state to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, ".test_jobs.json")
        tracker = JobTracker(state_file=state_file)
        job_id = str(uuid.uuid4())
        tracker.create_job(job_id, "mysql")
        tracker.update_progress(job_id, 0.75, current_table="Orders")

        # Create new tracker instance to verify persistence
        tracker2 = JobTracker(state_file=state_file)
        job = tracker2.get_job(job_id)
        assert job is not None
        assert job.progress == 0.75
        assert job.current_table == "Orders"
        assert job.status == "pending"


def test_job_tracker_add_result():
    """JobTracker should store table results."""
    from ms_access_mcp.models.migration import TableResult
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, ".test_jobs.json")
        tracker = JobTracker(state_file=state_file)
        job_id = str(uuid.uuid4())
        tracker.create_job(job_id, "sqlite")
        result = TableResult(table="Products", source_rows=50, rows_transferred=50, duration_ms=100, success=True)
        tracker.add_result(job_id, result)
        job = tracker.get_job(job_id)
        assert len(job.results) == 1
        assert job.results[0].table == "Products"
        assert job.results[0].source_rows == 50


def test_migration_service_has_extract_schema():
    """MigrationService should have extract_schema method."""
    service = MigrationService()
    assert hasattr(service, 'extract_schema')
    assert callable(service.extract_schema)


def test_migration_service_has_upload_schema():
    """MigrationService should have upload_schema method."""
    service = MigrationService()
    assert hasattr(service, 'upload_schema')
    assert callable(service.upload_schema)


def test_migration_service_has_transfer_data():
    """MigrationService should have transfer_data method."""
    service = MigrationService()
    assert hasattr(service, 'transfer_data')
    assert callable(service.transfer_data)


def test_migration_service_has_get_job_status():
    """MigrationService should have get_job_status method."""
    service = MigrationService()
    assert hasattr(service, 'get_job_status')
    assert callable(service.get_job_status)


def test_transfer_data_records_linked_strategy_telemetry(monkeypatch):
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[TableSchema(name="Customers", columns=[ColumnSchema(name="ID", source_type="Long Integer")])],
    )
    adapter = _TransferAdapter(rows_by_table={"Customers": [{"ID": 1}, {"ID": 2}]})
    factory = _TransferConnectorFactory(supports_linked=True)

    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    result = service.transfer_data("postgres", "fake-connection", schema, adapter)

    assert result["success"] is True
    job = service.get_job_status(result["job_id"])["job"]
    assert job["results"][0]["strategy_used"] == "linked"
    assert job["results"][0]["rows_transferred"] == 2
    assert factory.instance is not None
    assert factory.instance.linked_calls == 1
    assert factory.instance.batch_calls == 0


def test_transfer_data_falls_back_to_batch_when_linked_runtime_fails(monkeypatch):
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[TableSchema(name="Orders", columns=[ColumnSchema(name="OrderID", source_type="Long Integer")])],
    )
    adapter = _TransferAdapter(rows_by_table={"Orders": [{"OrderID": 10}, {"OrderID": 20}]})
    factory = _TransferConnectorFactory(supports_linked=True, linked_error=RuntimeError("linked crash"))

    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    result = service.transfer_data("postgres", "fake-connection", schema, adapter)

    assert result["success"] is True
    job = service.get_job_status(result["job_id"])["job"]
    assert job["results"][0]["strategy_used"] == "batch"
    assert job["results"][0]["strategy_fallback_reason"] == "linked runtime failed: linked crash"
    assert factory.instance is not None
    assert factory.instance.linked_calls == 1
    assert factory.instance.batch_calls == 1


def test_transfer_data_uses_capability_preflight_before_linked(monkeypatch):
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[TableSchema(name="Invoices", columns=[ColumnSchema(name="InvoiceID", source_type="Long Integer")])],
    )
    adapter = _TransferAdapter(rows_by_table={"Invoices": [{"InvoiceID": 99}]})
    factory = _TransferConnectorFactory(supports_linked=False)

    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    result = service.transfer_data("postgres", "fake-connection", schema, adapter)

    assert result["success"] is True
    job = service.get_job_status(result["job_id"])["job"]
    assert job["results"][0]["strategy_used"] == "batch"
    assert job["results"][0]["strategy_fallback_reason"] == "linked preflight failed"
    assert factory.instance is not None
    assert factory.instance.linked_calls == 0
    assert factory.instance.batch_calls == 1


def test_transfer_data_defaults_to_auto_transfer_and_full_verification(monkeypatch):
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[
            TableSchema(
                name="Customers",
                columns=[
                    ColumnSchema(name="ID", source_type="Long Integer"),
                    ColumnSchema(name="Name", source_type="Text"),
                ],
            )
        ],
    )
    adapter = _TransferAdapter(rows_by_table={"Customers": [{"ID": 1, "Name": "Alice"}, {"ID": 2, "Name": "Bob"}]})
    factory = _TransferConnectorFactory(supports_linked=True)

    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    result = service.transfer_data("postgres", "fake-connection", schema, adapter)

    assert result["success"] is True
    job = service.get_job_status(result["job_id"])["job"]
    table_result = job["results"][0]
    assert table_result["strategy_used"] == "linked"
    assert table_result["verification"]["status"] == "passed"
    assert {signal["signal_type"] for signal in table_result["verification"]["signals"]} == {
        "count",
        "checksum",
        "sample",
    }


def test_transfer_data_allows_batch_mode_override(monkeypatch):
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[TableSchema(name="Orders", columns=[ColumnSchema(name="OrderID", source_type="Long Integer")])],
    )
    adapter = _TransferAdapter(rows_by_table={"Orders": [{"OrderID": 10}, {"OrderID": 20}]})
    factory = _TransferConnectorFactory(supports_linked=True)

    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    result = service.transfer_data("postgres", "fake-connection", schema, adapter, transfer_mode="batch")

    assert result["success"] is True
    job = service.get_job_status(result["job_id"])["job"]
    assert job["results"][0]["strategy_used"] == "batch"
    assert factory.instance is not None
    assert factory.instance.linked_calls == 0
    assert factory.instance.batch_calls == 1


def test_transfer_data_supports_count_only_verification_mode(monkeypatch):
    service = MigrationService()
    schema = ExtractedSchema(
        source="source.accdb",
        tables=[TableSchema(name="Invoices", columns=[ColumnSchema(name="InvoiceID", source_type="Long Integer")])],
    )
    adapter = _TransferAdapter(rows_by_table={"Invoices": [{"InvoiceID": 1}, {"InvoiceID": 2}]})
    factory = _TransferConnectorFactory(supports_linked=False)

    monkeypatch.setattr("ms_access_mcp.services.migration.CONNECTORS", {"postgres": factory})

    result = service.transfer_data(
        "postgres",
        "fake-connection",
        schema,
        adapter,
        verification_mode="count-only",
    )

    assert result["success"] is True
    job = service.get_job_status(result["job_id"])["job"]
    verification = job["results"][0]["verification"]
    assert verification["status"] == "passed"
    assert [signal["signal_type"] for signal in verification["signals"]] == ["count"]
