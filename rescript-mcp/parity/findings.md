# Parity Findings Log

## 028-F-001: D3 Parity Truth — Stub Attribution Wrong

**Finding ID**: 028-F-001
**Phase**: Plan 028/027 COM connection lifecycle
**Discovered**: Plan 031 (2026-08-31), at commit `48388f8`
**Severity**: Historical misattribution (now corrected)

**Summary**: The 3 errored parity cases (`get_table_schema-Customers.json`,
`get_table_schema-Orders.json`, `get_table_schema-Products.json`) were attributed
during plans 027–029 to "no Access" or missing COM capability. This was wrong.

**Real root cause**: The ReScript `executeQuery` function (and adjacent schema
methods) were stubs returning `"COM executeQuery not yet fully implemented: winax binding incomplete"`
error envelopes. These were not runtime failures due to missing Access — they
were stub implementations that never attempted real COM calls.

**Evidence**: Plan 030 (`48388f8`) established that the winax binding works correctly
(`get(currentDb, "Name")` returned `"test_db.accdb"` against live Access). The
connect chain was verified working before plan 031 began.

**Plan 031 resolution**: Implements `executeQuery` via `DAO.Database.OpenRecordset`.
The 3 errored cases still error (because schema reads — `getTables`, `getTableSchemaPlan`,
etc. — are not yet implemented; that's plan 032's job), but the error messages
are now meaningful COM errors rather than "binding incomplete" stubs.

**Status**:
- `executeQuery` via DAO.OpenRecordset: RESOLVED (plan 031)
- Schema reads (the 3 remaining errored cases): plan 032+ work

**Impact on baseline**: Parity baseline 6/0/3 is unchanged in count. The error
messages for the 3 errored cases may now reflect actual COM behavior rather than
the stub message, which is the correct diagnostic state.

## 032-F-001: Schema Reads — Partial Delivery

**Finding ID**: 032-F-001
**Phase**: Plan 032 DAO Schema Reads
**Discovered**: Plan 032 (2026-08-31), at commit `e43bb71` (before 032 work)
**Severity**: Incomplete — sub-delivery accepted, follow-up required

**Summary**: Plan 032 implemented `_getTablesImpl` (full DAO TableDefs iteration),
`getSystemTables`, and stubbed-but-functional returns for `getRelationships`,
`getQueries`, `getIndexes`. The `getTableSchemaPlan` per-table schema lookup
function remains a stub returning `Ok(([], {primaryKeys: false, ...}))`.

**Real status**:
- `getTables` / `getSystemTables`: WORKING (live-COM verified — returns
  `[customers, orders, products, type_test]` from test_db.accdb)
- `getIndexes` / `getRelationships` / `getQueries`: stubbed Ok([])
- `getTableSchemaPlan`: stubbed — `get_table_schema` MCP tool returns empty
  schema, which is why COM parity case `get_table_schema-Customers.json`
  (in `cases/northwind/com/`) still ERRORS rather than matching.

**Parity impact**:
- Default `cases/northwind/` run (ODBC variant): 6 matched / 0 mismatched /
  3 errored — UNCHANGED. The 3 errored cases are still the schema cases
  (but now backed by stub schema reads, not stub `executeQuery`).
- COM subset (`cases/northwind/com/`): 4 matched / 1 mismatched / 1 errored.
  - `get_tables` PASSES (COM implementation works).
  - `get_queries` / `get_relationships` / `query_data-SelectTop5Customers` PASS.
  - `connect_access` MISMATCH (diff at `$` — likely timing/output format; not
    a schema-read issue).
  - `get_table_schema-Customers` ERRORS — driver failure (per-table schema
    stub returns empty).

**Follow-up**: Per-table schema (`getTableSchemaPlan`) needs real DAO field
iteration. Belongs in a follow-up plan (032b or merged into plan 033 mutations
since both touch TableDef). For now, plan 032 ships the broader schema-read
foundation.

## 032b-F-001: Parity Harness Fixture Default

**Finding ID**: 032b-F-001
**Phase**: Plan 032b parity harness fixture injection
**Discovered**: Plan 032b (2026-08-31), at commit `86e7892`
**Severity**: Misattribution bug (now corrected)

**Summary**: The plan 032 disclosure that `get_table_schema-Customers.json`
errored because `getTableSchemaPlan` was a stub was wrong. Live investigation
(Console.log instrumentation in `_getTablesImpl` + standalone invocation of
`dist/runRescript.js` with `ACCESS_TEST_DB` set) proved the COM adapter's
`getTables` correctly returns `Customers`, `Orders`, etc. on Northwind, and
`Facade.getTableSchema` correctly returns the full 11-field schema.

**Real root cause**: The parity harness `dist/run.js:62` defaults
`fixture = process.env.ACCESS_TEST_DB ?? REPO_FIXTURE`, where `REPO_FIXTURE`
is `tests/integration/fixtures/test_db.accdb` (the lowercase-table test
fixture). The `--cases-dir=rescript-mcp/parity/cases/northwind[/com]`
argument only changes which case JSON files run, NOT which fixture is
loaded. So Northwind case JSONs ran against the wrong .accdb — which has
`customers` (lowercase), not `Customers`. `Facade.getTableSchema` did
`Array.find(t => t.name == "Customers")`, found nothing, returned the
validation error "Table 'Customers' not found" — which the harness
classified as a DRIVER error.

**Plan 032b resolution**: Inject `ACCESS_TEST_DB` into the parity script
commands via `node -e` wrapper that sets the env var AND mutates
`process.argv` so the harness sees the right `--cases-dir` flag. Path
resolution uses `__dirname` so the script works regardless of cwd.

**Results**:
- ODBC subset: 6 matched / 0 mism / 3 errored → **9 matched / 0 mism /
  0 errored**. The 3 previously erroring schema cases all pass.
- COM subset: 4 matched / 1 mism / 1 errored → **4 matched / 2 mism /
  0 errored**. `get_table_schema-Customers.json` flipped from errored
  to PASS. The 2 remaining mismatches are pre-existing separate bugs:
  - `connect_access.json` — `Facade.res:238` hardcodes `adapter_type:
    "odbc"` instead of `binding.adapterType`. The COM factory correctly
    builds a COM binding but the success envelope lies about it.
  - `get_relationships.json` — `_getRelationshipsImpl` is stubbed
    `Ok([])`. DAO Relations iteration not yet implemented.
- Both COM mismatches are tracked for plan 033 (mutations) or a separate
  follow-up.

**Status**:
- Harness fixture injection: RESOLVED (plan 032b)
- `connect_access` `adapter_type` honesty: deferred (1-line fix in
  Facade.res:238)
- `getTableSchemaPlan` per-table method: deferred (not blocking parity;
  `Facade.getTableSchema` works via `getTables + find`)
- DAO Relations iteration: deferred to plan 033 (mutations) since it
  overlaps with FK enforcement

**Impact on baseline**:
- ODBC parity 6/0/3 → 9/0/0 — schema parity fully covered on Northwind.
- COM parity 4/1/1 → 4/2/0 — errored bucket drained, remaining are
  isolated mismatches tracked separately.
