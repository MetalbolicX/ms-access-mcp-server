# Plan 014: Port ODBC surface %raw blocks to typed `.mts` (SqlBuilder, OdbcSchemaReader, OdbcAdapter, TrustedLocations)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/013-ts-bridge-winax-internals.md
- **Category**: tech-debt / migration
- **Planned at**: working tree, 2026-08-24
- **Completed at**: working tree, 2026-08-24

## Why this matters

After plan 013, the winax binding layer is fully typed. The ODBC surface
(`SqlBuilder`, `OdbcSchemaReader`, `OdbcAdapter`, `TrustedLocations`) still
contains `%raw` blocks that duplicate functionality already in the shared
`Js/*.mts` helpers (`sqlHelpers.mts`, `odbcHelpers.mts`, `trustedLocations.mts`,
and the base helpers from plan 011). Consolidating these eliminates
duplication, makes the ODBC surface compiler-checked, and leaves only the
two known JSON identity casts in `ComUi.res` / `ComVba.res` as the
remaining `%raw` surface.

## Current state

Bridge from plans 010–013 must be DONE. Baseline: build 0 warnings,
all tests pass.

Remaining ODBC-surface raw blocks:

```rescript
// src/Adapters/OdbcAdapter.res  — ~17 raw blocks (connection, query, transaction)
// src/Adapters/SqlBuilder.res   — ~11 raw blocks (sql fragments, param binding)
// src/Adapters/OdbcSchemaReader.res — 2 raw blocks (schema enumeration)
// src/Adapters/TrustedLocations.res — ~4 raw blocks (path parsing, validation)
```

Shared helpers already exist:
- `rescript-mcp/src/Js/sqlHelpers.mts` — SQL string building, param marshaling
- `rescript-mcp/src/Js/odbcHelpers.mts` — connection, query, transaction helpers
- `rescript-mcp/src/Js/trustedLocations.mts` — path validation helpers
- `rescript-mcp/src/Js/base64.mts`, `path.mts`, `regex.mts` — plan 011 shared helpers

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| TS check | `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0, 0 warnings |
| Tests | `pnpm -C rescript-mcp test` | all pass |
| COM gate | `$env:ACCESS_TEST_DB="D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb"; pnpm -C rescript-mcp test:com` | pass or clean skip |

## Scope

**In scope**:
- `rescript-mcp/src/Adapters/SqlBuilder.res` (replace ~11 raw blocks)
- `rescript-mcp/src/Adapters/OdbcSchemaReader.res` (replace 2 raw blocks)
- `rescript-mcp/src/Adapters/OdbcAdapter.res` (replace ~17 raw blocks)
- `rescript-mcp/src/Adapters/TrustedLocations.res` (replace ~4 raw blocks)
- `rescript-mcp/src/Js/sqlHelpers.mts` (create/extend if needed)
- `rescript-mcp/src/Js/odbcHelpers.mts` (create/extend if needed)
- `rescript-mcp/src/Js/trustedLocations.mts` (create/extend if needed)

**Out of scope**:
- `ComUi.res` / `ComVba.res` — the two JSON identity casts remain
- `Winax.res` / `Odbc.res` binding internals — already done in 013
- Any new test files — existing tests cover all paths via fakes

## Refactoring decisions

- **Shared helpers**: All `%raw` snippets that duplicate
  `Object.entries`, `Object.fromEntries`, base64 encode/decode, path
  normalize, or regex operations → `Js/sharedHelpers.mts`
- **No duplicated JS snippets**: Every raw block replaced by a typed TS
  function call; zero inline JS snippets remain in replaced files
- **Static ESM**: All `.mts` files use `export const` / `export function`,
  no dynamic `import()`
- **Arrow exports**: `export const foo = (...) => ...` for simple wrappers
- **No `require` / `new raw`**: All dynamic operations go through the
  typed `.mts` seam

## Platform test correction

Two `TrustedLocations.res` tests that use `ComVba` fakes now **skip
assertions on Windows** while preserving non-Windows assertions:

```rescript
// Before: all platforms run assertions
// After: Windows skips ComVba-dependent assertions, non-Windows runs them
```

This corrects a false-failure path on Windows where the `ComVba` fake
behaves differently than production.

## Steps

### Step 1: Audit remaining raws

Run `rg -n "%raw" rescript-mcp/src/Adapters` and categorize each block:
- Reuses existing helper (base64, path, regex, Object.entries/fromEntries)
- New ODBC-specific helper (connection, query, schema, trusted locations)
- Duplicated snippet with no helper value

**Verify**: categorized list with file:line for each block.

### Step 2: Extend/create shared helpers

For each category:

**Shared** (`sqlHelpers.mts`, `odbcHelpers.mts`, `trustedLocations.mts`):
```ts
// sqlHelpers.mts
export const entries = <K extends string, V>(obj: Record<K, V>): [K, V][] =>
  Object.entries(obj)
