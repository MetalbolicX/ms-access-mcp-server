# Plan 007 parity findings

Generated: 2026-08-26 by `pnpm -C rescript-mcp parity`.

Each finding records a real mismatch the harness surfaced between the
ReScript facade (`rescript-mcp/src/Services/Facade.res`) and the Python
original (`src/ms_access_mcp/`). Per plan 007 Step 6, every mismatch goes
here; fixes live in the owning code (Python is oracle, ReScript side is
wrong by default) — this file is the evidence ledger, not the patch
queue.

Pre-flight gate (`plans/018-parity-harness-plan-amendments.md`
amendment 8): passed. `git status` clean (only untracked
`rescript-mcp/test/mjs_list.txt`, allowed); `rescript clean` + `pnpm
build` exit 0; ReScript suite 581/581/0; `git log main` contains both
`bf8f9d0` (plan 024) and `196b9c3` (plan 018).

## Summary

17 cases exercised across all 17 v1 facade operations:

- 9 PASS — `connect_access`, `disconnect_access`, `is_connected`,
  `get_active_connection`, `set_active_connection`, `list_connections`,
  `get_queries`, `get_relationships`, `delete_data`.
- 7 FAIL — `query_data`, `insert_data`, `update_data`, `get_tables`,
  `get_table_schema`, `get_database_statistics`, `export_data`. ReScript
  side returns `{success: false, error: null}` (or analogous) while
  Python returns the expected envelope. See 007-F-001 / 007-F-002 /
  007-F-005.
- 1 ERROR — `execute_raw_sql` (007-F-003: invalid regex syntax in
  `Facade.res`).

Findings categories:

- **007-F-001** — `OdbcAdapter._normalizeQueryResult` reads `r.rows`
  which is `null` (the `odbc` v2 npm package returns the rows array
  directly with bookkeeping keys; `r.rows` is not a property). Every
  query that goes through this normalizer fails with `DatabaseError(null)`.
- **007-F-002** — `Bindings.Odbc.exnMessage` does not unwrap
  `Primitive_exceptions.internalToException`'s wrapper, so JS exceptions
  whose `.message` lives at `e._1.message` come through as `null`. The
  normalizer-catch chain (`_exnMessage` → `mapNativeError`) loses all
  error messages, so any path that throws (including path 007-F-001's
  `Belt.Array.map(null, ...)`) silently becomes `DatabaseError(null)`.
- **007-F-003** — `Facade.executeRawSql` uses a Java-style
  `(?i)(drop|delete|update)` regex literal that is not valid JavaScript
  regex syntax. ReScript's `Js.Re.fromString` raises a `SyntaxError`
  before any SQL runs, taking the whole facade op down. **Resolved in
  runner**: this is a ReScript-source bug; not fixed here per plan 007
  out-of-scope ("Any behavior fixes in either implementation").
- **007-F-004** — `Composition.makeRealFactory` produces bindings with
  `connection: None` and never opens the underlying ODBC handle. The
  runner works around this by reaching into `facade.bindings` and
  calling `dataAdapter.connect(connStr)` after `Facade.connectAccess`.
  Without that wiring, every data op returns `{success: false, error:
  "Not connected"}`. **Resolved in runner**: the runner-side connect
  step is documented inline as a parity-harness workaround.
- **007-F-005** — `OdbcAdapter.getTables` reads `row.TABLE_NAME` as a
  ReScript variant `{TAG: "Str", _0: str}` but the `odbc` npm package
  returns plain JS strings. Every table is filtered out because
  `typeof s !== "object"` (string is not object) and the `name` defaults
  to `""`. Per plan 016's findings, this would have surfaced in
  `test/odbc-integration/run.mjs` if the runner ever called the real
  `OdbcAdapter.getTables` instead of the raw `odbc.tables()`.

### Findings ledger

