# Plan 019: Convert parity harness from `.mjs` to TypeScript (test-infra upgrade)

> **Amendment (2026-08-28)**: Branch cuts from current `main`, NOT from
> `rescript/007-parity-harness@e2e206f` — that branch was consolidated to
> `main` by plan 024 (`bf8f9d0` merge). Parity baseline on current `main`
> is `17 matched / 0 mismatched / 0 errored` (F-001..F-008 parity fixes
> landed on `rescript/fix-parity-findings`), NOT the plan's stale
> `9 matched / 7 mismatched / 1 errored`. Mutation-test gate must still
> prove detection by mutating a CURRENT behavioral seam (the plan's
> `Facade.res:327` site is stale; the executor must identify a current
> seam that flips a parity case and document it in the commit).

> **Executor instructions**: This plan converts `.mjs` files in
> `rescript-mcp/parity/` to `.ts` and wires `tsc` into the build.
> Behavior is preserved: same JSON envelopes, same mutation-test
> detection, same fixtures, same per-case env. NO product code changes.
> When done, update this plan's status row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git status` must be clean (ignore `rescript-mcp/test/mjs_list.txt`
> and any untracked fixture file under `tests/integration/fixtures/`).
> `git log -1 --oneline` on the working branch must be `e2e206f`
> (option-(a) JSON Schema lint landed) or later on
> `rescript/007-parity-harness`. Branch cuts from there.
> If `main` is ahead of `e2e206f` with non-trivial changes, STOP and
> report — plan 007's branch chain may need rebase.

## Status

- **Priority**: P2 (production-grade test infra, but not blocking parity
  coverage — the harness already works)
- **Effort**: S
- **Risk**: MED — a botched conversion can break the green parity
  harness and the mutation test. Convert one file at a time, gate each
  step with a fresh `pnpm parity` run.
- **Depends on**: plan 007 (parity harness shipped at
  `rescript/007-parity-harness` `fc6f5f7`); plan 019 option (a)
  (`e2e206f`, JSON Schema lint landed)
- **Category**: tests (verification infra upgrade)
- **Methodology**: NEITHER — behavior-preserving tooling upgrade; no new
  product behavior, no new contract. The existing mutation test (plan
  007 Step 5) is the gate for each step.
- **Planned at**: branch `rescript/007-parity-harness` `e2e206f`,
  2026-08-26

## Why this matters

The parity harness is now production verification infrastructure: it
gates every future change to either implementation. Its case files
already carry a JSON Schema (option a, `e2e206f`), so the static surface
is type-safe. The harness CODE itself is not — a rename of
`caseObj.mutating` to `caseObj.isMutating` would silently pass `undefined`
at runtime. The user explicitly asked for type safety here after
reviewing the `.mjs` choice in the original plan 007 text.

## Current state (verified 2026-08-26 on `e2e206f`)

- `rescript-mcp/parity/` contains four files:
  - `run.mjs` (273 lines) — orchestrator: spawns Python and ReScript
    children, copies fixtures per side for mutating cases, normalizes,
    differs, prints summary, exits non-zero on mismatch.
  - `runRescript.mjs` (~280 lines) — ReScript child: dynamic-imports
    compiled `Services/Facade.res` via `Composition.realFactory`,
    dispatches per-operation, prints envelope JSON.
  - `normalize.mjs` (~170 lines) — shared normalizer: key sort, int-
    valued-float canonicalization, Windows-path normalization, float
    tolerance 1e-9 for non-int-valued floats, ISO timestamps, structural
    differ.
  - `lint-cases.mjs` (~70 lines) — JSON Schema validator (ajv). Stays
    `.mjs` — no benefit to converting it.
- `rescript-mcp/scripts/parity_driver.py` (~430 lines) — Python child.
  Untouched by this plan unless the executor chooses to add mypy as an
  optional follow-up step.
- `rescript-mcp/package.json` has `"parity": "node parity/run.mjs"`.
- No `tsconfig.json` anywhere in the repo.
- No `typescript` or `@types/node` in `devDependencies` (only `ajv` and
  `rescript-test`).
- The mutation test (plan 007 Step 5) currently proves detection by
  renaming a field in `Facade.res:327` and observing `pnpm parity`
  flip `list_connections.json` from PASS to FAIL.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install TS toolchain | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && pnpm add -D typescript @types/node --ignore-scripts"` | exit 0 |
| Compile parity TS | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && pnpm build:parity"` | exit 0 |
| Run parity on compiled JS | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && pnpm parity"` | `N cases, 9 matched, 7 mismatched, 1 errored` (same baseline as `fc6f5f7`) |
| Verify mutation test still works | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"`, edit `Facade.res:327`, rebuild, `pnpm parity`, revert | One previously-PASS case flips to FAIL |

## Suggested executor toolkit

