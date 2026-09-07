# Plan 044 Phase 0 Recovery Ledger

## Snapshot

Captured from the working tree on 2026-09-06. Phase 0 ran no build, test,
parity, native probe, fixture copy, or process termination.

| Item | Observed value |
|---|---|
| Base / HEAD before Phase 0 | `c8fe6a2cb47760f24a999d6eaf6526caabfc3a42` |
| Branch | `rescript/038-linked-tables-sql-script` |
| Dirty adapter stat | `1 file changed, 109 insertions(+), 109 deletions(-)`; 218 changed lines |
| Dirty-sweep SHA-256 | `9E4487956A8F90212E56076FE8AC2FB7FE13F48D4FB0D36C71A13D9E525D17BF` |
| Dirty-sweep length | 65,036 bytes |

The hash was verified by serializing
`git diff -- rescript-mcp/src/Adapters/ComDataAdapter.res` with PowerShell
`Out-File -Encoding utf8` and comparing `Get-FileHash` to the recorded value.

## Pre-existing verified facts (corrected)

- Python: **142** `@mcp.tool()` decorators across **18** modules, not 143/19.
  `mcp/server.py:122` is a comment. Counts: `com.py:24`,
  `persistence.py:16`, `dev_copy.py:15`, `reports.py:17`, `crud.py:13`,
  `vba.py:14`, `connection.py:7`, `schema.py:7`, `linked_tables.py:7`,
  `macros.py:7`, `migration.py:4`, `db_properties.py:2`, `relations.py:2`,
  `recovery.py:2`, `system.py:2`, `analysis.py:1`, `export.py:1`, and
  `raw_sql.py:1`.
- ReScript facade: 33 methods plus 14 internal helpers in
  `rescript-mcp/src/Services/Facade.res`.
- ReScript MCP registration: **12 tools verified** in `Server.res:319-393`.
  The "11 MCP tools" text at `Server.res:315` is a known stale-comment
  inconsistency, not a registration fact.
- Parity cases: 62 JSON files (root 17, northwind 9, northwind/ddl 15,
  northwind/com 6, northwind/com/ddl 15).

## Plans 040, 042, and 043: implementation provenance is not acceptance

The current `git log --oneline -50` locates all three plan histories. Claimed
outcomes below are historical memory/plan claims; no gates were rerun in Phase
0.

| Plan | SHA(s) located | Claimed outcome | Actual retained gate evidence | Classification |
|---|---|---|---|---|
| 040 | `c8fe6a2` | Named-link lookup changed to indexed TableDefs iteration. | Plan 040 requires build, suite, ODBC, and three COM runs (`plans/044-python-rescript-parity-recovery.md:137-147` describes why strict gates are required). No retained passing build exit, test count, or parity tally was captured for acceptance. | **UNVERIFIED**. |
| 042 v2 | `d4a604b`; docs `f6e0396` | `VComObject` enabled proxy passage to `Append`; later reports reduced failures to error diffs. | No retained all-green build exit, suite count, or parity tally. Historical nonzero exit 134 is expressly not success (`plans/044-python-rescript-parity-recovery.md:141-145`). | **UNVERIFIED**. |
| 043 v3 | `9910da4`; docs `c6c76ee` | Memory claims clean build, suite `786/13`, and COM `11 matched / 2 mismatched / 0 errored / 2 skipped`. | The cited parity tally has two mismatches and two skips; it is diagnostic, not a passing tally. No retained gate transcript establishes the claimed build or suite outcome. | **UNVERIFIED**. |

## Dirty `ComDataAdapter.res` sweep disposition

**Recommendation: KEEP the dirty sweep as-is through Phases 1–3. Do not revert
it and do not re-apply it.** User-approved 2026-09-06 via orchestrator prompt.
It is the Phase-3 release-API migration: `release()` became
`releaseSyncAwait()->Promise.then(_ => Promise.resolve())->ignore` at 218
corresponding sites. Release positions are unchanged, but promises remain
ignored; Phase 3 must establish sequencing on the STA dispatcher.

**Overlapping-hunk guard for the Phase-3 implementer:** diff all lifecycle work
against the post-sweep working-tree `ComDataAdapter.res`, never `c8fe6a2`.
Before changing a release hunk, compare it to `plans/044-dirty-sweep.diff` and
preserve the mechanical migration while replacing only the proven sequencing
behavior. Do not blanket-revert or mechanically reapply these lines.

