# Plan 029 — Close plan 028's verification debt with a real-COM proof

## Drift check

```bash
git rev-parse --short HEAD        # expected: d408c53 (plan 028 tip)
git status --short                # expected: no tracked-file modifications (untracked junk at root is OK)
git diff --stat d408c53..HEAD -- rescript-mcp/ plans/   # expected: empty
```

## Status

- Status: TODO
- Branch: `rescript/029-com-verification-debt` from `d408c53`
- Owner: executor (standard implementation tier)
- Effort: S–M
- **Blocks: plans 030+ (executeQuery, schema reads, mutations, DDL). None of them may start before this plan is DONE.**
- Closes: plan 028 disclosures D1 (foundation bug), D2 (root verification commands), D4 (clean tooling), D5 (dead code). D3 (parity baseline record) is deferred to plan 031 — see "Deferred".

## Why this matters

Plan 028 shipped with an honest disclosure: the connect lifecycle was verified by
code inspection, not by executed tests, because the `~winax` injection seam was
dropped. Disclosure-driven review then found that the inspection **missed a real
bug**:

```rescript
// ComSession.res:157 — the opened DAO Database handle is DISCARDED
| Ok(_currentDb) => {
```

`session.handles.daoDb` holds the `DAO.DBEngine.120` object. The actual
`Database` object — the one carrying `OpenRecordset`, `Execute`, `TableDefs`,
`QueryDefs`, `Relations`, i.e. everything plans 030–033 consume — is bound to an
underscore-prefixed name and thrown away. The foundation plan 028 claims to have
closed does not exist yet in the form downstream plans need.

Additionally, the rollback paths leak the DBEngine COM object (set fields to
`None` without calling `release`), and the refactor left dead code behind
(`_setProperty`/`_getProperty` with zero callers, `_testMode`/`setTestMode`
with zero references, a stale `ComDataAdapter.res:3` comment claiming
ComDispatch serialization that has zero production callers).

**Why real-COM proof is viable here** (verified 2026-08-30, this machine):

| Probe | Result |
|-------|--------|
| `Test-Path HKLM:\SOFTWARE\Classes\Access.Application` | **True** |
| `Test-Path "C:\Program Files\Microsoft Office\root\Office16\MSACCESS.EXE"` | **True** |
| `.venv\Scripts\python.exe -c "import win32com.client"` | **pywin32 OK** |

Full Access is installed. The "no Access" theory behind `027-F-002` and the
3 errored COM parity cases was wrong (real cause: the ReScript `get_table_schema`
is a plan-027 stub; `parity/run.ts:282-287` marks a case errored when either
side returns an error object). We can and should prove the connect chain against
a real Access instance instead of another layer of fakes.

## Environment quirks (MANDATORY — apply to every verification command)

- PowerShell. Env vars via `$env:NAME="1"`, never bash-prefix syntax.
- pnpm only: `pnpm -C rescript-mcp <cmd>`. Never bare npm/python/uv. Root `npm run build` only works AFTER step 0.2 lands.
- **`pnpm -C rescript-mcp clean` deletes rescript-test's compiled output inside
  `node_modules/.pnpm/rescript-test@*/` and nothing regenerates it.** Manual
  recovery (until step 0.1 lands): `cd` into that package dir, run `npx rescript`.
  After 0.1 lands, use `clean:all` exclusively.
- Junk files at repo root (`led.out`, `nul`, `build_output.txt`,
  `test_output.txt`, `test_output2.txt`, any `*_temp.log`) are untracked. Do not
  commit. Do not `git add -A`. Use explicit paths.
- `ACCESS_TEST_ASSUME_ACE=1` for parity runs.
- Conventional commits, no AI attribution, no push, no PR.
- Fresh-build gate: every "suite green" claim must come from a clean + full
  rebuild + test in one run.

## Current state (verified at authoring time, 2026-08-30, SHA d408c53)

### The bug — `src/Adapters/ComSession.res:136-170`