- Hand-written `.d.ts` shim at `parity/types/facade.d.ts` covering the
  17 facade ops parity uses (NOT a generator — ReScript→TS type emit
  tooling is brittle and would couple the harness to the ReScript
  compiler's internal AST).
- `tsc --noEmit` after each conversion as a fast type-check before
  re-running the slower `pnpm parity`.
- Mutation test runs unchanged. Do NOT change the `list_connections.json`
  case file — same mutation site in `Facade.res:327`.

## Scope

**In scope**:
- `rescript-mcp/parity/tsconfig.json` (new)
- `rescript-mcp/parity/types/facade.d.ts` (new) — hand-written type
  shim for the ReScript facade dynamic import.
- `rescript-mcp/parity/normalize.mjs` → `normalize.ts`
- `rescript-mcp/parity/run.mjs` → `run.ts`
- `rescript-mcp/parity/runRescript.mjs` → `runRescript.ts`
- `rescript-mcp/package.json` — add `typescript`, `@types/node` to
  devDeps; add `build:parity` script; update `parity` to run compiled
  JS, not source TS.
- `rescript-mcp/parity/README.md` — update run instructions.
- `rescript-mcp/parity/findings.md` — note "parity converted to TS,
  baseline re-verified" in the change history block.

**Out of scope**:
- `rescript-mcp/parity/lint-cases.mjs` (stays `.mjs` — pure JSON-only).
- `rescript-mcp/scripts/parity_driver.py` (Python side — see optional
  follow-up note in Maintenance below).
- Any product code (`src/`, `rescript-mcp/src/`, `rescript-mcp/test/`).
- Any of the 7 ReScript bugs surfaced by the harness (007-F-001..006).
- Plan 008+ work.

## Git workflow

- Branch: cut from `rescript/007-parity-harness` at `e2e206f`, named
  `rescript/019-typescript-parity`.
- Conventional commits, one per step. Do NOT rebase after Step 1 lands
  if `e2e206f` advances (resolve with merge, not rebase, to keep the
  linear baseline visible).

## Steps

### Step 1: tsconfig.json + toolchain

- Add `rescript-mcp/parity/tsconfig.json`:
  - `compilerOptions.target`: `ES2024`
  - `compilerOptions.module`: `NodeNext`
  - `compilerOptions.moduleResolution`: `NodeNext`
  - `compilerOptions.strict`: `true`
  - `compilerOptions.noImplicitAny`: `true`
  - `compilerOptions.outDir`: `./dist`
  - `compilerOptions.rootDir`: `./`
  - `compilerOptions.types`: `["node"]`
  - `include`: `["normalize.ts", "run.ts", "runRescript.ts", "types/**/*.d.ts"]`
  - `exclude`: `["dist", "node_modules", "cases"]`
- `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && pnpm add -D typescript @types/node --ignore-scripts"`.
- Verify `node_modules/.bin/tsc --version` reports the installed version.

**Verify**: `pnpm build:parity` (script below) compiles an empty `dist/` → exit 0.

### Step 2: facade.d.ts shim

- Hand-write `rescript-mcp/parity/types/facade.d.ts` covering only the
  17 ops parity uses:
  - Each op as a function type matching `Facade.connectAccess`,
    `Facade.disconnectAccess`, `Facade.queryData`, etc., per the live
    `rescript-mcp/src/Services/Facade.res` signatures at `e2e206f`.
  - The `Facade.binding` type as `unknown` (the harness does not
    inspect binding internals — it only invokes methods on it). Tighten
    this only if the conversion surfaces a need.
  - The `Composition.realFactory` export as a function returning a
    `Promise<unknown>` (the binding).
  - `JSON.t` enum as a TypeScript discriminated union mirroring the
    runtime encoding documented at `runRescript.mjs:38-58`:
    `{ TAG: "Null" } | { TAG: "String", _0: string } | { TAG: "Number", _0: number } | { TAG: "Boolean", _0: boolean } | { TAG: "Object", _0: Record<string, JSON.t> } | { TAG: "Array", _0: JSON.t[] }`.
- Document in the .d.ts file header: "Hand-maintained. When facade ops
  change, update this shim. We deliberately do NOT use a generator
  from `.resi` because ReScript→TS type emission is not stable."

**Verify**: `tsc --noEmit` reports zero errors with this shim alone.

### Step 3: Convert `normalize.mjs` → `normalize.ts`

- Add types to all function signatures.
- Replace `let d = null` and reassignment patterns with proper return
  types.
- The differ return type is `{path: string, expected: unknown, actual: unknown} | null`.

**Verify**:
- `pnpm build:parity` exit 0.
- `pnpm parity` reports the same baseline as `e2e206f` (9 matched /
  7 mismatched / 1 errored) — `normalize.ts` is functionally identical
  to `normalize.mjs`.

### Step 4: Convert `run.mjs` → `run.ts`

- Add types to the `runChild`, fixture-copy, env-pinning, and main
  loop logic.
- The `caseObj` parsed from JSON: use the `CaseFile` type derived from
  `cases.schema.json` (declare a minimal hand-rolled TS interface
  matching the schema; do NOT auto-derive from JSON Schema — that would
  require a code generator).
- `child_process.spawnSync` returns typed `SpawnSyncReturns<string>` —
  no change to logic, just types.

**Verify**:
- `tsc --noEmit` zero errors.
- `pnpm build:parity` exit 0.
- `pnpm parity` baseline preserved.
- Mutation test on `Facade.res:327` still flips `list_connections.json`.

### Step 5: Convert `runRescript.mjs` → `runRescript.ts`

- Add types. The dynamic-import types resolve through the `facade.d.ts`
  shim.
- The `jsToJsonT` / `jsToJsonDict` helpers gain explicit return types.
- The `lifecycle: Set<string>` literal can stay literal-typed.

**Verify**:
- `tsc --noEmit` zero errors.
- `pnpm build:parity` exit 0.
- `pnpm parity` baseline preserved.
- Mutation test still detects.

### Step 6: Wire package.json + README

- `"build:parity": "tsc -p parity/tsconfig.json"` in `scripts`.
- Update `"parity": "node parity/run.mjs"` → `"parity": "node parity/dist/run.js"`.
- Update `parity/README.md` run section to add `pnpm build:parity`
  before `pnpm parity`.

**Verify**: `pnpm parity` from a clean checkout (after `pnpm install`)
runs end-to-end with no source-`.mjs` lookup.

### Step 7: Update `findings.md`

- Append a one-line note to `parity/findings.md`'s change history:
  `parity harness converted .mjs → .ts at <commit-sha>; baseline
  re-verified, mutation test re-proven`.

**Verify**: `git log` shows the commit with the note.

## Test plan

- `pnpm build:parity` exits 0 from a clean checkout.
- `pnpm parity` reproduces the `e2e206f` baseline (9 matched /
  7 mismatched / 1 errored).
- Mutation test (plan 007 Step 5) still detects the field rename.
- `tsc --noEmit` zero errors against the new tsconfig.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] All four `.mjs` → `.ts` conversions land (normalize, run,
      runRescript; lint-cases intentionally stays `.mjs`).