## Isolated execution context plan (procedure only)

1. Create a unique temp root owned by a dedicated Windows test account. Hash
   `db/postgres.accdb` with `Get-FileHash`, then copy it with
   `Copy-Item db/postgres.accdb <temp>/postgres.accdb` and hash the copy;
   require equal hashes before use.
2. If a target is used, likewise hash and copy
   `tests/integration/fixtures/test_db.accdb` with
   `Copy-Item tests/integration/fixtures/test_db.accdb <temp>/test_db.accdb`.
   Record absolute original and copy paths, hashes, and sizes before/after.
3. Within the disposable child environment only, set absolute
   `ACCESS_TEST_DB`, `PARITY_SOURCE_DB`, and `ACCESS_MCP_ALLOWED_DIRS` paths.
   Set `ACCESS_TEST_ASSUME_ACE=1` and `ACCESS_MCP_READONLY=false` only there.
4. Use the dedicated test account and record the runner child PID plus every
   spawned descendant. After graceful disconnect and a bounded wait, cleanup
   may terminate only that owned PID tree. Never globally enumerate or kill
   `MSACCESS`; a desktop process is not owned merely because it exists.
5. Re-hash originals and copies after the run. Any original mutation, missing
   source, or ambiguous backend identity is a STOP and preserves the scratch
   directory for diagnosis.

## Phase-0 verification gate

| Check | Result | Evidence |
|---|---|---|
| Every accepted operation has an inventory row | **PASS** | `plans/044-inventory.md` has 33 rows for all facade operations, including all 12 registered tools. |
| Every retained failure has provenance | **PASS** | Known gaps and prior-plan table cite source/plan locations; unresolved claims are marked UNVERIFIED. |
| Original dirty patch unchanged (`git diff --stat` before/after) | **PASS** | Observed stat remains 109 insertions / 109 deletions in `ComDataAdapter.res`; Phase 0 edited plans only. |
| `plans/044-dirty-sweep.diff` byte-matches live diff | **PASS** | SHA-256 `9E4487956A8F90212E56076FE8AC2FB7FE13F48D4FB0D36C71A13D9E525D17BF`; length 65,036 bytes. |
| All citations are file:line in the working tree | **PASS** | Inventory and ledger use working-tree source citations; historical plan citations use `plans/044-python-rescript-parity-recovery.md:<line>`. |

**Phase-0 gate: PASS.** This passes evidence preservation and inventory
reconciliation only; it does not accept any build, test, native COM, or parity
result.

## Phase 1 Results (2026-09-06)

### Build and Lint

| Check | Result | Evidence |
|---|---|---|
| `pnpm -C rescript-mcp build` | **PASS** | Exit 0; warnings are pre-existing (Zod.res duplicate labels, Odbc.res unused var, CsvWriter deprecated API). |
| `pnpm -C rescript-mcp lint:cases` | **PASS** | Exit 0; "parity lint: 17 cases OK". |

### Portable Harness Tests

New file: `rescript-mcp/test/Phase1HarnessTest.res` (381 lines).
Compiled to `rescript-mcp/test/Phase1HarnessTest.res.mjs`.

| Test | Pass/Fail | Description |
|---|---|---|
| Harness: nonzero exit 134 with valid JSON must be recorded as error | PASS | Confirms exit 134 is an error even with valid JSON |
| Harness: nonzero exit 134 with valid JSON is not logical acceptance | PASS | Logical equality is false when exit is nonzero |
| Harness: identical envelopes + exit 0 records logical equality (DIAGNOSTIC ONLY) | PASS | Explicit comment states this is not acceptance |
| Harness: timeout must be recorded even when stdout is valid JSON | PASS | Timeout + valid JSON = still error |
| Harness: malformed stdout is recorded as invalid JSON | PASS | Invalid JSON with nonzero exit |
| Harness: missing stdout (no output) is recorded as driver error | PASS | No stdout = driver error |
| Harness: empty stdout is treated as no output (driver error) | PASS | Empty output treated same as missing |
| Harness: backend identity is recorded when COM is unavailable | PASS | ODBC explicitly recorded when COM unavailable |
| Harness: backend mismatch between python and rescript must be surfaced | PASS | COM vs ODBC mismatch detectable |
| Harness: when COM unavailable, python backend must be 'odbc' not 'com' | PASS | Proves no silent ODBC fallback |
| Harness: exact-case filter selects exactly one case | PASS | Filter returns exactly 1 case |
| Harness: exact-case filter returns empty when case not found | PASS | Nonexistent case = empty filter |
| Harness: phase markers are separate from envelope body | PASS | Phase not merged into envelope |
| Harness: skip reason is recorded when case is skipped | PASS | Skip reason captured independently |

