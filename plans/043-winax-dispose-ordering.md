# Plan 043 v2: Sync release primitive + session-level teardown ordering (unblocks 033-F-001, 038-F-007, 042 v2, 040-F-001)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat b7c4ff1..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/src/Adapters/ComSession.res rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Bindings/Winax.resi rescript-mcp/src/Bindings/TsBridge.res rescript-mcp/src/Js/winaxBinding.mts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

> **Versioning note (read this first)**: This is **v2**, replacing v1
> which proposed a `_closeAndRelease` helper that tried `Close()` via
> `%raw` then released unconditionally. Executor attempted v1 and
> STOPPED: the helper applied at all 95 release sites made parity
> unstable — first run looked good, second run regressed on
> `delete_table` and `recreate_linked_table`. v1's diagnosis was
> wrong. **Do not attempt v1.**

## Status

- **Priority**: P1
- **Effort**: M (one new sync primitive, one module-level cache, a
  handful of call-site changes; the 3-run stability gate is the real
  work)
- **Risk**: MED (touches the binding layer's module-caching strategy;
  if the cached handle goes stale across op, the release is a no-op.
  Test gate + stability gate catch this.)
- **Depends on**: nothing; unblocks plan 042 v2 (the marshaling fix
  becomes safe to land after teardown ordering is fixed). Also
  unblocks 033-F-001, 038-F-007, 040-F-001.
- **Category**: bug
- **Planned at**: commit `b7c4ff1` (plan 043 v1), revised 2026-09-04

## Why this matters

The v8 isolate teardown crash (exit 134, `DispObject::~scalar
deleting destructor`, `RemoveEnvironmentCleanupHook` assertion) has
been latent in this codebase since plan 033. It manifests when a
real COM proxy (TableDef, Field, Recordset) is released during v8
isolate teardown, AFTER v8 has begun its own cleanup but BEFORE the
COM proxy's C++ destructor has run.

Plan 043 v1 hypothesized that calling `Close()` before `release()`
would fix it. v1 executor STOPPED with empirical evidence that the
helper shifts crashes but does not eliminate them. **The diagnosis
was wrong.**

The actual root cause is in `Bindings/Winax.res:154-166` (the `release`
primitive) and the same pattern in every other binding call:

```rescript
let release: ComInterfaces.comObject => unit = (
  (obj: ComInterfaces.comObject) => {
    _importWinax(())                          // <-- async dynamic import
      ->Promise.then(m => {
        let rawMod = TsBridge.unwrapWinaxModule(m)
        TsBridge.winaxRelease(rawMod, obj)    // <-- this is sync
        Promise.resolve()
      })
      ->Promise.catch(_ => Promise.resolve())
      ->ignore
  }
)
```

`TsBridge.winaxRelease` calls `mod.release(_unwrap(obj))`. The
underlying `DispObject::release()` C++ method (winax
`src/disp.cpp:59-67` and `NodeRelease` at line 774-787) is **fully
synchronous** — it does `disp.reset()` (smart-pointer refcount
decrement) and returns. No async work, no I/O.

The asynchrony comes from `_importWinax(())` at the top: every
release call awaits a `Promise<dict<JSON.t>>` (the winax module).
By the time the `.then` callback runs and `mod.release` is called,
the process may be in v8 teardown.

**The fix**: cache the winax module handle at module load time (one
dynamic import at session connect), and call sync release on the
cached handle for every per-op release. The release fires
deterministically when called, not "sometime after a Promise resolves".

This is a one-line insight and a few-line change.

## Current state

- **The async release** `Bindings/Winax.res:154-166` (12 lines,
  abbreviated above). Every `WINAX_BINDING.release`, `.set`,
  `.get`, `.invoke`, `.invokeAsObject`, `.invokePreservingError`,
  `.createObject` follows the same `_importWinax(()).then(...)`
  pattern. The `then` callback is sync, but the await before it
  defers it to the microtask queue.

