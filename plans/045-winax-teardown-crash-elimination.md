# Plan 045: Eliminate the 033-F-001 winax teardown crash (exit 134) from COM parity runs

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat 016ebdb..HEAD -- rescript-mcp/src/Adapters/ComSession.res rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Bindings/Winax.resi rescript-mcp/parity/runRescript.ts rescript-mcp/parity/run.ts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (crash is non-deterministic; all gates are repeat-count based)
- **Depends on**: none (plans 043 v3 and 042 v2 already landed)
- **Category**: bug
- **Planned at**: commit `016ebdb`, 2026-09-07

## Why this matters

The COM parity differential runner (`parity:northwind:com`, `parity:northwind:com:ddl`) loses 7 of 21 cases to a native Node crash: the ReScript child exits 134 with **no stdout**, so the case is scored `ERROR (DRIVER)` regardless of whether the operation itself succeeded. This single defect blocks `get_relationships`, `get_table_schema-Customers`, `get_tables`, `query_data-SelectTop5Customers`, `delete_table`, `generate_sql`, and `recreate_linked_table` — everything else in the remaining parity gap list is small contract work. The crash is `node::RemoveEnvironmentCleanupHook ... Assertion failed: (env) != nullptr` fired from `DispObject::`scalar deleting destructor'`: winax COM proxy objects are being destroyed by V8 GC finalizers **after** the Node environment has been torn down. Plan 043 v3 fixed the session-level handles; the surviving crashes come from per-operation temporary COM proxies (Fields/TableDefs items, recordsets) that are never deterministically released.

## Current state

The facts and excerpts you need (all verified at `016ebdb`):

### Files and roles

- `rescript-mcp/src/Bindings/Winax.res` — the winax FFI binding module. `WINAX_BINDING` (line 63) is the module value used everywhere.
- `rescript-mcp/src/Bindings/Winax.resi` — the module signature; `releaseSyncAwait` is declared here AND in a local `module type WINAX_BINDING` block inside `Winax.res` (plan 043 v3 found the local module type was the blocker — both must stay in sync).
- `rescript-mcp/src/Adapters/ComSession.res` — COM session lifecycle; owns the 4 top-level handles.
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — DAO adapter; contains the per-op COM loops that leak temporary proxies.
- `rescript-mcp/parity/runRescript.ts` — the ReScript parity child (built to `parity/dist/runRescript.js`).
- `rescript-mcp/parity/run.ts` — the parity orchestrator; spawns both children.
- `rescript-mcp/parity/findings.md` — the parity findings log (append-only convention, e.g. `033-F-001`).

### Release primitives (`Winax.res`)

Three coexist:

```rescript
// :187-199 — release: ASYNC fire-and-forget, UNCACHED import per call
// ... _importWinax(()) .then ... ->ignore

// :201-209 — releaseAsync: same uncached import, awaitable

// :217-225 — releaseSyncAwait (plan 043 v3): uses cached module, deterministic
```

The cache: `_winaxModule` lazy ref + `_getWinax` accessor at `Winax.res:81-92`. `_importWinax` (:73-75) re-does a dynamic import every call — every OTHER binding op (`createObject:169`, `get:233`, `set:253`, `invoke:273`, `invokeAsObject:295`, `invokePreservingError:332`, plain `release:187`) still uses the uncached path.

winax is version **3.6.9** (`rescript-mcp/node_modules/winax/package.json`). Its README says: release is variadic and synchronous (L157), *"Release COM objects (but other temporary objects may be keep references too)"* (L155 — child proxies can survive an explicit release), and its own test suite runs under `--expose-gc` (L329) — GC-finalizer-driven cleanup of undisposed proxies is the known default lifecycle. There is NO `dispose`/`collect` API; `release` is the only lifetime control surface.

### The plan-043 deviation: `_disconnect` does not await its releases

`ComSession.res:374-404`. Current shape:

```rescript
let releaseHandle = (obj, label) => {
  winaxBinding.releaseSyncAwait(obj)->ignore          // :385  ← fire-and-forget!
  Promise.resolve(Ok(label))
}
// LIFO order :390-397: adoConn → currentDb → daoDb → accessApp
// ...
Promise.resolve(Ok(()))                               // :400  ← returns immediately
```