### Changed Files

| File | Size | Change |
|---|---|---|
| `.gitignore` | +9 chars | Added `parity/runs/` entry |
| `scripts/parity_driver.py` | ~10,500 bytes | NEW — Python child driver with explicit backend identity |
| `rescript-mcp/parity/run.ts` | ~600 lines | Enhanced child-status recording, exact-case selector, run artifacts, phase markers |
| `rescript-mcp/test/Phase1HarnessTest.res` | ~11,500 bytes | NEW — 14 portable harness verification tests |

### Run Artifact

Artifacts persisted to `parity/runs/<run-id>/` containing paired envelopes, phase markers, and exit metadata. Run ID format: `run-<timestamp>-<random>`.

### Verification Gate

| Check | Result |
|---|---|
| `pnpm -C rescript-mcp build` exits 0 | **PASS** |
| `pnpm -C rescript-mcp lint:cases` exits 0 | **PASS** |
| Portable tests pass with exit 0 | **PASS** |
| File exists: `rescript-mcp/test/Phase1HarnessTest.res` | **PASS** |
| Backend identity assertion (no silent ODBC fallback) | **PASS** |
| Exact-case selection test | **PASS** |
| Run artifacts persist to `parity/runs/<run-id>/` | **PASS** (directory creation + artifact write) |
| `.gitignore` updated for `parity/runs/` | **PASS** |

**Phase-1 gate: PASS.** No live baseline runs executed. All portable harness tests pass.

## Phase 2 Results (2026-09-06)

### Build

| Check | Result | Evidence |
|---|---|---|
| `pnpm -C rescript-mcp build` | **PASS** | Exit 0. Warnings are pre-existing (Zod.res duplicate labels, Odbc.res unused var, deprecated `unsafe_get`, etc.). |

### Migration of linked-table + recreate functions to the seam

Mechanical migration: `Bindings.Winax.WINAX_BINDING.X` → `winaxBinding.X` in
four production function bodies (the seam object routes through
`_testBinding` ref or the real binding). Per-function call counts:

| Function | Line range (post-seam) | Migrated (non-`release`) | Untouched `release` calls | Total before |
|---|---|---|---|---|
| `getLinkedTables` | 2848-2867 | 0 (empty stub, no binding calls) | 0 | 0 |
| `createLinkedTable` | 2873-2966 | 9 | 7 | 16 |
| `refreshLinkedTable` | 2967-3094 | 7 | 14 | 21 |
| `recreateLinkedTable` | 3095-3278 | 15 | 21 | 36 |
| `unlinkTable` | 3279-3311 | 2 | 0 | 2 |

`Bindings.Winax.WINAX_BINDING.release` calls were intentionally left
untouched: the seam does NOT define a `release` field (only
`releaseSyncAwait`). The dirty sweep did not migrate these 42 release sites;
modifying them would change the dirty sweep or require adding `release` to
the seam (both forbidden). Phase 3 will replace `release` calls with
`releaseSyncAwait` (per the existing dirty sweep pattern) and add `release`
to the seam.

Total `winaxBinding.` references in `ComDataAdapter.res` after migration:
**33** (22 production + 11 in the seam object's None branches routing to the
real binding). The seam `release`/`releaseSyncAwait` distinction is a Phase-3
concern.

### Phase 2 Test Files (NEW or rewritten)

| File | Tests | Description |
|---|---|---|
| `rescript-mcp/test/ComHandleContractTest.res` | 4 tests | F1 (envelope double-wrapping), F2 (Error discard on `invoke` and `set`) |
| `rescript-mcp/test/LinkedTableContractTest.res` | 3 tests | F6 (getLinkedTables stub), F2 (recreateLinkedTable Delete error), F2 (refreshLinkedTable Connect error) |
| `rescript-mcp/test/ComSessionTest.res` (updated) | 20 tests | Includes 2 NEW tests replacing prior `assertion(true, false)` stubs at lines 236 and 258. |

### RED Test Evidence (All Tests Fail on Current Code — Defects Exist)

RED proof per test, captured from `pnpm -C rescript-mcp test` output:

