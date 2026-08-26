# Plan 010: Add a strict TypeScript → `.mjs` bridge to the ReScript package

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: this plan was written against the WORKING
> TREE, not a commit — the `rescript-mcp/` COM sources are untracked at
> planning time. Verify the "Current state" excerpts below match the live
> files. On a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt / migration
- **Planned at**: commit `256cd6b` (working tree), 2026-08-24

## Why this matters

The ReScript port still uses ~71 `%raw` blocks (inline untyped JavaScript
strings) for runtime error extraction, Buffer codepage codecs, filesystem
helpers, and Access COM orchestration. `%raw` bypasses all type checking and
is the acknowledged last resort under the project's ReScript rules. This
plan establishes the sanctioned alternative — a strict TypeScript bridge:
`.mts` modules compiled to `.mjs`, imported from ReScript via typed
`@module` externals — and proves it end-to-end with one real module
(`exnMessage`). Plans 011–013 then migrate the remaining `%raw` blocks onto
this bridge.

## Current state

- Package: `rescript-mcp/` — pnpm, `"type": "module"`, Node >= 24
  (v24.19.0 installed), TypeScript NOT installed.
- `rescript-mcp/rescript.json` compiles ESM **in-source**:
  `{ "package-specs": [{ "module": "esmodule", "in-source": true }], "suffix": ".res.mjs" }`.
  Compiled `Foo.res.mjs` files land NEXT TO `Foo.res` under `src/`, so a
  `@module("../Js/x.mjs")` external in `src/Bindings/TsBridge.res` emits
  `import ... from "../Js/x.mjs"` which Node resolves to `src/Js/x.mjs`.
  This relative-`@module` pattern is the officially documented interop
  (ReScript manual, "Import a JavaScript Module As a Single Value").
- Build/test gates are green at planning time: `pnpm -C rescript-mcp build`
  → 0 warnings; `pnpm -C rescript-mcp test` → 419 tests / 605 assertions,
  all passing.
- Existing binding convention to match: `src/Bindings/Winax.res:42`
  uses `@module("winax")` with a lazy dynamic import; new `Js` bindings
  use plain static `@module` externals (no lazy import needed — helper
  modules are side-effect-free).
- `rescript-mcp/.npmrc` contains `onlyBuiltDependencies=odbc,winax` —
  installing pure-JS devDependencies will NOT trigger native rebuilds.
- The three identical inline raw error-extractors this plan replaces:

```rescript
// src/Bindings/Winax.res:50
let raw: option<string> = %raw("(e) => (e && e.message) ? String(e.message) : undefined")(e)
// src/Bindings/Odbc.res:129  — identical
// src/Adapters/ComVba.res:64 — identical, inside _exnMsg
```

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pnpm -C rescript-mcp install` | exit 0, no native builds |
| TS check | `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0, 0 warnings |
| Tests | `pnpm -C rescript-mcp test` | all pass (>= 419 tests) |
| Raw count | `rg -c "%raw" rescript-mcp/src -g "*.res"` | per-file counts |

## Scope

**In scope** (the only files you should modify or create):
- `rescript-mcp/package.json` (devDependencies + `build` script only)
- `rescript-mcp/tsconfig.mjs.json` (create)
- `rescript-mcp/.gitignore` (add emitted `.mjs` ignore)
- `rescript-mcp/src/Js/runtime.mts` (create)
- `rescript-mcp/src/Bindings/TsBridge.res` (create; `Js.res` conflicts with ReScript's built-in `Js` interface)
- `rescript-mcp/test/JsBridgeTest.res` (create)
- `rescript-mcp/src/Bindings/Winax.res` (replace lines ~50 helper only)
- `rescript-mcp/src/Bindings/Odbc.res` (replace lines ~129 helper only)
- `rescript-mcp/src/Adapters/ComVba.res` (replace `_exnMsg` body only)

**Out of scope** (do NOT touch):
- Any other `%raw` block (plans 011–013 own them).
- `rescript.json`, `.npmrc`, any Adapter file other than the single
  `_exnMsg` helper in ComVba.
- The `dev` script (watch mode keeps `rescript watch`; see Maintenance
  notes).

## Git workflow

- Branch: `rescript/010-ts-bridge` off the current working branch.
- Conventional commits, matching `git log` style, e.g.
  `build(rescript): add strict TypeScript .mts bridge toolchain` /
  `refactor(rescript): route exception-message extraction through Js bridge`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Install TypeScript toolchain

Add to `rescript-mcp/package.json` devDependencies:
`"typescript": "^5.9.0"`, `"@types/node": "^24"`.

**Verify**: `pnpm -C rescript-mcp install` → exit 0; `pnpm -C rescript-mcp exec tsc --version` → prints 5.x.

### Step 2: Create `rescript-mcp/tsconfig.mjs.json`

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "target": "es2022",
    "module": "nodenext",
    "moduleResolution": "nodenext",
    "skipLibCheck": true,
    "declaration": false,
    "sourceMap": false,
    "types": ["node"]
  },
  "include": ["src/Js/**/*.mts", "src/Js/types/**/*.d.ts"]
}
```

No `outDir`: `tsc` emits each `.mjs` beside its `.mts` source
(`src/Js/runtime.mts` → `src/Js/runtime.mjs`).

**Verify**: `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` → exit 0 (no inputs yet is fine — if tsc errors on zero inputs, proceed to Step 3 first and re-verify).

### Step 3: Create the pilot module `src/Js/runtime.mts`

```ts
// Shared runtime helpers that ReScript's type system cannot express
// without %raw. Keep every function pure and side-effect-free.

