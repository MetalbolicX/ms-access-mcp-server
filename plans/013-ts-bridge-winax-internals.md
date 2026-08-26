# Plan 013: Move winax binding internals into a typed `.mts` module (optional)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: written against the WORKING TREE. Verify
> the "Current state" excerpts match live files. On a mismatch, STOP.

## Status

- **Priority**: P3 (optional finishing move)
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/012-ts-bridge-com-surface.md
- **Category**: tech-debt / migration
- **Planned at**: commit `256cd6b` (working tree), 2026-08-24

## Why this matters

After plan 012, the last non-ODBC `%raw` blocks live inside the winax
and odbc binding layers (`mod.Object`, `mod.cast`, `mod.invoke`, and the
CJS-default unwrap). Moving them into one typed `.mts` module makes the
binding layer fully compiler-checked and leaves `Winax.res` as pure
externals + the module-type contract used by every fake in the test
suite. This is optional: the current blocks are small, isolated, and
documented — do this plan only if the maintainer wants a `%raw`-free
binding layer.

## Current state

Bridge from plans 010–012 must be DONE. Baseline: build 0 warnings,
all tests pass.

Remaining binding-layer raw blocks:

```rescript
// src/Bindings/Winax.res:88 — CJS default-unwrap fallback
| None => %raw("m => m")(m)

// src/Bindings/Winax.res:125 — createObject
let obj: ComInterfaces.comObject = %raw("(mod, progid) => mod.Object(progid)")(rawMod, progid)

// src/Bindings/Winax.res:156 — property get via cast
let value: JSON.t = %raw("(mod, obj, prop) => mod.cast(obj, prop)")(rawMod, obj, property)

// src/Bindings/Winax.res:189 — method invoke + arg marshaling
let value: JSON.t = %raw("(mod, obj, method, args) => mod.invoke(obj, method, args)")(rawMod, obj, method, rawArgs)

// src/Bindings/Odbc.res:149 — same CJS default-unwrap fallback
| None => %raw("m => m")(m)
```

Key constraint — the lazy import seam: `Winax.res:42` does
`@module("winax") external _importWinax: unit => Promise.t<dict<JSON.t>> = "import"`.
Unit tests inject fake modules through this seam via duck-typed JS
objects (`WinaxTest.res`, 286 tests). Whatever moves to `.mts` MUST keep
receiving the already-imported `mod` object as a parameter — the `.mts`
module must never import winax itself, or the fake-injection seam dies.

Variant marshaling (if you also move `toVariant` marshaling, optional
sub-step): the compiled JS representation of
`ComInterfaces.variant` constructors is defined by what
`src/Adapters/ComInterfaces.res` emits — DISCOVER it by reading
`src/Adapters/ComInterfaces.res.mjs` (in-source output) before typing
anything. Only type what you can verify there.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| TS check | `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0, 0 warnings |
| Tests | `pnpm -C rescript-mcp test` | all pass (WinaxTest is the gate) |
| COM gate | `$env:ACCESS_TEST_DB="D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb"; pnpm -C rescript-mcp test:com` | pass or clean skip |

## Scope

**In scope**:
- `rescript-mcp/src/Js/winaxBinding.mts` (create)
- `rescript-mcp/src/Bindings/Winax.res` (replace the 4 listed blocks)
- `rescript-mcp/src/Bindings/Odbc.res` (replace line 149 fallback only)

**Out of scope**:
- `Winax.resi` / the `WINAX_BINDING` module type — the public seam
  stays byte-identical.
- The lazy `@module("winax")` import seam (see constraint above).
- ODBC-side raws beyond line 149.

## Git workflow

- Branch: `rescript/013-ts-winax-internals`.
- Conventional commits, e.g. `refactor(rescript): type winax dispatch internals via winaxBinding.mts`.

## Steps

### Step 1: Create `src/Js/winaxBinding.mts`

```ts
// Typed wrappers over the dynamically-imported winax module object.
// The `mod` parameter is ALWAYS the injected module (real or fake) —
// this module must never import winax directly (fake-injection seam).

export interface WinaxModule {
  Object(progid: string): unknown
  cast(obj: unknown, prop: string): unknown
  invoke(obj: unknown, method: string, args: unknown[]): unknown
}

export function unwrapDefault(m: Record<string, unknown>): unknown {
  return "default" in m ? m.default : m
}
export function createObject(mod: WinaxModule, progid: string): unknown {
  return mod.Object(progid)
}
export function getProperty(mod: WinaxModule, obj: unknown, prop: string): unknown {
  return mod.cast(obj, prop)
}
export function invokeMethod(mod: WinaxModule, obj: unknown, method: string, args: unknown[]): unknown {
  return mod.invoke(obj, method, args)
}
```

`WinaxModule` typing accepts fakes structurally (duck typing), which is
exactly how the tests inject them.

**Verify**: `tsc -p tsconfig.mjs.json` exit 0.

### Step 2: Bind and swap `Winax.res` blocks (88, 125, 156, 189)

Add externals in `src/Bindings/TsBridge.res` (or a small
`src/Bindings/JsWinax.res`) pointing at `../Js/winaxBinding.mjs`; map
`unknown` returns to the existing ReScript types exactly as the raws did
(`comObject`, `JSON.t`) — the external IS the trusted cast point now,
one line, documented, instead of scattered raws.

**Verify**: build 0 warnings; `pnpm -C rescript-mcp test` all pass —
WinaxTest's 286 fake-driven tests are the gate.

### Step 3: Swap the `Odbc.res:149` unwrap fallback

Same `unwrapDefault` external.

**Verify**: build 0 warnings; all tests pass.

### Step 4: Final raw inventory + COM gate

**Verify**: `rg -n "%raw" rescript-mcp/src -g "*.res"` → binding layer
clean; remaining raws are only the two documented `toComObject`/
`_toComObject` casts and the deferred ODBC-side files. Run the COM gate
if Windows+Access is available; record pass or clean skip.

## Test plan

- No new tests: WinaxTest (286 tests) already drives every binding path
  through fakes; Odbc tests cover the unwrap fallback.
- COM gate validates the real winax module on Windows.

## Done criteria

- [ ] `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` exits 0
- [ ] `pnpm -C rescript-mcp build` exits 0, 0 warnings
- [ ] `pnpm -C rescript-mcp test` all pass
- [ ] `rg -n "%raw"` — Winax.res / Odbc.res binding internals gone
- [ ] `Winax.resi` byte-identical to pre-plan (`git diff` empty for it)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any WinaxTest failure after the swap — the seam or marshaling
  changed; one fix attempt, then report.
- You find yourself typing the winax module beyond `Object`/`cast`/
  `invoke` — the live binding uses only those; anything more is drift.
- If attempting the optional variant-marshaling sub-step and
  `ComInterfaces.res.mjs` shows a representation the TS types cannot
  express without lying — drop that sub-step, keep the rest.

## Maintenance notes

- The externals' return casts (`unknown` → `comObject`/`JSON.t`) are now
  the single documented trust point for winax values — keep them
  consolidated there.
- ODBC-side files (`OdbcAdapter.res` ~17 raws, `SqlBuilder.res` ~11,
  `OdbcSchemaReader.res` 2) remain the long tail; the same `.mts`
  pattern applies when prioritized.
