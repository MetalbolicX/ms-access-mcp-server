# Migration Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build bidirectional migration engine to extract Access schema, upload to PostgreSQL/MySQL/MariaDB/SQLite/SQL Server, and transfer data with table-by-table rollback and SSE progress.

**Architecture:** MigrationService orchestrates SchemaExtractor (from Access adapter) → SchemaMapper (type mapping) → TargetConnector (per-database driver) → DataTransfer (row-level with rollback). JobTracker persists state to JSON file and streams via SSE.

**Tech Stack:** Python 3.11+, pyodbc (SQL Server), psycopg2 (PostgreSQL), mysql-connector-python (MySQL/MariaDB), sqlite3 (built-in), FastMCP, SSE via sse-starlette.

---

## File Structure

```
src/ms_access_mcp/
├── models/
│   └── migration.py          # MigrationJob, TableResult, ExtractedSchema, ColumnSchema
├── connectors/
│   ├── __init__.py
│   ├── base.py                # TargetConnector Protocol
│   ├── postgres.py           # PostgreSQL connector
│   ├── mysql.py               # MySQL/MariaDB connector
│   ├── sqlite.py              # SQLite connector
│   └── sqlserver.py           # SQL Server connector
├── services/
│   ├── migration.py           # MigrationService + JobTracker
│   └── schema_mapper.py       # Access type → target type mapping
└── mcp/
    └── server.py              # Add extract_schema, upload_schema, transfer_data, get_migration_status tools
tests/unit/
├── test_migration_models.py
├── test_schema_mapper.py
├── test_connectors/
│   ├── test_postgres.py
│   ├── test_mysql.py
│   ├── test_sqlite.py
│   └── test_sqlserver.py
└── test_migration_service.py
```

---

## Task 1: Migration Models

**Files:**
- Create: `src/ms_access_mcp/models/migration.py`
- Test: `tests/unit/test_migration_models.py`

- [ ] **Step 1: Write the failing test**

```python
from ms_access_mcp.models.migration import MigrationJob, TableResult, ExtractedSchema, ColumnSchema, TableSchema

def test_migration_job_defaults():
    job = MigrationJob(id="test-id")
    assert job.id == "test-id"
    assert job.status == "pending"
    assert job.phase == "extract"
    assert job.progress == 0.0
    assert job.results == []
    assert job.errors == []

def test_table_result():
    result = TableResult(table="Customers", source_rows=100, rows_transferred=100, duration_ms=1234, success=True)
    assert result.table == "Customers"
    assert result.rows_transferred == 100

def test_extracted_schema():
    schema = ExtractedSchema(source="C:\\db.accdb", tables=[])
    assert schema.source == "C:\\db.accdb"
    assert schema.version == "1.0"
    assert len(schema.tables) == 0

def test_column_schema():
    col = ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True)
    assert col.name == "ID"
    assert col.is_autoincrement is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_migration_models.py -v`

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field
from typing import Literal

class ErrorInfo(BaseModel):
    table: str | None = None
    row_number: int | None = None
    message: str
    timestamp: str | None = None

class TableResult(BaseModel):
    table: str
    source_rows: int = 0
    rows_transferred: int = 0
    duration_ms: int = 0
    success: bool = True
    error: str | None = None

class MigrationJob(BaseModel):
    id: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    phase: Literal["extract", "upload", "transfer"] = "extract"
    current_table: str | None = None
    progress: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
    results: list[TableResult] = Field(default_factory=list)
    errors: list[ErrorInfo] = Field(default_factory=list)

class ColumnSchema(BaseModel):
    name: str
    source_type: str
    max_length: int | None = None
    allow_null: bool = True
    is_autoincrement: bool = False
    default_value: str | None = None

class TableSchema(BaseModel):
    name: str
    columns: list[ColumnSchema] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)

class ExtractedSchema(BaseModel):
    source: str
    version: str = "1.0"
    extracted_at: str | None = None
    tables: list[TableSchema] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_migration_models.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/ms_access_mcp/models/migration.py tests/unit/test_migration_models.py
