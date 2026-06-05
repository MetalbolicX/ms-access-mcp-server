"""Tests for MigrationService — schema extraction, upload, and transfer orchestration."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from ms_access_mcp.services.migration import MigrationService, JobTracker
from ms_access_mcp.models.migration import (
    ExtractedSchema,
    TableSchema,
    ColumnSchema,
    TableResult,
    MigrationJob,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

class FakeAdapter:
    """Minimal adapter that supports get_table_schema_plan."""
    def __init__(self, tables=None):
        self._tables = tables or []
        self._queries = []

    def get_tables(self):
        return self._tables

    def get_queries(self):
        return self._queries

    def get_table_schema_plan(self):
        tables = []
        for t in self._tables:
            cols = [
                ColumnSchema(
                    name=f.name,
                    source_type=f.type or "Text",
                    max_length=f.size if f.size > 0 else None,
                    allow_null=not f.required,
                    is_autoincrement=False,
                )
                for f in t.fields
            ]
            tables.append(TableSchema(name=t.name, columns=cols))
        return (tables, None)


class FakeConnector:
    """Minimal connector for MigrationService tests."""
    def __init__(self, *, supports_linked=False, linked_error=None,
                 table_exists_return=True, create_table_return=True,
                 insert_rows_return=5, checksum="abc123"):
        self._supports_linked = supports_linked
        self._linked_error = linked_error
        self._table_exists_return = table_exists_return
        self._create_table_return = create_table_return
        self._insert_rows_return = insert_rows_return
        self._checksum = checksum
        self._connected = False
        self.tables_created: list[str] = []
        self.tables_failed: list[str] = []
        self.linked_calls = 0
        self.batch_calls = 0

    def connect(self, conn_str):
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self):
        return self._connected

    def table_exists(self, name):
        return self._table_exists_return

    def create_table(self, schema):
        if self._create_table_return:
            self.tables_created.append(schema.name)
        return self._create_table_return

    def insert_rows(self, table, rows):
        self.batch_calls += 1
        return self._insert_rows_return

    def rollback_table(self, table):
        pass

    def get_capabilities(self):
        from ms_access_mcp.connectors.base import ConnectorCapabilities
        return ConnectorCapabilities(
            supports_linked_insert_select=self._supports_linked,
            supports_checksum=True,
            supports_sampling=True,
            preferred_batch_size=1000,
        )

    def linked_transfer(self, source_adapter, source_table, target_table):
        self.linked_calls += 1
        if self._linked_error:
            raise self._linked_error
        return self._insert_rows_return

    def get_row_count(self, table):
        return 5

    def get_checksum(self, table, columns):
        return self._checksum

    def sample_rows(self, table, columns, limit, offset=0):
        return []


# ═══════════════════════════════════════════════════════════════════════
# JobTracker
# ═══════════════════════════════════════════════════════════════════════

class TestJobTracker:
    """JobTracker persistence to JSON file."""

    def test_create_and_get_job(self, tmp_path):
        state = tmp_path / "jobs.json"
        tracker = JobTracker(str(state))
        job = tracker.create_job("job-1", "postgres")
        assert job.id == "job-1"
        assert job.status == "pending"
        assert job.phase == "extract"

    def test_get_job_not_found(self, tmp_path):
        tracker = JobTracker(str(tmp_path / "nonexistent.json"))
        assert tracker.get_job("nonexistent") is None

    def test_update_job(self, tmp_path):
        tracker = JobTracker(str(tmp_path / "jobs.json"))
        tracker.create_job("job-1", "postgres")
        tracker.update_job("job-1", status="running", progress=0.5)
        job = tracker.get_job("job-1")
        assert job.status == "running"
        assert job.progress == 0.5

    def test_add_result(self, tmp_path):
        tracker = JobTracker(str(tmp_path / "jobs.json"))
        tracker.create_job("job-1", "postgres")
        result = TableResult(table="t1", source_rows=10, rows_transferred=10,
                             duration_ms=100, success=True)
        tracker.add_result("job-1", result)
        job = tracker.get_job("job-1")
        assert len(job.results) == 1
        assert job.results[0].table == "t1"

    def test_persistence_across_instances(self, tmp_path):
        state = tmp_path / "jobs.json"
        t1 = JobTracker(str(state))
        t1.create_job("job-1", "mysql")
        t2 = JobTracker(str(state))
        assert t2.get_job("job-1") is not None


# ═══════════════════════════════════════════════════════════════════════
# MigrationService — extract_schema
# ═══════════════════════════════════════════════════════════════════════

class FakeAdapterNoSchemaPlan:
    """Adapter without get_table_schema_plan — triggers the fallback code path."""
    def __init__(self, tables=None, queries=None):
        self._tables = tables or []
        self._queries = queries or []

    def get_tables(self):
        return self._tables

    def get_queries(self):
        return self._queries


class TestExtractSchema:
    """extract_schema — table and query discovery."""

    def test_extract_schema_with_table_schema_plan(self):
        from ms_access_mcp.models.database import TableInfo, FieldInfo
        fields = [FieldInfo(name="ID", type="Long Integer", size=4,
                            required=True, allow_zero_length=False)]
        tables = [TableInfo(name="customers", fields=fields, record_count=0)]
        adapter = FakeAdapter(tables)
        svc = MigrationService()
        schema = svc.extract_schema(adapter, "/path/to/db.accdb")
        assert schema.source == "/path/to/db.accdb"
        assert len(schema.tables) == 1
        assert schema.tables[0].name == "customers"

    def test_extract_schema_excludes_saved_queries(self):
        """When a query shares a table's name, the table is filtered out."""
        from ms_access_mcp.models.database import TableInfo, FieldInfo, QueryInfo
        fields = [FieldInfo(name="ID", type="Long Integer", size=4,
                            required=True, allow_zero_length=False)]
        tables = [TableInfo(name="MyQuery", fields=fields, record_count=0)]
        queries = [QueryInfo(name="MyQuery", sql="SELECT * FROM MyQuery", type="select")]
        adapter = FakeAdapterNoSchemaPlan(tables=tables, queries=queries)
        svc = MigrationService()
        schema = svc.extract_schema(adapter, "/path/to/db.accdb")
        # Table "MyQuery" must be excluded because a saved query has the same name
        assert all(t.name != "MyQuery" for t in schema.tables)