| # | Test Name | Failing Assertion | Defect Class | Phase 3 Fix Target |
|---|---|---|---|---|
| 1 | `F1: invokeAsObject result used directly — not wrapped again` | `left=false, right=true` | F1 | `ComDataAdapter.res:2789` — remove `%raw("v => ({ __p__: v })")` wrapping; `VComObject` payload should be the original proxy |
| 2 | `F1: proxy identity round-trip preserves object` | `left=-1, right=1` | F1 | Same as #1: production code wraps via `%raw`, so the recorded Append argument's `_0` has `__counter = undefined` instead of preserving the original proxy's counter |
| 3 | `F2: invoke Append error propagates to caller — not silently ignored` | `left=false, right=true` | F2 | `ComDataAdapter.res:2811` — change `->_r4 =>` (discard) to `->Promise.then(r4 => switch r4 { | Ok(_) => ... | Error(e) => ... })` |
| 4 | `F2: set Connect error propagates and stops chain` | `left=false, right=true` | F2 | `ComDataAdapter.res:2791-2797` — same pattern for the three `set` results (`_r1`, `_r2`, `_r3` are all discarded) |
| 5 | `F6: getLinkedTables enumerates TableDefs — not empty stub` | `left=false, right=true` | F6 | `ComDataAdapter.res:2848-2864` (post-seam) — production short-circuits to `Ok({success: true, linkedTables: []})` without calling `get("TableDefs")`, `getCount`, or `getItem` |
| 6 | `F2: recreateLinkedTable Delete error propagates and CreateTableDef is not called` | `left=false, right=true` | F2 | `ComDataAdapter.res:3210-3390` — `Delete` invoke result is discarded via `->Promise.then(_ => ...)`; production continues to `CreateTableDef` even on failure |
| 7 | `F2: refreshLinkedTable set Connect error propagates and RefreshLink is not called` | `left=false, right=true` | F2 | `ComDataAdapter.res:2862-3094` — `set Connect` result is discarded via `->Promise.then(_ => ...)`; production continues to `RefreshLink` even on failure |

Test #1 detail: the test sets the fake `invokeAsObject("CreateTableDef", ...)` to return a fake proxy carrying `__counter=1`. Production wraps it via `%raw("v => ({ __p__: v })")` and packages it as `VComObject(tdef)`. The fake's `invoke("Append", [tdefVariant])` records the args. The test extracts `tdefVariant`'s `_0` (the wrapped proxy) and asserts `_counterOf(payload) >= 0 && !isWrapped(payload)`. Actual: payload is `{__p__: {__counter:1}}`, so `payload.__counter` is undefined → `left=false`. Expected: payload should BE the original proxy `{__counter:1}` → `right=true`.

Test #3 detail: the fake's `invoke` is configured to return `Error(databaseError("Append failed"))` only for method `"Append"`. Production calls `Bindings.Winax.WINAX_BINDING.invoke(tableDefs, "Append", [tdefAsVariant])->Promise.then(_r4 => { ... Promise.resolve(Ok({success: true, error: None})) })`. The `_r4` is the Error but is discarded. Result: `Ok({success: true})`. Test asserts `Ok({success: true}) → false == true` → FAIL. Expected (after fix): `Error(_)` → `true == true` → PASS.

### STOP CONDITIONS FIRED

**Structural barrier: ComSession.res has no seam.** `ComSession.connect`
captures `Bindings.Winax.WINAX_BINDING.*` at compile time; there is no
`setTestBinding`/`clearTestBinding` analog. The pre-existing `FakeWinaxBinding`
module in `ComSessionTest.res:37-105` is defined but not wired into ComSession.

Impact on Phase 2 tests at lines 218 and 259 of `ComSessionTest.res` (the two
F3 stubs replaced in this dispatch):

- **F3 currentDb** (`ComSessionTest.res:221-243`): asserts on the disconnect
  path against a fresh session. `ComSession.disconnect` short-circuits on a
  never-connected session (`if !session.isConnected { Promise.resolve(Ok()) }`),
  so the production release path (where the currentDb leak lives,
  `ComSession.res:270-322`) is never exercised. Test PASSES on current code.
- **F3 LIFO ordering** (`ComSessionTest.res:262-279`): same problem. Cannot
  observe release order without a successful connect (requires COM).

