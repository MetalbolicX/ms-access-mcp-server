# Plan 030: Make the winax binding actually load and dispatch real COM calls

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 2a57922..HEAD -- rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Js/winaxBinding.mjs rescript-mcp/src/Js/winaxBinding.mts rescript-mcp/test/ComIntegrationTest.res`
> If any of those files changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P0 (blocks the real-COM acceptance of plan 029 and all plans 031+)
- **Effort**: S
- **Risk**: LOW–MED (runtime semantics were verified live on this machine; see Current state)
- **Depends on**: plans/029-com-verification-debt.md (DONE, tip `2a57922`)
- **Category**: bug
- **Planned at**: commit `2a57922`, 2026-08-31

## Why this matters

Every real-COM call in the ReScript server throws `TypeError: Winax.import is
not a function`. The COM layer looks implemented (~25 capabilities) but none of
it has ever executed against real Access — plan 029's integration suite had to
skip, so its "real-COM proof" acceptance never ran. Two independent defects
hide behind that one crash: (1) the module loader calls a nonexistent winax
export, and (2) the bridge layer uses `winax.cast` (a variant-type converter)
as a property getter and `winax.invoke` (which does not exist) for method
calls. Fixing all three makes plan 029's 7-test live suite actually run, and
gives plans 031–034 working primitives.

## Current state

All facts below verified on this machine at `2a57922` (2026-08-31).

### Defect 1 — loader: `rescript-mcp/src/Bindings/Winax.res:45-46`

```rescript
@module("winax")
external _importWinax: unit => Promise.t<dict<JSON.t>> = "import"
```

This compiles to `Winax.import()` — a **named export** that does not exist.
winax 3.6.9's namespace (live probe: `import("winax")` → keys `default`,
`module.exports`; the real exports live on `.default`): `Object, cast, release,
getConnectionPoints, peekAndDispatchMessages, Variant, winaxsleep`. There is no
`import` and no `invoke`.

**The proven fix pattern already exists in this repo** — `Bindings/Odbc.res:100-109`
documents the identical bug and its fix:

```rescript
// _importOdbc — dynamic-import the odbc package as a JS Promise.
// Was previously `external ... = "import"` which compiled to
// `Odbc.import()` (a method call that does not exist on the odbc CJS
// module). The %raw escape hatch delegates to a real dynamic
// `import("odbc")`.
let _importOdbc: unit => Promise.t<dict<odbcModule>> = () => {
  %raw("(p) => import(p)")("odbc")->Promise.resolve
}
```

Copy this pattern verbatim for winax. Do not "improve" it — it runs in
production for ODBC today.

### Defects 2a/2b — bridge semantics: `rescript-mcp/src/Js/winaxBinding.mjs`

```js
export const getProperty = (mod, obj, prop) => mod.cast(obj, prop);        // WRONG
export const invokeMethod = (mod, obj, method, args) => mod.invoke(obj, method, args); // WRONG (no such export)
export const invokeReturningObject = (mod, obj, method, args) => mod.invoke(obj, method, args); // WRONG
export const createObject = (mod, progid) => mod.Object(progid);           // correct
export const setProperty = (mod, obj, prop, value) => { (obj)[prop] = value }; // correct
export const release = (mod, obj) => { if (typeof mod.release === "function") mod.release(obj); }; // correct
export const unwrapModule = (mod) => unwrapCjsDefault(mod);                // correct
```

`winax.cast(value, type)` converts a Variant to a `VariantType` string
(`'int'`, `'string'`, …) — it is NOT property access. And `mod.invoke` does
not exist. The `.mts` twin (`src/Js/winaxBinding.mts`) declares the same
wrong shapes in its `WinaxModule` interface (`cast`/`invoke` members).

### Verified winax proxy semantics (live probe, this machine, 2026-08-31)

Ran a throwaway Node script against the installed winax + real Access:

| Operation | Form used | Result |
|---|---|---|
| Load module | `import("winax")` → `.default` | keys: `Object, cast, release, …, Variant` |
| Create | `W.Object("Access.Application")` (no `new`) | OK — `typeof app === "function"` (proxy) |
| Property write | `app.Visible = false` | OK |
| Property read | `app["Name"]`, `app["Version"]` | `"Microsoft Access"`, `"16.0"` |
| Object-returning property | `app["DBEngine"]` | returns a COM proxy (typeof function) |
| Method call | `app.Quit()` — direct, no helper | OK |
| Release | `W.release(app)` | OK; MSACCESS.EXE exits on its own **~2–3 s after Quit** (a check 1.5 s after Quit still saw the process; it was gone by +3 s) |

So: **property access is bracket/dot access on the proxy; method invocation is
a direct call on the proxy.** No `cast`/`invoke` helpers involved.

### Consumers that must keep working unchanged

`Bindings/TsBridge.res:83-102` binds each bridge function via
`@module("../Js/winaxBinding.mjs")` with signatures like
`winaxGetProperty: (JSON.t, 'a, string) => JSON.t`. **Keep every external
signature as-is** — only the `.mjs`/`.mts` bodies change (the `mod` first
parameter stays in the signatures and is simply unused by the fixed bodies;
note it in a comment). `Bindings/Winax.res:40-281` (`WINAX_BINDING`) calls
`_importWinax` → `TsBridge.unwrapWinaxModule` → the bridge functions; its
logic is otherwise correct and stays untouched. `Winax.resi` needs no change.

### The acceptance suite: `rescript-mcp/test/ComIntegrationTest.res`

7 probe-gated tests committed in plan 029 (`9a01c91`). Today the probe
(ComIntegrationTest.res:19-48) catches every error and prints
`ComIntegrationTest: skipped (Access unavailable)`, because `createObject`
throws synchronously. After this plan, on this machine the suite must RUN and
PASS — a skip here means this plan failed. (Known weakness, out of scope: the
probe cannot distinguish "no Access" from "binding regressed" on OTHER
machines; recorded in Maintenance notes.)

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Clean+rebuild | `pnpm -C rescript-mcp clean:all` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Full test | `pnpm -C rescript-mcp test` | all pass, `ComIntegration:` tests RUN (not "skipped") |
| Parity regression | `$env:ACCESS_TEST_ASSUME_ACE="1"; pnpm -C rescript-mcp parity:northwind` | 6 matched / 0 mismatched / 3 errored (unchanged) |
| Orphan check | `tasklist /FI "IMAGENAME eq MSACCESS.EXE"` | run AFTER 3+ s settle; expect no MSACCESS |

PowerShell syntax for env vars. Never bare npm/python/uv; `clean:all` only
(plain `rescript clean` breaks rescript-test's compiled output).

## Scope

**In scope** (the only files you should modify):
- `rescript-mcp/src/Bindings/Winax.res` — replace the `_importWinax` external (≈2 lines + comment)
- `rescript-mcp/src/Js/winaxBinding.mjs` — fix `getProperty`, `invokeMethod`, `invokeReturningObject` bodies
- `rescript-mcp/src/Js/winaxBinding.mts` — same fixes + correct the `WinaxModule` interface doc
- `plans/README.md` — status row 030

**Out of scope** (do NOT touch):
- `Bindings/TsBridge.res` and `Bindings/Winax.resi` — signatures unchanged
- `Bindings/Winax.res` logic beyond the loader (the `WINAX_BINDING` functions)
- `test/ComIntegrationTest.res` — it is the acceptance, not the fix
- `ComSession.res`, `ComDataAdapter.res`, anything under `src/ms_access_mcp/`
- No new tests, no refactor of the bridge file structure

## Git workflow

- Branch: `rescript/030-winax-binding-fix` from `2a57922`
- Commit 1: `fix(rescript-mcp): load winax via dynamic import and fix proxy property/method dispatch`
- Commit 2 (after README row update): `docs(plans): mark 030 done`
- Conventional commits, no AI attribution, no push, no PR. Never
  `git add -A` (untracked junk files at repo root).

## Steps

### Step 1: Fix the loader in `Winax.res`

Replace lines 45-46 (`@module("winax") external _importWinax … = "import"`)
with the Odbc.res pattern, keeping the same name/type and copying the
explanatory comment style:

```rescript
// _importWinax — dynamic-import the winax package as a JS Promise.
// Was `@module("winax") external … = "import"` which compiled to
// `Winax.import()` (a named export that does not exist on the winax CJS
// module). The %raw escape hatch delegates to a real dynamic
// `import("winax")`. Mirrors Bindings/Odbc.res (D11/REQ-D11).
let _importWinax: unit => Promise.t<dict<JSON.t>> = () => {
  %raw("(p) => import(p)")("winax")->Promise.resolve
}
```

**Verify**: `pnpm -C rescript-mcp build` → exit 0. (If the compiler rejects
`%raw` here for any reason, STOP — do not invent an alternative loader.)

### Step 2: Fix the bridge bodies in `winaxBinding.mjs` AND `.mts`

- `getProperty`: `(mod, obj, prop) => obj[prop]` (bracket access on the proxy; `mod` unused)
- `invokeMethod`: `(mod, obj, method, args) => obj[method](...args)`
- `invokeReturningObject`: identical body to `invokeMethod` (the difference is the documented return contract — raw COM proxy — and the ReScript-side type; keep both exports)
- Keep `createObject`, `setProperty`, `release`, `unwrapModule` exactly as they are
- In `.mts`: apply the same body fixes and shrink the `WinaxModule` interface to
  the members actually used (`Object`, `release`) — remove the wrong `cast`/`invoke`
  members. Keep all exported function signatures (`(mod: WinaxModule, …)`) unchanged.
- One-line comment at top of each fixed function: property/method access on
  winax proxies is direct; `winax.cast` is variant type-conversion, not property access.

**Verify**: `pnpm -C rescript-mcp build` → exit 0.

### Step 3: Run the real-COM acceptance

```
pnpm -C rescript-mcp clean:all
pnpm -C rescript-mcp test
```

**Verify**: output contains the 7 `ComIntegration:` tests **passing** — NOT
the line `ComIntegrationTest: skipped (Access unavailable)`. The money test:
`get(currentDb,"Name")` contains `test_db.accdb`. Wait 3+ seconds after the
suite, then `tasklist /FI "IMAGENAME eq MSACCESS.EXE"` → no MSACCESS process.

### Step 4: Regression sweep

```
$env:ACCESS_TEST_ASSUME_ACE="1"; pnpm -C rescript-mcp parity:northwind
git status --short
```

**Verify**: parity identical to pre-plan (6 matched / 0 mismatched / 3 errored —
COM stubs are plan 031+'s work); only in-scope files modified.

### Step 5: Closeout

Update `plans/README.md` row 030 → DONE (final SHA, test count, one-line note
that ComIntegration now runs live). Commit `docs(plans): mark 030 done`.

## Test plan

No new tests. The acceptance is plan 029's existing suite executing for real
for the first time: `test/ComIntegrationTest.res` (7 tests, probe-gated).
Secondary regression: the full 722-test suite and the parity baseline above.

## Done criteria

- [ ] `grep -n "external _importWinax" rescript-mcp/src/Bindings/Winax.res` → no matches
- [ ] `grep -n "mod.cast\|mod.invoke" rescript-mcp/src/Js/winaxBinding.mjs` → no matches
- [ ] `pnpm -C rescript-mcp build` exits 0 from clean (`clean:all`)
- [ ] `pnpm -C rescript-mcp test`: all pass; `ComIntegration:` tests RUN and PASS on this machine; suite count ≥ 722
- [ ] No MSACCESS.EXE process 3+ s after the suite
- [ ] Parity unchanged: 6 matched / 0 mismatched / 3 errored
- [ ] `TsBridge.res`, `Winax.resi`, `ComIntegrationTest.res` unmodified (`git diff --stat 2a57922..HEAD -- …` empty for them)
- [ ] `plans/README.md` row 030 updated; two conventional commits

## STOP conditions

- The "Current state" excerpts don't match the live code (drift).
- `import("winax")` via the `%raw` pattern fails at runtime (loader theory wrong on this Node/winax version).
- Live proxy behavior contradicts the verified semantics table (e.g. `obj[prop]` returns `undefined` for a string property that the Python side reads fine) — report the exact property/call, do not paper over it.
- Any `ComIntegration:` test hangs > 60 s (likely a blocked Access dialog — report which step).
- An MSACCESS.EXE process survives 10+ s after the suite ends (leak — report; do not blind-`taskkill` processes you didn't start).
- The fix appears to require touching any out-of-scope file.

## Maintenance notes

- For plans 031+ (executeQuery, schema reads, mutations, DDL): the sanctioned
  COM primitives are exactly `WINAX_BINDING` — `get`/`set` (bracket access),
  `invoke`/`invokeAsObject` (direct method call), `getCount`/`getItem`
  (built on get/`Item` method). Never call `winax.cast` for property access.
- Access teardown after `Quit()` takes ~2–3 s. Any test/orphan-check that
  samples sooner will produce false orphans.
- The integration suite's skip path treats every probe error as "Access
  unavailable". On machines WITHOUT Access a regressed binding would skip
  silently instead of failing. If that ever matters, narrow the skip to
  module-not-found class errors — deferred, not this plan.
- `WinaxModule` in `winaxBinding.mts` is deliberately minimal (`Object`,
  `release`). `unwrapModule`/`unwrapCjsDefault` handles the CJS `.default`
  unwrap — verified live (`import("winax")` exposes real exports only via
  `.default`).
- Plan 029's acceptance is retroactively satisfied by this plan: its 7-test
  suite running green IS the real-COM proof.