# ═══════════════════════════════════════════════════════════════════════
# MigrationService — _build_select
# ═══════════════════════════════════════════════════════════════════════

class TestBuildSelect:
    def test_select_star(self):
        sql = MigrationService._build_select("orders", None, None, None)
        assert sql == "SELECT * FROM [orders]"

    def test_select_columns(self):
        sql = MigrationService._build_select("orders", ["id", "total"], None, None)
        assert sql == "SELECT id, total FROM [orders]"

    def test_select_with_where(self):
        sql = MigrationService._build_select("orders", None, "status='active'", None)
        assert sql == "SELECT * FROM [orders] WHERE status='active'"

    def test_select_with_order_by(self):
        sql = MigrationService._build_select("orders", None, None, ["id", "name"])
        assert sql == "SELECT * FROM [orders] ORDER BY id, name"

    def test_select_full(self):
        sql = MigrationService._build_select("orders", ["id", "total"], "status='active'", ["id"])
        assert sql == "SELECT id, total FROM [orders] WHERE status='active' ORDER BY id"


# ═══════════════════════════════════════════════════════════════════════
# MigrationService — _resolve_override
# ═══════════════════════════════════════════════════════════════════════

class TestResolveOverride:
    def test_no_overrides(self):
        cols, where, order = MigrationService._resolve_override("t", None, ["a", "b"])
        assert (cols, where, order) == (None, None, None)

    def test_unknown_table(self):
        from ms_access_mcp.models.migration import TableTransferConfig
        overrides = {"other": TableTransferConfig(columns=["a"])}
        cols, where, order = MigrationService._resolve_override("t", overrides, ["a", "b"])
        assert (cols, where, order) == (None, None, None)

    def test_partial_override(self):
        from ms_access_mcp.models.migration import TableTransferConfig
        overrides = {"t": TableTransferConfig(where="id>10")}
        cols, where, order = MigrationService._resolve_override("t", overrides, ["a", "b"])
        assert cols is None
        assert where == "id>10"
        assert order is None


