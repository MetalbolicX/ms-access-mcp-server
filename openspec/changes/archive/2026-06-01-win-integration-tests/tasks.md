# Tasks: Win Integration Tests

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~895-1320 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (fixture + data/schema) → PR 2 (VBA + UI) → PR 3 (advanced + tooling) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Fixture expansion and safe destructive CRUD | PR 1 | base=main; rollback boundary = PR 1 files |
| 2 | VBA and form/report round-trip coverage | PR 2 | base=PR 1 branch; rollback boundary = PR 2 files |
| 3 | Linked tables, dispatcher, dev-copy, MCP wrappers | PR 3 | base=PR 2 branch; rollback boundary = PR 3 files |

## Phase 1 / PR 1: Fixture + Data/Schema

| Task | File | Depends | Acceptance | Lines | Rollback |
|------|------|---------|------------|-------|----------|
| 1.1 | `tests/integration/generate_fixture.py` | — | Builds `customers`, `orders`, `products`, `qrySalesSummary`, `frmMain`, `rptCustomers`, `modUtilities`, `frmWithCode`, `macTest` | 150-220 | Revert fixture generator |
| 1.2 | `tests/integration/conftest.py` | 1.1 | Adds temp-clone fixture via `shutil.copy2()` + `tempfile.mkdtemp()`; cleanup always removes clone | 45-70 | Revert shared clone fixture |
| 1.3 | `tests/integration/test_wincom_data_write.py` | 1.1-1.2 | Insert/update/delete pass on clone; master fixture stays unchanged; uses `com_integration` markers | 90-130 | Drop data-write tests |
| 1.4 | `tests/integration/test_wincom_table_query.py` | 1.1-1.2 | Create/delete table and create/set/delete query pass; `qrySalesSummary` is asserted and mutable on clone | 110-150 | Drop table/query tests |

- [x] 1.1 — `tests/integration/generate_fixture.py` expanded with customers, orders, products, qryCustomerOrders, modUtilities, frmMain, frmWithCode, rptCustomers, macTest
- [x] 1.2 — `tests/integration/conftest.py` created with `temp_db_copy` fixture
- [x] 1.3 — `tests/integration/test_wincom_data_write.py` created with TestWinComDataInsert, TestWinComDataUpdate, TestWinComDataDelete
- [x] 1.4 — `tests/integration/test_wincom_table_query.py` created with TestWinComTableCreate, TestWinComTableDelete, TestWinComTableLifecycle, TestWinComQueryCreate, TestWinComQuerySetSql, TestWinComQueryDelete, TestWinComQueryLifecycle

## Phase 2 / PR 2: VBA + UI

| Task | File | Depends | Acceptance | Lines | Rollback |
|------|------|---------|------------|-------|----------|
| 2.1 | `tests/integration/test_wincom_vba_write.py` | 1.1-1.2 | `set_vba_code`, `add_vba_procedure`, `delete_module` use compile-retry flow and preserve rollback safety | 110-150 | Drop VBA tests |
| 2.2 | `tests/integration/test_wincom_form_report.py` | 1.1-1.2 | Export-modify-import round-trip works for `frmMain`/`rptCustomers`; controls and `cmdHello_Click` are verified | 130-180 | Drop form/report tests |

- [x] 2.1 — `tests/integration/test_wincom_vba_write.py` created with TestWinComVbaSetCode, TestWinComVbaAddProcedure, TestWinComVbaDeleteModule (7 tests total)
- [x] 2.2 — `tests/integration/test_wincom_form_report.py` created with TestWinComFormExportImport, TestWinComReportExportImport, TestWinComControlProperties (6 tests total)

## Phase 3 / PR 3: Advanced + Tooling

| Task | File | Depends | Acceptance | Lines | Rollback |
|------|------|---------|------------|-------|----------|
| 3.1 | `tests/integration/test_wincom_advanced.py` | 1.1-1.2 | Linked-table source DB, schema calls, and `launch_access`/`close_access` pass on isolated DBs | 120-170 | Drop advanced adapter tests |
| 3.2 | `tests/integration/test_com_dispatcher.py` | 1.2 | Dispatcher start/call/shutdown lifecycle is covered without leaking connection state | 70-110 | Drop dispatcher tests |
| 3.3 | `tests/integration/test_wincom_dev_copy.py` | 1.1-1.2 | Dev-copy compile/import paths pass with `preserve_trusted_locations=False` | 80-120 | Drop dev-copy tests |
| 3.4 | `tests/integration/test_wincom_mcp_tools.py` | 1.3-3.3 | Reuses `_call_tool()` with real WinComAdapter for CRUD/VBA/form tools against cloned DBs | 100-150 | Drop MCP wrapper tests |

- [x] 3.1 — `tests/integration/test_wincom_advanced.py` created with TestWinComLinkedTables, TestWinComSchemaQueries, TestWinComAppLifecycle, TestWinComMultiConnection (12 tests total)
- [x] 3.2 — `tests/integration/test_com_dispatcher.py` created with TestComDispatcherLifecycle, TestComDispatcherErrorHandling (9 tests total)
- [x] 3.3 — `tests/integration/test_wincom_dev_copy.py` created with TestDevCopyCompileRetry, TestDevCopyModuleImport, TestDevCopyServiceManifest, TestDevCopyPipeline, TestDevCopyFormBackup (11 tests total)
- [x] 3.4 — `tests/integration/test_wincom_mcp_tools.py` created with TestMcpCrudTools, TestMcpVbaTools, TestMcpFormTools, TestMcpSystemTools, TestMcpDevCopyTools (14 tests total)

## Execution Order

`1.1 -> 1.2 -> (1.3, 1.4) -> (2.1, 2.2) -> (3.1, 3.2, 3.3) -> 3.4`

PR 1 establishes the writable fixture and isolation boundary. PR 2 consumes the richer fixture for VBA/UI paths. PR 3 adds cross-cutting lifecycle, linked-table, service, and MCP wrapper coverage on top of the proven base.