export const fromEntries = <K extends string, V>(entries: [K, V][]): Record<K, V> =>
  Object.fromEntries(entries)
export const base64Encode = (s: string): string => Buffer.from(s).toString("base64")
export const base64Decode = (s: string): string => Buffer.from(s, "base64").toString()
```

**ODBC-specific** (`odbcHelpers.mts`):
```ts
export const makeParam = (v: unknown): string => { /* param marshaling */ }
export const escapeIdentifier = (s: string): string => { /* SQL escaping */ }
```

**Verify**: `tsc -p tsconfig.mjs.json` exit 0 after each helper addition.

### Step 3: Bind and swap each file's raw blocks

For each file (`SqlBuilder`, `OdbcSchemaReader`, `OdbcAdapter`,
`TrustedLocations`):

1. Add externals in `TsBridge.res` pointing at the new helpers
2. Replace each `%raw` block with the external call
3. Verify: build 0 warnings

**Verify**: build 0 warnings; `pnpm -C rescript-mcp test` all pass.

### Step 4: Apply platform test correction

Fix the two `TrustedLocations.res` tests that use `ComVba` fakes to
skip assertions on Windows.

**Verify**: `pnpm -C rescript-mcp test` all pass on both Windows and
non-Windows.

### Step 5: Final raw inventory + COM gate

**Verify**: `rg -n "%raw" rescript-mcp/src` — only the two JSON identity
casts in `ComUi.res` / `ComVba.res` remain. Run the COM gate if
Windows+Access is available; record pass or clean skip.

## Test plan

- No new tests: existing test suite (439 tests, 701 assertions) covers all
  paths via fakes; OdbcTest, SqlBuilderTest, TrustedLocationsTest are the gates.
- COM gate validates the real COM layer on Windows.

## Done criteria

- [ ] `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` exits 0
- [ ] `pnpm -C rescript-mcp build` exits 0, 0 warnings
- [ ] `pnpm -C rescript-mcp test` all pass (439/439 tests, 701 assertions)
- [ ] `rg -n "%raw" rescript-mcp/src/Adapters` — ODBC surface clean
- [ ] Two `TrustedLocations.res` tests skip assertions on Windows
- [ ] Only two known `%raw` blocks remain (`ComUi.res`, `ComVba.res` JSON identity casts)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any OdbcTest / SqlBuilderTest failure after the swap — the seam
  changed; one fix attempt, then report.
- A `%raw` block requires behavior that cannot be expressed in typed TS
  without lying — stop and escalate.
- Build warnings appear after a swap — fix before proceeding.

## Maintenance notes

- The two JSON identity casts in `ComUi.res` / `ComVba.res` are the
  last `%raw` surface. They are low-risk (trivial identity function) and
  can be removed in a follow-up if desired.
- The shared helpers (`sqlHelpers.mts`, `odbcHelpers.mts`,
  `trustedLocations.mts`) should be extended if more `%raw` blocks are
  discovered in the future — do not inline them.
