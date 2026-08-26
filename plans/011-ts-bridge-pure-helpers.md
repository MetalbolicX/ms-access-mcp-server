# Plan 011: Migrate pure-helper `%raw` blocks to typed TypeScript modules

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: written against the WORKING TREE (COM
> sources untracked at planning time). Verify the "Current state" excerpts
> match live files. On a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW-MED
- **Depends on**: plans/010-ts-bridge-foundation.md (toolchain + `Js.res` shim)
- **Category**: tech-debt / migration
- **Planned at**: commit `256cd6b` (working tree), 2026-08-24

## Why this matters

After plan 010, the largest class of remaining `%raw` is pure logic —
Buffer codepage codecs (cp1252 / UTF-16LE+BOM), filename sanitization,
file hashing, and platform probes — that has clean TypeScript types but no
typed ReScript binding (Node's typed bindings lack cp1252; ReScript's
RegExp API can't express these global replaces). Moving them into strict
`.mts` modules makes them compiler-checked, unit-testable, and removes
~11 more raw blocks while leaving the risky COM surface (plan 012) cleanly
separated.

## Current state

Bridge from plan 010 (must be DONE): `tsconfig.mjs.json`, `src/Js/`
module pattern, `src/Bindings/TsBridge.res` shim, `pnpm build` chains
`tsc && rescript`. Baseline: build 0 warnings, all tests pass
(>= 420 after plan 010).

The exact raw blocks this plan owns (file:line + body shape):

| # | Location | Body | Replacement module |
|---|----------|------|--------------------|
| 1 | `ComUi.res:190` | `Array.from(Buffer.from(text, "cp1252"))` | `codec.mts` |
| 2 | `ComUi.res:197` | `Array.from(buf)` (Buffer→bytes) | `codec.mts` |
| 3 | `ComUi.res:208` | `Buffer.from(bytes).toString("cp1252")` | `codec.mts` |
| 4 | `ComUi.res:211` | UTF-16LE decode with 2-byte BOM strip | `codec.mts` |
| 5 | `ComUi.res:231` | `Buffer.from(textData, enc)` for tmp write | `codec.mts` |
| 6 | `ComDbProps.res:208` | `name.replace(/[\\\\/:*?"<>|]/g, '_')` | `fsHelpers.mts` |
| 7 | `ComDbProps.res:307` | `require('crypto') sha256 file hash` | `hash.mts` |
| 8 | `ComDbProps.res:339` | `Array.from(Buffer.from(textData, enc))` | `codec.mts` |
| 9 | `ComDbProps.res:362` | `Buffer.from(raw).toString(enc)` | `codec.mts` |
| 10 | `ComDbProps.res:1434` | `.bas`/`.txt` ext strip + `_`→space | `fsHelpers.mts` |
| 11 | `TrustedLocations.res:12` | `process.platform === 'win32'` | `runtime.mts` |

Notes:

- Encoding strings (`"cp1252"`, `"utf16le"`, `"utf-8"`) pass the current
  419-test suite on Node 24 — keep them byte-identical in TS.
- `ComDbProps.res:204-208` (`safeFilename`) is guarded by 13 dedicated
  tests in `ComDbPropsTest.res` — port the regex verbatim.
- Line 307 (`_fileHash`) uses CJS `require('crypto')` from ESM — a known
  archived warning (verify report obs#957); this plan closes it with a
  proper `import { createHash } from "node:crypto"`.
- `ComUi.res:151` (`toComObject`) and `ComVba.res:59` are type-level
  identity casts, NOT owned by this plan — they stay.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| TS check | `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0, 0 warnings |
| Tests | `pnpm -C rescript-mcp test` | all pass |
| Raw count | `rg -n "%raw" rescript-mcp/src -g "*.res"` | listed blocks gone |

## Scope

**In scope**:
- `rescript-mcp/src/Js/codec.mts`, `src/Js/fsHelpers.mts`,
  `src/Js/hash.mts`, `src/Js/runtime.mts` (append `isWindows`)
- `rescript-mcp/src/Bindings/TsBridge.res` (append externals)
- `rescript-mcp/src/Adapters/ComUi.res` (only blocks #1–#5)
- `rescript-mcp/src/Adapters/ComDbProps.res` (only blocks #6–#10)
- `rescript-mcp/src/Adapters/TrustedLocations.res` (only block #11)
- `rescript-mcp/test/JsBridgeTest.res` (append codec/fs/hash tests)

**Out of scope**:
- ALL COM-orchestration raws (`ComUi.res:256+`, `ComDbProps.res:483+`) —
  plan 012.
- `OdbcAdapter.res`, `SqlBuilder.res`, `OdbcSchemaReader.res` raws
  (ODBC-side; same pattern applies later — see plans/README.md notes).
- `toComObject`/`_toComObject` identity casts.

## Git workflow

- Branch: `rescript/011-ts-pure-helpers`.
- Conventional commits, e.g. `refactor(rescript): port codec/fs/hash raw helpers to typed .mts bridge`.

## Steps

### Step 1: Write failing bridge tests first (strict TDD)

Append to `test/JsBridgeTest.res` tests calling the NOT-yet-bound
externals (they fail to compile — that is the RED gate): encode/decode
round-trips (cp1252 with a smart quote `“` char, UTF-16LE with BOM
prefix `0xFF 0xFE`), `safeFilename("a:b*c?d")` → `"a_b_c_d"`,
`cleanName("01_My Form.bas")` per existing ComDbProps expectations
(read `ComDbPropsTest.res` for exact expectations), `isWindows()` equals
`process.platform` check.

**Verify**: `pnpm -C rescript-mcp build` → fails on missing externals (expected RED).

### Step 2: Create `src/Js/codec.mts`

Port bodies VERBATIM from the raw blocks, adding types only. Export:

```ts
export function encodeCp1252(text: string): number[]            // block 1
export function bufferToBytes(buf: Buffer): number[]            // block 2
export function decodeCp1252(bytes: number[]): string           // block 3
export function decodeUtf16LeSkipBom(bytes: number[]): string   // block 4
export function encodeToBuffer(text: string, enc: string): Buffer // block 5
export function bytesFromString(text: string, enc: string): number[] // block 8
export function bytesToString(raw: number[], enc: string): string   // block 9
```

Keep the exact `Buffer.from(...)` / `.toString(...)` calls and encoding
strings. `Buffer` stays INSIDE the module except `encodeToBuffer` (its
consumer feeds NodeJs.Fs write — if the rescript-nodejs Buffer type
clashes at the external, move that whole write call into TS as
`writeFileEncoded(path, text, enc): void` instead; prefer this if in
doubt).

**Verify**: `tsc -p tsconfig.mjs.json` exit 0.

### Step 3: Create `src/Js/fsHelpers.mts`, `src/Js/hash.mts`, extend `runtime.mts`

- `fsHelpers.mts`: `safeFilename(name: string): string` (block 6 regex
  verbatim), `cleanName(fname: string): string` (block 10 regexes
  verbatim: strip `.bas`/`.txt` suffixes, `_`→` ` — read the live block
  first and copy exactly).
- `hash.mts`: `import { createHash } from "node:crypto"`;
  `fileHash(path: string): string` — same sha256-hex-of-file-bytes
  semantics as block 7, errors → `""`.
- `runtime.mts`: append `export function isWindows(): boolean { return process.platform === "win32" }`.

**Verify**: `tsc` exit 0; `pnpm -C rescript-mcp build` exit 0.

### Step 4: Bind and swap — codec (ComUi #1–#5)

Add externals to `src/Bindings/TsBridge.res`
(`@module("../Js/codec.mjs")`, types `string => array<int>` etc. —
`array<int>` matches `number[]` since all values are 0–255 ints).
Replace ComUi blocks #1–#5 with the bound calls, keeping surrounding
control flow identical.

**Verify**: `pnpm -C rescript-mcp build` → 0 warnings; `pnpm -C rescript-mcp test` → all pass (ComUi encoding tests are the regression gate).

### Step 5: Bind and swap — ComDbProps (#6–#10) and TrustedLocations (#11)

Same pattern. `_fileHash` now returns the TS hash; `safeFilename` /
`cleanName` call the bound helpers; TrustedLocations line 12 becomes
`Js.isWindows()`.

**Verify**: build 0 warnings; `pnpm -C rescript-mcp test` all pass
(the 13 `safeFilename` tests are the gate); `rg -n "%raw"` shows all 11
blocks gone.

## Test plan

- New bridge tests (Step 1) cover: cp1252 round-trip incl. non-ASCII,
  UTF-16LE BOM strip, safeFilename invalid-char set, cleanName suffix
  rules, isWindows, fileHash of a temp fixture file.
- Existing suites (ComUi encoding tests, ComDbProps safeFilename +
  versioning tests, TrustedLocations tests) must stay green unchanged.
- Verification: `pnpm -C rescript-mcp test` → all pass.

## Done criteria

- [ ] `pnpm -C rescript-mcp exec tsc -p tsconfig.mjs.json --noEmit` exits 0
- [ ] `pnpm -C rescript-mcp build` exits 0, 0 warnings
- [ ] `pnpm -C rescript-mcp test` all pass
- [ ] `rg -n "%raw" rescript-mcp/src` — all 11 listed blocks replaced
- [ ] `ComDbProps.res:307` CJS `require('crypto')` gone (closes obs#957
      warning #2)
- [ ] `git status` clean outside in-scope list; `plans/README.md` updated

## STOP conditions

- Any listed block's live body differs materially from the plan table
  (drift).
- `Buffer.from(text, "cp1252")` throws `ERR_UNKNOWN_ENCODING` on this
  Node — it demonstrably works today via the raw blocks (suite green),
  so a throw means you changed the call; restore exact call and retest.
- A test regression you cannot fix in one attempt — report rather than
  adapt test expectations.
- The `encodeToBuffer` Buffer crossing needs more than the fallback in
  Step 2 — report.

## Maintenance notes

- Reviewer: diff each `.mts` body against the raw block it replaced —
  semantics must be verbatim; only types added.
- `SqlBuilder.res` / `OdbcAdapter.res` / `OdbcSchemaReader.res` raws
  (~30 more) are future candidates for the same pattern; deliberately
  deferred (see README "Findings considered and rejected").
- If Node ever gains typed cp1252 in rescript-nodejs, `codec.mts` can
  shrink — the ReScript externals would stay the same.