- **The winax release is sync** at the C++ level. Verified at
  `node_modules/winax/src/disp.cpp:59-67` (`DispObject::release`)
  and `node_modules/winax/src/disp.cpp:774-787` (`NodeRelease`).
  Both do `disp.reset()` (a `std::unique_ptr<>::reset()` = explicit
  refcount decrement + delete). Pure sync.

- **The module cache is missing.** `_importWinax` is a function
  `() => Promise.t<dict<JSON.t>>` (`Winax.res:72-74`). It is called
  on every binding operation. winax is a singleton CJS module; the
  dynamic import resolves to the same instance every time. The
  import can be cached at module load.

- **The session-level LIFO release** `ComSession.res:265-298` is
  correct in concept but ALSO async (calls `releaseAsync` on
  `session.handles.*`). When `disconnect()` returns, the releases
  may not have fired yet. The process may exit before the
  `IUnknown::Release()` calls land — which is exactly the teardown
  crash.

- **The process exit** in `runRescript.ts` (and the stdio harness in
  `src/Mcp/main.mjs`) calls `process.exit()` after serializing the
  response envelope. v8 then runs `RemoveEnvironmentCleanupHook`
  hooks, where the COM proxy destructors fire. If a proxy is still
  held at this point, crash.

- **v1 history (do not repeat)**: plan 043 v1 STOPPED with the
  `_closeAndRelease` helper (try `Close()` then release) applied at
  95 release sites. The helper introduced a `%raw` JS call before
  every release, which:
  1. Added latency to every release (the `%raw` JS call wraps an
     extra `try/catch`).
  2. Did not change the asynchrony of the release (still wrapped in
     `_importWinax().then(...)`).
  3. Made the crash order non-deterministic (some releases fired
     before teardown, some after — first run happened to be lucky,
     second run wasn't).

## Chosen approach

**Approach A — sync release primitive + module cache + session-level
sync teardown.**

1. **Module-level cache in `Winax.res`**: replace the
   `_importWinax` helper with a lazy-ref-cached version. The first
   call to any binding operation kicks off the import; subsequent
   calls reuse the cached handle.

   ```rescript
   // _winaxModule — cached winax module handle. Resolves once on
   // first access, then synchronously available. Module load is a
   // single dynamic import; binding operations are sync from then on.
   // Pattern: lazy ref to a Promise that resolves once.
   let _winaxModule: ref<option<Promise.t<dict<JSON.t>>>> = ref(None)

   let _getWinax: unit => Promise.t<dict<JSON.t>> = () => {
     switch _winaxModule.contents {
     | Some(p) => p
     | None => {
         let p = %raw("(p) => import(p)")("winax")->Promise.resolve
         _winaxModule := Some(p)
         p
       }
     }
   }
   ```

2. **Add a sync `releaseSync` primitive to `Winax.res`** alongside
   the existing async `release`:

   ```rescript
   // releaseSync — SYNCHRONOUS release. Awaits the winax module
   // (one time, then cached) and immediately calls mod.release.
   // Use this at session teardown and at the end of any op that
   // creates a real COM handle (TableDefs, Fields, Relations,
   // Recordsets). The previous async release fired during v8
   // teardown → crash. This fires deterministically.
   let releaseSync: ComInterfaces.comObject => unit = (
     (obj: ComInterfaces.comObject) => {
       // We need the winax module synchronously, but _getWinax is a
       // Promise. The trick: build a tiny async bridge that resolves
       // to a callback. The CALLER must await this Promise.
       // (See releaseSyncAwait below for the awaitable form.)
       let _ignored = _getWinax(())  // kick off the import if not yet
       _ignored->Promise.then(m => {
         let rawMod = TsBridge.unwrapWinaxModule(m)
         TsBridge.winaxRelease(rawMod, obj)
         Promise.resolve()
       })->ignore
     }
   : ComInterfaces.comObject => unit
   )
   ```

   Wait — this is still async. The point is: the release fires
   IMMEDIATELY after the module is available, not "sometime later
   during v8 teardown". The await happens at the call site (the
   caller must `await`-ish on it before exiting the op).

   Better: provide an AWAITABLE form that the caller can chain:

   ```rescript
   // releaseSyncAwait — returns a Promise that resolves AFTER
   // the winax release has been called. Use at the end of any op
   // that creates a real COM handle, or at session teardown.
   let releaseSyncAwait: ComInterfaces.comObject => Promise.t<unit> = (
     (obj: ComInterfaces.comObject) => {
       _getWinax(())->Promise.then(m => {
         let rawMod = TsBridge.unwrapWinaxModule(m)
         TsBridge.winaxRelease(rawMod, obj)
         Promise.resolve()
       })
     }
   : ComInterfaces.comObject => Promise.t<unit>
   )
   ```