Plan 043's Step-2 design said "Critical: the call site must AWAIT this Promise" (plan 043 lines 259-261) — the landed code deviates: it `->ignore`s each `releaseSyncAwait` and resolves instantly. The releases usually land on the next microtask, but nothing enforces it.

`_disconnect` also does NOT release any per-op/temporary handles. The ADO path at `ComSession.res:326,342` fabricates `{__p__: v}` envelope handles for `CurrentProject`/`Connection` intermediates that are never released.

### Per-op releases are the async uncached `release`

Roughly 91 sites in `ComDataAdapter.res` call `Bindings.Winax.WINAX_BINDING.release(x)->ignore`. Only 4 were converted to `releaseSyncAwait` by plan 043 v3 (at `:2570, :2608, :2809, :2988` — the linked-table Append sites). Plan 043 explicitly deferred the long tail ("the long tail can be left for a future plan", plan 043 line 471) and its maintenance note mandates: *"per-op release of real COM handles MUST use releaseSyncAwait; new handle types must be added to the LIFO chain children-first"*.

The crashing operations' code paths contain these unreleased-proxy hotspots:

- `_getTablesImpl` (`ComDataAdapter.res:1112-1258`) + `_readDaoField` (:991) + `_enumerateTableFields` (:1053) — per-table `td`, per-field `fld`, `fieldsHandle` proxies (get_tables, get_table_schema)
- `_getRelationshipsImpl` (:1163-1274) — `relHandle`, `relsHandle` (get_relationships)
- `_executeQueryImpl` (:404-461) — recordset + row Fields handles (query_data)
- `deleteTable`, `generateSql` (:1473+), `recreateLinkedTable` `resolveAttrs` probe (:3503-3543)

### The child exit path

`runRescript.ts`:

- `:423-429` — awaits `Facade.disconnectAccess(facade)` (non-fatal catch)
- `:431` — `process.stdout.write(JSON.stringify(envelope))`
- `:445-448` — `if (useCom) await new Promise(r => setTimeout(r, 5000))` then `process.exit(0)`

There is **no drain/GC step** between the last release and `process.exit(0)` — only a 5-second sleep. `src/Mcp/main.mjs:11` has the sibling fix `setImmediate(() => process.exit(0))` (server path, plan 043).

`run.ts:431` spawns the child as `runChild(NODE, [RS_RUNNER_JS, casePath], ...)` — no `--expose-gc`.

### Crash signature (identical across all 7 cases)

```
node.exe[<pid>]: void __cdecl node::RemoveEnvironmentCleanupHook(Isolate *, CleanupHook, void *) at src\api\hooks.cc:142
#  Assertion failed: (env) != nullptr
 1: node::MultiIsolatePlatform::DisposeIsolate+765370
 2: node::RemoveEnvironmentCleanupHook+234
 3: DispObject::`scalar deleting destructor'+203