```rescript
| Ok(daoDb) => {
    session.handles.daoDb = Some(daoDb)        // holds DBEngine.120

    // Step 5: OpenDatabase (readwrite, not exclusive, optionally with password)
    let daoConnect = switch password { | Some(p) => ";PWD=" ++ p | None => "" }
    Bindings.Winax.WINAX_BINDING.invokeAsObject(
      daoDb, "OpenDatabase",
      [VStr(path), VBool(false), VBool(false), VStr(daoConnect)],
    )
      ->Promise.then(dbOpenResult => {
        switch dbOpenResult {
        | Error(e) => {
            _releaseAccessApp(accessApp)        // LEAK: daoDb COM object never released
            session.handles.accessApp = None
            session.handles.daoDb = None
            Promise.resolve(Error(e))
          }
        | Ok(_currentDb) => {                   // BUG: Database handle discarded
            ...
            Bindings.Winax.WINAX_BINDING.invoke(accessApp, "OpenCurrentDatabase", openCurrArgs)
              ->Promise.then(ocdResult => {
                switch ocdResult {
                | Error(e) => {
                    _releaseAccessApp(accessApp)  // LEAK: daoDb never released here either
                    ...
```

### The session type — `src/Adapters/ComSession.res:9-13`

```rescript
type t = {
  mutable handles: ComInterfaces.sessionHandles,
  mutable isConnected: bool,
  mutable pid: option<int>,
}
```

`currentDb` belongs on `t`, NOT on `sessionHandles`: the shared
`sessionHandles` record has **39 constructor sites in tests** (ComUiTest 9,
ComDbPropsTest 10+, ComVbaTest 12, WinaxTest 2, ComSessionTest 2); `t` has
**zero literal constructors** (tests go through `ComSession.make()`). This
mirrors Python, which stores `_current_db` on the dispatcher, not on any shared
handle bag.

### `_disconnect` current release order — `src/Adapters/ComSession.res` (LIFO section)

`adoConn → daoDb → accessApp`. Must become `adoConn → currentDb → daoDb → accessApp`.

### Root `package.json` — 3 lines, `packageManager` field only, NO scripts

`npm run build` / `npm test` at repo root always exit 1. This caused three
false router rejections during plan 028 execution.

### Dead code (grep-verified)

- `_setProperty` (def `ComDataAdapter.res:83`) and `_getProperty` (def `:99`): **0 call sites**.
- `_testMode`/`setTestMode` (`test/ComDataAdapterTest.res:94-98`): **0 references** beyond definition.
- `ComDispatch`: 0 production callers; only `Adapters.res:10` alias, stale `ComDataAdapter.res:3` comment, and its own tests. Node's single-threaded event loop makes STA serialization unnecessary (unlike Python's threaded ComDispatcher); keep the module + tests, fix the comment.

### Existing integration-test pattern to copy

`test/OdbcAdapterIntegrationTest.res` — env/fixture-gated tests that skip
cleanly when prerequisites are missing. Fixture:
`tests/integration/fixtures/test_db.accdb` (exists; `Customers` table, 3 rows —
plan 016 inventory). Executor re-verifies with `Test-Path` before writing tests.

## Commands

| Goal | Command |
|------|---------|
| Clean+rebuild everything | `pnpm -C rescript-mcp clean:all` (after 0.1) |
| Build | `pnpm -C rescript-mcp build` |
| Test | `pnpm -C rescript-mcp test` |
| Root-level (after 0.2) | `npm run build` / `npm test` at repo root |
| Parity (no-regression check) | `$env:ACCESS_TEST_ASSUME_ACE="1"; pnpm -C rescript-mcp parity:northwind` |
| Drift | `git diff --stat d408c53..HEAD -- rescript-mcp/ plans/ AGENTS.md package.json` |

## Scope

IN:
- `rescript-mcp/package.json` — `clean:all` script
- Root `package.json` — delegating `scripts`
- `AGENTS.md` — correct standard #6 wording + verification commands
- `src/Adapters/ComSession.res` + `.resi` — `currentDb` field on `t`, store the handle, `getCurrentDb` accessor, complete LIFO rollback/release
- `src/Adapters/ComDataAdapter.res` — delete `_setProperty`/`_getProperty`, fix stale line-3 comment
- `test/ComDataAdapterTest.res` — delete `_testMode`/`setTestMode`
- `test/ComIntegrationTest.res` — NEW: probe-gated real-COM connect suite
- `plans/README.md` — row 029 + amendment note on row 028

OUT (deferred, do not touch):
- D3 parity re-diagnosis + `028-F-001` finding record → plan 031 (when schema reads make COM cases real)
- Functor test seam (`module Make = (W: WINAX_BINDING) => …`) for CI-without-Access → maintenance note only
- Any executeQuery/schema/mutation/DDL implementation
- `sessionHandles` record shape (unchanged)