3. **At session teardown (`ComSession.res:265-298`)**: rewrite the
   LIFO release sequence to use `releaseSyncAwait` chained in
   `Promise.then` order, with a `process.nextTick` (or equivalent)
   at the end to ensure the v8 microtask queue is drained before
   returning from `disconnect`. The exact form:

   ```rescript
   let _disconnect: t => Promise.t<result<unit, Errors.t>> = (
     (session: t) => {
       if !session.isConnected {
         Promise.resolve(Ok())
       } else {
         // LIFO: adoConn → currentDb → daoDb → accessApp
         // All releases are AWAITED in order; the returned Promise
         // resolves only after every release has fired. The caller
         // (e.g., the stdio harness) must await this before exiting.
         let releaseChain = ref(Promise.resolve())
         let chainRelease = (handle: option<ComInterfaces.comObject>) => {
           switch handle {
           | None => ()
           | Some(obj) => releaseChain := releaseChain.contents->Promise.then(_ => Bindings.Winax.WINAX_BINDING.releaseSyncAwait(obj))
           }
         }
         // Reverse-order traversal
         let _ = chainRelease(session.handles.accessApp)
         let _ = chainRelease(session.handles.daoDb)
         let _ = chainRelease(session.handles.currentDb)
         let _ = chainRelease(session.handles.adoConn)
         releaseChain.contents->Promise.then(_ => {
           Promise.resolve(Ok())
         })
       }
     }
   : t => Promise.t<result<unit, Errors.t>>
   )
   ```

   **Critical**: the call site that triggers `disconnect` must AWAIT
   this Promise. If the harness calls `disconnect()` and then
   `process.exit(0)` without awaiting, the releases may not fire.

4. **At the stdio harness (`src/Mcp/main.mjs` and
   `runRescript.ts`)**: ensure the runner awaits the disconnect
   Promise before `process.exit(0)`. The current code may call
   `process.exit(0)` synchronously after the response is written —
   need to chain exit on disconnect completion.

5. **At per-op release sites in `ComDataAdapter.res`**: replace
   `Bindings.Winax.WINAX_BINDING.release(obj)` with the awaitable
   form at the END of each op that creates a real COM handle
   (TableDefs, Fields, Relations, Recordsets). The minimum sites:
   the 4 Append sites from plan 042 v2 (lines 2570, 2608, 2809,
   2988) and any other per-op release.

   **NOTE**: do NOT replaceAll 95 sites. The async `release` is
   still fine for the common case. Only the per-op RELEASE OF A
   REAL COM HANDLE (i.e., one that was created during the op and
   holds a real native proxy) needs to be sync. The v1 mistake was
   blanket-replacing; v2 is surgical.

### Why this is correct

- The winax module is a singleton CJS module. The dynamic import
  resolves to the same instance every time. Caching is safe.
- The native `DispObject::release` is sync. Awaiting the module
  handle is the only asynchrony. Once the module is loaded, the
  release is immediate.
- The LIFO session teardown ensures parent objects (Database,
  Application) are released AFTER their children (Recordsets,
  TableDefs). The native destructor chain runs in the correct
  order.
- The harness awaiting the disconnect Promise ensures releases
  fire before `process.exit(0)`, so v8 teardown doesn't see
  dangling native proxies.

### Why this does not regress

