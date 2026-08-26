# Plan 012: Port the Access COM surface to typed `.mts` modules

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: written against the WORKING TREE (COM
> sources untracked at planning time). Verify the "Current state" excerpt
> inventory matches live files. On a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: plans/011-ts-bridge-pure-helpers.md (bridge pattern proven on pure helpers)
- **Category**: tech-debt / migration
- **Planned at**: commit `256cd6b` (working tree), 2026-08-24

## Why this matters

Twenty `%raw` blocks orchestrate the Access COM object model
(`DoCmd`, `Forms`, `Controls`, `Sections`, `SaveAsText`, DAO database
properties). They are the biggest and least-typed surface in the port:
one typo'd property name is invisible until it hits a real Access
instance. Hand-rolled TypeScript interfaces for exactly the members we
call make every call site compiler-checked while keeping the JS bodies
byte-identical. The 419-test suite (duck-typed fakes) pins behavior;
the real-COM gate (`test:com`) validates on Windows+Access.

## Current state

Bridge from plans 010–011 must be DONE (`src/Bindings/TsBridge.res` owns pure-helper externals). Baseline: build 0 warnings,
all tests pass.

The 20 COM raw blocks this plan owns (all take `app` — the live
`Access.Application` dispatch object — plus plain args, and return
JSON-able shapes):

**`ComUi.res` (15 blocks)** — save/load text ops and form/report/
control/section orchestration at lines: 256, 301 (SaveAsText /
LoadFromText via tmp files), 458, 514, 562, 593 (open/close/list/detail
forms + set property), 726, 782 (reports), 902, 955, 993, 1026
(controls: get/set property, create, delete), 1066, 1134, 1183
(sections: list/detail/set property).

**`ComDbProps.res` (5 blocks)** — lines: 483 (list DB properties via
`CurrentDb.Properties`), 634 (set DB property with type coercion),
703 (export module to text), 738 (`_tempSaveAsText`), 768
(`_tempLoadFromText`).

Execution-discovery discipline: before typing each block, READ ITS LIVE
BODY (`rg -n "%raw" rescript-mcp/src/Adapters/ComUi.res` etc.) — the
bodies enumerate exactly which Access members the interfaces must
declare. Do not type members from memory of the Access OM.

Existing seams to honor:

- `app` values cross the boundary as `ComInterfaces.comObject` (an
  opaque type; effectively untyped at the ReScript external — the REAL
  typing lives in the `.d.ts`). This is accepted and documented.
- Unit tests inject duck-typed JS fakes as `app` — TS types are
  compile-time only, so fakes keep working UNCHANGED.
- `toComObject` (`ComUi.res:151`) / `_toComObject` (`ComVba.res:59`)
  identity casts stay — they are the ReScript type-level boundary.
