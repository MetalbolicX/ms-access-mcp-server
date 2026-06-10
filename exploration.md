# Full Codebase Exploration — MS Access MCP Server

## 1. MCP Tool Inventory — Complete Catalog

**126 registered tools** across 14 modules:

| Module | Tools | Categories |
|--------|-------|------------|
| `connection.py` | 6 | connect, disconnect, list, set/get active, is_connected — lifecycle |
| `schema.py` | 6 | get_tables, get_indexes, get_table_schema, get_relationships, generate_sql, get_er_diagram — read-only |
| `crud.py` | 13 | get_queries, create/delete/set_query_sql, create/delete_table, create/drop_index, query/insert/update/delete_data, alter_table — read-write + destructive |
| `export.py` | 1 | export_data — read-only (file output) |
| `com.py` | 26 | launch/close_access, get_forms/reports/macros/modules, open/close_form, form_exists, form/get/set properties, controls (CRUD), sections, events — mostly read-only + some destructive |
| `reports.py` | 16 | report_exists, create/rename_report, properties (get/set), controls (get/set CRUD), sections — read-only + destructive |
| `vba.py` | 11 | get_vba_projects, get/set_vba_code, add_vba_procedure, compile_vba, save_database, delete_module, list/get/replace_procedure, save_query — read-write + destructive |
| `system.py` | 2 | get_system_tables, get_object_metadata — read-only |
| `persistence.py` | 15 | export/import form/report/module/macro/query text, delete_form/report, bulk versioning, schema DDL, execute_sql_script — mixed |
| `recovery.py` | 2 | recover_access, diagnose_environment — destructive + read-only |
| `migration.py` | 4 | extract_schema, upload_schema, transfer_data, get_migration_status — read-write |
| `linked_tables.py` | 7 | get/create/refresh/unlink/upsert_linked_table, store/clear_credentials — read-write + destructive |
| `dev_copy.py` | 15 | compact_repair, copy_database, module/form/report backup/restore (3 each), create/deploy/discard dev_copy, get_dev_copy_status — destructive |
| `analysis.py` | 1 | analyze_query — read-only |

---

## 2. Access Object Coverage

| Access Object | List | Read | Create | Update | Delete | Other | Coverage |
|:---|---:|---:|---:|---:|---:|---:|:---:|
| **Tables** | ✅ `get_tables` | ✅ `get_table_schema` | ✅ `create_table` | ✅ `alter_table` | ✅ `delete_table` | indexes, relationships, linked tables | **FULL** |
| **Queries** | ✅ `get_queries` | ✅ (SQL) | ✅ `create_query` | ✅ `set_query_sql` `save_query` | ✅ `delete_query` | export/import text | **FULL** |
| **Forms** | ✅ `get_forms` | ✅ properties, controls, sections, events | ✅ `create_form` | ✅ `set_form_property/ies`, `rename_form` | ✅ `delete_form` | open/close, control CRUD, event procedures, export/import text | **FULL** |
| **Reports** | ✅ `get_reports` | ✅ properties, controls, sections | ✅ `create_report` | ✅ `set_report_property/ies`, `rename_report` | ✅ `delete_report` | control CRUD, sections, export/import text | **FULL** |
| **Macros** | ✅ `get_macros` | ⚠️ `export_macro_to_text` (metadata only) | ❌ | ❌ | ❌ | — | **PARTIAL** |
| **Modules** | ✅ `get_modules` | ✅ `get_vba_code`, `export_module_to_text` | ✅ `add_vba_procedure` | ✅ `set_vba_code`, `vba_replace_procedure` | ✅ `delete_module` | compile, save, list/get/replace procedures | **FULL** |

### MACROS GAP ⚠️
Macros are the most under-served Access object. The toolset can **list them** and **export metadata** — but there are zero tools for:
- Creating a macro
- Editing a macro
- Deleting a macro
- Opening/running a macro
- Exporting macro actions as structured code (Access macros **do** have a structured action model accessible via COM)

---

## 3. Asymmetries (Forms vs Reports vs Others)

### Fixed: Forms ↔ Reports symmetry now complete
As of `reports.py`, forms and reports have identical CRUD: properties, controls, sections, rename, delete, text export/import.

### Remaining asymmetries:

| Feature | Forms | Reports | Macros | Modules |
|---------|:-----:|:-------:|:------:|:-------:|
| Existence check | ✅ `form_exists` | ✅ `report_exists` | ❌ | ❌ |
| Open in UI | ✅ `open_form` | ❌ | ❌ | ❌ |
| Close from UI | ✅ `close_form` | ❌ | ❌ | ❌ |
| Open in design view | ✅ (implied by property tools) | ✅ (implied) | ❌ | ❌ |
| Control events | ✅ `get/set_control_event_procedures` | ❌ | N/A | N/A |
| Rename | ✅ | ✅ | ❌ | ❌ |
| Create | ✅ | ✅ | ❌ | ❌ |
| Delete | ✅ `delete_form` | ✅ `delete_report` | ❌ | ✅ `delete_module` |

### Macro asymmetry is the most impactful — it's the only Access object without **any** mutation tools.

---

## 4. Adapter Layer Gaps

### 4.1 IUiAdapter Interface — WinComAdapter doesn't implement `launch_access`/`close_access`

WinComAdapter (`class WinComAdapter(IDataAdapter, ISchemaAdapter, IUiAdapter)`) is **missing two IUiAdapter methods**:
- `launch_access(self, visible: bool = False) -> None`
- `close_access(self) -> None`

These exist only in:
- `ComOnlyAdapterMixin` (which WinComAdapter does NOT inherit)
- `COMAutomationService` (the service layer, not the adapter)

This is an **ISP violation** — the class claims to implement IUiAdapter but doesn't satisfy the protocol. pyright should flag this (check `pyright` output).

### 4.2 COMAutomationService is an incomplete facade

Out of **67 IUiAdapter methods**, COMAutomationService wraps only:
- launch/close_access
- open/close_form
- get/set form properties, control properties
- form section CRUD
- compile_vba
- get/set_control_event_procedures
- create/rename form, add/remove control
- **All report operations** (create, rename, properties, controls, sections)

**Missing from COMAutomationService** (30+ methods): get_forms, get_reports, get_macros, get_modules, form_exists, report_exists, delete_form, delete_report, get_vba_code, set_vba_code, add_vba_procedure, save_database, delete_module, vba_list/get/replace_procedure, all text export/import methods, compact_repair, copy_database, etc.

The tools use **two inconsistent paths**: sometimes through `_com()` (COMAutomationService), sometimes through `adapter.*` directly. This is confusing and makes behavior harder to predict.

### 4.3 OdbcAdapter missing `execute_sql_script`

`execute_sql_script` is defined only in the ComOnlyAdapterMixin (raises NotImplementedError). The ISchemaAdapter interface defines it, but the ODBC path can't execute SQL scripts — it would need a pyodbc-based implementation.

### 4.4 Data adapter `export_data` — format support inconsistency

The `ODBC` path for export_data may not support Excel format the same way COM does. The strategy pattern handles fallbacks but there's no test matrix verifying all 3 formats (csv/json/excel) work on both adapter paths.

---

## 5. Test Coverage Gaps

### Modules with NO unit tests:

