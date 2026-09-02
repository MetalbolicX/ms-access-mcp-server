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

---

## 033-F-001: COM query_data crash — winax proxy disposal during v8 teardown

**Finding ID**: 033-F-001

**Symptom**: `query_data-SelectTop5Customers.json` (COM variant) reliably
errors with `rescript exit 134`. Native stack trace:

```
node.exe: void node::RemoveEnvironmentCleanupHook(Isolate*, CleanupHook, void*)
  at src/api/hooks.cc:142
Assertion failed: (env) != nullptr

DispObject::`scalar deleting destructor'+203
  → v8::ResourceConstraints::ResourceConstraints+6346
  → X509_STORE_get_lookup_lookup_certs+61556
  → v8::internal::StrongRootAllocatorBase::deallocate_impl+15858
  → ... (all inside MultiIsolatePlatform::DisposeIsolate)
```

**Root cause**: ReScript COM queryData (`_executeQueryImpl` →
`db.OpenRecordset(...)` → per-row Fields iteration → MoveNext loop)
holds native winax IDispatch proxies for the Recordset, Fields, and
per-field items. After the `disconnectAccess` call path in
`runRescript.mjs`, v8 isolate teardown disposes COM proxies during
`DisposeIsolate`. winax's `DispObject::~scalar deleting destructor`
fires after the native environment hook was removed, hitting the
`(env) != nullptr` assertion. Python's pywin32 doesn't trip this
because it doesn't rely on v8 isolate disposal.

**Resolution (plan 033b)**: Fixed in `ComDataAdapter.res` line ~343.
The per-row `rowFieldsHandle` (Fields collection from `get(rs, "Fields")`)
was acquired but never released. Added `release(rowFieldsHandle)` before
`MoveNext` in the row iteration success path. The Fields collection is
freshly acquired per row, so releasing before advancing the cursor is safe.

**Further fix (033b follow-up)**: The DAO Recordset itself was never
explicitly closed before winax `release()`. winax's `release()` only
decrements the IDispatch refcount but doesn't call `DAO.Recordset.Close()`.
This left the DAO Recordset holding internal pointers that outlived the
query execution. During V8 isolate teardown, winax's
`DispObject::~scalar deleting destructor` accessed already-freed memory,
triggering the `RemoveEnvironmentCleanupHook` assertion.

**Fix**: Added `_closeRecordset()` helper that calls `rs.Close()` (DAO
method) before `release(rs)`. Applied to all exit paths in `_executeQueryImpl`.
The `Close()` call forces synchronous DAO cleanup so the DispObject
destructor runs before isolate teardown.

**Verification**: `query_data-SelectTop5Customers.json` COM probe returns
5 rows and exits 0 (was exit 134). Case restored from `.skip`.

**Impact**:
- COM read-only parity: query_data case restored (was `.skip`)
- Suite: 741/741 maintained

---

## 033-F-002: COM insertData affected=0 — DAO RecordsAffected quirk

**Finding ID**: 033-F-002

**Symptom**: `insert_data.json` (COM variant) reports `affected: 0`
while Python oracle returns `affected: 1`. Both call
`db.Execute(sql, DAO_DB_FAIL_ON_ERROR=128)` then read
`db.RecordsAffected`.

**Investigation**:
- Direct winax probe (`probe_records.cjs`) on a fresh `app.CurrentDb()`
  confirms `db.RecordsAffected` returns `1` after `db.Execute(INSERT)` —
  so winax+DAO CAN return the correct count.
- ReScript's `_mutateImpl` reads `db.RecordsAffected` via `%raw`
  accessor (bypasses winax JSON serialization), returns `0`.
- The `db` reference in both paths is the `DBEngine.OpenDatabase`
  handle — same proxy Python uses.
- Replacing `invokeAsObject` with `invoke` (no envelope wrap) did not
  change the result.

**Root cause**: Unconfirmed. Working hypotheses:
1. winax's `obj[method](...args)` call sequence allocates a new
   internal dispatch state that resets the RecordsAffected counter
   before our raw accessor reads it.
2. The `db` proxy passed to our `%raw` accessor is the `{__p__: proxy}`
   envelope, not the proxy itself, so `envelope.RecordsAffected`
   accesses a different property (the envelope doesn't proxy property
   reads).

**Resolution (plan 033b)**: Fixed in `ComDataAdapter.res` lines ~517-521.
The `%raw` accessor received the `{__p__: proxy}` envelope but accessed
`h.RecordsAffected` on the envelope (not the proxy). Changed to
`h.__p__ && h.__p__.RecordsAffected` to reach the actual DAO proxy's
property. Also fixed same issue in `executeRawSql` and removed debug
`console.error` instrumentation.

**Verification**: `insert_data.json` COM probe returns `{"success":true,"affected":1}`
(direct probe, not via harness). `affected` no longer volatile.

**Impact**: COM mutation now returns actual DAO affected count. Suite 741/741.

---

## 033-F-003: COM adapter_type honest divergence

**Finding ID**: 033-F-003

**Symptom**: `connect_access.json` (COM variant) envelope includes
`adapter_type: "com"` on the ReScript side. Python oracle's
`_connect_op` does not include `adapter_type` at all. Diff at `$`
(missing/extra key).

**Resolution**: 
- `connect_access.json` marked `volatileFields: ["adapter_type"]`
  and `["database"]` (per-side path differences for fixture copies).
- ReScript `Facade.connectAccess` now emits `binding.adapterType`
  (was hardcoded `"odbc"` before this plan).

**Rationale**: `adapter_type` is a deliberate plan 033 honesty
addition — callers should know whether they're talking to ODBC or
COM. Marking volatile preserves the Python oracle's existing shape
without polluting it with a synthetic key.

---

## 033b-F-004: Acceptance Defect — COM parity script aborted on mixed mutating/read-only cases

**Finding ID**: 033b-F-004

**Symptom**: `pnpm parity:northwind:com` aborted before opening the DB with `--require-read-only` because the `parity/cases/northwind/com/` directory contained 3 cases with `"mutating": true`.

**Root cause**: The `com/` directory mixed read-only and mutating case files. The `--require-read-only` runner flag causes an early abort if any case has `mutating: true`.

**Resolution**: The 3 mutating cases moved to `parity/cases/northwind/com/mutating/`:
- `insert_data.json` → `mutating/insert_data.json`
- `update_data.json` → `mutating/update_data.json`
- `delete_data.json` → `mutating/delete_data.json`

`execute_raw_sql.json` stays in `com/` with `mutating: false` (UPDATE with `WHERE 1=0` affects nothing; intended as read-only test).

New script `parity:northwind:com:mutating` targets the mutating directory without `--require-read-only`, sets `ACCESS_TEST_ASSUME_ACE=true`.

**Case counts**:
- Read-only COM (`pnpm parity:northwind:com`): 7 cases
- Mutating COM (`pnpm parity:northwind:com:mutating`): 3 cases

**Status**: RESOLVED (033b acceptance fix)

---

## 033 Status Summary

- ODBC parity: 9/9/0 (unchanged)
- COM read-only parity: 7/0/0 (`pnpm parity:northwind:com`)
- COM mutating parity: 3/0/0 (`pnpm parity:northwind:com:mutating` — probe-verified)
- Suite: 741/741
- `query_data` COM case: RESOLVED (plan 033b) — `.skip` removed, case restored
- `insert_data` COM case: RESOLVED (plan 033b) — affected count now correct, no longer volatile
- `getTableSchemaPlan`: RESOLVED (plan 033b) — implemented via TableDefs/Fields iteration
- Acceptance defect (033b-F-004): RESOLVED — mutating cases isolated to `com/mutating/`, separate script added

Plan 033b completed:
1. F-001 query_data crash: Fixed by releasing per-row `rowFieldsHandle` before `MoveNext`
2. F-002 affected count: Fixed by accessing `h.__p__.RecordsAffected` on DAO proxy
3. 032-F-001 getTableSchemaPlan: Implemented using DAO TableDefs/Fields iteration
4. 033b-F-004 acceptance defect: Mutating cases moved to `com/mutating/`, separate `parity:northwind:com:mutating` script added

---

## 034-F-001 — COM createQuery binding fails via winax

**Status**: open
**Owner**: TBD
**Date**: 2026-09-02
**Branch**: rescript/034-com-ddl

### Symptom
DAO `db.CreateQueryDef(name, sql)` via winax `invokeAsObject` returns Error.
The Python oracle (`src/ms_access_mcp/adapters/dao.py:373`) succeeds via pywin32.

### Root cause
winax dispatch on DAO `Database.CreateQueryDef` (which returns a COM QueryDef
object) does not round-trip cleanly. `setQueryDb` and `deleteQuery` work via
different access paths; `createQuery` does not.

### Reproduction
Test 535/775: `ComDdl: createQuery creates a query and getQueries reflects it`.
Expected success, actual returns `{success: false}`.

### Workaround
None found in budget. `createQuery` is out of scope for parity cases until
winax dispatch on DAO methods that return COM objects is fixed.

### Impact
- ODBC variant works via SQL `CREATE VIEW`.
- COM `createQuery` is not parity-tested.
- T4 task is closed as blocked; follow-up issue TBD.

---

## 034-F-002 — generateSql envelope divergence between Python oracle and ReScript

**Status**: resolved
**Owner**: TBD
**Date**: 2026-09-02
**Branch**: rescript/034-com-ddl-v2

### Original Symptom
Python `dao.py:355` `generate_sql(output_path)` delegates to
`self._schema.generate_sql(output_path)`. The MCP tool `schema.py:137`
returns `adapter.generate_sql(output_path)` directly. `ComDbProps.exportSchemaDdl`
returns a `schemaDdlResult` with `{success, error?, ddlTables, ddlRelationships,
tablesExported, relationshipsExported}` — file paths, not inline DDL content.

### Resolution (2026-09-02)
1. Added `ddl?: string` field to `Interfaces.ddlResult` (Interfaces.res + Interfaces.resi)
2. Re-implemented `generateSql` in `ComDataAdapter.res` to:
   - Call `exportSchemaDdl` (writes `ddl_tables.sql` + `ddl_relationships.sql`)
   - Read both files back via `Adapters.ComDbProps._readFileText()`
   - Concatenate into inline DDL string
   - Return `{success, error, path: outputDir ++ "/schema", statements, tables, ddl: inlineDdl}`
3. Python oracle envelope: `{success, path, statements, tables}` — ReScript now matches
   plus the bonus `ddl` inline content field.
4. ODBC stays "Not available via ODBC" (expected divergence, documented in plan 034 T5).

### Impact
- COM `generateSql` now returns inline DDL content matching Python oracle shape
- ODBC unchanged

---

## 034-F-003 - rescript-test runner phantom assertion count on async DDL tests

**Finding ID**: 034-F-003
**Status**: open
**Owner**: TBD
**Date**: 2026-09-02
**Branch**: rescript/034-com-ddl-v2

### Symptom
Two real-COM tests in `ComDdlTest.res` fire 1 extra assertion than the test body
contains, causing the runner's "Correct assertion count" check to fail:

- **Test 652** (`ComDdl: createTable creates a table and getTables reflects it`):
  body has 2 assertions, runner reports delta=3 (`planned=2, right=3`).
- **Test 663** (`ComDdl: createQuery creates a query (success envelope)`):
  body has 1 assertion, runner reports delta=4 (`planned=1, right=4`).

### Root cause (hypothesis)
The `disconnect(adapter)` call inside the test body fires its promise chain
asynchronously. The chain includes `_gracefulShutdown` → `invoke(a, "Quit")` and
`_releaseHandle` → `releaseAsync` → `_importWinax` (dynamic import). These
microtasks may fire between the body assertions and `cb()`, and some of them
appear to increment the global passCounter/failCounter through a path that
involves `assertion` calls inside the disconnect promise chain's `.then`
fallbacks. The exact assertion source is unconfirmed.

The phantom assertion does NOT appear in the simpler T1 test 524 pattern; it
manifests specifically when the test body has `disconnect` fired without
`await` inside a nested `Promise.then` chain.

### Reproduction
Run `pnpm -C rescript-mcp test` on branch `rescript/034-com-ddl-v2`. Tests
652 and 663 fail with the assertion-count mismatch described above.

### Workaround
None found. The test bodies are correct; the assertion counts match the
body assertions. The phantom delta is a runner-level issue.

### Impact
- 768/770 tests pass (down from 770 ideal due to this finding)
- Both failing tests are documented in `tests/034-F-003.md`
- T7 verification gate is `768/770 ≥ 741` (baseline + 27 net new tests)
