# Plan 021: Aggregator housekeeping + pre-existing bug fix (catch-up commit)

> **Executor instructions**: Mechanical work — no new design, no public API
> changes. Touch only the files named in the steps below. After each step,
> confirm the build + suite state. When done, update this plan's status row
> in `plans/README.md`.
>
> **Drift check (run first)**: HEAD must be `8b190f1` on branch
> `rescript/015-instance-types-and-producers`. Working tree has
> untracked files only (no modified tracked files). `pnpm -C rescript-mcp build`
> currently FAILS (this plan fixes it).

## Status

- **Priority**: P1 (unblocks plan 015 apply + re-verifies plans 016/017)
- **Effort**: S
- **Risk**: LOW (mechanical; no design decisions)
- **Depends on**: nothing (independent of plan 015 cycle)
- **Category**: infrastructure
- **Methodology**: NEITHER. Mechanical catch-up; no behavior change; no
  public API change. The `_importOdbc` fix is bounded strict-TDD (red test
  exists implicitly as the suite crash at test 482/576).
- **Planned at**: commit `8b190f1` on branch
  `rescript/015-instance-types-and-producers`, working tree with untracked
  critical files, 2026-08-25

## Why this matters

Plan 015's apply phase surfaced a structural blocker that goes beyond its
scope:

1. **Aggregator state broken**: `Bindings.res` only registers `Odbc`,
   missing `TsBridge`, `Winax`, `JsCom`. `Services.res` only registers
   `ConnectionPool`, `BackendSelector`, missing `Facade`. Build fails with
   "module or file can't be found".
2. **Pre-existing bug in `Bindings/Odbc.res:129`**:
   `external _importOdbc: unit => Promise.t<...> = "import"` compiles to
   `Odbc.import()` — a method call that doesn't exist on the `odbc` CJS
   namespace. Throws `TypeError: Odbc.import is not a function` whenever
   real `OdbcAdapter.connect` runs. Was masked by fakes; surfaced when
   test 482/576 (real connect) ran.
3. **Untracked critical files**: 30+ source/test files exist on disk but
   not in git index. The "553/553/0 baseline" from plan 017 must have
   run against cached build artifacts.

This plan makes the build + suite clean again BEFORE plan 015's apply
phase resumes.

## Current state

- HEAD: `8b190f1` on `rescript/015-instance-types-and-producers`
- `pnpm -C rescript-mcp build` fails: "Bindings.TsBridge can't be found",
  "Bindings.Winax can't be found" — and other module-not-found errors from
  COM adapters (`ComDbProps`, `ComSession`, `ComUi`, `ComVba`, `ComInterfaces`)
  and schema/facade consumers (`FacadeTest`, etc.).
- `pnpm -C rescript-mcp test` runs against stale `lib/bs/*.mjs` from prior
  builds; the 553/553/0 result from plan 017 was against cached artifacts,
  not a fresh build.
- Suite baseline claim: 553/553/0 (from plan 017, against stale cache).
  After this plan: same or better, against a fresh build.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build | `pnpm -C rescript-mcp build` (or via `cmd.exe /c` wrapper) | exit 0, no module-not-found errors |
| Unit suite | `pnpm -C rescript-mcp test` | 553/553/0 or better |
| Inspect untracked | `git ls-files --others --exclude-standard` | the lists in step 1 |

## Scope

**In scope**:
- New branch `rescript/021-housekeeping` cut from `8b190f1`
- Commit all untracked critical source/test files as one catch-up commit
- Fix `rescript-mcp/src/Bindings.res` to register `TsBridge`, `Winax`, `JsCom`
- Fix `rescript-mcp/src/Services.res` to register `Facade`
- Fix `rescript-mcp/src/Bindings/Odbc.res` `_importOdbc` external
  (replace with a function using JS dynamic `import()`)
- New test pinning the `_importOdbc` fix (red-first under strict TDD)
- `plans/README.md` row 021 DONE