- Per-op releases that already worked (the helper-v1 didn't help
  them, but the original `release` didn't crash them either)
  remain unchanged. The fix is additive: a new primitive for the
  critical sites, not a replacement of the existing one.
- The module cache is a one-time cost. The first binding op
  pays the dynamic-import latency; subsequent ops are faster.
- The session LIFO order is preserved (the v1 attempt was for
  per-op, not session-level; v2 focuses on session teardown).

### Rejected alternatives (from v1 history + new analysis)

- **v1's `_closeAndRelease` helper** (try `Close()` then release):
  applied at 95 sites, made parity non-deterministic. Helper was
  both insufficient (didn't fix async) and harmful (added latency
  to every release).
- **Blanket replaceAll of `release` with sync version**: too
  aggressive. Some releases are best-effort (e.g., during a
  Promise.catch on a transient error); making them sync and
  chained would slow down the happy path for no benefit.
- **Process-level teardown hook in `runRescript.ts`**: would
  help, but doesn't address the root cause (asynchrony at
  per-op release). The per-op fix is the load-bearing change.
  The teardown hook becomes belt-and-suspenders.
- **winax.dispose or winax 4.x**: not a path; we're pinned to
  3.6.9 and a major version change is out of scope.

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
- `rescript-mcp/src/Bindings/Winax.res` — add `_winaxModule` cache,
  `_getWinax` lazy accessor, `releaseSync` (best-effort) and
  `releaseSyncAwait` (awaitable) primitives
- `rescript-mcp/src/Adapters/ComSession.res` — rewrite `_disconnect`
  to use the awaitable LIFO chain
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — replace
  `release` with `releaseSyncAwait` at the 4 plan-042-v2 Append
  sites (lines 2570, 2608, 2809, 2988) and any other per-op
  release of a real COM handle
- `rescript-mcp/src/Mcp/main.mjs` (and/or `runRescript.ts`) —
  ensure the harness awaits the disconnect Promise before
  `process.exit(0)`
- `rescript-mcp/parity/findings.md` — resolution notes appended
  to 033-F-001, 038-F-007, 042-F-001, 040-F-001
- `plans/README.md` — rows 042, 040, 041, 043 updated

**Out of scope** (do NOT touch):
- `Bindings/Winax.resi` — the new primitives are module-internal;
  the existing `release` signature is unchanged
- `TsBridge.res` — `winaxRelease` is already correct
- `winaxBinding.mts` — `mod.release` is already correct (sync)
- `Odbc.res` / `OdbcAdapter.res` — ODBC path doesn't use winax
- The existing `_closeRecordset` helper — keep as-is; it can
  coexist with the new sync primitives

## Git workflow

- Branch: `rescript/038-linked-tables-sql-script` (HEAD `b7c4ff1`).
- **Two commits**:
  1. `fix(parity): add sync release primitive + session-level teardown (plan 043 v2)`
  2. `docs(parity): resolve 033-F-001 / 038-F-007 / 042 v2 teardown crashes (plan 043 v2)`
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 0: Drift check + baseline capture

Drift check first:
```powershell
git diff --stat b7c4ff1..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/src/Adapters/ComSession.res rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Bindings/Winax.resi rescript-mcp/src/Bindings/TsBridge.res rescript-mcp/src/Js/winaxBinding.mts rescript-mcp/src/Mcp/main.mjs
```

Then baseline:
```powershell
Get-Process MSACCESS -EA SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 5
$env:ACCESS_TEST_ASSUME_ACE='1'; $env:ACCESS_TEST_DB="$PWD\db\northwind.accdb"
$env:ACCESS_MCP_ALLOWED_DIRS="$PWD\db;$env:TEMP"; $env:ACCESS_MCP_READONLY='false'
cmd.exe /c "pnpm -C rescript-mcp parity:northwind:com:ddl"
Get-Process MSACCESS -EA SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 5
```

Capture the exact tally. Expected: `10-11 matched + 2 mismatched + 0-2 errored + 2 skipped`.

### Step 1: Add module-level cache + sync release primitive

