# Tool Verification Results

**Database**: D:/JMS/Limbo/excel-and-sql-book/data/db/helper.accdb
**Date**: 2026-05-23
**Server**: http://172.19.208.1:8000

## Summary

| # | Tool | Status | Result / Error |
|---|------|--------|----------------|
| 1 | `connect_access` | PASS | connected=true |
| 2 | `is_connected` | PASS | connected=true |
| 3 | `get_tables` | PASS | 0 tables, first='' |
| 4 | `get_queries` | PASS | 0 queries |
| 5 | `get_relationships` | PASS | 0 relationships |
| 6 | `get_forms` | PASS | 1 forms, first='frmDsnlessConnection' |
| 7 | `get_reports` | PASS | 0 reports, first='' |
| 8 | `get_macros` | PASS | 0 macros, first='' |
| 9 | `get_modules` | PASS | 3 modules, first='mod_funcs' |
| 10 | `get_system_tables` | PASS | 0 system tables |
| 11 | `get_vba_projects` | PASS | 1 VBA projects |
| 12 | `get_table_schema` | SKIP | no table name |
| 13 | `get_object_metadata` | SKIP | no object name |
| 14 | `form_exists` | PASS | exists=true |
| 15 | `get_form_controls` | PASS | 22 controls |
| 16 | `export_form_to_text` | PASS | 107942 chars |
| 17 | `export_report_to_text` | SKIP | no report name |
| 18 | `export_module_to_text` | PASS | 110 chars |
| 19 | `export_macro_to_text` | SKIP | no macro name |
| 20 | `export_all_versioning` | PASS | exported to C:/Users/MetalbolicX/tool-test-export |
| 21 | `get_vba_code` | PASS | 110 chars |
| 22 | `set_vba_code` | PASS | code set |
| 23 | `add_vba_procedure` | PASS | procedure added |
| 24 | `compile_vba` | WARN | Not supported (expected) |
| 25 | `execute_sql_script` | WARN | Idempotency conflict (expected on re-run) |
| 26 | `extract_schema` | PASS | schema extracted |
| 27 | `get_er_diagram` | PASS | 0 nodes, 0 edges |
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
| Passed | 28 |
| Failed | 0 |
| Skipped / Expected-fail | 4 |
