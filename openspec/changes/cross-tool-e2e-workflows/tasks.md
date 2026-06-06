# Tasks: cross-tool-e2e-workflows

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 220-320 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | single PR |
| Delivery strategy | single-pr |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Add E2E fixtures, helpers, workflows, and config update | PR 1 | Tests and verification stay together |

## Phase 1: Infrastructure

- [ ] 1.1 Create `tests/e2e/conftest.py` with `e2e_pool`, `e2e_two_adapters`, `temp_export_dir`, and `e2e_http_client`; delegate to integration fixtures, reset HTTP globals, and use `TemporaryDirectory()`.
- [ ] 1.2 Create `tests/e2e/helpers.py`; re-export `call_mcp_tool` from `tests/integration/helpers.py` and add `assert_file_exists()` plus `assert_workflow_result()`.

## Phase 2: Pool workflows

- [ ] 2.1 Add `TestCrudCycle` to `tests/e2e/test_workflows_pool.py` for spec scenario “Complete CRUD cycle via pool”; use `__e2e_test_products`, assert `success=True`, 2 query rows, and 3 schema columns.
- [ ] 2.2 Add `TestDataExport` to `tests/e2e/test_workflows_pool.py` for CSV/JSON export scenarios; export from `__e2e_test_export*`, assert CSV has 4 lines and JSON parses to expected records.
- [ ] 2.3 Add `TestMultiTableWorkflow` to `tests/e2e/test_workflows_pool.py`; create `__e2e_test_a` and `__e2e_test_b`, verify `get_tables`, delete `__e2e_test_a`, and re-check remaining tables.
- [ ] 2.4 Add `TestMultiConnectionIsolation` to `tests/e2e/test_workflows_pool.py` with `e2e_two_adapters`; verify `prod` table `__e2e_test_secret` is hidden from `dev` and `dev` still works after `disconnect("prod")`.
- [ ] 2.5 Add `TestSchemaErDiagram` to `tests/e2e/test_workflows_pool.py`; verify `get_table_schema("__meta")`, `get_relationships`, and `get_er_diagram` return the required structures.

## Phase 3: HTTP workflows

- [ ] 3.1 Add `TestHttpWorkflow` to `tests/e2e/test_workflows_http.py`; initialize session, call `tools/list`, then `tools/call` for `create_table`, `insert_data`, and `query_data`, asserting `jsonrpc="2.0"` and returned data.

## Phase 4: Config and verification

- [ ] 4.1 Update `openspec/config.yaml` to set `testing.layers.e2e` to `{ available: true, tool: pytest }`.
- [ ] 4.2 Run `pytest tests/e2e/` and `pytest tests/`; confirm all new workflows pass, no regressions appear, and each test cleans up via explicit `try/finally` with `__e2e_test_` object names.