```

Exit 134, no stdout. **Non-deterministic**: in run `run-1788835040391-62bejy4` both `get_tables` and `query_data` passed (exit 0, valid envelope); in runs `run-1788834704720-vlm6qzq` / `run-1788834805035-osgzqoz` they crashed. Every gate in this plan is therefore a repeat-count gate.

### Conventions to match

- Conventional commits (`fix(winax): ...` — see `git log --oneline -10` for style).
- Branch naming: `rescript/045-winax-teardown-elimination` (pattern: `rescript/NNN-slug`).
- Findings are recorded in `rescript-mcp/parity/findings.md` with an `NNN-F-NNN` id and a dated entry; see the existing `033-F-001` entry for the format.

## Commands you will need

All commands run from the repo root (`D:\code\python\ms-access-mcp-server`) in PowerShell unless noted. `pnpm -C rescript-mcp ...` works from anywhere in the repo.

| Purpose | Command | Expected on success |
|---|---|---|
| Build ReScript | `pnpm -C rescript-mcp build` | exit 0 (warnings OK) |
| Full rebuild | `pnpm -C rescript-mcp clean:all` then `pnpm -C rescript-mcp build` | exit 0 |
| Build parity TS | `pnpm -C rescript-mcp build:parity` | exit 0 |
| Unit suite | `pnpm -C rescript-mcp test` | 827 tests, 0 failed (1511+ assertions) |
| COM read-only parity | `pnpm -C rescript-mcp parity:northwind:com` | summary line, see gates |
| COM DDL parity | `pnpm -C rescript-mcp parity:northwind:com:ddl` | summary line, see gates |
| ODBC regression | `pnpm -C rescript-mcp parity:northwind` | `9 cases, 9 matched` |

**Environment preconditions (before every parity run):**

```powershell
Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item tests\integration\fixtures\*.laccdb, db\*.laccdb -ErrorAction SilentlyContinue
Remove-Item rescript-mcp\REPLACE_AT_RUNTIME -ErrorAction SilentlyContinue   # stray generate_sql artifact
Copy-Item db\northwind.accdb tests\integration\fixtures\test_db.accdb -Force # unit-suite fixture
```

**Single-case invocation (use exactly this shape — do NOT run `node parity/dist/run.js` directly with `PARITY_VARIANT` set; the ESM `require("winax")` probe in `run.ts:108` fails when run.js is the main module, but succeeds when run.js is require()d from a CJS `node -e` wrapper — that is why every pnpm parity script uses the `node -e` pattern):**

```powershell
$env:PARITY_VARIANT="com"
node -e "process.env.ACCESS_TEST_DB=require('path').resolve('D:/code/python/ms-access-mcp-server/db/northwind.accdb');process.env.ACCESS_TEST_ASSUME_ACE='1';process.argv=['node','run.js','--cases-dir=D:/code/python/ms-access-mcp-server/rescript-mcp/parity/cases/northwind/com','--case=get_tables.json'];require('D:/code/python/ms-access-mcp-server/rescript-mcp/parity/dist/run.js')"
```

Swap `--cases-dir=...` (append `/ddl`) and `--case=<name>.json` per case. The 7 crash cases:

- read-only dir: `get_relationships.json`, `get_table_schema-Customers.json`, `get_tables.json`, `query_data-SelectTop5Customers.json`
- ddl dir: `delete_table.json`, `generate_sql.json`, `recreate_linked_table.json`

**Crash-rate loop (the gate metric)** — run this and count `ERROR` lines; 0 is the goal:

```powershell
$cases = @(
  @{dir='.../cases/northwind/com';        name='get_relationships.json'},
  @{dir='.../cases/northwind/com';        name='get_table_schema-Customers.json'},
  @{dir='.../cases/northwind/com';        name='get_tables.json'},
  @{dir='.../cases/northwind/com';        name='query_data-SelectTop5Customers.json'},
  @{dir='.../cases/northwind/com/ddl';    name='delete_table.json'},
  @{dir='.../cases/northwind/com/ddl';    name='generate_sql.json'},
  @{dir='.../cases/northwind/com/ddl';    name='recreate_linked_table.json'}
)  # replace ... with D:/code/python/ms-access-mcp-server/rescript-mcp/parity
foreach ($round in 1..3) {
  foreach ($c in $cases) {
    Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
    node -e "process.env.ACCESS_TEST_DB=require('path').resolve('D:/code/python/ms-access-mcp-server/db/northwind.accdb');process.env.ACCESS_TEST_ASSUME_ACE='1';process.argv=['node','run.js','--cases-dir=$($c.dir)','--case=$($c.name)'];require('D:/code/python/ms-access-mcp-server/rescript-mcp/parity/dist/run.js')" 2>&1 | Select-String "PASS|FAIL|ERROR"
  }
}
```

Record the output (21 lines: 3 rounds × 7 cases) into `plans/045-evidence.md` as you go.

## Scope

**In scope** (the only files you should modify):

- `rescript-mcp/src/Adapters/ComSession.res` — Step 2
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — Step 3 (release-site conversions only; NO behavior changes)
- `rescript-mcp/src/Bindings/Winax.res` and `Winax.resi` — Step 4 only (keep module type + resi in sync)
- `rescript-mcp/parity/runRescript.ts` — Step 5
- `rescript-mcp/parity/run.ts` — Step 5 (spawn args only)
- `rescript-mcp/test/ComSessionTest.res` (and other test files) — only if a Step 2-4 change breaks an assertion
- `rescript-mcp/parity/findings.md`, `plans/README.md`, `plans/045-evidence.md` — recording

**Out of scope** (do NOT touch):

- `rescript-mcp/src/Mcp/Server.res` — plan 043 v3 explicitly excluded it (v2 flaw #2); the server exit path already has `main.mjs:11`.
- Any change to envelope shapes / parity case JSONs — contract work lives in plans 046-050.
- `rescript-mcp/parity/runRescript.mjs` — legacy parallel copy; `runRescript.ts` is the source of truth.
- winax itself (no native patching, no version bump).
- Python code under `src/ms_access_mcp/`.

## Git workflow

- Branch: `rescript/045-winax-teardown-elimination` from current HEAD.
- Commit per step, conventional style: `fix(winax): await LIFO release chain in _disconnect`, `fix(winax): convert crash-path per-op releases to releaseSyncAwait`, `fix(parity): drain + gc before child exit`, etc.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Measure the baseline crash rate

No code changes. Rebuild everything (`clean:all` + `build` + `build:parity`), then run the crash-rate loop from "Commands you will need" once (3 rounds × 7 cases). Write the 21 result lines into `plans/045-evidence.md` as "Baseline".

**Verify**: evidence file contains the baseline table; note the ERROR count (expected: nonzero — historically 4-7 of 21 crash per round, varying).

### Step 2: Make `_disconnect` await the LIFO release chain

Close the plan-043 deviation. In `ComSession.res:374-404`:

- `releaseHandle` must return the `releaseSyncAwait(obj)` promise (chained with a `Promise.then` that maps to `Ok(label)`), not `->ignore` + immediate resolve.
- `_disconnect` must sequence the four releases LIFO (`adoConn → currentDb → daoDb → accessApp` — keep the existing order) so each release completes before the next starts, and resolve only when the chain completes. Follow the design quoted in `plans/043-winax-dispose-ordering.md` Step 2 (lines 222-261) — the plan text is authoritative; the landed code deviated.
- Keep the error-tolerance semantics: a failed release must not abort the chain (each step's error is tolerated, chain continues) and `_disconnect` still resolves `Ok(())` even if individual releases fail. There is an existing test "disconnect returns Ok(()) even when process cleanup fails" that pins this — it must keep passing.

**Verify**:
1. `pnpm -C rescript-mcp build` → exit 0
2. `pnpm -C rescript-mcp test` → 827 tests, 0 failed. If a ComSession test fails because it asserted the fire-and-forget timing, fix the test to await semantics (do not weaken the assertion's intent).
3. Run the crash-rate loop → record in evidence file as "After Step 2". Compare to baseline (improvement is likely but NOT required to proceed).

### Step 3: Convert crash-path per-op releases to `releaseSyncAwait`

Mechanical conversion, NO behavior changes. In `ComDataAdapter.res`, convert `Bindings.Winax.WINAX_BINDING.release(<x>)->ignore` to `Bindings.Winax.WINAX_BINDING.releaseSyncAwait(<x>)->ignore` — but ONLY inside these functions (the code paths of the 7 crashing cases):

- `_executeQueryImpl` (:404-461)
- `_readDaoField` (:991), `_enumerateTableFields` (:1053), `_getTablesImpl` (:1112-1258)
- `_getRelationshipsImpl` (:1163-1274)
- `_getTableSchemaPlanImpl` (:1229+) — same TableDefs/Fields iteration family
- `deleteTable`, `generateSql` (:1473+), `recreateLinkedTable` including the `resolveAttrs` probe (:3503-3543)
- the `_closeRecordset` helper (:231-243) — its `release(rs)` calls

Find sites with:

```powershell
Select-String -Path rescript-mcp\src\Adapters\ComDataAdapter.res -Pattern "WINAX_BINDING\.release\("
```

and convert the matches falling inside the listed functions (expect roughly 20-35 sites). Leave all other functions untouched — do not batch-convert the file. This honors plan 043's maintenance note ("per-op release of real COM handles MUST use releaseSyncAwait") without a mega-diff.

**Verify**:
1. `pnpm -C rescript-mcp build` → exit 0
2. `pnpm -C rescript-mcp test` → 827 tests, 0 failed (fake-injected tests use ComSession's `winaxBinding` shim, not these direct calls — they should be unaffected; if a test injects a fake lacking `releaseSyncAwait` and fails, extend that fake with a no-op `releaseSyncAwait` rather than reverting the conversion)
3. Crash-rate loop → record "After Step 3".

### Step 4: Deterministic pre-exit settle in the parity child

Two changes:

1. `run.ts` — spawn the ReScript child with `--expose-gc`: at the `runRescript` function (`run.ts:423-432`), change the spawn args from `[RS_RUNNER_JS, casePath]` to `["--expose-gc", RS_RUNNER_JS, casePath]` (the `runChild` helper already passes args through). winax's own test suite uses this flag (precedent, winax README L329).
2. `runRescript.ts` — in the `useCom` exit path (:445-448), BEFORE the existing 5s sleep, add a settle sequence:
   - `await` two macrotask turns (`await new Promise(r => setImmediate(r))` twice) so all pending release microtasks/`releaseSyncAwait` hops complete;
   - if `global.gc` exists (it will, via `--expose-gc`), call it twice to force surviving `DispObject` finalizers to run **while the environment is still alive**;
   - keep the existing 5s sleep and `process.exit(0)` afterward unchanged.

The intent: any DispObject that would have been finalized during env teardown is finalized here instead, where its cleanup hook can still find a live environment.

**Verify**:
1. `pnpm -C rescript-mcp build:parity` → exit 0
2. `pnpm -C rescript-mcp test` → unchanged 827/827
3. Crash-rate loop ×2 (6 rounds total) → **GATE: 0 ERROR lines across all 42 runs.** This is the plan's primary acceptance gate.

### Step 5: Full verification matrix + record

Run everything, in this order, from a clean process state:

```powershell
Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
pnpm -C rescript-mcp parity:northwind:com
pnpm -C rescript-mcp parity:northwind:com:ddl
pnpm -C rescript-mcp parity:northwind
```

- COM read-only: expected 6/6 matched (or at minimum: zero `ERROR` lines; `get_relationships` may still FAIL on the known Python-oracle `attributes` flake — see "STOP conditions").
- COM DDL: expected ≥ 14 matched + 1 skipped (`get_linked_tables`, plan 048) — `execute_sql_script` content diff belongs to plan 046, `recreate_linked_table` may FAIL on contract (plan 049); the gate is zero exit-134 ERRORs.
- ODBC: `9 cases, 9 matched` — regression gate.

Then:

1. Append the outcome to `rescript-mcp/parity/findings.md` under `033-F-001` (dated entry; reference this plan and the evidence file).
2. Finish `plans/045-evidence.md` (baseline + per-step loop results + final matrix tallies).
3. Update the `045` row in `plans/README.md` to DONE with a one-line summary.
4. Delete stray run artifacts: `rescript-mcp/parity/runs/` contents and `rescript-mcp/REPLACE_AT_RUNTIME` are disposable (runs/ is gitignored; REPLACE_AT_RUNTIME is generated by the generate_sql case writing to the literal placeholder path). `parity/findings.json` gets rewritten by every run — refresh and commit it with the evidence.

**Verify**: all four command outputs recorded in `plans/045-evidence.md`; findings.md + README.md updated.

## Test plan

No new unit tests are required by this plan (the fix is teardown determinism, not observable behavior). Existing suite is the regression net:

- `pnpm -C rescript-mcp test` → 827/827 after every step.
- If Step 2 requires touching `ComSessionTest.res`, keep the pinned behaviors: LIFO order, per-release error tolerance, overall `Ok(())`.

The real test is the repeat-count parity gate (Step 4.3: 0 ERROR in 6 rounds).

## Done criteria

ALL must hold:

- [ ] `pnpm -C rescript-mcp build` and `build:parity` exit 0
- [ ] `pnpm -C rescript-mcp test` → 827 tests, 0 failed
- [ ] Crash-rate loop: 0 `ERROR` (exit-134) results across 6 consecutive rounds × 7 cases, recorded in `plans/045-evidence.md`
- [ ] `pnpm -C rescript-mcp parity:northwind:com` → no `ERROR` lines
- [ ] `pnpm -C rescript-mcp parity:northwind:com:ddl` → no `ERROR` lines
- [ ] `pnpm -C rescript-mcp parity:northwind` → 9 matched, 0 mismatched (ODBC regression gate)
- [ ] `Select-String -Path rescript-mcp\src\Adapters\ComDataAdapter.res -Pattern "WINAX_BINDING\.release\("` shows no remaining matches inside the Step 3 function list
- [ ] No files outside the in-scope list modified (`git status`)
- [ ] `rescript-mcp/parity/findings.md`, `plans/045-evidence.md`, `plans/README.md` updated

## STOP conditions

Stop and report back (do not improvise) if:

- The drift check shows in-scope files changed since `016ebdb` in ways that contradict the excerpts above.
- After Steps 2+3+4, the crash rate is NOT reduced to 0 in the 6-round gate (a reduced-but-nonzero rate means a winax-level or native-stack cause remains — report the evidence file; patching winax or Node is out of scope).
- Converting release sites (Step 3) breaks fake-injected unit tests in a way that requires changing a fake's public shape.
- `--expose-gc` is unavailable or changes child behavior unexpectedly (spawn error, hang).
- The ODBC regression gate (`parity:northwind` 9/9) ever fails — immediate stop, revert the offending step.
- A `get_relationships` FAIL appears whose diff is `$.relationships[*].attributes` with Python returning `""` — that is the documented Python-oracle flake (non-deterministic `str(rel.Attributes)`), NOT a crash regression; note it in evidence and continue, but do not "fix" ReScript to emit `""`.

## Maintenance notes

- Every future per-op release of a real COM handle must use `releaseSyncAwait` (plan 043 maintenance note, reaffirmed here). New handle types go into the `_disconnect` LIFO chain children-first.
- If a new operation starts crashing with exit 134, run the crash-rate loop with its case added — the Step 4 settle (drain + gc + `--expose-gc`) is the safety net, and its absence in new spawn paths is the first suspect.
- Plans 046-050 verify against a crash-free runner; land this plan first or expect their verification to be flaky.
- The `node -e` require-wrapper invocation quirk (direct `node run.js` + `PARITY_VARIANT=com` fails the winax probe) is documented in "Commands you will need" — keep using the wrapper until the ESM `require` probe in `run.ts:104-122` is modernized (out of scope here).

## Phase 5 outcome (landed at commits `bf47c97`, `a354667`, `165d8d7`)

Four of the seven target cases fixed: `get_tables` and `delete_table` are PASS, `create_linked_table` recovered (Phase 2 win), `get_relationships` no longer crashes (now a content FAIL at `$.count`, plan 040 territory). One unclear: `get_table_schema-Customers` now errors with `python exit 1` (Python-oracle harness issue, not ReScript). Three cases still exit-134: `query_data-SelectTop5Customers`, `generate_sql`, `recreate_linked_table`.

### Why three cases survived

The Phase 5 implementation enqueued exactly one COM handle per operation. Recon at `165d8d7` revealed several operations obtain additional handles that were missed:

- `_executeQueryImpl` (ComDataAdapter.res:508-740): `fields` collection at 561, per-row `Fields` collection re-obtained at 635 inside the row loop, per-row per-col `cItem` at 662, plus the per-col `fieldHandle` at 590. All released same-iteration via `releaseSyncAwait`, but the JS wrapper objects survive until GC.
- `recreateLinkedTable` (ComDataAdapter.res:3517-3707): main-body `tableDefsJson` at 3614 (resolveAttrs enqueued at 3543 only), `CreateTableDef` result `tdefJson` at 3629, `tdefsJson` re-obtained before `Append` at 3641 (released fire-and-forget at 3653), and per-iteration `tdef` in `findLoop` at 3558.
- `generateSql` (ComDataAdapter.res:1597-1698): zero direct obtain sites. Indirect crash: the operation runs `_getTablesImpl` twice and `_getRelationshipsImpl` once via callbacks. The inner functions' per-iteration handles (per-column `Field` items, per-row `Fields` collections) are the actual crash source — not the outer-level enqueues.

### Phase 6 (committed — commit `165d8d7` + Phase 6 insertions)

Nine `_enqueueTempRelease(session, handle)->ignore` insertions at previously-missed per-iteration obtain sites:

- `_executeQueryImpl` (4 inserts): `fieldsHandle` after line ~570, `fieldHandle` after line ~594, `rowFieldsHandle` after line ~640, `cItem` after line ~666
- `recreateLinkedTable` main body (3 inserts): `tableDefs` after line ~3619, `tdef` after line ~3634, `tdefs` after line ~3649
- `_getTablesImpl` (1 insert): per-table `td` after line ~1159
- `_getRelationshipsImpl` (1 insert): per-relation `relHandle` after line ~1319

**Status**: Phase 6 complete. All 3 target cases now PASS in single-case probe runs (query_data-SelectTop5Customers, recreate_linked_table, generate_sql).
