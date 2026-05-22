# Migration Engine Specification

## Purpose

Provides bidirectional schema extraction and data transfer between Microsoft Access databases and PostgreSQL, MySQL, MariaDB, SQLite, and SQL Server.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    MigrationService                          │
│  orchestrates: schema extract → target upload → data transfer │
└──────────┬───────────────┬──────────────┬─────────────────────┘
           │               │              │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │SchemaExtractor│ │SchemaMapper │ │DataTransfer │
    │  (Access)   │ │ (type map)  │ │ (row-level) │
    └──────────────┘ └──────┬──────┘ └──────┬──────┘
                           │               │
              ┌────────────┴───┐    ┌──────▼──────┐
              │  Target DBs    │    │  JobTracker │
              │ PostgresSQL    │    │  (SSE + CLI) │
              │ MySQL          │    └──────────────┘
              │ MariaDB        │
              │ SQLite         │
              │ SQL Server     │
              └────────────────┘
```

## Data Flow

1. **`extract_schema`** → Access adapter reads tables/columns/types/relationships → returns portable JSON schema
2. **`upload_schema`** → SchemaMapper maps Access types to target types → TargetConnector creates tables
3. **`transfer_data`** → DataTransfer reads each Access table → writes to target → rollback on failure per table → SSE progress updates

## Data Models

### MigrationJob

```python
class MigrationJob(BaseModel):
    id: str                           # UUID
    status: Literal["pending", "running", "completed", "failed"]
    phase: Literal["extract", "upload", "transfer"]
    current_table: str | None
    progress: float                   # 0.0 - 1.0
    started_at: datetime | None
    completed_at: datetime | None
    results: list[TableResult] = Field(default_factory=list)
    errors: list[ErrorInfo] = Field(default_factory=list)
```

### TableResult

```python
class TableResult(BaseModel):
    table: str
    source_rows: int
    rows_transferred: int
    duration_ms: int
    success: bool
    error: str | None
```

### ErrorInfo

```python
class ErrorInfo(BaseModel):
    table: str | None
    row_number: int | None
    message: str
    timestamp: datetime
```

### ExtractedSchema

```python
class ExtractedSchema(BaseModel):
    source: str                       # database path
    version: str = "1.0"
    extracted_at: datetime
    tables: list[TableSchema]
    relationships: list[RelationshipInfo] = Field(default_factory=list)
```

### TableSchema

```python
class TableSchema(BaseModel):
    name: str
    columns: list[ColumnSchema]
    primary_key: list[str] = Field(default_factory=list)
```

### ColumnSchema

```python
class ColumnSchema(BaseModel):
    name: str
    source_type: str                  # Access data type name
    max_length: int | None
    allow_null: bool
    is_autoincrement: bool
    default_value: str | None