- COM gate: `ACCESS_TEST_DB=D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb pnpm -C rescript-mcp test:com` — Windows + MS Access 16 only; without it the runner skips cleanly (exit 0).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| TS check | `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0, 0 warnings |
| Tests | `pnpm -C rescript-mcp test` | all pass |
| COM gate | `$env:ACCESS_TEST_DB="D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb"; pnpm -C rescript-mcp test:com` | `COM integration passed` (or clean skip off-Windows) |
| Raw count | `rg -n "%raw" rescript-mcp/src -g "*.res"` | 20 blocks gone |

## Scope

**In scope**:
- `rescript-mcp/src/Js/types/access.d.ts` (create)
- `rescript-mcp/src/Js/accessUi.mts`, `src/Js/accessDbProps.mts` (create)
- `rescript-mcp/src/Bindings/JsCom.res` (create)
- `rescript-mcp/src/Adapters/ComUi.res` (only the 15 listed blocks)
- `rescript-mcp/src/Adapters/ComDbProps.res` (only the 5 listed blocks)

**Out of scope**:
- `ComVba.res` (its raws are already minimal: `_toComObject` stays;
  `_exnMsg` was handled in plan 010).
- Any behavior change to the ported blocks — bodies are verbatim.
- `Bindings/Winax.res` internals (plan 013).
- ODBC-side raws.

## Git workflow

- Branch: `rescript/012-ts-com-surface`.
- Conventional commits per batch, e.g.
  `refactor(rescript): port ComUi save/load text ops to typed accessUi.mts`.

## Steps

### Step 1: Write `src/Js/types/access.d.ts` (discovery-driven)

Read each of the 20 live raw bodies and declare ONLY the members they
call. Target shape (extend as discovery requires):

```ts
export interface AccessCollection<T> {
  Count: number
  Item(index: number): T
}
export interface DoCmd {
  RunCommand(cmd: number): void
  OpenForm(name: string, view?: number, filter?: string, where?: string): void
  Close(objectType: number, name: string, save?: number): void
  Save(objectType?: number, name?: string): void
  DeleteObject(objectType?: number, name?: string): void
}
export interface AccessProperty { Name: string; Value: unknown; Type: number }
export interface AccessForm { /* members discovered from blocks 458-593 */ }
export interface AccessControl { /* from blocks 902-1026 */ }
export interface AccessSection { /* from blocks 1066-1183 */ }
export interface AccessApp {
  DoCmd: DoCmd
  Forms: AccessCollection<AccessForm>
  Reports: AccessCollection<AccessForm>  // adjust per live bodies
  CurrentProject: { AllForms: AccessCollection<{ Name: string }>, AllReports: AccessCollection<{ Name: string }> }
  SaveAsText(objectType: number, name: string, path: string): void
  LoadFromText(objectType: number, name: string, path: string): void
  CurrentDb: { Properties: AccessCollection<AccessProperty> }
}
```

The interface above is a STARTING SKELETON — the live raw bodies are the
source of truth. Unknown-return members may be typed `unknown` and cast
at use inside `.mts` only where the raw body itself did runtime checks.

**Verify**: `tsc -p tsconfig.mjs.json --noEmit` exit 0 (d.ts parses; no
module imports it yet).

### Step 2: Create `src/Js/accessDbProps.mts` (smaller file first)

Port the 5 ComDbProps blocks as exported functions
(`app: AccessApp` first param, then the raw block's params, returning the
raw block's exact return shape). Copy each JS body VERBATIM from the raw
string; change only: replace untyped member access with the typed
interfaces, keep every try/catch, string literal, and sentinel value.

**Verify**: `tsc` exit 0; `pnpm -C rescript-mcp build` exit 0.

### Step 3: Bind and swap ComDbProps

Create `src/Bindings/JsCom.res` with
`@module("../Js/accessDbProps.mjs")` externals — param type for `app` is
`ComInterfaces.comObject`; other params/returns map per the plan 011
type table (`string`, `int`/`float`, `bool`, `array<...>`, `option<_>`
via `T | null/undefined`). Swap the 5 ComDbProps raw call sites to the
bound functions, keeping all surrounding promise/error flow identical.

**Verify**: `pnpm -C rescript-mcp build` → 0 warnings;
`pnpm -C rescript-mcp test` → all pass (ComDbProps tests are the gate).

### Step 4: Port `ComUi` in three batches, verify each

Create `src/Js/accessUi.mts` and port + bind + swap in batches, running
the full gate between batches:
1. Save/load text ops (blocks 256, 301).
2. Form + report ops (458, 514, 562, 593, 726, 782).
3. Control + section ops (902, 955, 993, 1026, 1066, 1134, 1183).

Add externals per batch. Same verbatim-body discipline; externals live
in `src/Bindings/JsCom.res`.

**Verify (after EACH batch)**: build → 0 warnings; test → all pass
(ComUiTest covers each operation against fakes).

### Step 5: COM gate + final inventory

Run the COM integration gate if Windows+Access is available; otherwise
record the clean skip. Then:

**Verify**: `rg -n "%raw" rescript-mcp/src -g "*.res"` → remaining raws
are exactly: ComVba `_toComObject`, ComUi `toComObject`, Winax/Odbc
binding internals (plan 013), and the deferred ODBC-side files.

## Test plan

- No new tests required — the port is behavior-preserving, gated by the
  existing ComUiTest / ComDbPropsTest suites against duck-typed fakes.
- If a batch breaks a fake test, the port is NOT verbatim — fix the
  port, never the test.
- COM gate on Windows validates member names against real Access 16.

## Done criteria

- [ ] `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` exits 0
- [ ] `pnpm -C rescript-mcp build` exits 0, 0 warnings
- [ ] `pnpm -C rescript-mcp test` all pass
- [ ] `rg -n "%raw"` shows all 20 COM blocks gone from ComUi/ComDbProps
- [ ] COM gate run (pass or documented clean skip)
- [ ] `git status` clean outside in-scope list; `plans/README.md` updated

## STOP conditions

- A live raw body diverges materially from its plan-table line (drift).
- Any fake-based test fails after a verbatim port — means the body was
  altered; one fix attempt, then report.
- `access.d.ts` grows members NOT called by any ported body (scope
  creep — stop typing aspirational API).
- A return shape cannot be typed without changing the JSON-able
  structure the adapters expect — report.

## Maintenance notes

- `access.d.ts` is OUR subset, not the Access OM — it grows only when
  new operations are ported. Reviewer: spot-check 3–4 ported bodies
  against their `git diff` predecessors for verbatim fidelity.
- The `app` param being opaque on the ReScript side is the accepted
  tradeoff of this phase: TS owns call-time types, tests own behavior.
- Plan 013 (optional) finishes the binding-layer raws; without it, the
  two `toComObject` casts and Winax internals remain as documented
  boundaries.