**Out of scope**:
- Any plan 015 work (T2-T6) — that resumes after this plan lands
- Any plan 018 work
- Changing any facade, adapter, or test logic
- Committing `gentleman-guardian-angel/`, `fix_*.js`, `fix_tests*.js`,
  `test_backslash.js`, `test_crypto.mjs`, `test_sha256.mjs`, `test-cp1252.js`
  (junk from prior agent iterations — leave untracked; if any are needed,
  they'll surface as broken tests)
- Committing `openspec/`, `pnpm-workspace.yaml`, `rescript-mcp/.nvmrc`,
  `rescript-mcp/rescript.json`, `rescript-mcp/pnpm-workspace.yaml`,
  `rescript-mcp/tsconfig.mjs.json`, `rescript-mcp/.npmrc`,
  `rescript-mcp/scripts/`, `rescript-mcp/parity/` — these are NOT source;
  they are tooling/parity artifacts and should stay untracked or be a
  separate repo-state plan
- The `.atl/` cache files
- Opening PRs (orchestrator's job)

## Git workflow

- Branch: `rescript/021-housekeeping` (off `8b190f1`)
- 3 commits expected:
  1. `chore(repo): catch-up untracked source + test files`
  2. `fix(rescript): register TsBridge/Winax/JsCom in Bindings aggregator; register Facade in Services aggregator`
  3. `fix(rescript-odbc): use dynamic import() in _importOdbc to fix Odbc.import is not a function`

## Steps

### Step 1: Catch-up commit (untracked critical files)

Identify and commit the critical source/test files only. The list to commit
(verified present on disk and referenced by the build):

```
rescript-mcp/src/Adapters/ComDbProps.res
rescript-mcp/src/Adapters/ComDbProps.resi
rescript-mcp/src/Adapters/ComInterfaces.res
rescript-mcp/src/Adapters/ComInterfaces.resi
rescript-mcp/src/Adapters/ComSession.res
rescript-mcp/src/Adapters/ComSession.resi
rescript-mcp/src/Adapters/ComUi.res
rescript-mcp/src/Adapters/ComUi.resi
rescript-mcp/src/Adapters/ComVba.res
rescript-mcp/src/Adapters/ComVba.resi
rescript-mcp/src/Adapters/TrustedLocations.res
rescript-mcp/src/Adapters/TrustedLocations.resi
rescript-mcp/src/Bindings/JsCom.res
rescript-mcp/src/Bindings/TsBridge.res
rescript-mcp/src/Bindings/Winax.res
rescript-mcp/src/Bindings/Winax.resi
rescript-mcp/src/Config.res
rescript-mcp/src/Errors.res
rescript-mcp/src/Js/                 (whole directory — contents listed below)
rescript-mcp/src/Logging.res
rescript-mcp/src/PathGuard.res
rescript-mcp/src/Services/BackendSelector.res
rescript-mcp/src/Services/ConnectionPool.res
rescript-mcp/src/Services/Facade.res
rescript-mcp/test/BackendSelectorTest.res
rescript-mcp/test/ComDbPropsTest.res
rescript-mcp/test/ComSessionTest.res
rescript-mcp/test/ComUiTest.res
rescript-mcp/test/ComVbaTest.res
rescript-mcp/test/ConfigTest.res
rescript-mcp/test/ConnectionPoolTest.res
rescript-mcp/test/FacadeTest.res
rescript-mcp/test/Fakes.res
rescript-mcp/test/FakesTest.res
rescript-mcp/test/JsBridgeTest.res
rescript-mcp/test/PathGuardTest.res
rescript-mcp/test/WinaxTest.res
```

Inspect `rescript-mcp/src/Js/` first — list its contents and commit each
`.mts` / `.mjs` / `.d.ts` file present.

DO commit these as ONE atomic commit (a single catch-up; do NOT split per
module — the aggregator fix in step 2 needs them all present at once).

### Step 2: Aggregator fixes

After step 1, edit ONLY these two files:

- `rescript-mcp/src/Bindings.res`: append
  ```rescript
  module TsBridge = TsBridge
  module Winax = Winax
  module JsCom = JsCom
  ```
  (in alphabetical order; preserve existing `module Odbc = Odbc` line)

- `rescript-mcp/src/Services.res`: append
  ```rescript
  module Facade = Facade
  ```
  (preserve existing lines)

Verify: `pnpm -C rescript-mcp build` no longer reports "module or file
can't be found" for any Bindings.* or Services.* reference.

### Step 3: `_importOdbc` bug fix (strict TDD)

The bug: `external _importOdbc: unit => Promise.t<dict<odbcModule>> = "import"`
compiles to `Odbc.import()` — a method call that doesn't exist.

**RED (write first)**: `rescript-mcp/test/OdbcImportDynamicTest.res` —
a new test that exercises the `_importOdbc` path. Simplest form: call
`Bindings.Odbc.connect("DBQ=...path...")` against a known-non-existent
path and assert it returns `Error` (not throws). This will fail under
the current bug with `TypeError: Odbc.import is not a function`.

```rescript
testAsync("_importOdbc: dynamic import resolves without throwing TypeError", cb => {
  // Use a path that cannot exist so the connect promise resolves (not hangs)
  Bindings.Odbc.connect("DBQ=C:\\nonexistent\\notreal.accdb")
    ->Promise.then(r => {
      switch r {
      | Ok(_) | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, true, true)
          cb(~planned=1, ())
        }
      }
      Promise.resolve()
    })
    ->Promise.catch(_e => {
      // Currently the bug throws TypeError before the connect call returns;
      // after the fix, this catch should never fire (the inner Promise resolves).
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})
```

**GREEN**: edit `rescript-mcp/src/Bindings/Odbc.res` line 129 area.
Replace the broken external with a function that uses JS dynamic `import()`:

```rescript
// _importOdbc — dynamic-import the odbc package as a JS Promise.
// Was previously `external ... = "import"` which compiled to
// `Odbc.import()` (a method call that does not exist on the odbc CJS
// namespace). Replaced with a typed %raw wrapper that uses real JS
// `import("odbc")`.

let _importOdbc: unit => Promise.t<dict<odbcModule>> = () => {
  %raw("(p) => import(p)")("odbc")->Promise.resolve
}
```

(If `Promise.resolve` shape differs, mirror the convention used elsewhere
in the file — search for similar `%raw`-based dynamic imports in the
repo's existing code. If unsure, the simplest possible fix that makes the
red test green is acceptable; do NOT redesign the type.)

If the fix requires more than ~5 lines of changes, STOP and report.

**VERIFY**: full suite → 553+/553/0 (the new test passes; all 553 prior
tests still pass — including test 482/576 `connect missing file` which
previously crashed).

### Step 4: Done criteria + finalization

- `pnpm -C rescript-mcp build` exits 0 against a fresh tree
  (`rescript clean && rescript build`)
- `pnpm -C rescript-mcp test` exits 0 with 553+/553/0 (or better)
- `git status` shows ONLY the intended housekeeping changes
- 3 commits land on `rescript/021-housekeeping`
- `plans/README.md` row 021 → DONE

## Test plan

- New RED test in step 3 must pass after the fix
- Full suite must remain at 553/553/0 (no new failures introduced)
- Build must succeed against a fresh `rescript clean`

## STOP conditions

- A catch-up file is referenced by code that requires a config file
  that's also untracked but missing (e.g. `rescript-mcp/.npmrc`,
  `pnpm-workspace.yaml`, `tsconfig.mjs.json`). Don't commit those — they
  are tooling config, not source. If the build needs them, the catch-up
  file must depend on existing infra. Report.
- The `_importOdbc` fix needs >5 lines or a redesign → STOP; this is
  out of plan 021 scope (it's a follow-up).
- After step 1 + 2, the build fails with errors NOT covered by the
  aggregator fix → STOP and report; do NOT scope-creep.
- The suite has FEWER passes than 553 → STOP; the fix introduced a
  regression. Revert step 3 only.

## Maintenance notes

- After this plan lands, plan 015 apply resumes from commit `8b190f1`
  PLUS this branch (3 commits ahead). Update plan 015's dependency
  note if you rebase.
- Future plan cycles MUST start by verifying a fresh build succeeds
  before trusting prior cycle's suite claims.
- The catch-up commit is a one-time fix; subsequent cycles should commit
  files as they're created.
- The `_importOdbc` bug fix is a behavioral change (the import path
  now actually works); for any future work that depends on real ODBC
  connections, verify the new path end-to-end.