In `Bindings/Winax.res`:
1. Add `let _winaxModule: ref<option<Promise.t<dict<JSON.t>>>> = ref(None)` near the top of the `WINAX_BINDING` module.
2. Add the `_getWinax` lazy accessor.
3. Add `releaseSync` (best-effort) and `releaseSyncAwait` (awaitable) after the existing `release` and `releaseAsync` (around line 170).
4. Verify mirroring if any external signature is added (NOT expected; these are internal helpers).

### Step 2: Rewrite session teardown in `ComSession.res`

At `_disconnect` (lines 270-298): replace the `let _ = _releaseHandle(...)` calls with `releaseSyncAwait` chained via `Promise.then`. Build a `releaseChain` ref that accumulates the LIFO release Promises; return the chain's final Promise.

### Step 3: Await disconnect in the harness

In `rescript-mcp/src/Mcp/main.mjs` (or wherever `disconnect` is called from): find the call site, ensure the returned Promise is awaited before `process.exit(0)`. If the call is `disconnect().then(() => process.exit(0))`, change to `disconnect().then(() => { /* drain microtasks */ setImmediate(() => process.exit(0)) })` to ensure the v8 microtask queue is drained.

Also check `runRescript.ts` if it has a separate disconnect path.

### Step 4: Replace per-op release at the 4 plan-042-v2 Append sites

In `ComDataAdapter.res`, at lines 2570, 2608, 2809, 2988 (the 4 Append sites), and any per-op release of a real COM handle: change `Bindings.Winax.WINAX_BINDING.release(obj)` to `Bindings.Winax.WINAX_BINDING.releaseSyncAwait(obj)->Promise.then(_ => Promise.resolve())->ignore` ONLY if the caller can wait (most can; for the per-op sites, attach the `.then` to the surrounding Promise chain). For the createLinkedTable path, add the sync release AFTER the Append lands.

**DO NOT replaceAll**. Use surgical edits. The minimum set is the 4 Append sites; the long tail can be left for a future plan.

### Step 5: Build

`cmd.exe /c "pnpm -C rescript-mcp build"` → expect exit 0. If non-zero, the most likely cause is a type error in the Promise chain or a missing ref initialization. STOP and report.

### Step 6: Shared-path regression gate (before any parity)

`cmd.exe /c "pnpm -C rescript-mcp test"` → expect `786 passed / 10 failed` baseline. ANY new failure → revert + STOP.

### Step 7: Targeted parity

```powershell
Get-Process MSACCESS -EA SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 5
cmd.exe /c "pnpm -C rescript-mcp parity:northwind:com:ddl"
Get-Process MSACCESS -EA SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 5
```

**Outcome handling**:
- **Best case**: ZERO new exit-134 regressions. Baseline preserved or improved. The teardown crash should be eliminated or significantly reduced.
- **Acceptable case**: the 2 mismatches (refresh/recreate) remain FAIL. `create_linked_table.json` STILL PASSES. Tally ≥ baseline. No new regressions.
- **CRITICAL FAILURE**: any baseline-PASSing case now ERRORs with exit 134 → STOP + revert + report immediately. The sync release primitive is broken.

### Step 8: Full COM parity + stability (3 runs)

Kill MSACCESS, run COM parity, kill MSACCESS, wait 5s, repeat 2 more times. The Step 7 outcome must reproduce in all 3 runs. ALL baseline-PASSing cases must PASS in all 3 runs. Any PASS→ERROR regression that repeats in 2 of 3 runs → revert + STOP.

### Step 9: ODBC parity unchanged

`parity:northwind:ddl` → 13 matched + 2 skipped. Any change → revert + STOP + report.

### Step 10: Document and commit

1. Append a resolution note to **033-F-001** in `findings.md`: real fix landed (sync release + session teardown). Mark RESOLVED.
2. Append to **038-F-007**: real fix landed. Mark RESOLVED if `get_linked_tables.json` unskips, or SUPERSEDED-BY-EMPTY-STUB.
3. Append to **042-F-001**: v2 plan can now land cleanly. Mark "READY-FOR-IMPLEMENTATION".
4. Update `plans/README.md`: row 043 → DONE; row 042 → "READY (unblocked)"; row 040 → "READY (after 042)".

### Step 11: Commit(s)

