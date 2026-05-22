# Access SQL Script Executor — Specification

## Purpose

Execute raw Jet SQL DDL/DML script files directly against a connected Access database via COM automation. Enables schema changes, data modifications, and batch operations using standard Access SQL syntax (same as you'd write in Access query designer).

## Design

### MCP Tool

**Name:** `execute_sql_script`

**Input:**
```json
{
  "script_path": "C:\\path\\to\\schema.sql"
}
```

**Output (success):**
```json
{
  "success": true,
  "statements_executed": 3,
  "message": "3 statements executed successfully"
}
```

**Output (failure):**
```json
{
  "success": false,
  "statements_executed": 1,
  "error": "Syntax error in CREATE TABLE statement",
  "failing_statement": "CREATE TABLE Bad (ID COUNTER PRIMARY KEY, Name TEXT(255) NOT NULL)",
  "failing_line": 4,
  "access_error_code": 3289,
  "access_error_message": "Syntax error in CONSTRAINT clause."
}
```

### Behavior

| Scenario | Behavior |
|----------|----------|
| File not found | Return error immediately, no execution |
| File empty or only whitespace | Return `success: true, statements_executed: 0` |
| One or more statements fail | **Rollback all** — no partial commit |
| All statements succeed | Auto-commit on last statement |
| Statement returns records (SELECT) | Records are discarded, count noted in output |

### Script File Format

- Encoding: UTF-8
- Statement delimiter: `;` (semicolon)
- Blank lines between statements are allowed and ignored
- Each statement is trimmed of leading/trailing whitespace before execution

### SQL Types Supported

All Jet SQL DDL and DML:
- `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`
- `CREATE INDEX`, `DROP INDEX`
- `INSERT`, `UPDATE`, `DELETE`
- `CREATE VIEW`, `DROP VIEW`
- `ALTER TABLE ... ADD COLUMN`, `ALTER TABLE ... DROP COLUMN`
- `CREATE PROCEDURE`, `DROP PROCEDURE` (if permitted)

### DAO Execution Parameters

```python
db.Execute(sql, dbFailOnError)
```

- `dbFailOnError` — if any error occurs, transaction is rolled back and exception raised
- No `dbSeeChanges` needed (Access doesn't use it like SQL Server)
- RecordsAffected is not captured for DDL statements

### Implementation

**Adapter method:** `execute_sql_script(script_path: str) -> dict`

**Location:** `src/ms_access_mcp/adapters/wincom.py` (COM-only, not ODBC)

**File structure:**
```
src/ms_access_mcp/adapters/wincom.py        # add execute_sql_script
src/ms_access_mcp/services/schema.py       # delegate execute_sql_script to adapter
src/ms_access_mcp/mcp/server.py             # MCP tool wrapper
tests/unit/test_schema_service.py          # add test for execute_sql_script
tests/unit/test_adapters_comprehensive.py  # add tests
```

### Edge Cases

- File path with special characters — handled by Python's file read
- Very large script (thousands of statements) — DAO handles, but return early if memory issue
- Duplicate table name — Access throws error, caught and returned
- Access reserved words as column names — user must bracket them `[Reserved Word]`
- Unicode in SQL — file should be UTF-8, pywin32 handles Unicode strings

### What This Does NOT Do

- **Not** a general SQL executor for other databases (PostgreSQL, MySQL, etc.)
- **Not** ANSI-92 translation — raw Jet SQL passed as-is to Access
- **Not** a migration tool — just executes what Access itself would execute

## Test Scenarios

1. **Success:** Two CREATE TABLE statements, both succeed → `statements_executed: 2`
2. **File not found:** Invalid path → `success: false, error: File not found`
3. **Syntax error:** Bad SQL → `success: false, failing_statement: "CREATE TABLE Bad..."`
4. **Empty file:** → `success: true, statements_executed: 0`
5. **Multiple statements with failure:** → rollback, return error on first failure