## Git workflow

Branch `rescript/029-com-verification-debt` from `d408c53`. Commit order:

1. `chore(tooling): add clean:all script, root run-scripts, correct AGENTS clean note`
2. `fix(rescript-mcp): store opened DAO Database handle and complete rollback release`
3. `test(rescript-mcp): add real-COM connect integration suite`
4. `docs(plans): mark 029 done, amend 028 row`

## Steps

### Step 0.1 — `clean:all` script

`rescript-mcp/package.json` scripts:

```json
"clean:all": "rescript clean && node -e \"const p=require.resolve('rescript-test/package.json');const{execSync}=require('child_process');const{dirname}=require('path');execSync('npx rescript',{cwd:dirname(p),stdio:'inherit'})\" && rescript"
```

**Evidence:** `pnpm -C rescript-mcp clean:all && pnpm -C rescript-mcp test` in one shot → 715/715, zero manual node_modules steps.

### Step 0.2 — Root delegating scripts

Root `package.json` gains:

```json
"scripts": {
  "build": "pnpm -C rescript-mcp build",
  "test": "pnpm -C rescript-mcp test",
  "clean": "pnpm -C rescript-mcp clean:all"
}
```

**Evidence:** `npm run build` and `npm test` at repo root both exit 0.

### Step 0.3 — AGENTS.md correction

Fix the standard #6 claim (`rescript clean` **does** clear rescript-test's
compiled output in node_modules; `clean:all` is the recovery). Add a
"Verification commands" line: pnpm-based only.

**Evidence:** `Select-String -Path AGENTS.md -Pattern "clean:all"` returns a hit.

### Step 1.1 — `currentDb` on `ComSession.t`

`.res` and `.resi` type:

```rescript
type t = {
  mutable handles: ComInterfaces.sessionHandles,
  mutable isConnected: bool,
  mutable pid: option<int>,
  mutable currentDb: option<ComInterfaces.comObject>,  // opened DAO Database (NOT DBEngine)
}
```

`_make` initializes `currentDb: None`. Add to `.resi`: `let getCurrentDb: t => option<ComInterfaces.comObject>`.

**Evidence:** build exits 0 and suite stays 715/715 with **zero** other file edits — this empty diff outside ComSession* is itself the proof the field placement avoided the 39-site ripple.

### Step 1.2 — Store the handle

`ComSession.res:157`: `| Ok(currentDb) => { session.currentDb = Some(currentDb) …` (drop underscore; shadowing the field name is fine).

### Step 1.3 — Complete rollback + LIFO release

- Add `_releaseHandle: option<comObject> => unit` helper (release + it is safe on `None`).
- Step-5 failure: release `daoDb` THEN `accessApp`; clear both fields.
- Step-6 failure: release `daoDb`, `accessApp` (currentDb not yet stored at that point — verify against actual code order).
- `_disconnect` LIFO: `adoConn → currentDb → daoDb → accessApp`; clear `session.currentDb = None`.

**Gate:** code inspection within commit + the Phase 2 tests exercise disconnect twice; no `MSACCESS.EXE` orphan remains after the suite (see Phase 2 cleanup).

### Step 1.4 — Dead code

Delete `_setProperty`/`_getProperty` from `ComDataAdapter.res`; delete
`_testMode`/`setTestMode` from `test/ComDataAdapterTest.res`; replace the stale
line-3 comment (state: COM calls run on Node's single-threaded event loop;
ComDispatch retained for future STA needs, currently test-only).

**Gate:** `grep -rn "_setProperty\|_getProperty\|_testMode\|setTestMode" rescript-mcp/src rescript-mcp/test` → **0 matches**.

### Step 2 — Real-COM integration suite (THE ACCEPTANCE)

New `test/ComIntegrationTest.res`, patterned after `OdbcAdapterIntegrationTest.res`:

```
probe: WINAX_BINDING.createObject("Access.Application")
  → Error ⇒ console.log("ComIntegrationTest: skipped (Access unavailable)") + cb(~planned=0)
  → Ok(anim) ⇒ release(anim); run suite against tests/integration/fixtures/test_db.accdb:
    1. connect: Ok(true); isConnected true
    2. getCurrentDb(): Some
    3. get(currentDb, "Name") → JSON.String containing "test_db.accdb"   ← LIVE-handle proof
    4. getHandles: accessApp = Some AND daoDb = Some
    5. disconnect: Ok; isConnected false; getCurrentDb None
    6. disconnect again: Ok (idempotent)
```