/** Extract a message from an unknown thrown value.
 *  Returns undefined when the value carries no usable message —
 *  callers map that to their own default ("Unknown error", "Unknown"). */
export function exnMessage(e: unknown): string | undefined {
  const anyE = e as { message?: unknown } | null | undefined
  return anyE && anyE.message ? String(anyE.message) : undefined
}
```

Semantics are byte-identical to the raw blocks it replaces
(`(e) => (e && e.message) ? String(e.message) : undefined`).

**Verify**: `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json` → exit 0 AND `rescript-mcp/src/Js/runtime.mjs` exists.

### Step 4: Chain the build script and ignore emitted files

- `package.json` scripts: `"build": "tsc -p tsconfig.mjs.json && rescript"`.
- `.gitignore` (create if absent): add `src/Js/*.mjs` and
  `src/Js/**/*.mjs` (emitted artifacts; the `.mts` sources are committed).

**Verify**: `pnpm -C rescript-mcp build` → exit 0, 0 warnings.

### Step 5: Create the ReScript shim `src/Bindings/TsBridge.res`

```rescript
// TsBridge.res — typed externals for src/Js/*.mjs (strict TypeScript bridge).
// Paths are relative to this file; with in-source ESM output they resolve
// to src/Js/*.mjs at runtime. ReScript `option<string>` matches the TS
// `string | undefined` return (None is undefined at runtime).
@module("../Js/runtime.mjs")
external exnMessage: exn => option<string> = "exnMessage"
```

**Verify**: `pnpm -C rescript-mcp build` → exit 0, 0 warnings
(if the module path is wrong the failure appears at test time as an ESM
resolution error — that is a STOP condition).

### Step 6: Replace the three inline raw extractors

In `Bindings/*`, replace the `%raw` extraction with `TsBridge.exnMessage(e)`;
in adapters, use `Bindings.TsBridge.exnMessage(e)`,
keeping the surrounding `switch ... | Some(m) => m | None => <existing
default>` shape exactly:

- `src/Bindings/Winax.res` — `exnMessage` helper (~line 49-55), default
  stays `"Unknown error"`.
- `src/Bindings/Odbc.res` — same helper (~line 128-133), same default.
- `src/Adapters/ComVba.res` — `_exnMsg` body (~line 62-66), default stays
  `"Unknown"`.

**Verify**: `rg -n "%raw" rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Bindings/Odbc.res rescript-mcp/src/Adapters/ComVba.res` → only ComVba line ~59 (`_toComObject`, out of scope) remains; build → exit 0.

### Step 7: Add bridge smoke test `test/JsBridgeTest.res`

Model imports/structure on `rescript-mcp/test/ComSessionTest.res`
(rescript-test `test` function). Cover:

1. `exnMessage(Js.Exn.raiseError("boom"))` — wait: `raiseError` raises;
   instead construct: catch a raised error, e.g.
   `try Js.Exn.raiseError("boom") catch { | Js.Error(e) => test exnMessage(e) == Some("boom") }`
   (match the exception-catch idiom already used in this repo's tests).
2. `exnMessage(Obj.trustedCasts? ...)`: non-Error value path — pass a
   string via a caught `Failure`-style raise or `raise(Not_found)`-like
   builtin and assert the result falls to the caller's `None` default
   (i.e. `exnMessage` itself returns `None` for values without `.message`).

**Verify**: `pnpm -C rescript-mcp test` → ALL pass, count grew by the new
tests (>= 420).

### Step 8: Full gate

**Verify**: `pnpm -C rescript-mcp build` → 0 warnings;
`pnpm -C rescript-mcp test` → all pass;
`rg -c "%raw" rescript-mcp/src -g "*.res"` → total dropped by exactly 3
(vs the planning-time inventory in Plan 011's table).

## Test plan

- New: `test/JsBridgeTest.res` — Error-message path + no-message path
  (cases listed in Step 7).
- Existing 419 tests are the regression gate: error-path tests in
  WinaxTest/ComVbaTest/Odbc tests exercise `exnMessage` through the fakes.
- Verification: `pnpm -C rescript-mcp test` → all pass.

## Done criteria

- [ ] `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` exits 0
- [ ] `pnpm -C rescript-mcp build` exits 0 with 0 warnings
- [ ] `pnpm -C rescript-mcp test` all pass (>= 420 tests)
- [ ] `rg -n "%raw"` shows Winax.res and Odbc.res error extractors gone
- [ ] `git status` shows no files modified outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any in-scope file's current content does not match the excerpts above
  (drift since planning).
- The `@module("../Js/runtime.mjs")` external fails to resolve at test
  runtime (ESM resolution error) — do not switch to absolute paths or
  copy hacks; report.
- TypeScript install triggers a native build attempt (winax/odbc) —
  report; do not remove `onlyBuiltDependencies`.
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- `pnpm dev` (`rescript watch`) does not watch `.mts` — after editing TS
  helpers, rerun `pnpm build` (tsc runs first). A `concurrently`-based
  watcher is deliberate YAGNI until it hurts.
- Every future `.mts` helper module goes in `src/Js/` with its externals
  in `src/Bindings/TsBridge.res` (or `JsCom.res` for COM, plan 012) — do not
  scatter `@module` externals across adapters.
- Plans 011/012/013 depend on the toolchain added here; they fail fast
  if this plan is not DONE.
