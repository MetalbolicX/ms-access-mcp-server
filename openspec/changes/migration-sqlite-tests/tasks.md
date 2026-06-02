# Tasks: Migration SQLite Tests

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~320-400 across 2 PRs |
| 400-line budget risk | Low |
| Chained PRs recommended | Yes |
| Suggested split | PR #1 fixture + extract/upload tests; PR #2 transfer/status/error tests |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Fixture + extract/upload coverage | PR #1 | Base main; ship tests/docs together |
| 2 | Transfer/status/error coverage | PR #2 | Base main after PR #1 merges |

## Phase 1: Fixture Foundation (PR #1)

- [ ] 1.1 `tests/integration/generate_fixture.py` add 3+ seed rows each for `customers`, `orders`, and `products`; verify regenerated fixture returns >=3 rows per table.
- [ ] 1.2 `tests/integration/generate_fixture.py` add `type_test(id, name, active, created, price, notes, guid, rating, level)` and mixed NULL/non-NULL rows; verify table exists and sample values are queryable.

## Phase 2: Extract + Upload Tests (PR #1)

- [ ] 2.1 Create `tests/integration/test_migration.py` scaffold with `TEST_DB_PATH`, module skips/`@pytest.mark.com_integration`, fresh `WinComAdapter` + fresh `MigrationService` in `setup_method`, disconnect in `teardown_method`; verify it matches `tests/integration/test_real_adapter.py` style.
- [ ] 2.2 Add RED `extract_schema` happy-path test using `service.extract_schema(adapter, TEST_DB_PATH)`; verify `customers`, `orders`, `products`, `type_test`, and typed columns appear.
- [ ] 2.3 Add `extract_schema` idempotency test; verify two extractions return the same table/column structure.
- [ ] 2.4 Add RED `upload_schema` table-creation test using `service.upload_schema("sqlite", str(tmp_path / "target.db"), schema)`; verify SQLite tables via raw `sqlite3.connect()`.
- [ ] 2.5 Add `upload_schema` mapping test; verify PRAGMA types for YESNO, DATETIME, CURRENCY, MEMO, GUID, DOUBLE, and BYTE map as expected.

## Phase 3: Transfer + Status + Errors (PR #2)

- [x] 3.1 Add full-pipeline helper in `tests/integration/test_migration.py` that extracts, uploads, and calls `service.transfer_data("sqlite", sqlite_path, schema, adapter)`; use `tmp_path` and `monkeypatch` only where isolation is needed.
- [x] 3.2 Add `transfer_data` row-count test; verify SQLite counts match Access counts for `customers`, `orders`, `products`, and `type_test`.
- [x] 3.3 Add `transfer_data` value test; verify representative rows preserve NULLs, booleans, currency, datetime text, GUIDs, and numeric values.
- [x] 3.4 Add status test using `service.get_job_status(job_id)`; verify completed job, progress `1.0`, and per-table results.
- [x] 3.5 Add disconnected-adapter error test for `extract_schema`; verify current failure behavior explicitly.
- [x] 3.6 Add invalid-path tests for `upload_schema` and `transfer_data`; verify `success=False` and connector error handling.

## Phase 4: Refactor / Verification

- [ ] 4.1 Refactor local helpers in `tests/integration/test_migration.py` for SQLite assertions and schema setup; verify targeted `pytest` integration selection stays green with no shared service state.