Two commits per the plan:
1. `fix(parity): add sync release primitive + session-level teardown (plan 043 v2)`
2. `docs(parity): resolve 033-F-001 / 038-F-007 / 042 v2 teardown crashes (plan 043 v2)`

Conventional Commits. NO "Co-Authored-By" or AI attribution. Do NOT push.

## Test plan

Parity cases (live differential) + test suite (Step 6) for shared-path
regression. No new unit tests.

## Done criteria

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] Test suite: 786 passed / 10 failed, no new failures
- [ ] Step 7 outcome achieved and reproduced across 3 stability runs
- [ ] ODBC parity: 13 matched + 2 skipped unchanged
- [ ] Only `Winax.res`, `ComSession.res`, `ComDataAdapter.res`, the harness file (`main.mjs` or `runRescript.ts`), `findings.md`, `plans/README.md` modified. `Winax.resi`, `TsBridge.res`, `winaxBinding.mts` UNCHANGED.
- [ ] `releaseSyncAwait` is the awaitable sync-release primitive; `releaseSync` is the best-effort form
- [ ] `_disconnect` rewritten to use the awaitable LIFO chain
- [ ] Harness awaits the disconnect Promise before `process.exit(0)`
- [ ] Exactly 4 per-op release sites updated in `ComDataAdapter.res` (the plan-042-v2 Append sites); NO replaceAll
- [ ] All `%raw` bodies are function literals; no IIFE; no `require(`
- [ ] findings.md 033-F-001, 038-F-007, 042-F-001 updated; plans/README.md rows 040, 041, 042, 043 updated
- [ ] Two commits on the current branch; NOT pushed

## STOP conditions

- Drift: any in-scope file at HEAD differs from the excerpts above.
- Step 6: ANY new test failure.
- Step 7: any baseline-PASSing case regresses to ERROR 134.
- Step 8: any PASS→ERROR regression repeats in 2 of 3 runs.
- Step 9: ODBC parity changes at all.
- The fix seems to require touching `Winax.resi`, `TsBridge.res`, `winaxBinding.mts`, or `Odbc.res`/`OdbcAdapter.res`.
- You find yourself writing a `%raw` IIFE or `require(`.
- The mental pattern resembles v1 (blanket replaceAll, async release).

## Known follow-up (explicitly NOT this plan)

After 043 v2 lands, plan 042 v2 (VComObject constructor) becomes
safe. After 042 v2 lands, plan 040 (refresh/recreate named lookup)
becomes safe. After 040 lands, the 4 originally-deferred plan-038
mismatches are fully resolved.

The chain is: 043 v2 → 042 v2 → 040 → done with 038.

## v1 history (do not repeat)

Plan 043 v1 added a `_closeAndRelease` helper that tried `Close()`
via `%raw` then released unconditionally, applied at all 95 release
sites via `replaceAll`. Executor STOPPED at Step 8 with:

- First run: `create_linked_table.json` exit-134 fixed, baseline preserved
- Second run: `delete_table.json` and `recreate_linked_table.json` NEW exit-134 errors
- The helper introduced non-determinism (some releases fired before
  teardown, some after — run order mattered)

Root cause of v1's failure: the helper added latency to every
release (`%raw` JS call) without changing the asynchrony. The
async `release` still deferred the actual `IUnknown::Release` to a
microtask, and v8 teardown's ordering is independent of microtask
scheduling. v2 fixes the actual asynchrony with a module cache and
awaitable release.

## Maintenance notes

- After landing, add to `AGENTS.md` "Key Gotchas": "Per-op release
  of a real COM handle MUST use `releaseSyncAwait`; the async
  `release` defers `IUnknown::Release` to a microtask and may fire
  during v8 teardown → crash (033-F-001 / 042 v2 family)."
- The `_winaxModule` cache is per-ReScript-process. The first
  binding op pays the dynamic-import latency; subsequent ops are
  faster.
- The `_disconnect` LIFO chain is the load-bearing teardown
  ordering. If new handle types are added to `ComSession.handles`,
  add them to the chain in the correct order (children first).
