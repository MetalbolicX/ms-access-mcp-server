# Plan 043: Winax dispose-ordering fix (unblocks 033-F-001, 038-F-007, 042 v2, 040-F-001)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 7846e88..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/src/Adapters/ComSession.res rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Bindings/Winax.resi rescript-mcp/src/Bindings/TsBridge.res rescript-mcp/src/Js/winaxBinding.mts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M (the helper is ~15 lines; ~10 call sites to update; the
  3-run stability gate is the real work)
- **Risk**: MED (touches every DAO object creation/release site; the
  pattern is established for recordsets but new for TableDefs/Fields/
  Relations/QueryDefs/Indexes. The blast radius is large but the
  change is mechanical: replace `release(obj)` with
  `closeAndRelease(obj)` at each release site)
- **Depends on**: nothing; unblocks plan 042 v2 (resolves the teardown
  regression that prevented 042 v2 from landing). Also unblocks:
  - 033-F-001 (`generate_sql` was teardown-skipped)
  - 038-F-007 (`get_linked_tables` Approach A was teardown-skipped)
  - 040-F-001 Branch 4a path (depends on TableDefs.Item enumeration
    working, which is also teardown-affected)
- **Category**: bug
- **Planned at**: commit `7846e88` (post-042 v2 plan), 2026-09-04

## Why this matters

Plan 042 v2 (commit `7846e88`) proved that any fix that makes the
`TableDefs.Append` call ACTUALLY LAND a real COM handle (instead of
silently no-opping on a null arg) surfaces a latent v8 isolate
teardown crash — exit 134, `DispObject::~scalar deleting destructor`,
`RemoveEnvironmentCleanupHook` assertion, no stdout. The crash class
is the same 033-F-001 family that has kept `generate_sql` skipped since
plan 033 and that plan 041's Approach A (`get_linked_tables`) hit on
first iteration.

The codebase already knows the fix. `ComDataAdapter.res:115-139`
defines a `_closeRecordset` helper for DAO Recordsets:

```rescript
// _closeRecordset — explicitly close a DAO Recordset before release.
// DAO recordsets hold internal pointers to their parent Database object.
// Without explicit Close(), winax's async release defers the DispObject
// destructor until the event loop spins again — but that can be AFTER
// V8 isolate teardown, causing RemoveEnvironmentCleanupHook crash.
// Calling Close() forces synchronous DAO cleanup so the DispObject
// destructor runs before isolate teardown.
let _closeRecordset: ComInterfaces.comObject => Promise.t<unit> = (
  rs: ComInterfaces.comObject,
) => {
  Bindings.Winax.WINAX_BINDING.invoke(rs, "Close", [])
    ->Promise.then(_ => {
      Bindings.Winax.WINAX_BINDING.release(rs)->ignore
      Promise.resolve()
    })
    ->Promise.catch(_ => {
      Bindings.Winax.WINAX_BINDING.release(rs)->ignore
      Promise.resolve()
    })
}
```

The pattern is correct but UNDER-APPLIED. Only recordsets use it.
TableDefs, Fields, Relations, QueryDefs, and Indexes are created,
appended/used, and released without an explicit `Close()`. When the
parent Database is released during v8 teardown, these child objects'
native destructors fire AFTER v8 has started tearing down — crash.