- [ ] `parity/tsconfig.json` exists with strict mode.
- [ ] `parity/types/facade.d.ts` exists with hand-maintained header.
- [ ] `pnpm build:parity` exits 0.
- [ ] `pnpm parity` reproduces the `e2e206f` baseline (9 matched /
      7 mismatched / 1 errored).
- [ ] Mutation test still detects the injected mismatch.
- [ ] `plans/README.md` row 019 → DONE.

## STOP conditions

- `tsc --noEmit` reports > 5 errors on Step 1's tsconfig → STOP; the
  tsconfig is over- or under-constrained. Re-read this plan, narrow
  the `include` to just the three `.ts` files, re-run.
- `pnpm parity` baseline drifts (mismatched count changes) at any
  step → STOP; the conversion changed behavior. Revert, re-derive
  the type signature, retry.
- `facade.d.ts` shim requires more than 50 lines to type the dynamic
  import → STOP and report. The harness may need an architectural
  rethink (likely: introduce a thin ReScript→TS bridge in
  `rescript-mcp/src/Bindings/`, which is its own plan).
- Plan 007's branch chain advances past `e2e206f` mid-execution → STOP,
  rebase or merge, re-run the mutation test on the new baseline.

## Maintenance notes

- The `.d.ts` shim is hand-maintained. When a facade op is added (plan
  008+), update `parity/types/facade.d.ts` in the same commit that
  updates `rescript-mcp/src/Services/Facade.res`. The README of plan
  008 should call this out.
- The mutation test (plan 007 Step 5) keeps working because the `.d.ts`
  shim is hand-written and does NOT auto-regenerate when `Facade.res`
  changes. If a future plan introduces a `.d.ts` generator, the
  mutation test must be redesigned — likely by mutating the `.d.ts`
  itself instead of `Facade.res`.
- **Optional follow-up (out of scope for this plan)**: add `mypy`
  strict mode to `rescript-mcp/scripts/parity_driver.py`. Symmetric
  rationale — the Python driver has the same drift surface as the JS
  side. Scope: add `mypy.ini`, install `mypy`, gate it on the same
  hygiene check. Could become plan 020 if the user wants it.
- Per repo rule #8 (plan authoring standard), grep gates should specify
  intent. This plan's "no `.mjs` in parity/" gate means "no `.mjs`
  files that are part of the parity runner surface" — `lint-cases.mjs`
  is an exception (no types benefit) and `cases.schema.json` is not a
  script.