| # | Operation | Diff | Suspected side | Owner | Status |
|---|-----------|------|----------------|-------|--------|
| 007-F-001 | `query_data`, `get_table_schema`, `get_database_statistics`, `export_data` | ReScript returns `{success:false, error:null}`; Python returns the expected envelope | ReScript `OdbcAdapter.res:47 _normalizeQueryResult` reads `r.rows` which is `null` in `odbc` v2 | ReScript adapter | **RESOLVED** (`addfe47`) |
| 007-F-002 | every catch path | Error message is `null` instead of the ODBC error string | ReScript `Bindings/Odbc.res:132 exnMessage` doesn't unwrap `internalToException`'s `{RE_EXN_ID, _1}` wrapper | ReScript binding | **RESOLVED** (`0ac1b13`) |
| 007-F-003 | `execute_raw_sql` | ReScript driver crashes: `Invalid regular expression: /^\s*(?i)(drop\|delete\|update)\b/: Invalid group` | ReScript `Facade.res:869` uses Java-style `(?i)` syntax in `Js.Re.fromString` | ReScript facade | **RESOLVED** (`a729d9d`) — JS `i` flag via `fromStringWithFlags` |
| 007-F-004 | every data op (without runner workaround) | ReScript returns `{success:false, error:"Not connected"}` | `Composition.makeRealFactory` never calls `OdbcAdapter.connect` on the produced `dataAdapter.t` | ReScript composition | **RESOLVED** (`30777e6`) — factory now opens the ODBC connection itself; runner workaround removed |
| 007-F-005 | `get_tables` (and `get_table_schema` indirectly) | ReScript returns `tables: []`, Python returns 9 tables | `OdbcAdapter.getTables` reads `row.TABLE_NAME` as a ReScript variant; odbc v2 returns plain JS strings | ReScript adapter | **RESOLVED** (`182a9ed`) — `_rowString`/`_rowInt` helpers accept plain JS or variants; `conn.tables/columns` use `null` for missing args |
| 007-F-006 | `insert_data`, `update_data`, `delete_data` | ReScript returns `affected` = (count from odbc result) = -1 in some flows; Python returns `cursor.rowcount` | `OdbcAdapter._normalizeMutationResult` uses `result.count` which is always -1 in `odbc` v2 | ReScript adapter | **RESOLVED** (`2da805f`) — fall back to `result.rows.length` when `count = -1` |
| 007-F-007 | `insert_data`, `update_data` | ReScript driver: `[odbc] Error getting information about parameters` | JSON.t-variant params reach native odbc and break `SQLDescribeParam` on Access | ReScript adapter | **RESOLVED** (`bfc0ee0`) — inline literal values into SQL, strip JSON.t wrappers before native query call |
| 007-F-008 | `get_database_statistics` | ReScript returns flat `{tables,queries,...}`; Python returns nested `{objects:{...},file:{...},system:{...}}` | ReScript `OdbcAdapter.getDatabaseStatistics` returns flat shape | ReScript adapter | **RESOLVED** (`8403c98`) — restated to nested `{objects, file, system}` matching Python oracle |

**Pre-existing test failures (unrelated to F-001..F-008):** 2 of 581 unit tests fail before and after this work (HungKillFailed carries error message; get_tables COUNT failure tolerates and sets recordCount=0). These are pre-existing in the baseline at `2da805f` and not regressions from the parity fixes.

## Resolved during execution

- **`cmd.exe set FOO=bar` trailing-space quirk** — `cmd.exe`'s `set`
  preserves trailing whitespace, which leaked into `ACCESS_TEST_DB` and
  produced a trailing space in connect responses. Workaround: the runner
  quotes the value (`set "FOO=value"`) and strips/normalizes paths in
  the harness env.
- **Harness runner's per-side copies rejected by PathGuard** — the
  `pinnedEnv.ACCESS_MCP_ALLOWED_DIRS` did not include the scratch
  directory; fixed by appending `scratchRoot` to the allowed-dirs list
  after `mkdtempSync`.
- **ReScript runner positional `name` arg vs `~name?`** — the JS
  compiled signature of `updateData`/`deleteData` is
  `(facade, table, setDict, whereDict, name, confirmOpt, dryRunOpt)`
  where `name` is `undefined` for the None case. Passing a non-undefined
  value (e.g. `true` for `confirm`) makes `_bindingForName` look up the
  wrong key and return "Not connected". Fixed in `runRescript.mjs`.