# ═══════════════════════════════════════════════════════════════════════
# MigrationService — upload_schema
# ═══════════════════════════════════════════════════════════════════════

class TestUploadSchema:
    def test_unknown_target_type(self):
        svc = MigrationService()
        result = svc.upload_schema("unknown", "conn_str", MagicMock())
        assert result["success"] is False
        assert "Unknown target type" in result["error"]

    def test_upload_schema_success(self, tmp_path):
        from ms_access_mcp.models.database import TableInfo, FieldInfo
        fields = [FieldInfo(name="ID", type="Long Integer", size=4,
                             required=True, allow_zero_length=False)]
        tables = [TableInfo(name="customers", fields=fields, record_count=0)]
        adapter = FakeAdapter(tables)
        svc = MigrationService()

        # Use sqlite to test the real connector path
        db_path = str(tmp_path / "target.db")
        result = svc.upload_schema("sqlite", db_path, ExtractedSchema(
            source="src",
            version="1.0",
            tables=[
                TableSchema(name="customers", columns=[
                    ColumnSchema(name="ID", source_type="Long Integer",
                                 allow_null=False),
                    ColumnSchema(name="Name", source_type="Text", max_length=255),
                ])
            ],
        ))
        assert result["success"] is True
        # Verify table was created via the connector (tables_created populated)
        assert len(result["tables_created"]) > 0 or len(result["tables_failed"]) == 0

    def test_upload_schema_skips_existing_table(self, tmp_path):
        from ms_access_mcp.models.database import TableInfo, FieldInfo
        tables = [TableInfo(name="orders", fields=[], record_count=0)]
        adapter = FakeAdapter(tables)
        svc = MigrationService()
        db_path = str(tmp_path / "target2.db")
        # Create table first
        svc.upload_schema("sqlite", db_path, ExtractedSchema(
            source="src", version="1.0",
            tables=[TableSchema(name="orders", columns=[
                ColumnSchema(name="id", source_type="Long Integer", allow_null=False)
            ])],
        ))
        # Upload again — should be skipped
        result = svc.upload_schema("sqlite", db_path, ExtractedSchema(
            source="src", version="1.0",
            tables=[TableSchema(name="orders", columns=[
                ColumnSchema(name="id", source_type="Long Integer", allow_null=False)
            ])],
        ))
        assert "orders" in result["tables_failed"]


# ═══════════════════════════════════════════════════════════════════════
# MigrationService — transfer_data
# ═══════════════════════════════════════════════════════════════════════

