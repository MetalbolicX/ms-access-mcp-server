# Tool Verification Results

**Database**: D:/JMS/Limbo/excel-and-sql-book/data/db/helper.accdb
**Date**: 2026-05-25
**Server**: http://127.0.0.1:8000

## Summary

| # | Tool | Status | Result / Error |
|---|------|--------|----------------|
| 1 | `connect_access` | PASS | connected=true |
| 2 | `is_connected` | PASS | connected=true |
| 3 | `get_tables` | PASS | 11 tables, first='calendar' |
| 4 | `get_queries` | PASS | 10 queries |
| 5 | `get_relationships` | PASS | 1 relationships |
| 6 | `get_forms` | PASS | 1 forms, first='frmDsnlessConnection' |
| 7 | `get_reports` | PASS | 0 reports, first='' |
| 8 | `get_macros` | PASS | 0 macros, first='' |
| 9 | `get_modules` | PASS | 3 modules, first='mod_funcs' |
| 10 | `get_system_tables` | PASS | 15 system tables |
| 11 | `get_vba_projects` | PASS | 1 VBA projects |
| 12 | `get_table_schema` | PASS | 11 fields |
| 13 | `get_object_metadata` | PASS | metadata retrieved |
| 14 | `form_exists` | PASS | exists=true |
| 15 | `get_form_controls` | PASS | 22 controls |
| 16 | `export_form_to_text` | PASS | 111014 chars |
| 17 | `export_report_to_text` | SKIP | no report name |
| 18 | `export_module_to_text` | PASS | 184 chars |
| 19 | `export_macro_to_text` | SKIP | no macro name |
| 20 | `export_all_versioning` | PASS | exported to C:/Users/MetalbolicX/tool-test-export |
| 21 | `get_vba_code` | PASS | 184 chars |
| 22 | `set_vba_code` | PASS | code set |
| 23 | `add_vba_procedure` | PASS | procedure added |
| 24 | `compile_vba` | PASS | compiled |
| 25 | `execute_sql_script` | FAIL | {'jsonrpc': '2.0', 'id': 2, 'result': {'content': [{'type': 'text', 'text': 'Output validation error |
| 26 | `extract_schema` | PASS | schema extracted |
| 27 | `get_er_diagram` | PASS | 11 nodes, 1 edges |
| 28 | `open_form` | PASS | form opened |
| 29 | `close_form` | PASS | form closed |
| 30 | `get_control_properties` | PASS | 90 properties |
| 31 | `set_control_property` | PASS | property set |
| 32 | `launch_access` | PASS | Access launched |
| 33 | `close_access` | PASS | Access closed |
| 34 | `disconnect_access` | PASS | disconnected |

## Summary

| Metric | Value |
|--------|-------|
| Total tools tested | 34 |
| Passed | 31 |
| Failed | 1 |
| Skipped / Expected-fail | 2 |

### VBA Lifecycle Tests


### Migration Tests


### Dev Copy Tests


### Export Tests


### VBA Lifecycle Tests

| 1 | `get_vba_projects` | PASS | 1 VBA project(s): ['helper'] |
| 2 | `get_modules` | PASS | 3 modules, first='mod_funcs' |
| 3 | `export_module_backup` | PASS | Backup of 'mod_funcs' at C:\Users\METALB~1\AppData\Local\Temp\ms_access_dev\backups\mod_funcs.bas (192 bytes) |
| 4 | `delete_module (original)` | SKIP | Access protects built-in modules; delete_module only tested on temp modules |
| 5 | `get_modules (verify preserve)` | PASS | 'mod_funcs' preserved after backup in 3 module(s) |
| 6 | `restore_module_backup (original)` | SKIP | Module was not deleted — restore not needed |
| 7 | `get_modules (verify restore)` | SKIP | Module was not deleted — nothing to restore |
| 8 | `import_module_from_text` | FAIL | Import failed: Failed to import module '__test_vba_1779731103': Failed to write code to module |
| 9 | `save_database` | PASS | Database saved successfully |
| 10 | `get_modules (verify import)` | WARN | '__test_vba_1779731103' not found in 3 module(s) |
| 11 | `delete_module (temp)` | FAIL | Could not delete '__test_vba_1779731103': ? |
| 12 | `get_modules (verify delete)` | PASS | '__test_vba_1779731103' removed, 3 module(s) remain |

### Migration Tests

| 1 | `extract_schema` | FAIL | success=True keys=['success', 'schema', 'reused_connection'] error=? |
| 2 | `generate_sql` | FAIL | success=None keys=[] error=? |
| 3 | `ddl_file_exists` | FAIL | DDL file not found at 'C:/Users/MetalbolicX/tool-test-export\test_ddl_1779731114.sql' |
| 4 | `copy_database (for compact)` | PASS | Copied DB from 'D:/JMS/Limbo/excel-and-sql-book/data/db/helper.accdb' to 'C:/Users/MetalbolicX/tool-test-export\test_cop |
| 5 | `compact_repair` | FAIL | success=False error=Source file not found: C:/Users/MetalbolicX/tool-test-export\test_copy_1779731114.accdb source=C:/Us |
| 6 | `compacted_file_exists` | FAIL | Compacted file not found at 'C:/Users/MetalbolicX/tool-test-export\test_compacted_1779731114.accdb' |
| 7 | `get_migration_status (invalid)` | PASS | Graceful error: Job nonexistent_job_id not found |
| 8 | `upload_schema` | SKIP | Requires external target DB — cannot test in isolation |
| 9 | `transfer_data` | SKIP | Requires external target DB — cannot test in isolation |

### Dev Copy Tests

| 1 | `copy_database` | PASS | Copied DB from 'D:/JMS/Limbo/excel-and-sql-book/data/db/helper.accdb' to 'C:/Users/MetalbolicX/tool-test-export\test_dev |
| 2 | `copy_database (file exists)` | FAIL | Copy file not found at 'C:/Users/MetalbolicX/tool-test-export\test_dev_copy_1779731243.accdb' |
| 3 | `get_dev_copy_status` | PASS | active=False |
| 4 | `create_dev_copy` | SKIP | Destructive: modifies file system and connection |
| 5 | `deploy_dev_copy` | SKIP | Destructive: writes to production path |
| 6 | `discard_dev_copy` | SKIP | Destructive: deletes files |

### Export Tests

| 1 | `export_table_csv` | FAIL | success=True error=? |
| 2 | `csv_file_exists` | PASS | CSV file exists (2 bytes) |
| 3 | `export_query_json` | FAIL | success=True error=? |
| 4 | `json_file_valid` | PASS | JSON file exists (2 bytes) and is valid |