Notes:
- Every test disconnects in its final assertion chain. If a test aborts
  mid-chain, an orphan `MSACCESS.EXE` may linger — after the suite run,
  `Get-Process MSACCESS -ErrorAction SilentlyContinue`; if orphans exist,
  kill ONLY PIDs started during this run (record before/after), never a blind
  `/IM`. Blind `/IM` is acceptable only if the operator confirms no other
  Access instance is open.
- The skip path (no Access) cannot be executed on this machine — mark it
  inspection-verified in the plan's final report; do not fake it.
- Test count: 715 → 715+N (N ≈ 6).

**Evidence (plan 028's replaced acceptance):** suite output shows the new tests
PASSING on this machine — the connect chain proven against a real Access
instance. Step 3 is the money shot: reading `.Name` off the stored handle fails
if the `_currentDb` storage is wrong, so this test is red on `d408c53` and green
only with the Step 1 fix.

### Step 3 — Regression sweep + closeout

```bash
pnpm -C rescript-mcp clean:all && pnpm -C rescript-mcp build && pnpm -C rescript-mcp test
$env:ACCESS_TEST_ASSUME_ACE="1"; pnpm -C rescript-mcp parity:northwind
# Expect EXACTLY the pre-plan state: 6 matched, 0 mismatched, 3 errored (COM stubs) — 029 changes no ODBC behavior
git status --short      # only in-scope files
```

Update `plans/README.md`: row 029 → DONE (final SHA, test count, one-line
"real-COM proof" note); amend row 028's note with: "connect evidence superseded
by plan 029 real-COM suite (028's inspection missed the discarded Database
handle, fixed in 029)". Renumber note for successors: **030 executeQuery, 031
schema reads (+D3 parity record), 032 mutations, 033 DDL** — all consume
`ComSession.getCurrentDb()`.

## Done criteria

- [ ] `ComSession.currentDb` stored on connect; `getCurrentDb` exported in `.resi`.
- [ ] Rollback and `_disconnect` release ALL acquired COM objects in LIFO order (adoConn → currentDb → daoDb → accessApp).
- [ ] `test/ComIntegrationTest.res` exists; its live-handle test (`get(currentDb,"Name")` contains `test_db.accdb`) **passes on this machine**.
- [ ] No orphan `MSACCESS.EXE` after the suite.
- [ ] `clean:all` one-shot works; `npm run build`/`npm test` at root exit 0.
- [ ] Dead-code grep gate: 0 matches.
- [ ] Fresh clean+build+test: 715+N / 715+N, 0 failed.
- [ ] Parity unchanged: 6 matched / 3 errored (pre-existing COM stubs).
- [ ] Drift check shows only in-scope files; README rows 028+029 updated; conventional commits.

## STOP conditions

- The `Access.Application` probe fails despite the registry ProgID being present (COM activation blocked — e.g. DCOM permissions, click-to-run broken). STOP and report the exact winax error; do NOT force tests.
- Any of the existing 715 tests regresses → STOP, report.
- Real-COM tests hang >60s (Access dialog blocked on something) → STOP, report which step; do not blind-kill Access processes outside this run.
- Adding `currentDb` to `t` breaks files outside `ComSession.*` → unexpected ripple; STOP and report (would mean hidden `t` constructors exist).

## Maintenance notes (for plans/README.md after done)

- `ComSession.getCurrentDb()` is the ONLY sanctioned way for plans 030–033 to reach the DAO Database handle. Do not re-derive it via `invokeAsObject(daoDb, "OpenDatabase", …)` — the session owns the open/close lifecycle.
- Real-COM evidence lives in `test/ComIntegrationTest.res`; it self-skips on machines without Access (probe-gated). CI without Access still gets signature/state coverage from the 715-test unit suite.
- Functor seam (`module Make = (W: WINAX_BINDING) => …`) remains a documented option if deterministic fake-captured sequence tests are ever wanted; not needed while real-COM proof exists.
- D3 (parity baseline truth + `028-F-001`) is plan 031's first step.