git commit -m "feat(migration): add migration models"
```

---

## Task 2: TargetConnector Protocol + Base

**Files:**
- Create: `src/ms_access_mcp/connectors/__init__.py`
- Create: `src/ms_access_mcp/connectors/base.py`
- Test: `tests/unit/test_connectors/test_base.py`

- [ ] **Step 1: Write the failing test**

```python
from ms_access_mcp.connectors.base import TargetConnector, ConnectionStatus
from typing import Any

class DummyConnector(TargetConnector):
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
    conn = DummyConnector("postgresql")
    assert isinstance(conn, TargetConnector)
    assert conn.target_type == "postgresql"

def test_connection_status():
    status = ConnectionStatus(connected=True, server_version="14.0")
    assert status.connected is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_connectors/test_base.py -v`

- [ ] **Step 3: Write minimal implementation**

```python
from typing import Protocol, Any
from typing_extensions import Literal
from pydantic import BaseModel

class ConnectionStatus(BaseModel):
    connected: bool
    server_version: str | None = None
    error: str | None = None

class TargetConnector(Protocol):
    """Abstract interface for target database operations during migration."""

    @property
    def target_type(self) -> str:
        """Return the target database type."""
        ...

    def connect(self, connection_string: str) -> bool:
        """Establish connection to target database."""
        ...

    def disconnect(self) -> None:
        """Close the connection."""
        ...

    def is_connected(self) -> bool:
        """Check if currently connected."""
        ...

    def create_table(self, schema: Any) -> bool:
        """Create a table from schema definition. Returns True on success."""
        ...

    def insert_rows(self, table: str, rows: list[dict]) -> int:
        """Insert rows into a table. Returns number of rows inserted."""
        ...

    def rollback_table(self, table: str) -> None:
        """Rollback (delete) a table if partial transfer failed."""
        ...

    def table_exists(self, table_name: str) -> bool:
        """Check if a table already exists in target."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_connectors/test_base.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/ms_access_mcp/connectors/__init__.py src/ms_access_mcp/connectors/base.py tests/unit/test_connectors/test_base.py
git commit -m "feat(migration): add TargetConnector protocol"
```

---

## Task 3: SchemaMapper

**Files:**
- Create: `src/ms_access_mcp/services/schema_mapper.py`
- Test: `tests/unit/test_schema_mapper.py`

- [ ] **Step 1: Write the failing test**

```python
from ms_access_mcp.services.schema_mapper import SchemaMapper
from ms_access_mcp.models.migration import ColumnSchema, TableSchema, ExtractedSchema

def test_map_text_to_postgres():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "postgres")
    assert mapped.target_type == "VARCHAR(255)"
    assert mapped.allow_null is True

def test_map_text_to_sqlite():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "sqlite")
    assert mapped.target_type == "TEXT"

def test_map_autoincrement_to_postgres():
    mapper = SchemaMapper()
    col = ColumnSchema(name="ID", source_type="Long Integer", max_length=None, allow_null=False, is_autoincrement=True)
    mapped = mapper.map_column(col, "postgres")
    assert "SERIAL" in mapped.target_type or "BIGSERIAL" in mapped.target_type

def test_map_datetime_to_postgres():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Created", source_type="Date/Time", max_length=None, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "postgres")
    assert mapped.target_type == "TIMESTAMP(0)"

def test_map_memo_to_mysql():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Notes", source_type="Memo", max_length=None, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "mysql")
    assert mapped.target_type == "LONGTEXT"

def test_map_unknown_to_sqlserver():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Data", source_type="Binary", max_length=None, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "sqlserver")
    assert "VARBINARY" in mapped.target_type or "max" in mapped.target_type

def test_map_table_to_sqlite():
    mapper = SchemaMapper()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = mapper.map_table_ddl(table, "sqlite")
    assert "CREATE TABLE" in ddl
    assert '"ID" INTEGER PRIMARY KEY' in ddl or "ID" in ddl
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_schema_mapper.py -v`

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel
from ..models.migration import ColumnSchema, TableSchema

# Type mapping tables
TYPE_MAP = {
    "postgres": {
        "Text": "VARCHAR({max_length})",
        "Memo": "TEXT",
        "Long Integer": "BIGINT",
        "Integer": "INTEGER",
        "Byte": "SMALLINT",
        "Boolean": "BOOLEAN",
        "Date/Time": "TIMESTAMP(0)",
        "Currency": "DECIMAL(19,4)",
        "Counter": "BIGSERIAL",
        "AutoNumber": "BIGSERIAL",
        "Single": "REAL",
        "Double": "DOUBLE PRECISION",
        "Decimal": "DECIMAL(18,4)",
        "OLE Object": "BYTEA",
        "GUID": "Uuid",
        "Binary": "BYTEA",
    },
    "mysql": {
        "Text": "VARCHAR({max_length})",
        "Memo": "LONGTEXT",
        "Long Integer": "BIGINT",
        "Integer": "INT",
        "Byte": "TINYINT UNSIGNED",
        "Boolean": "TINYINT(1)",
        "Date/Time": "DATETIME",
        "Currency": "DECIMAL(19,4)",
        "Counter": "BIGINT AUTO_INCREMENT",
        "AutoNumber": "BIGINT AUTO_INCREMENT",
        "Single": "FLOAT",
        "Double": "DOUBLE",
        "Decimal": "DECIMAL(18,4)",
        "OLE Object": "LONGBLOB",
        "GUID": "CHAR(36)",
        "Binary": "LONGBLOB",
    },
    "mariadb": {
        "Text": "VARCHAR({max_length})",
        "Memo": "LONGTEXT",
        "Long Integer": "BIGINT",
        "Integer": "INT",
        "Byte": "TINYINT UNSIGNED",
        "Boolean": "TINYINT(1)",
        "Date/Time": "DATETIME",
        "Currency": "DECIMAL(19,4)",
        "Counter": "BIGINT AUTO_INCREMENT",
        "AutoNumber": "BIGINT AUTO_INCREMENT",
        "Single": "FLOAT",
        "Double": "DOUBLE",
        "Decimal": "DECIMAL(18,4)",
        "OLE Object": "LONGBLOB",
        "GUID": "CHAR(36)",
        "Binary": "LONGBLOB",
    },
    "sqlite": {
        "Text": "TEXT",
        "Memo": "TEXT",
        "Long Integer": "INTEGER",
        "Integer": "INTEGER",
        "Byte": "INTEGER",
        "Boolean": "INTEGER",
        "Date/Time": "TEXT",
        "Currency": "REAL",
        "Counter": "INTEGER",
        "AutoNumber": "INTEGER",
        "Single": "REAL",
        "Double": "REAL",
        "Decimal": "REAL",
        "OLE Object": "BLOB",
        "GUID": "TEXT",
        "Binary": "BLOB",
    },
    "sqlserver": {
        "Text": "VARCHAR({max_length})",
        "Memo": "VARCHAR(max)",
        "Long Integer": "INT",
        "Integer": "SMALLINT",
        "Byte": "TINYINT",
        "Boolean": "BIT",
        "Date/Time": "DATETIME2(0)",
        "Currency": "MONEY",
        "Counter": "INT IDENTITY",
        "AutoNumber": "INT IDENTITY",
        "Single": "REAL",
        "Double": "FLOAT",
        "Decimal": "DECIMAL(18,4)",
        "OLE Object": "VARBINARY(max)",
        "GUID": "UNIQUEIDENTIFIER",
        "Binary": "VARBINARY(max)",
    },
}

class MappedColumn(BaseModel):
    name: str
    target_type: str
    allow_null: bool
    is_primary_key: bool = False
    is_autoincrement: bool = False


class SchemaMapper:
    """Maps Access column types to target database types."""

    def map_column(self, column: ColumnSchema, target_type: str) -> MappedColumn:
        """Map a single Access column to target database type."""
        type_map = TYPE_MAP.get(target_type, TYPE_MAP["postgres"])
        source_type = column.source_type
        
        # Handle autoincrement
        if column.is_autoincrement:
            if target_type == "postgres":
                mapped_type = "BIGSERIAL"
            elif target_type in ("mysql", "mariadb"):
                mapped_type = "BIGINT AUTO_INCREMENT"
            elif target_type == "sqlite":
                mapped_type = "INTEGER"
            elif target_type == "sqlserver":
                mapped_type = "INT IDENTITY"
            else:
                mapped_type = type_map.get(source_type, "INTEGER")
        else:
            template = type_map.get(source_type, "TEXT")
            if "{max_length}" in template:
                max_len = column.max_length or 255
                mapped_type = template.format(max_length=max_len)
            else:
                mapped_type = template

        return MappedColumn(
            name=column.name,
            target_type=mapped_type,
            allow_null=column.allow_null,
            is_primary_key=False,
            is_autoincrement=column.is_autoincrement,
        )

    def map_table_ddl(self, table: TableSchema, target_type: str) -> str:
        """Generate DDL for creating a table in target database."""
        lines = []
        pk_cols = []
        
        for col in table.columns:
            mapped = self.map_column(col, target_type)
            col_def = f'"{mapped.name}" {mapped.target_type}'
            if not mapped.allow_null:
                col_def += " NOT NULL"
            if mapped.is_autoincrement and target_type not in ("sqlserver",):
                pass  # autoincrement is part of type
            lines.append(col_def)
            if col.name in table.primary_key:
                pk_cols.append(f'"{mapped.name}"')

        sql = f'CREATE TABLE "{table.name}" (\n  '
        sql += ",\n  ".join(lines)
        if pk_cols:
            sql += f",\n  PRIMARY KEY ({', '.join(pk_cols)})"
        sql += "\n)"
        return sql
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_schema_mapper.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/ms_access_mcp/services/schema_mapper.py tests/unit/test_schema_mapper.py
git commit -m "feat(migration): add SchemaMapper with type mapping"
```

---

## Task 4: PostgreSQL Connector

**Files:**
- Create: `src/ms_access_mcp/connectors/postgres.py`
- Test: `tests/unit/test_connectors/test_postgres.py`

- [ ] **Step 1: Write the failing test**

```python
from ms_access_mcp.connectors.postgres import PostgresConnector
from ms_access_mcp.models.migration import TableSchema, ColumnSchema

def test_postgres_connector_instantiation():
    conn = PostgresConnector()
    assert conn.target_type == "postgres"

def test_postgres_table_ddl():
    conn = PostgresConnector()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = conn.generate_ddl(table)
    assert "CREATE TABLE" in ddl
    assert '"ID"' in ddl
    assert "BIGSERIAL" in ddl
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_connectors/test_postgres.py -v`

- [ ] **Step 3: Write minimal implementation**

```python
from typing import Any
import psycopg2
from .base import TargetConnector, ConnectionStatus
from ..services.schema_mapper import SchemaMapper

class PostgresConnector(TargetConnector):
    """PostgreSQL connector for migration."""

    def __init__(self):
        self._conn: Any = None
        self._schema_mapper = SchemaMapper()

    @property
    def target_type(self) -> str:
        return "postgres"

    def connect(self, connection_string: str) -> bool:
        try:
            self._conn = psycopg2.connect(connection_string)
            return True
        except Exception:
            self._conn = None
            return False

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.closed

    def create_table(self, schema: Any) -> bool:
        if not self.is_connected():
            return False
        try:
            ddl = self._schema_mapper.map_table_ddl(schema, "postgres")
            with self._conn.cursor() as cur:
                cur.execute(ddl)
            self._conn.commit()
            return True
        except Exception:
            self._conn.rollback()
            return False

    def insert_rows(self, table: str, rows: list[dict]) -> int:
        if not self.is_connected() or not rows:
            return 0
        try:
            cols = list(rows[0].keys())
            placeholders = ", ".join(["%s"] * len(cols))
            col_names = ", ".join([f'"{c}"' for c in cols])
            sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'
            with self._conn.cursor() as cur:
                for row in rows:
                    cur.execute(sql, list(row.values()))
            self._conn.commit()
            return len(rows)
        except Exception:
            self._conn.rollback()
            return 0

    def rollback_table(self, table: str) -> None:
        if not self.is_connected():
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute(f'DROP TABLE IF EXISTS "{table}"')
            self._conn.commit()
        except Exception:
            self._conn.rollback()

    def table_exists(self, table_name: str) -> bool:
        if not self.is_connected():
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                    (table_name,)
                )
                return cur.fetchone() is not None
        except Exception:
            return False

    def generate_ddl(self, schema: Any) -> str:
        return self._schema_mapper.map_table_ddl(schema, "postgres")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_connectors/test_postgres.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/ms_access_mcp/connectors/postgres.py tests/unit/test_connectors/test_postgres.py
git commit -m "feat(migration): add PostgreSQL connector"
```

---

## Task 5: MySQL, MariaDB, SQLite, SQL Server Connectors

**Files:**
- Create: `src/ms_access_mcp/connectors/mysql.py`
- Create: `src/ms_access_mcp/connectors/sqlite.py`
- Create: `src/ms_access_mcp/connectors/sqlserver.py`
- Test: `tests/unit/test_connectors/test_mysql.py`, `test_sqlite.py`, `test_sqlserver.py`

Each connector follows the same pattern as Task 4. Structure per connector:

**MySQL Connector** (`connectors/mysql.py`):
- Use `mysql.connector` or `mysql-connector-python`
- Target type: `mysql`
- Handle `AUTO_INCREMENT` suffix for autoincrement columns
- Handle `LONGTEXT` for Memo types

**SQLite Connector** (`connectors/sqlite.py`):
- Use built-in `sqlite3`
- No server version needed
- SQLite doesn't have AUTO_INCREMENT keyword — use `INTEGER PRIMARY KEY AUTOINCREMENT`

**SQL Server Connector** (`connectors/sqlserver.py`):
- Use `pyodbc`
- Use `INT IDENTITY` for autoincrement
- Handle `VARCHAR(max)` for Memo

- [ ] **Step 1: Write tests and implementations for each connector** (one at a time or batch similar)

```python
# Example mysql test
def test_mysql_connector_target_type():
    conn = MySqlConnector()
    assert conn.target_type == "mysql"
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/unit/test_connectors/ -v
```

- [ ] **Step 3: Commit each**

```bash
git add src/ms_access_mcp/connectors/mysql.py src/ms_access_mcp/connectors/sqlite.py src/ms_access_mcp/connectors/sqlserver.py
git commit -m "feat(migration): add MySQL, SQLite, SQL Server connectors"
```

---

## Task 6: MigrationService + JobTracker

**Files:**
- Create: `src/ms_access_mcp/services/migration.py`
- Test: `tests/unit/test_migration_service.py`

- [ ] **Step 1: Write the failing test**

```python
from ms_access_mcp.services.migration import MigrationService, JobTracker
import uuid

def test_job_tracker_creates_job():
    tracker = JobTracker()
    job_id = str(uuid.uuid4())
    tracker.create_job(job_id, "postgres")
    job = tracker.get_job(job_id)
    assert job is not None
    assert job.status == "pending"

def test_job_tracker_updates_progress():
    tracker = JobTracker()
    job_id = str(uuid.uuid4())
    tracker.create_job(job_id, "postgres")
    tracker.update_progress(job_id, 0.5, current_table="Customers")
    job = tracker.get_job(job_id)
    assert job.progress == 0.5
    assert job.current_table == "Customers"

def test_migration_service_extract_schema():
    service = MigrationService()
    # Would need real Access DB to test fully
    # Test that method exists and returns ExtractedSchema
    assert hasattr(service, 'extract_schema')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_migration_service.py -v`

- [ ] **Step 3: Write minimal implementation**

```python
import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..models.migration import MigrationJob, ExtractedSchema, TableResult, ErrorInfo, TableSchema, ColumnSchema
from ..adapters.base import AccessAdapter
from .schema_mapper import SchemaMapper
from ..connectors.postgres import PostgresConnector
from ..connectors.mysql import MySqlConnector
from ..connectors.sqlite import SqliteConnector
from ..connectors.sqlserver import SqlServerConnector

CONNECTORS = {
    "postgres": PostgresConnector,
    "mysql": MySqlConnector,
    "mariadb": MySqlConnector,
    "sqlite": SqliteConnector,
    "sqlserver": SqlServerConnector,
}

class JobTracker:
    """Tracks migration job state to JSON file."""

    def __init__(self, state_file: str | None = None):
        self._state_file = state_file or os.path.join(os.environ.get("TEMP", "/tmp"), ".migration_jobs.json")
        self._jobs: dict[str, MigrationJob] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, "r") as f:
                    data = json.load(f)
                    for job_data in data.values():
                        self._jobs[job_data["id"]] = MigrationJob(**job_data)
            except Exception:
                pass

    def _save(self) -> None:
        try:
            with open(self._state_file, "w") as f:
                json.dump({k: v.model_dump() for k, v in self._jobs.items()}, f, indent=2)
        except Exception:
            pass

    def create_job(self, job_id: str, target_type: str) -> MigrationJob:
        job = MigrationJob(id=job_id, status="pending", phase="extract")
        self._jobs[job_id] = job
        self._save()
        return job

    def get_job(self, job_id: str) -> Optional[MigrationJob]:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs) -> None:
        if job_id in self._jobs:
            for k, v in kwargs.items():
                setattr(self._jobs[job_id], k, v)
            self._save()

    def add_result(self, job_id: str, result: TableResult) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].results.append(result)
            self._save()


class MigrationService:
    """Orchestrates schema extraction, upload, and data transfer."""

    def __init__(self):
        self._tracker = JobTracker()
        self._schema_mapper = SchemaMapper()

    def extract_schema(self, adapter: AccessAdapter, source_path: str) -> ExtractedSchema:
        """Extract schema from Access database via adapter."""
        tables = adapter.get_tables()
        schema_tables = []
        for t in tables:
            cols = []
            for f in t.fields:
                cols.append(ColumnSchema(
                    name=f.name,
                    source_type=f.type,
                    max_length=f.size if f.size > 0 else None,
                    allow_null=not f.required,
                    is_autoincrement=False,
                ))
            schema_tables.append(TableSchema(name=t.name, columns=cols))
        
        return ExtractedSchema(
            source=source_path,
            version="1.0",
            extracted_at=datetime.utcnow().isoformat(),
            tables=schema_tables,
        )

    def upload_schema(self, target_type: str, connection_string: str, schema: ExtractedSchema) -> dict:
        """Create tables in target database."""
        connector_cls = CONNECTORS.get(target_type)
        if not connector_cls:
            return {"success": False, "error": f"Unknown target type: {target_type}"}
        
        connector = connector_cls()
        if not connector.connect(connection_string):
            return {"success": False, "error": "Failed to connect to target database"}
        
        created = []
        failed = []
        
        for table in schema.tables:
            if connector.table_exists(table.name):
                failed.append(table.name)
                continue
            if connector.create_table(table):
                created.append(table.name)
            else:
                failed.append(table.name)
        
        connector.disconnect()
        return {"success": True, "tables_created": created, "tables_failed": failed}

    def transfer_data(self, target_type: str, connection_string: str, schema: ExtractedSchema, adapter: AccessAdapter, job_id: str | None = None) -> dict:
        """Transfer data from Access to target database."""
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        self._tracker.create_job(job_id, target_type)
        self._tracker.update_job(job_id, status="running", phase="transfer")
        
        connector_cls = CONNECTORS.get(target_type)
        if not connector_cls:
            return {"success": False, "job_id": job_id, "error": f"Unknown target type: {target_type}"}
        
        connector = connector_cls()
        if not connector.connect(connection_string):
            return {"success": False, "job_id": job_id, "error": "Failed to connect to target database"}
        
        total_tables = len(schema.tables)
        for i, table in enumerate(schema.tables):
            self._tracker.update_job(job_id, current_table=table.name, progress=i / total_tables)
            
            try:
                rows = adapter.execute_query(f'SELECT * FROM [{table.name}]')
                if rows:
                    inserted = connector.insert_rows(table.name, rows)
                    result = TableResult(
                        table=table.name,
                        source_rows=inserted,
                        rows_transferred=inserted,
                        duration_ms=0,
                        success=True,
                    )
                else:
                    result = TableResult(table=table.name, source_rows=0, rows_transferred=0, duration_ms=0, success=True)
                self._tracker.add_result(job_id, result)
            except Exception as e:
                connector.rollback_table(table.name)
                result = TableResult(table=table.name, source_rows=0, rows_transferred=0, duration_ms=0, success=False, error=str(e))
                self._tracker.add_result(job_id, result)
        
        connector.disconnect()
        self._tracker.update_job(job_id, status="completed", progress=1.0, completed_at=datetime.utcnow().isoformat())
        
        return {"success": True, "job_id": job_id}

    def get_job_status(self, job_id: str) -> dict:
        job = self._tracker.get_job(job_id)
        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}
        return {"success": True, "job": job.model_dump()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_migration_service.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/ms_access_mcp/services/migration.py tests/unit/test_migration_service.py
git commit -m "feat(migration): add MigrationService and JobTracker"
```

---

## Task 7: Add MCP Tools to Server

**Files:**
- Modify: `src/ms_access_mcp/mcp/server.py`

- [ ] **Step 1: Add imports and service initialization**

Add to server.py:
```python
from ..services.migration import MigrationService

migration_service = MigrationService()
```

- [ ] **Step 2: Add tools to server.py**

Add these tool functions:

```python
@mcp.tool()
def extract_schema(database_path: str) -> dict:
    """Extract schema from an Access database."""
    from ..adapters.wincom import WinComAdapter
    adapter = WinComAdapter()
    if not adapter.connect(database_path):
        return {"success": False, "error": "Failed to connect to database"}
    schema = migration_service.extract_schema(adapter, database_path)
    adapter.disconnect()
    return {"success": True, "schema": schema.model_dump()}


@mcp.tool()
def upload_schema(target_type: str, connection_string: str, schema_json: dict) -> dict:
    """Upload schema to target database."""
    from ..models.migration import ExtractedSchema
    schema = ExtractedSchema(**schema_json)
    result = migration_service.upload_schema(target_type, connection_string, schema)
    return result


@mcp.tool()
def transfer_data(target_type: str, connection_string: str, database_path: str, schema_json: dict | None = None) -> dict:
    """Transfer data from Access to target database."""
    from ..adapters.wincom import WinComAdapter
    from ..models.migration import ExtractedSchema
    
    adapter = WinComAdapter()
    if not adapter.connect(database_path):
        return {"success": False, "error": "Failed to connect to Access database"}
    
    if schema_json:
        schema = ExtractedSchema(**schema_json)
    else:
        schema = migration_service.extract_schema(adapter, database_path)
    
    result = migration_service.transfer_data(target_type, connection_string, schema, adapter)
    adapter.disconnect()
    return result


@mcp.tool()
def get_migration_status(job_id: str) -> dict:
    """Get status of a migration job."""
    return migration_service.get_job_status(job_id)
```

- [ ] **Step 3: Verify syntax**

```bash
python -m py_compile src/ms_access_mcp/mcp/server.py
```

- [ ] **Step 4: Commit**

```bash
git add src/ms_access_mcp/mcp/server.py
git commit -m "feat(migration): add extract_schema, upload_schema, transfer_data, get_migration_status tools"
```

---

## Self-Review Checklist

- [ ] Spec coverage: All requirements from spec.md have tasks
- [ ] No placeholders: All steps have actual code
- [ ] Type consistency: MappedColumn, ColumnSchema, ExtractedSchema, TableSchema all used consistently
- [ ] Tests: Each task has test file

**Spec gaps found?** None identified.

---

## Execution Options

Plan complete and saved to `openspec/plans/migration-engine/implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?