| Module | Test File | Risk |
|--------|-----------|------|
| `persistence.py` | **NONE** | 15 tools untested. Bulk versioning, form/report/module/macro/query text export/import — no tests |
| `recovery.py` | **NONE** | 2 tools untested. `recover_access` (destructive — kills processes) and `diagnose_environment` |
| `ai_tools.py` | Partial (`test_mcp_llm_tools.py` exists) | Tests exist for LLM adapter and config, but not for the tool registration (which doesn't use @mcp.tool()) |

### Categories with thin coverage:

| Category | Coverage Assessment |
|----------|-------------------|
| **Destructive tools** (delete_, confirm=) | Tested per-module (com.py, crud.py have tests) but `guard_destructive` itself has `test_mcp_helpers.py` |
| **Versioning/persistence** | **ZERO coverage** — all 15 tools |
| **Recovery/diagnostics** | **ZERO coverage** — both tools |
| **COM Automation Service** | `test_com_automation_service.py` exists |
| **WinComAdapter** | `test_wincom_adapter.py` exists, plus integration tests |
| **Reports** | `test_reports.py` (720 lines) |
| **Dev Copy** | `test_dev_copy.py` and `test_dev_copy_service.py` |
| **Linked Tables** | `test_linked_tables.py` and `test_linked_tables_mcp.py` |

---

## 6. LLM Tools — Implementation Status

The AI tools in `ai_tools.py` (`disambiguate_intent`, `generate_structured_plan`) are **fully implemented** (not stubs):
- Guarded by `LlmConfig.enabled` — return `{"disabled": True}` when off
- Delegate to `LlmService` → `LlmAdapter` → `ProviderFacade` when enabled
- No provider SDK imports in core

**BUT: These functions are NOT registered as MCP tools with `@mcp.tool()`**. They're exported via `__all__` but never registered in `server.py`. A client can't call them through the MCP protocol. They're only callable as Python functions, which defeats the purpose of having them in the MCP server.

---

## 7. Error Handling Gaps

Most tools consistently return `{"success": False, "error": str(e)}` — good.

**Inconsistencies found:**

| Tool | Response Pattern | Issue |
|------|-----------------|-------|
| `compile_vba` | Returns raw adapter result (dict) | No wrapping — assumes adapter returns consistent shape |
| `save_database` | Returns raw adapter result (dict) | Same issue |
| `get_migration_status` | Returns raw service result | No error dict wrapping |
| `compare_versioning` | Wraps in try/except but returns dict | OK but inconsistent with others |
| `export_all_versioning` | Wraps in try/except | OK |
| `launch_access` | Returns `{"success": result, "access_running": ...}` | Different format — no `"error"` key on failure |

**The guard_destructive helper** is used inconsistently:
- `delete_data`, `delete_table`, `delete_query`, `delete_module`: uses `guard_destructive`
- `delete_form`, `delete_report`: uses `guard_destructive`
- `set_vba_code`: uses `guard_destructive` with only `confirm`, no `dry_run` (has `confirm: bool` but the param signature doesn't match the tool's stated params)
- `set_control_event_procedure`: uses `guard_destructive`
- `alter_table`: checks `confirm` manually for `drop_column` only — doesn't use `guard_destructive`
- Some `confirm` params default to `False` (good), but `recover_access` defaults `confirm=True` (dangerous pattern)

---

## 8. Phase 1 SDD Scope vs Current Code

### Files tagged "Phase 1 SDD" (9 files):
- `mcp/connection.py`, `mcp/crud.py`, `mcp/schema.py`, `mcp/com.py`, `mcp/vba.py`
- `mcp/linked_tables.py`, `mcp/dev_copy.py`, `mcp/migration.py`
- `services/connection.py`

### Files NOT tagged:
- `mcp/reports.py` (labeled "PR1 Core/CRUD/Properties" — different origin)
- `mcp/persistence.py` (no phase label — post-Phase 1 addition)
- `mcp/system.py` (no phase label)
- `mcp/recovery.py` (no phase label)
- `mcp/analysis.py` (no phase label)
- `mcp/ai_tools.py` (no phase label — clearly later)

### What Phase 1 originally excluded:
- **Reports** (added later as a follow-up PR)
- **Versioning/persistence** (bulk export/import, compare)
- **Recovery & diagnostics**
- **Query analysis**
- **LLM integration**
- **Report manipulation** (added after Phase 1 as a known gap fix)

The current code has **grown beyond Phase 1** in reports, persistence, analysis, and LLM. The "Phase 1" label on 9 files is now misleading — those files have also grown beyond their original scope.

---

## 9. README vs Actual Code

### Claims that don't match code:

| README Claim | Reality |
|-------------|---------|
| `list_migration_targets` tool | **Does not exist.** No such tool anywhere |
| `upload_sql_schema` tool | **Does not exist.** Actual tool is `upload_schema` |
| `migrate_to` tool | **Does not exist.** Actual tool is `transfer_data` |

### Features missing from README:
- All 16 **report manipulation tools** (report_exists, create_report, rename_report, properties, controls, sections)
- All 7 **linked table tools**
- All 15 **dev copy tools**
- `analyze_query`
- `recover_access`, `diagnose_environment`
- `execute_sql_script`
- `export_schema_ddl`
- `get_migration_status`
- All CRUD tools: `create_table`, `delete_table`, `alter_table`, `create/drop_index`, `insert_data`, `update_data`, `delete_data`
- Form manipulation tools: `create_form`, `rename_form`, form/control/section property tools, event procedures
- All VBA tools beyond basic list: `add_vba_procedure`, `delete_module`, procedure-level tools
- Multi-connection tools: `list_connections`, `set_active_connection`, `get_active_connection`

### Summary: README lists ~20 tools; actual code has **126 tools**. The README is ~85% incomplete.

---

## 10. Architecture / SOLID Gaps

### 🔴 Critical
1. **ISP Violation — WinComAdapter**: Declares `IUiAdapter` but doesn't implement `launch_access`/`close_access`. Would fail pyright in strict mode.
2. **LLM tools not registered**: `ai_tools.py` functions are not `@mcp.tool()` decorated — invisible to MCP clients.

### 🟡 Significant
3. **Massive code duplication**: 14 MCP tool modules each define their own `_pool()`, `_get_adapter()`, `_check_connected()` helpers. The `_helpers.py` file exists but only `analysis.py` uses it — all others re-implement. ~150 redundant lines across the codebase.
4. **COMAutomationService is an incomplete pass-through**: ~30 of 67 IUiAdapter methods are missing. Some tools call it, some bypass it — inconsistent architecture.
5. **Report section properties — identical code to form section properties**: The set_property loop opens/closes the object for **each** property (O(n) Access opens). This is both code duplication and performance anti-pattern.
6. **UiOperations is too large**: Despite extraction from WinComAdapter, it still handles forms, reports, controls, sections, events, versioning — 1000+ lines. Could be split further.

### 🔵 Minor
7. **`alter_table` doesn't use `guard_destructive`**: Manually checks confirm for `drop_column` only. The other operations (`rename_table`, `rename_column`) don't require confirm at all — inconsistent safety model.
8. **`recover_access` defaults `confirm=True`**: This kills processes. Should default `False` like every other destructive tool.
9. **Mixed naming**: `upload_schema` vs the README-claimed `upload_sql_schema`. `transfer_data` vs `migrate_to`.

---

## Top 5 Most Impactful Gaps to Fix

### 1. 🏆 Macros — Mutation Tools (HIGH impact, MEDIUM effort)
- **Why**: Macros are the only Access object with zero mutation capability. Users can list them but can't do anything.
- **What**: Add `create_macro`, `delete_macro`, `get_macro_actions`, `set_macro_action` tools.
- **Effort**: Medium — requires COM automation via Access' Macro object model (accessible through CurrentDb.AllMacros + DoCmd).

### 2. 📄 README Update (HIGH impact, LOW effort)
- **Why**: 85% of tools are undocumented. New users have no idea what's available.
- **What**: Audit all 126 tools and update the README tool table. Rename/add missing functions.
- **Effort**: Low — 1 file change.

### 3. 🔌 LLM Tools Registration (MEDIUM impact, LOW effort)
- **Why**: The AI tools exist but are invisible to MCP clients. The investment in LlmService, ProviderFacade, and guards is wasted without registration.
- **What**: Either decorate with `@mcp.tool()` or register them in `server.py`'s import section.
- **Effort**: Low — ~10 lines of code.

### 4. 🧪 Persistence & Recovery Tests (MEDIUM impact, MEDIUM effort)
- **Why**: 17 tools (persistence + recovery) have zero unit test coverage. These include destructive operations like `delete_form`, `delete_report`, `import_*`, and `recover_access`.
- **What**: Add `test_persistence.py` and `test_recovery.py` with mock adapters.
- **Effort**: Medium — repetitive but many edge cases.

### 5. 🧹 Architecture Cleanup — `launch_access`/`close_access` + Duplicate Helpers (MEDIUM impact, LOW effort)
- **Why**: ISP violation, dead code paths, and 150 lines of identical helper functions.
- **What**: (a) Add wrapper methods in WinComAdapter, (b) consolidate `_pool()`/`_get_adapter()`/`_check_connected()` into `_helpers.py` and delete from 12 other modules.
- **Effort**: Low-medium — mechanical but touches many files.

---

## Quick Wins (1-2 File Changes)

| Change | Files | Effort |
|--------|-------|--------|
| Register LLM tools via `@mcp.tool()` | `ai_tools.py` + `server.py` | ~10 min |
| Fix README tool table | `README.md` | ~30 min |
| Add `launch_access`/`close_access` stubs to WinComAdapter | `wincom.py` | ~5 min |
| Fix `recover_access` default confirm=False | `recovery.py` | ~2 min |

---

## Architectural Debt to Watch

1. **UiOperations + VbaOperations as WinComAdapter's delegation targets**: This pattern is good (SRP) but there's no abstract base — they're duck-typed. If the internal API between them changes, there's no compiler guard.

2. **Module-level `_pool()`/`_com()` lazy accessors**: These rely on `get_container()` being called at runtime, which means import order doesn't matter. But it also means errors manifest at runtime, not import time — harder to debug.

3. **The `_helpers.py` file** is a step in the right direction but only `analysis.py` actually uses it. The others define their own versions. This should be a single consolidated source.

4. **VersioningIo construction in WinComAdapter** passes private methods (`_save_object_to_text`, `_load_object_from_text`) as callbacks. This creates a tight coupling between UiOperations internals and VersioningIo.

5. **Test reset pattern** — tests call `_reset_container()` which is fragile. Some tests patch module-level functions, others patch container methods — two competing patterns. This will eventually cause flaky tests.
