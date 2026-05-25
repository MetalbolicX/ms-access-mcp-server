# Integration Test Coverage Specification

## Purpose

HTTP end-to-end tests for 37 untested MCP tools. JSON-RPC via `curl` against real Access DB with session + auth, matching `test-all-tools.py`.

## Constraints (ALL)

- Server check MUST abort after 5s
- MUST init session, pass `mcp-session-id`
- DB objects MUST use `__test_` prefix
- Cleanup in `finally`, MUST NOT mask results
- SHALL NOT modify real objects — temps or copies only
- Record PASS/FAIL/SKIP to shared markdown

## Requirements

### R1: Data CRUD — `test-crud-data.py` (`query_data`, `insert_data`, `update_data`, `delete_data`)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| CRUD cycle | `__test_crud_` table with 3 cols | insert → update → query → delete | all `success: true` |
| Param query | temp table with data | `query_data` with WHERE params | results match filter |
| Cleanup | temp table created | `finally` deletes table | table gone from `get_tables` |

### R2: Query CRUD — `test-crud-query.py` (`create_query`, `set_query_sql`, `delete_query`)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| Create | none | `create_query("__test_q_...", "SELECT")` | `success: true`, query in `get_queries` |
| Update SQL | `__test_q_` query exists | `set_query_sql` with new SQL | `success: true` |
| Delete | same query | `delete_query`, then check `get_queries` | query absent |

### R3: Table CRUD — `test-crud-table.py` (`create_table`, `delete_table`)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| Create | none | `create_table("__test_table_...", 3 cols)` | `success: true`, in `get_tables` |
| Verify schema | temp table exists | `get_table_schema` | columns match definition |
| Delete | temp table exists | `delete_table` | removed from `get_tables` |

### R4: Export — `test-export.py` (`export_table_csv`, `export_query_json`)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| CSV export | existing user table | `export_table_csv` to temp path | `success: true`, file exists |
| JSON export | existing query | `export_query_json` to temp path | `success: true`, file is valid JSON |
| Cleanup | temp files created | teardown | export dir removed |

### R5: VBA Lifecycle — `test-vba-lifecycle.py` (module backup/restore, `save_database`, `delete_module`)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| Backup/delete/restore | existing module | export → delete → restore | module in `get_modules` |
| Save | after restore | `save_database` | `success: true` |

`delete_module` only tested via backup/restore — module always restored.

### R6: Form/Report Lifecycle — `test-form-report-lifecycle.py` (form/report import/delete/backup/restore)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| Form backup/delete/restore | existing form | export → `delete_form` → restore | `form_exists` true |
| Report import from text | `export_report_to_text` data | `import_report_from_text("__test_report_...", data)` | `success: true` |
| Report cleanup | `__test_report_` exists | `delete_report` | removed |

### R7: Migration — `test-migration.py` (`generate_sql`, `upload_schema`, `transfer_data`, `get_migration_status`, `compact_repair`)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| generate_sql | connected | `generate_sql` to temp `.sql` | file exists with CREATE TABLE |
| compact_repair | helper.accdb source | `compact(action, src, dst)` | file copy exists |
| upload_schema | no external DB | `upload_schema(...)` | SKIP (limitation noted) |
| transfer_data | no external DB | `transfer_data(...)` | SKIP (limitation noted) |
| get_migration_status | non-existent job_id | `get_migration_status("nonexistent")` | graceful error, no crash |

### R8: Linked Tables — `test-linked-tables.py` (`get_linked_tables`, `create_linked_table`, `refresh_linked_table`, `unlink_table`)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| List linked | connected | `get_linked_tables` | `success: true` (0+ tables) |
| Destructive ops | no external ODBC DSN | create/refresh/unlink | SKIP (limitation noted) |

### R9: Dev Copy — `test-dev-copy.py` (`copy_database`, `get_dev_copy_status`, `create_dev_copy`, `deploy_dev_copy`, `discard_dev_copy`)

| Scenario | GIVEN | Action | THEN |
|----------|-------|--------|------|
| copy_database | helper.accdb | `copy_database(src, dest)` | dest file exists |
| get_dev_copy_status | connected | `get_dev_copy_status` | graceful return (`active: false`) |
| Destructive ops | none allowed | create/deploy/discard | SKIP (limitation noted) |