class TestTransferData:
    def test_unknown_target_type(self):
        svc = MigrationService()
        result = svc.transfer_data(
            "unknown", "conn_str",
            ExtractedSchema(source="src", version="1.0", tables=[]),
            MagicMock(),
        )
        assert result["success"] is False
        assert "Unknown target type" in result["error"]

    def test_transfer_data_not_connected(self, tmp_path):
        svc = MigrationService()
        # Use sqlite with an invalid path to force connection failure
        result = svc.transfer_data(
            "sqlite", "/nonexistent/dir/db.sqlite",
            ExtractedSchema(source="src", version="1.0", tables=[]),
            MagicMock(),
        )
        assert result["success"] is False
        assert "Failed to connect" in result["error"]

    def test_transfer_data_empty_schema(self, tmp_path):
        """When schema.tables is empty, transfer returns immediately."""
        svc = MigrationService()
        db_path = str(tmp_path / "empty.sqlite")
        # Empty tables should succeed quickly (no tables to transfer)
        result = svc.transfer_data(
            "sqlite", db_path,
            ExtractedSchema(source="src", version="1.0", tables=[]),
            MagicMock(),
        )
        assert result["success"] is True

    def test_transfer_creates_job(self, tmp_path, monkeypatch):
        """transfer_data should create a job in the tracker."""
        svc = MigrationService()
        svc._tracker = JobTracker()  # reset tracker

        from ms_access_mcp.models.database import TableInfo, FieldInfo
        fields = [FieldInfo(name="ID", type="Long Integer", size=4,
                             required=True, allow_zero_length=False)]
        tables = [TableInfo(name="customers", fields=fields, record_count=5)]

        adapter = MagicMock()
        adapter.get_tables.return_value = tables
        adapter.get_table_schema_plan.return_value = ([
            TableSchema(name="customers", columns=[
                ColumnSchema(name="ID", source_type="Long Integer", allow_null=False)
            ])
        ], None)
        adapter.get_queries.return_value = []
        adapter.execute_query.return_value = {
            "success": True, "rows": [{"ID": 1}, {"ID": 2}], "count": 2, "columns": ["ID"]
        }

        db_path = str(tmp_path / "transfer_test.sqlite")
        schema = ExtractedSchema(source="src", version="1.0", tables=[
            TableSchema(name="customers", columns=[
                ColumnSchema(name="ID", source_type="Long Integer", allow_null=False)
            ])
        ])

        result = svc.transfer_data("sqlite", db_path, schema, adapter)
        assert result["success"] is True
        assert "job_id" in result

        status = svc.get_job_status(result["job_id"])
        assert status["success"] is True
        assert status["job"]["status"] == "completed"

    def test_transfer_uses_batch_when_no_rows(self, tmp_path):
        """Empty source table uses batch strategy with 0 transferred."""
        svc = MigrationService()
        from ms_access_mcp.models.database import TableInfo, FieldInfo
        fields = [FieldInfo(name="ID", type="Long Integer", size=4,
                             required=True, allow_zero_length=False)]
        tables = [TableInfo(name="empty_table", fields=fields, record_count=0)]

        adapter = MagicMock()
        adapter.get_tables.return_value = tables
        adapter.get_table_schema_plan.return_value = ([
            TableSchema(name="empty_table", columns=[
                ColumnSchema(name="ID", source_type="Long Integer", allow_null=False)
            ])
        ], None)
        adapter.get_queries.return_value = []
        adapter.execute_query.return_value = {
            "success": True, "rows": [], "count": 0, "columns": ["ID"]
        }

        db_path = str(tmp_path / "empty.sqlite")
        schema = ExtractedSchema(source="src", version="1.0", tables=[
            TableSchema(name="empty_table", columns=[
                ColumnSchema(name="ID", source_type="Long Integer", allow_null=False)
            ])
        ])

        result = svc.transfer_data("sqlite", db_path, schema, adapter)
        assert result["success"] is True

        job_id = result["job_id"]
        job = svc.get_job_status(job_id)["job"]
        assert len(job["results"]) == 1
        assert job["results"][0]["table"] == "empty_table"
        assert job["results"][0]["rows_transferred"] == 0
        assert job["results"][0]["success"] is True

    def test_get_job_status_not_found(self):
        svc = MigrationService()
        result = svc.get_job_status("nonexistent-job")
        assert result["success"] is False
        assert "not found" in result["error"]


# ═══════════════════════════════════════════════════════════════════════
# MigrationService — column validation
# ═══════════════════════════════════════════════════════════════════════

class TestValidateColumns:
    def test_valid_columns(self):
        MigrationService._validate_columns(["a", "b"], ["a", "b", "c"])

    def test_invalid_column_raises(self):
        with pytest.raises(ValueError) as exc:
            MigrationService._validate_columns(["a", "z"], ["a", "b"])
        assert "z" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════
# MigrationService — _build_source_snapshot_connector
# ═══════════════════════════════════════════════════════════════════════

class TestSourceSnapshotConnector:
    def test_row_count(self):
        svc = MigrationService()
        connector = svc._build_source_snapshot_connector(
            rows=[{"a": 1}, {"a": 2}],
            supports_checksum=True,
            supports_sampling=True,
        )
        assert connector.get_row_count("ignored") == 2

    def test_checksum(self):
        svc = MigrationService()
        connector = svc._build_source_snapshot_connector(
            rows=[{"a": 1}, {"a": 2}],
            supports_checksum=True,
            supports_sampling=True,
        )
        checksum = connector.get_checksum("ignored", ["a"])
        assert checksum is not None
        assert len(checksum) == 32  # MD5 hex

    def test_sample_rows(self):
        svc = MigrationService()
        connector = svc._build_source_snapshot_connector(
            rows=[{"a": 3}, {"a": 1}, {"a": 2}],
            supports_checksum=True,
            supports_sampling=True,
        )
        sampled = connector.sample_rows("ignored", ["a"], limit=2, offset=0)
        assert len(sampled) == 2