```

## Type Mapping

Best-effort fallback mapping from Access types to each target database. If a type cannot be mapped cleanly, the system uses a safe default and logs a warning.

| Access Type | → PostgreSQL | → MySQL/MariaDB | → SQLite | → SQL Server |
|-------------|-------------|-----------------|----------|--------------|
| Text (≤255) | VARCHAR(n) | VARCHAR(n) | TEXT | VARCHAR(n) |
| Text (>255) | TEXT | VARCHAR(65535) | TEXT | VARCHAR(max) |
| Memo | TEXT | LONGTEXT | TEXT | VARCHAR(max) |
| Long Integer | BIGINT | BIGINT | INTEGER | INT |
| Integer | INTEGER | INT | INTEGER | SMALLINT |
| Byte | SMALLINT | TINYINT UNSIGNED | INTEGER | TINYINT |
| Boolean | BOOLEAN | TINYINT(1) | INTEGER | BIT |
| Date/Time | TIMESTAMP(0) | DATETIME | TEXT | DATETIME2(0) |
| Currency | DECIMAL(19,4) | DECIMAL(19,4) | REAL | MONEY |
| Counter/AutoNumber | BIGSERIAL | BIGINT AUTO_INCREMENT | INTEGER | INT IDENTITY |
| Single | REAL | FLOAT | REAL | REAL |
| Double | DOUBLE PRECISION | DOUBLE | REAL | FLOAT |
| Decimal | DECIMAL(18,4) | DECIMAL(18,4) | REAL | DECIMAL(18,4) |
| OLE Object | BYTEA | LONGBLOB | BLOB | VARBINARY(max) |
| GUID | UUID | CHAR(36) | TEXT | UNIQUEIDENTIFIER |
| (unknown) | TEXT | TEXT | TEXT | VARCHAR(max) |

**Note:** PostgreSQL `TIMESTAMP(0)` is used for Access Date/Time because Access stores dates without sub-second precision. Full `TIMESTAMP(n)` with higher decimals cannot be achieved in Access.

## MCP Tools

### extract_schema

**Input:** `database_path: str` (path to .accdb or .mdb file)

**Output:**
```json
{
  "success": true,
  "schema": {
    "source": "C:\\path\\to\\db.accdb",
    "version": "1.0",
    "extracted_at": "2026-05-22T12:00:00Z",
    "tables": [
      {
        "name": "Customers",
        "columns": [
          {"name": "ID", "source_type": "Long Integer", "max_length": null, "allow_null": false, "is_autoincrement": true},
          {"name": "Name", "source_type": "Text", "max_length": 255, "allow_null": true, "is_autoincrement": false}
        ],
        "primary_key": ["ID"]
      }
    ],
    "relationships": [
      {"name": "FK_Customers_Orders", "table": "Orders", "foreign_table": "Customers", "attributes": "CustomerID"}
    ]
  }
}
```

### upload_schema

**Input:** `target_type: str` (postgres|mysql|mariadb|sqlite|sqlserver), `connection_string: str`, `schema_json: ExtractedSchema`

**Output:**
```json
{
  "success": true,
  "tables_created": ["Customers", "Orders"],
  "tables_failed": []
}
```

### transfer_data

**Input:** `target_type: str`, `connection_string: str`, `schema_json: ExtractedSchema` (optional — uses last extracted)

**Output:** Returns job ID and starts migration. Client should poll `get_migration_status` or connect to SSE endpoint.

```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Migration started"
}
```

### get_migration_status

**Input:** `job_id: str`

**Output:**
```json
{
  "success": true,
  "job": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "phase": "transfer",
    "current_table": "Orders",
    "progress": 0.65,
    "results": [
      {"table": "Customers", "source_rows": 100, "rows_transferred": 100, "duration_ms": 1234, "success": true, "error": null},
      {"table": "Orders", "source_rows": 500, "rows_transferred": 234, "duration_ms": 567, "success": false, "error": "Connection timeout"}
    ],
    "errors": [
      {"table": "Orders", "row_number": 235, "message": "Connection timeout", "timestamp": "2026-05-22T12:05:00Z"}
    ]
  }
}
```

## Progress Tracking

### SSE Endpoint

`GET /migrations/{job_id}/stream` — Server-Sent Events stream pushing job updates.

### Event Format

```
event: progress
data: {"table": "Customers", "rows_transferred": 50, "total_rows": 100, "progress": 0.5}

event: table_complete
data: {"table": "Customers", "rows_transferred": 100, "success": true, "duration_ms": 1234}

event: error
data: {"table": "Orders", "row_number": 235, "message": "Connection timeout"}

event: complete
data: {"status": "completed", "total_tables": 5, "tables_transferred": 4, "tables_failed": 1}
```

## Error Handling

- **Per-table rollback:** If a table transfer fails, only that table is rolled back. Other completed tables remain committed.
- **Retry support:** Client can call `transfer_data` again with same parameters to retry failed tables.
- **Connection errors:** Transient errors (timeout, network) are logged but do not abort the job. Fatal errors (invalid credentials, schema conflict) abort immediately.
- **Type fallback:** Unknown Access types default to TEXT/VARCHAR(max) with a warning logged.

## File Structure

```
src/ms_access_mcp/
├── services/
│   ├── migration.py          # MigrationService + JobTracker
│   └── schema_mapper.py     # Type mapping logic
├── connectors/
│   ├── __init__.py
│   ├── base.py              # TargetConnector Protocol
│   ├── postgres.py          # PostgreSQL connector
│   ├── mysql.py             # MySQL/MariaDB connector
│   ├── sqlite.py            # SQLite connector
│   └── sqlserver.py         # SQL Server connector
```