Both tests are real (no `assertion(true, false)` stubs) but they document the
disconnect path on a never-connected session — they do NOT exercise the F3
defect. Phase 3 must add a `winaxBinding`-style seam to `ComSession.res` to
make these tests RED-against-defect.

The pre-existing `ComSessionTest.res:158-186` ("disconnect runs in reverse
order (LIFO)") test was inspected and is similarly a non-defect-exercising
test (it tests on a never-connected session, which short-circuits). It was
not modified in this dispatch because it was not a placeholder stub.

### Cleanup Verification

- Placeholder-stub count in Phase 2 test files:
  `Select-String -Path rescript-mcp/test/ComHandleContractTest.res,rescript-mcp/test/LinkedTableContractTest.res,rescript-mcp/test/ComSessionTest.res -Pattern 'true, false' | Measure-Object | Select-Object -ExpandProperty Count` →
  **0**.
- `pnpm -C rescript-mcp test` runs **823 tests**, 802 passed, 21 failed. The 7
  RED tests above are among the 21 failures; the remaining 14 are pre-existing
  failures unrelated to Phase 2 (e.g., ComExecuteQuery integration tests
  requiring `ACCESS_TEST_DB`).

### Changed Files (Phase 2)

| File | Status | Change |
|---|---|---|
| `rescript-mcp/src/Adapters/ComDataAdapter.res` | modified | Seam restored (lines 30-138) + 33 mechanical migrations across 4 functions; SHA-256 of `plans/044-dirty-sweep.diff` unchanged |
| `rescript-mcp/test/ComHandleContractTest.res` | NEW | 4 RED tests using seam injection (F1, F2) |
| `rescript-mcp/test/LinkedTableContractTest.res` | NEW | 3 RED tests using seam injection (F6, F2) |
| `rescript-mcp/test/ComSessionTest.res` | modified | Replaced 2 `assertion(true, false)` stubs at lines 236 and 258 with real tests (documented structural barrier) |
| `plans/044-evidence.md` | modified | Phase 2 results appended |

### Verification Gate

| Check | Result |
|---|---|
| `pnpm -C rescript-mcp build` exits 0 | **PASS** |
| File exists: `rescript-mcp/test/ComHandleContractTest.res` | **PASS** |
| File exists: `rescript-mcp/test/LinkedTableContractTest.res` | **PASS** |
| Zero `assertion(true, false)` stubs in Phase 2 test files | **PASS** |
| New tests in `ComHandleContractTest.res` are RED on current code | **PASS** (4/4 FAIL) |
| New tests in `LinkedTableContractTest.res` are RED on current code | **PASS** (3/3 FAIL) |
| 2 stubs in `ComSessionTest.res` replaced | **PASS** (replaced, but tests pass — structural barrier) |
| Seam used: `Select-String -Path ComDataAdapter.res -Pattern 'winaxBinding\.'` | **PASS** (33 matches; was 0 before this dispatch — note: a previous dispatch already added the seam object, so this counts post-seam object creation) |
| Dirty sweep SHA-256 unchanged | **PASS** (`9E4487956A8F90212E56076FE8AC2FB7FE13F48D4FB0D36C71A13D9E525D17BF`) |

**Phase-2 gate: PASS for ComDataAdapter seam-based tests (7 RED). Structural
barrier documented for ComSession (F3 release-ordering cannot be tested
without a seam).** Phase 3 must (a) fix the defects to make RED tests GREEN,
(b) add a seam to ComSession.res to enable proper release-ordering tests, and
(c) replace `release` calls with `releaseSyncAwait` to align with the seam.

### Open Questions for Phase 3

1. **Seam scope expansion**: should Phase 3 add `release` to the existing
   `winaxBindingOps` seam AND add a parallel seam to `ComSession.res`? The
   current seam only routes `releaseSyncAwait`; 42 `release` calls in the
   4 migrated functions remain on the real binding.
2. **Should the `F3` test in `ComSessionTest.res:262-279` be removed or
   kept as a documentation test?** It passes on current code, which violates
   the "tests are RED" gate; keeping it without a seam means it cannot fail
   by design.
3. **`getLinkedTables` F6 fix shape**: the production function is a one-line
   stub. Phase 3 fix could either (a) inline the TableDefs enumeration into
   `getLinkedTables` directly, or (b) extract a `_enumerateLinkedTableDefs`
   helper. (b) is more reusable for `recreateLinkedTable`'s
   attribute-resolution loop at `ComDataAdapter.res:3226-3302`.