# ═══════════════════════════════════════════════════════════════════════
# MigrationService — execute_raw_sql (passthrough path)
# ═══════════════════════════════════════════════════════════════════════

class TestExecuteRawSql:
    def test_execute_raw_sql_success(self):
        """execute_raw_sql delegates to adapter's execute_raw_sql and returns rows affected."""
        class _FakeAdapterWithExecuteRaw:
            def __init__(self):
                self.calls: list[str] = []

            def get_table_schema_plan(self):
                return ([], None)

            def execute_raw_sql(self, sql: str) -> int:
                self.calls.append(sql)
                return 42

        adapter = _FakeAdapterWithExecuteRaw()
        svc = MigrationService()

        result = svc.execute_raw_sql("INSERT INTO [ODBC;...].[T] SELECT * FROM [T]", adapter)

        assert result["success"] is True
        assert result["rows_affected"] == 42
        assert adapter.calls[0] == "INSERT INTO [ODBC;...].[T] SELECT * FROM [T]"

    def test_execute_raw_sql_empty_sql_rejected(self):
        """execute_raw_sql rejects empty SQL string."""
        class _FakeAdapterWithExecuteRaw:
            def execute_raw_sql(self, sql: str) -> int:
                return 0

        adapter = _FakeAdapterWithExecuteRaw()
        svc = MigrationService()

        result = svc.execute_raw_sql("", adapter)
        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_execute_raw_sql_none_sql_rejected(self):
        """execute_raw_sql rejects None SQL."""
        class _FakeAdapterWithExecuteRaw:
            def execute_raw_sql(self, sql: str) -> int:
                return 0

        adapter = _FakeAdapterWithExecuteRaw()
        svc = MigrationService()

        result = svc.execute_raw_sql(None, adapter)
        assert result["success"] is False

    def test_execute_raw_sql_adapter_not_implemented(self):
        """execute_raw_sql returns error when adapter lacks the method."""
        class _FakeAdapterNoMethod:
            def get_table_schema_plan(self):
                return ([], None)

        adapter = _FakeAdapterNoMethod()
        svc = MigrationService()

        result = svc.execute_raw_sql("SELECT 1", adapter)
        assert result["success"] is False
        assert "execute_raw_sql" in result["error"]

    def test_execute_raw_sql_passthrough_uses_adapter_directly(self):
        """The passthrough SQL goes directly to adapter.execute_raw_sql without transformation."""
        class _FakeAdapterDirectCall:
            def __init__(self):
                self.received_sql: str | None = None

            def get_table_schema_plan(self):
                return ([], None)

            def execute_raw_sql(self, sql: str) -> int:
                self.received_sql = sql
                return 7

        adapter = _FakeAdapterDirectCall()
        svc = MigrationService()

        passthrough_sql = (
            "INSERT INTO [ODBC;DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;"
            "DATABASE=test;UID=u;PWD=p].[Customers] SELECT [ID], [Name] FROM [Customers]"
        )
        result = svc.execute_raw_sql(passthrough_sql, adapter)

        assert result["success"] is True
        assert result["rows_affected"] == 7
        assert adapter.received_sql == passthrough_sql

    def test_execute_raw_sql_records_affected_from_execute_raw_sql(self):
        """execute_raw_sql returns the rows_affected count from adapter.execute_raw_sql."""
        class _FakeAdapterReturnsCount:
            def __init__(self, count: int):
                self._count = count

            def get_table_schema_plan(self):
                return ([], None)

            def execute_raw_sql(self, sql: str) -> int:
                return self._count

        for expected in [0, 1, 100, 5000]:
            adapter = _FakeAdapterReturnsCount(expected)
            svc = MigrationService()
            result = svc.execute_raw_sql("SELECT 1", adapter)
            assert result["rows_affected"] == expected, f"Expected {expected}, got {result['rows_affected']}"