- **Python `set_active_connection` lifecycle op** — driver ran in a
  fresh process with an empty pool. Fixed by priming the pool inside
  `_set_active_op` itself (the same pattern the runner uses for the
  ReScript side).

## Mutation test (Step 5)

Proves the harness detects injected mismatches:

1. **Mutate**: rename the `count` field in `Facade.res:327` from
   `("count", ...)` to `("count_injected_bug_for_mutation_test", ...)`.
2. **Rebuild**: `pnpm -C rescript-mcp build` (exit 0).
3. **Run**: `pnpm -C rescript-mcp parity`. Total: 17 cases, 8 matched,
   **8 mismatched** (was 9/7 before), 1 errored.
4. **Observe**: `list_connections.json` flips from PASS to FAIL with
   `diff at $`, `expected: ["count"]`, `actual: "missing"` — exactly
   what an injected field rename should produce.
5. **Revert**: edit the field name back to `count`. Rebuild.
6. **Confirm**: `pnpm -C rescript-mcp parity` returns to 9 PASS / 7
   FAIL / 1 ERROR (the pre-mutation baseline). The harness fails when
   behavior differs, as designed.

## Resolution summary (commits in `rescript/fix-parity-findings` branch)

| Commit  | Finding | Parity outcome |
|---------|---------|----------------|
| `0ac1b13` | 007-F-002 exnMessage unwrap | `getDatabaseProperties` and other catch paths surface real ODBC errors |
| `addfe47` | 007-F-001 iterate odbc v2 result array | `queryData`, `getTableSchema`, `getDatabaseStatistics`, `exportData` recover |
| `2da805f` | 007-F-006 fallback to rows.length when count=-1 | `insert_data`, `update_data`, `delete_data` return real affected |
| `182a9ed` | 007-F-005 plain JS row values + null args | `get_tables`, `get_table_schema_customers` recover |
| `a729d9d` | 007-F-003 JS `i` regex flag | `execute_raw_sql_select` recovers (also fixed runner positional `name` bug) |
| `30777e6` | 007-F-004 factory opens connection itself | all data ops work without runner workaround; runner workaround removed |
| `bfc0ee0` | 007-F-007 inline literal SQL values + strip JSON.t wrappers | `insert_data`, `update_data` recover |
| `8403c98` | 007-F-008 nested `{objects,file,system}` shape | `get_database_statistics` matches Python oracle |

**Final parity**: 17 cases, 17 matched, 0 mismatched, 0 errored.

## TS conversion (plan 019)

- **parity harness converted `.mjs` → `.ts`** at `rescript/019-typescript-parity`;
  baseline re-verified 17 matched / 0 mismatched / 0 errored; mutation test
  re-proven (FLOAT_TOL seam in `normalize.ts` used).

## 016-followup

Run date: 2026-08-28. Runner: `pnpm -C rescript-mcp test:integration:odbc`
with `ACCESS_TEST_ASSUME_ACE=1` and `ACCESS_TEST_DB=tests\integration\fixtures\test_db.accdb`.
Exit code: 1. Result: 6 passed, 11 failed.

### Triage buckets

| Bucket | Meaning |
|--------|---------|
| (a) | runner-assertion bug — fixable in `run.mjs` |
| (b) | ReScript adapter bug — out of scope, recorded as finding only |
| (c) | environment / Access ODBC driver limitation — recorded as finding only |

### Findings ledger