This plan generalizes the pattern to a `_closeAndRelease` helper
that:
1. Attempts `Close()` (some DAO objects have it; TableDef properties
   don't)
2. On `Close()` success or failure, releases the COM proxy
3. Is used at every DAO object release site

The teardown crash should be eliminated. The cases that were
teardown-skipped (`generate_sql`, `get_linked_tables`) or
teardown-regressed (plan 042 v2's `create_linked_table.json`) should
move from ERROR/CRASH to clean PASS or clean MISMATCH.

## Current state

- **The established pattern** `rescript-mcp/src/Adapters/ComDataAdapter.res:115-139`:
  the `_closeRecordset` helper. It is the only place that explicitly
  closes a DAO object before release.

- **The release path**:
  - `Bindings.Winax.WINAX_BINDING.release` (`Winax.res:154-166`):
    dynamic-imports winax, then calls `TsBridge.winaxRelease(rawMod, obj)`.
    Returns unit. Catches errors silently (`->Promise.catch(_ => ...)`).
  - `TsBridge.winaxRelease` (`TsBridge.res:102`): the FFI external
    `release`.
  - `winaxBinding.mts:62-70`: `release(mod, obj)` — unwraps the
    `{__p__: ...}` envelope (if any), then calls
    `mod.release(_unwrap(obj))`. winax's `release` is
    `IDispatch::Release()` (the COM `IUnknown::Release`), which
    decrements the refcount.

- **The teardown crash signature** (multiple findings, all the same):
  - exit code 134
  - no stdout (crash happens DURING the op or DURING process exit)
  - stderr may show `DispObject::~scalar deleting destructor` and
    `RemoveEnvironmentCleanupHook assertion` (v8 native)
  - reproducible on Windows + winax 3.6.9 + Node 22

- **The DAO object creation sites** (`rg invokeAsObject` in
  `ComDataAdapter.res` + `ComSession.res`):

  | Line | Method | Object class | Has `Close()`? |
  |------|--------|--------------|-----------------|
  | ComSession:156 | `CreateObject("ADODB.Connection")` | ADODB.Connection | yes (`Close()`) |
  | ComSession:140 | `CreateObject("DAO.DBEngine.120")` | DAO.DBEngine | no |
  | ComSession:129 | `CreateObject("Access.Application")` | Access.Application | no (use `Quit()`) |
  | ComDataAdapter:436 | `OpenRecordset` | DAO.Recordset | yes (already handled by `_closeRecordset`) |
  | ComDataAdapter:1441 | `CreateQueryDef` | DAO.QueryDef | no (use `Close()` if it has one; fall back to release) |
  | ComDataAdapter:1473 | `QueryDefs(name)` | DAO.QueryDef | no |
  | ComDataAdapter:1999 | `TableDefs(name)` | DAO.TableDef | no |
  | ComDataAdapter:2058 | `TableDefs(name)` | DAO.TableDef | no |
  | ComDataAdapter:2070 | `Fields(name)` | DAO.Field | no |
  | ComDataAdapter:2551 | `CreateRelation` | DAO.Relation | no |
  | ComDataAdapter:2587 | `CreateField` | DAO.Field | no |
  | ComDataAdapter:2784 | `CreateTableDef` | DAO.TableDef | no |
  | ComDataAdapter:2876 | `TableDefs(name)` | DAO.TableDef | no |
  | ComDataAdapter:2944 | `TableDefs(name)` | DAO.TableDef | no |
  | ComDataAdapter:2967 | `CreateTableDef` | DAO.TableDef | no |

  The "Has `Close()`?" column is approximate. Some DAO objects
  (Recordsets, Connections) have `Close()`. Others (TableDef, Field,
  Relation, QueryDef) do not. The helper must be defensive: try
  `Close()`, fall back to release on missing method.

- **The release sites for these objects** are scattered. Many do NOT
  have explicit `release()` calls — the COM proxy is left for v8 GC.
  This is a key contributor to the teardown bug: the GC may not run
  before v8 teardown begins, leaving dangling native pointers.

- **The session-level release** `ComSession.res:265-298`:
  `adoConn → currentDb → daoDb → accessApp` LIFO order. This is
  CORRECT. The issue is the per-op objects created during a call
  (TableDefs, Fields, etc.) — they need explicit release before the
  session-level release fires.

- **`generate_sql` is teardown-skipped** (`findings.md:683-720`).
  The crash happens DURING the op, not post-serialization. Plan 036
  improved the runner to tolerate non-zero exit but could not fix the
  underlying winax dispose-ordering.

- **`get_linked_tables` is teardown-skipped** (`findings.md:886-937`,
  plan 041). Approach A failed because `getTables()` itself crashes
  via `TableDefs.Item(i)` — same teardown family. Plan 041
  escape-hatched the case.

- **Plan 042 v2 regression** (this session): `create_linked_table.json`
  flipped from PASS to ERROR 134 because the v2 fix made Append
  actually land, exposing the same teardown bug.

## Chosen approach

**Approach A — generalized `_closeAndRelease` helper + apply at every
DAO object release site.**

1. Define a new helper in `ComDataAdapter.res` (alongside the
   existing `_closeRecordset`):

```rescript
// _closeAndRelease — generalized close-before-release for any DAO
// object. Mirrors the _closeRecordset pattern (ComDataAdapter.res:115-139).
// Some DAO objects have a Close() method (Recordset, Connection); others
// (TableDef, Field, Relation, QueryDef) do not. Try Close() first;
// ignore "method not found" errors, then release unconditionally.
// This forces synchronous DAO cleanup so the DispObject destructor
// runs before V8 isolate teardown, preventing the
// RemoveEnvironmentCleanupHook crash (033-F-001 / 042 v2 family).
//
// FUNCTION LITERAL — never an IIFE (ComDataAdapter.res:57-59).
let _closeAndRelease: ComInterfaces.comObject => Promise.t<unit> = (
  obj: ComInterfaces.comObject,
) => {
  %raw("(o) => { try { if (o && o.__p__ && typeof o.__p__.Close === 'function') { o.__p__.Close(); } return true; } catch (e) { return false; } }")(Obj.magic(obj))->ignore
  Bindings.Winax.WINAX_BINDING.release(obj)->ignore
  Promise.resolve()
}
```

  The `%raw` call checks if the object has a `Close()` method on its
  raw proxy and calls it if so. Errors are swallowed. The `release`
  then fires unconditionally. This handles both classes (Recordset
  with `Close()` and TableDef without) without needing to know the
  class up front.

  **Alternative considered**: defensive `Bindings.Winax.WINAX_BINDING.invoke(obj, "Close", [])`
  with a try/catch — would round-trip through winax twice (invoke +
  release) vs. one `%raw` call. The `%raw` is faster and the pattern
  matches the existing `_closeRecordset` intent (synchronous cleanup).

2. Replace `Bindings.Winax.WINAX_BINDING.release(obj)` with
   `_closeAndRelease(obj)` at every per-op DAO object release site in
   `ComDataAdapter.res` and `ComSession.res`. Concretely: any release
   that targets a DAO object (Recordset, TableDef, Field, Relation,
   QueryDef, Connection). The session-level LIFO release in
   `ComSession.res:294-298` is already LIFO-ordered and correct — do
   not change its structure, but consider wrapping each release call
   in `_closeAndRelease` (Connections have `Close()`, so this is a
   pure improvement).

3. Add explicit release calls for DAO objects that currently rely on
   v8 GC. The minimum set is the 4 Append sites from plan 042 v2:
   - `ComDataAdapter.res:2570` (rel handle) — needs `release` after
     Append lands
   - `ComDataAdapter.res:2608` (field handle) — needs `release` after
     Append lands
   - `ComDataAdapter.res:2809` (tdef handle) — needs `release` after
     Append lands
   - `ComDataAdapter.res:2988` (tdef handle) — needs `release` after
     Append lands

   For the createLinkedTable flow specifically:
   - `tdef` (from `CreateTableDef`) — release via `_closeAndRelease`
     AFTER `Connect` is set, BEFORE returning success
   - `tableDefs` (collection) — release via `_closeAndRelease`
     IMMEDIATELY after Append returns (it has no `Close()`, but
     `_closeAndRelease` is safe to call on it)

4. (Optional) Add a process-level teardown hook in `runRescript.ts`:
   call `Bindings.Winax.WINAX_BINDING.release(session.handles.accessApp)`
   before `process.exit(0)` in the after-envelope code. This is a
   belt-and-suspenders move; the per-op releases should be sufficient.

### Why this fixes all 3 affected cases

- **`generate_sql`**: the op creates a temporary QueryDef via
  `CreateQueryDef`, runs it, then discards it. Without explicit
  release, the QueryDef native proxy's destructor fires during v8
  teardown. With `_closeAndRelease` at the end of the op, the
  QueryDef is released before v8 teardown. Teardown crash → clean.

- **`get_linked_tables` Approach A**: the op iterates `TableDefs.Item(i)`.
  Each `Item(i)` returns a new TableDef handle. Currently the
  handle is held in the local `tdef` and discarded after `.Name` is
  read. Without explicit release, the TableDef native proxy's
  destructor accumulates. With `_closeAndRelease` after each `.Name`
  read, the proxies are released as they go. Teardown crash → clean.

- **`plan 042 v2 create_linked_table regression`**: the TableDef is
  appended, then released via `release(tdef)` without `Close()`. The
  TableDef's parent Database reference is still live. With
  `_closeAndRelease`, the (no-op-for-TableDef) Close is attempted,
  then release fires — and crucially, the TableDef is released
  BEFORE the v8 isolate begins teardown. Teardown crash → clean.

### Why this does NOT regress

- `_closeAndRelease` is a superset of `release`. If the object has no
  `Close()` method, the `%raw` swallows the "not a function" check
  and the `release` fires. Net behavior: identical to today for
  objects without `Close()`.
- For recordsets, the new helper does the same thing as
  `_closeRecordset`. Net behavior: identical.
- For Connections, `Close()` is a real method — the new helper adds
  cleanup that wasn't happening. Win-win.

### Why not a session-level cleanup?

The session-level LIFO release in `ComSession.res:265-298` runs at
disconnect, but the crash is per-op, not per-session. The intermediate
DAO objects (TableDefs, Fields, etc.) are created during a single op,
held briefly, and discarded. If the process exits before the next
op's disconnect fires, the per-op objects are still live. The fix
must be at the per-op level.

## Commands you will need

| Purpose        | Command (from repo root)                                    | Expected on success                |
|----------------|--------------------------------------------------------------|------------------------------------|
| Build          | `cmd.exe /c "pnpm -C rescript-mcp build"`                    | exit 0                             |
| Tests          | `cmd.exe /c "pnpm -C rescript-mcp test"`                     | 786 passed / 10 failed (baseline)  |
| COM parity     | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:com:ddl"` | see per-step expectations          |
| ODBC parity    | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:ddl"`     | 13 matched + 2 skipped             |
| Kill Access    | `Get-Process MSACCESS -EA SilentlyContinue \| Stop-Process -Force` then `Start-Sleep -Seconds 5` | before AND after every COM run |

Parity env (PowerShell):
```powershell
$env:ACCESS_TEST_ASSUME_ACE='1'; $env:ACCESS_TEST_DB="$PWD\db\northwind.accdb"
$env:ACCESS_MCP_ALLOWED_DIRS="$PWD\db;$env:TEMP"; $env:ACCESS_MCP_READONLY='false'
```

## Scope

**In scope** (exactly these files):
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — add `_closeAndRelease`
  helper, replace `release(obj)` with `_closeAndRelease(obj)` at
  every per-op DAO object release site, add explicit release calls
  for the 4 plan-042-v2 Append sites
- `rescript-mcp/src/Adapters/ComSession.res` — wrap each release call
  in `_disconnect` (Lines 285-300) with `_closeAndRelease`. Note
  `_releaseHandle` (line 106) may need to dispatch on object type
  OR the session's existing call sites may need to call
  `_closeAndRelease` directly.
- `rescript-mcp/parity/findings.md` — resolution notes appended to
  033-F-001, 038-F-007, 042-F-001, 040-F-001
- `plans/README.md` — rows 042, 040, 041, 043 updated

**Out of scope** (do NOT touch):
- `Bindings/Winax.res` / `.resi` — the `release` primitive is fine;
  the bug is at the call site level, not the binding level
- `winaxBinding.mts` / `TsBridge.res` — `_unwrap` and `mod.release`
  are correct
- `Odbc.res` / `OdbcAdapter.res` — ODBC path doesn't use winax
- `process.exit` teardown in `runRescript.ts` — defer; per-op release
  is the primary fix; the teardown hook is "optional" and listed as
  enhancement, not required

## Git workflow

- Branch: `rescript/038-linked-tables-sql-script` (HEAD `7846e88`).
- **Two commits**:
  1. `fix(parity): add _closeAndRelease for winax dispose-ordering (plan 043)`
  2. `docs(parity): resolve 033-F-001 / 038-F-007 / 042 v2 teardown crashes (plan 043)`
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 0: Baseline capture

Kill MSACCESS, set parity env, run `parity:northwind:com:ddl` once,
kill MSACCESS. Record the exact tally.

**Verify**: `generate_sql.json` is SKIPped, `get_linked_tables.json`
is SKIPped, `refresh_linked_table.json` and `recreate_linked_table.json`
FAIL. Expected: `11 matched + 2 mismatched + 0-1 errored + 2 skipped`
(the 0-1 errored is the known transient exit-134 flake on
`delete_table` / `get_indexes` / `drop_index`).

### Step 1: Grep-verify the call sites

```bash
rg -n "Bindings\.Winax\.WINAX_BINDING\.release\(" rescript-mcp/src/Adapters/
```

Inventory the release call sites. Each one is a candidate for
`_closeAndRelease`. Note any that should be left alone (e.g.,
releasing a transient handle in a Promise.catch where the parent
session is also being torn down — those are non-issues).

Expected ~20-30 release call sites across `ComDataAdapter.res` and
`ComSession.res`. Most of the in-op releases should be wrapped;
the session-level LIFO release in `ComSession.res:294-298` is
optional but recommended for completeness.

### Step 2: Add the `_closeAndRelease` helper

Add the helper to `ComDataAdapter.res` immediately AFTER
`_closeRecordset` (around line 140). Use the EXACT code from the
"Chosen approach" section above. The `%raw` body must be a function
literal — never an IIFE.

### Step 3: Wrap release calls at per-op DAO object sites

For each release call site identified in Step 1, change
`Bindings.Winax.WINAX_BINDING.release(obj)` to
`_closeAndRelease(obj)`. The minimum required sites:

- `ComDataAdapter.res:2804` — `release(tdef)` (early return on error)
- `ComDataAdapter.res:2812` — `release(tableDefs)` (after Append)
- `ComDataAdapter.res:2816` — `release(tdef)` (after Connect)
- `ComDataAdapter.res:2820` — `release(tdef)` (error path)
- `ComDataAdapter.res:2987-2998` — tdef/tdes releases in recreate path
- `ComDataAdapter.res:2570-2580` — rel/field releases
- `ComDataAdapter.res:2608-2620` — field releases
- `_closeRecordset` itself — consider using `_closeAndRelease`
  internally for consistency (but `_closeRecordset` is fine as-is)

Other sites (the long tail of `release(thing)` calls in other DAO
ops) should also be wrapped but are not strictly required for
the 3 affected cases. If the executor has time, wrap them all.
If not, the minimum set is the createLinkedTable + recreateLinkedTable
+ createRelationship + _closeRecordset paths.

### Step 4: Add explicit releases for the 4 plan-042-v2 Append sites

After each successful Append at:
- `ComDataAdapter.res:2570` (relAsVariant → Append → release rel)
- `ComDataAdapter.res:2608` (fieldAsVariant → Append → release field)
- `ComDataAdapter.res:2809` (tdefAsVariant → Append → release tdef AFTER Connect)
- `ComDataAdapter.res:2988` (tdefAsVariant → Append → release tdef)

Add `_closeAndRelease` calls. Verify with `rg -n "_closeAndRelease"
rescript-mcp/src/Adapters/ComDataAdapter.res` after the edit.

### Step 5: Build

`cmd.exe /c "pnpm -C rescript-mcp build"` → expect exit 0. If
non-zero, the most likely cause is a typo in the `%raw` body or a
missing `ignore` on a Promise return value. STOP and report.

### Step 6: Shared-path regression gate (before any parity)

`cmd.exe /c "pnpm -C rescript-mcp test"` → expect `786 passed / 10
failed` baseline. ANY new failure → revert and STOP.

### Step 7: Targeted parity

Kill MSACCESS, `parity:northwind:com:ddl`, kill MSACCESS.

**Expected outcomes, in preference order**:
- **Best**: the 2 currently-Failing cases (`refresh_linked_table.json`,
  `recreate_linked_table.json`) remain FAIL (no change, plan 042
  still needed for those). `create_linked_table.json` STILL PASSES
  (the v2 regression is gone). `generate_sql.json` MAY flip from
  SKIP to PASS (real fix). `get_linked_tables.json` MAY flip from
  SKIP to a real MISMATCH (no longer crashes, but the implementation
  is still the empty stub). Tally: 12-13 matched + 0-2 mismatched
  + 0-1 errored + 0-2 skipped.
- **Acceptable**: zero new exit-134 regressions. The teardown
  crash class should be eliminated. Cases that were previously
  PASSing (the baseline) must STILL PASS. Any baseline-PASS
  regressing to ERROR 134 → STOP/revert (the helper introduced a
  new bug).
- **Failure**: a previously-PASSing case now ERRORs with 134
  → STOP/revert.

### Step 8: Full COM parity + stability (3 runs)

Three consecutive `parity:northwind:com:ddl` runs, killing MSACCESS
and waiting 5s between each.

**Verify**: the Step 7 outcome (whichever branch) reproduces in all
3 runs. ALL baseline-PASSing cases must PASS in all 3 runs. Any
PASS→ERROR regression that repeats in 2 of 3 runs → STOP and revert.
The transient-flake category (exit 134 on
`delete_table`/`get_indexes`/`drop_index`) is pre-existing — accept
it if Step 7 also showed it.

### Step 9: ODBC parity unchanged

`parity:northwind:ddl` → 13 matched + 2 skipped. The ODBC path
doesn't use winax, so any change here means something is deeply
wrong → STOP and revert.

### Step 10: Document and commit

1. Append a resolution note to **033-F-001** in
   `rescript-mcp/parity/findings.md`: real fix landed, the
   `_closeAndRelease` helper, the parity outcome. Mark 033-F-001
   RESOLVED.
2. Append a resolution note to **038-F-007**: real fix landed.
   Mark RESOLVED if `get_linked_tables.json` can now be unskipped
   (it can — the existing empty-stub body doesn't crash). Mark
   SUPERSEDED-BY-EMPTY-STUB if unskipping is out of scope (defer
   the implementation to a follow-up).
3. Append a resolution note to **042-F-001**: the v2 plan can now
   land cleanly. Re-state the v2 design. Mark 042 v2 as
   "READY-FOR-IMPLEMENTATION" (the next plan to dispatch).
4. Update `plans/README.md`: row 043 → DONE with one-line summary;
   row 042 → "READY (blocked on 043, now unblocked)"; row 040
   stays BLOCKED (still needs 042); row 041 → can be re-evaluated.
5. Commit(s) per "Git workflow".

## Test plan

The parity cases are the tests (live differential vs the Python
oracle). The existing suite (Step 6) is the shared-path regression
gate. No new unit tests — the behavior requires live COM.

## Done criteria

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] Test suite: 786 passed / 10 failed, no new failures
- [ ] Step 7 outcome achieved and reproduced across 3 stability runs
- [ ] ODBC parity: 13 matched + 2 skipped unchanged
- [ ] Only `ComDataAdapter.res`, `ComSession.res`, `findings.md`,
  `plans/README.md` modified (verify with `git diff --name-only`).
  `Winax.res`/`.resi`, `TsBridge.res`, `winaxBinding.mts` UNCHANGED.
- [ ] `_closeAndRelease` is a new top-level helper near the existing
  `_closeRecordset`; not a local lambda
- [ ] The 4 plan-042-v2 Append sites have explicit `_closeAndRelease`
  calls AFTER the Append
- [ ] All `%raw` bodies are function literals; no IIFE; no `require(`
- [ ] findings.md 033-F-001, 038-F-007, 042-F-001 updated; plans/README.md
  rows 040, 041, 042, 043 updated
- [ ] Two commits on the current branch; NOT pushed

## STOP conditions

- Drift: any in-scope file at HEAD differs from the excerpts above.
- Step 6: ANY new test failure.
- Step 7: any baseline-PASSing case regresses to ERROR 134.
- Step 8: any PASS→ERROR regression repeats in 2 of 3 runs.
- Step 9: ODBC parity changes at all.
- The fix seems to require touching `Winax.res`/`.resi`,
  `TsBridge.res`, `winaxBinding.mts`, or `process.exit` teardown.
- You find yourself writing a `%raw` IIFE or `require(` — STOP and
  re-read the `%raw` discipline note.

## Known follow-up (explicitly NOT this plan)

After plan 043 lands, plan 042 v2 (VComObject constructor + new arm
in `variantToJson`) becomes safe to dispatch. After 042 v2 lands,
plan 040 (refresh/recreate named lookup) becomes safe to dispatch.
After 040 lands, the 4 originally-deferred plan-038 mismatches are
fully resolved. The chain is:
043 (this plan) → 042 v2 → 040 → done with 038.

A separate follow-up could investigate the v8 isolate
`RemoveEnvironmentCleanupHook` crash more deeply (e.g., the
process-level teardown hook in `runRescript.ts`). The per-op
`_closeAndRelease` is sufficient for the parity suite; the
teardown hook is belt-and-suspenders for production use.

## Maintenance notes

- After landing, add one line to `AGENTS.md` "Key Gotchas": "All
  DAO object release sites must use `_closeAndRelease` (not raw
  `release`); the close-then-release ordering prevents the v8
  teardown crash (033-F-001 / 042 v2 family)."
- `_closeAndRelease` is safe to call on any object — the `%raw`
  check handles "no `Close()` method" defensively.
- `_closeRecordset` can be kept for clarity (DAO Recordset
  semantics) or replaced by `_closeAndRelease`; both work.
- The `process.exit(0)` in `runRescript.ts` happens AFTER the
  envelope is serialized, but the per-op `_closeAndRelease` calls
  fire during the op — so the teardown ordering is correct.
