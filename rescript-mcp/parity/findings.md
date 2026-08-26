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
| 007-F-001 | `query_data`, `get_table_schema`, `get_database_statistics`, `export_data` | ReScript returns `{success:false, error:null}`; Python returns the expected envelope | ReScript `OdbcAdapter.res:47 _normalizeQueryResult` reads `r.rows` which is `null` in `odbc` v2 | ReScript adapter | OPEN |
| 007-F-002 | every catch path | Error message is `null` instead of the ODBC error string | ReScript `Bindings/Odbc.res:132 exnMessage` doesn't unwrap `internalToException`'s `{RE_EXN_ID, _1}` wrapper | ReScript binding | OPEN |
| 007-F-003 | `execute_raw_sql` | ReScript driver crashes: `Invalid regular expression: /^\s*(?i)(drop\|delete\|update)\b/: Invalid group` | ReScript `Facade.res:869` uses Java-style `(?i)` syntax in `Js.Re.fromString` | ReScript facade | OPEN (driver-level failure) |
| 007-F-004 | every data op (without runner workaround) | ReScript returns `{success:false, error:"Not connected"}` | `Composition.makeRealFactory` never calls `OdbcAdapter.connect` on the produced `dataAdapter.t` | ReScript composition | OPEN (workaround in runner) |
| 007-F-005 | `get_tables` (and `get_table_schema` indirectly) | ReScript returns `tables: []`, Python returns 9 tables | `OdbcAdapter.getTables` reads `row.TABLE_NAME` as a ReScript variant; odbc v2 returns plain JS strings | ReScript adapter | OPEN |
| 007-F-006 | `insert_data`, `update_data`, `delete_data` | ReScript returns `affected` = (count from odbc result) = -1 in some flows; Python returns `cursor.rowcount` | `OdbcAdapter._normalizeMutationResult` uses `result.count` which is always -1 in `odbc` v2 | ReScript adapter | OPEN |

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

## Follow-ups for plan 008+

- Fix 007-F-001 (`r.rows` → `r[0..n]` array iteration) — unblocks every
  query-driven facade op.
- Fix 007-F-002 (unwrap `_1` in `exnMessage`) — surfaces actual error
  messages instead of `null`.
- Fix 007-F-003 (`(?i)` → `i` flag) — `executeRawSql` works.
- Fix 007-F-004 (composition should call `OdbcAdapter.connect` after
  producing the binding) — restores parity without runner workarounds.
- Fix 007-F-005 (treat `odbc.tables()` row values as plain JS, not
  ReScript variants).
- Fix 007-F-006 (`_normalizeMutationResult` should compute affected from
  `result.rows.length` when `result.count = -1`, or use the OdbcAdapter's
  own row-counting strategy).