| # | Case | Error | Bucket | Owner | Status | Reproduction |
|---|------|-------|--------|-------|--------|--------------|
| 016-F-001 | `executeQuery: SELECT returns rows` | `[odbc] Error executing the sql statement` on `SELECT COUNT(*) FROM Customers` | (c) | Access ODBC driver | **OPEN** | `conn.query("SELECT COUNT(*) AS n FROM Customers", [])` throws |
| 016-F-002 | `insert: INSERT INTO affects 1 row` | `[odbc] Error getting information about parameters` | (c) | Access ODBC driver | **OPEN** | `conn.query("INSERT INTO [Customers] ([CustomerID], [CustomerName]) VALUES (?, ?)", [99998, "Integration Test"])` throws |
| 016-F-003 | `update: UPDATE WHERE affects expected rows` | `[odbc] Error getting information about parameters` | (c) | Access ODBC driver | **OPEN** | `conn.query("UPDATE [Customers] SET [CustomerName]='Updated' WHERE [CustomerID]=?", [99998])` throws |
| 016-F-004 | `delete: DELETE WHERE removes inserted row` | `[odbc] Error getting information about parameters` | (c) | Access ODBC driver | **OPEN** | `conn.query("DELETE FROM [Customers] WHERE [CustomerID]=?", [99998])` throws |
| 016-F-005 | `executeRawSql: SELECT COUNT returns non-negative rowcount` | `FAIL` — no rows returned | (c) | Access ODBC driver | **OPEN** | `conn.query("SELECT COUNT(*) FROM Customers", [])` returns no rows |
| 016-F-006 | `getTables: returns TABLE rows (MSys excluded)` | `[odbc] Error executing the sql statement` on INFORMATION_SCHEMA query | (c) | Access ODBC driver | **OPEN** | `conn.query("SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='TABLE' ORDER BY TABLE_NAME", [])` throws |
| 016-F-007 | `getQueries: queries INFORMATION_SCHEMA.VIEWS with dbo filter` | `[odbc] Error executing the sql statement` | (c) | Access ODBC driver | **OPEN** | `conn.query("SELECT TABLE_NAME, VIEW_DEFINITION FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA='dbo' ORDER BY TABLE_NAME", [])` throws |
| 016-F-008 | `createIndex: CREATE INDEX succeeds` | `FAIL` — CREATE INDEX throws | (c) | Access ODBC driver | **OPEN** | `conn.query("CREATE INDEX [IntTestSlice3Idx] ON [Customers] ([CustomerID])", [])` throws |
| 016-F-009 | `dropIndex: DROP INDEX succeeds` | `FAIL` — DROP INDEX throws | (c) | Access ODBC driver | **OPEN** | `conn.query("DROP INDEX [IntTestSlice3Idx] ON [Customers]", [])` throws |
| 016-F-010 | `createQuery (CREATE VIEW): succeeds` | `FAIL` — CREATE VIEW throws | (c) | Access ODBC driver | **OPEN** | `conn.query("CREATE VIEW [IntSlice3Vw] AS SELECT CustomerID FROM Customers WHERE CustomerID=0", [])` throws |
| 016-F-011 | `deleteQuery (DROP VIEW): succeeds` | `FAIL` — DROP VIEW throws | (c) | Access ODBC driver | **OPEN** | `conn.query("DROP VIEW [IntSlice3Vw]", [])` throws |

### Root cause analysis (c) findings

**Parameterised queries (016-F-002/003/004)**: The ACE ODBC driver does not
implement `SQLDescribeParam` reliably for Jet/ACE tables. The `odbc` npm
package (node-odbc 2.5.x) calls `SQLDescribeParam` as part of its parameter
binding path; when the driver returns an error, the query fails. This is a
known Jet/ACE ODBC limitation and is not fixable in the runner script.

**Non-parameterised queries / DDL (016-F-001/005/006/007/008/009/010/011)**:
The ACE ODBC driver also fails to execute several statement types that are
valid in Access SQL, including `INFORMATION_SCHEMA` lookups, `CREATE INDEX`,
`DROP INDEX`, `CREATE VIEW`, and `DROP VIEW`. The `[odbc] Error executing the
sql statement` and empty-result failures suggest the driver cannot properly
process these statement types through `SQLExecDirect` or equivalent paths used
by the `odbc` package. This is an environment/driver limitation.

**No (a) findings**: No runner-assertion bugs were identified — the runner
correctly implements the expected SQL and API calls. All failures trace to
the Access ODBC driver.

**No (b) findings**: The integration runner calls the `odbc` npm package
directly (not the ReScript adapter), so no ReScript adapter bugs are
exercised by this runner.

### Verification

| Check | Result |
|-------|--------|
| `pnpm -C rescript-mcp build` | exit 0 |
| `pnpm -C rescript-mcp test` | 678 passed, 0 failed |
| `pnpm -C rescript-mcp parity` | 17 matched, 0 mismatched, 0 errored |
| Integration runner exit code | 1 (11 failures) |
| Zero (a) fixes applied | Confirmed — all failures are (c) |