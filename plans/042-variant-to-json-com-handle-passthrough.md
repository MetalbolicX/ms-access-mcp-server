# Plan 042 v2: VComObject variant constructor for COM-handle passthrough (unblocks 040-F-001, resolves 038-F-005)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat eeeeb1f..HEAD -- rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Bindings/Winax.resi rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/src/Adapters/ComInterfaces.res rescript-mcp/src/Adapters/ComInterfaces.resi`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

> **Versioning note (read this first)**: This is **v2**, replacing v1
> which proposed a `__p__` envelope probe inside `variantToJson`.
> Executor attempted v1 and STOPPED at Step 3 with a catastrophic
> regression (10+1+2+2 baseline → 0+13+0+2 after fix). The probe
> intercepted `variant` values that happened to flow through the shared
> path, not just the four call sites it was intended for. See
> `## v1 history` at the bottom of this file. **Do not attempt v1.**

## Status

- **Priority**: P1
- **Effort**: S (4 file edits, ~15 lines net; the verification and the
  two-phase rollout are the real work)
- **Risk**: LOW (the new ADT constructor is purely additive; the shared
  `variantToJson` adds exactly one arm; no call site is forced through
  the new path — only the four identified call sites opt in)
- **Depends on**: nothing; unblocks plan 040 (refresh/recreate, 038-F-005).
  Plan 041 is already SKIPPED and unaffected.
- **Category**: bug
- **Planned at**: commit `eeeeb1f` (v1 docs), revised 2026-09-04 (v2)

## Why this matters

Plan 040's probe (finding **040-F-001** in `rescript-mcp/parity/findings.md:972-1024`)
proved the root cause of 038-F-005: every `Append` of a COM handle through
`WINAX_BINDING.invoke` silently no-ops because `variantToJson` in
`Bindings/Winax.res:94-108` erases unrecognized variants to `JSON.Null`
before they reach winax. Four call sites are affected
(`ComDataAdapter.res:2570`, `:2608`, `:2809`, `:2988`).

The standalone winax probe (040-F-001, probes in `$TEMP\probe040` on the
probing session) proved that passing the **raw proxy** (not the
`{__p__: ...}` envelope) to `Append` works perfectly: Count 80→81, named
lookup succeeds, `RefreshLink` succeeds. The only thing between that
success and the adapter is `variantToJson`.

This plan makes the minimal ADT addition that the probe evidence
supports: add a typed `VComObject` constructor to the variant ADT and a
single corresponding arm to `variantToJson`. The new arm is the ONLY
thing that can return a raw COM proxy as `JSON.t`; every other arm
behaves identically. This is the only design that scopes the change so
tightly that the v1-style bidirectional regression is structurally
impossible.

## Current state

- **The shared marshaling chokepoint** `rescript-mcp/src/Bindings/Winax.res:94-108`:

```rescript
let variantToJson: ComInterfaces.variant => JSON.t = (v: ComInterfaces.variant) => {
  switch v {
  | ComInterfaces.VBool(b) => JSON.Boolean(b)
  | ComInterfaces.VDate(d) => JSON.String(Date.toISOString(d))
  | ComInterfaces.VNull => JSON.Null
  | ComInterfaces.VEmpty => JSON.Null
  | ComInterfaces.VInt(n) => JSON.Number(Int.toFloat(n))
  | ComInterfaces.VFloat(f) => JSON.Number(f)
  | ComInterfaces.VCurrency(c) => JSON.Number(c)
  | ComInterfaces.VDecimal(d) => JSON.Number(d)
  | ComInterfaces.VStr(s) => JSON.String(s)
  | ComInterfaces.VArray(_) => JSON.Null
  | ComInterfaces.VByRef(_) => JSON.Null
  }
}
```

  No variant constructor carries a COM handle. Any call site that smuggled
  one via `let tdefAsVariant: ComInterfaces.variant = %raw("(t) => t")(Obj.magic(tdef))`
  produced a runtime value with no recognizable `TAG`; the compiled switch
  fell through and emitted `JSON.Null`, making winax receive `null` and
  silently no-op.

- **The variant ADT** `rescript-mcp/src/Adapters/ComInterfaces.res:8-19`:

```rescript
type rec variant =
  | VBool(bool)
  | VDate(Date.t)
  | VNull
  | VEmpty
  | VInt(int)
  | VFloat(float)
  | VCurrency(float)
  | VDecimal(float)
  | VStr(string)
  | VArray(array<variant>)
  | VByRef(ref<variant>)
```

  Mirrored in `ComInterfaces.resi:11-21`. Adding a constructor requires
  touching both files.

- **The four Append call sites** (all the same pattern):
  - `ComDataAdapter.res:2570` — relations Append (`createRelationship`)
  - `ComDataAdapter.res:2608` — fields Append (`createRelationship`, nested)
  - `ComDataAdapter.res:2809` — linked-table Append (`createLinkedTable`)
  - `ComDataAdapter.res:2988` — linked-table Append (`recreateLinkedTable`)

- **Why `invoke`/`get`/`set` themselves are fine**: `TsBridge.winaxInvokeMethod`
  (`src/Js/winaxBinding.mts:44-50`) calls `(_unwrap(obj))[method](...args)`.
  `_unwrap` (`winaxBinding.mts:23-28`) unwraps the OUTER object but passes
  `args` through verbatim. The only mutator of args is `variantToJson` in
  the ReScript layer (`Winax.res:228` in `invoke`, `:207` in `set`, `:249`
  in `invokeAsObject`, `:286` in `invokePreservingError`). Fix at the
  ReScript layer and the args arrive intact.

- **The `%raw` discipline** (mandatory, from plan 039's failure history):
  `%raw` bodies must be function literals `(e) => { ... }`, never IIFEs —
  see the warning at `ComDataAdapter.res:57-59`.

- **`variantToJson` is called on the args path only.** It is NOT called
  on return values — returns flow through `winaxInvokeMethod` directly
  (line 229) as native `JSON.t`. (v1's diagnosis of a bidirectional
  regression was based on a hallucinated `TsBridge.Variant` return-path
  wrapper. That function does not exist. The real cause of v1's
  regression is the shared-path probe intercepting values that were
  expected to be ignored by the variant switch — see `## v1 history`.)

## Chosen approach

**Approach D (v2 shape) — `VComObject` ADT constructor + scoped arm.**

1. Add one constructor to the `variant` ADT in `ComInterfaces.res:8-19`
   and the mirror in `ComInterfaces.resi:11-21`:

```rescript
type rec variant =
  | VBool(bool)
  | VDate(Date.t)
  | VNull
  | VEmpty
  | VInt(int)
  | VFloat(float)
  | VCurrency(float)
  | VDecimal(float)
  | VStr(string)
  | VArray(array<variant>)
  | VByRef(ref<variant>)
  | VComObject(ComInterfaces.comObject)  // Plan 042 v2: COM handle passthrough
```

2. Add one arm to `variantToJson` in `Winax.res:94-108`. The arm is the
   ONLY path that can return a raw COM proxy as `JSON.t`. All other arms
   behave identically to today. The arm strips a `{__p__: ...}` envelope
   if present (the pattern used at the call sites) and otherwise passes
   through (defensive: handles the case where a raw proxy was passed
   directly):

```rescript
| ComInterfaces.VComObject(proxy) => {
  // Plan 042 v2: pass COM handle through to winax. The call sites wrap
  // the proxy as {__p__: rawProxy}; strip the envelope so winax gets
  // the dispatch pointer (matches winaxBinding.mts:_unwrap contract).
  // FUNCTION LITERAL — never an IIFE (ComDataAdapter.res:57-59).
  let unwrapped: option<JSON.t> = %raw(
    "(p) => (p != null && typeof p === 'object' && p.__p__ !== undefined) ? p.__p__ : null"
  )(proxy)
  switch unwrapped {
  | Some(raw) => raw
  | None => proxy
  }
}
```

3. Change the four Append call sites to construct `VComObject` instead
   of the smuggled `%raw` identity. The change is from
   `let tdefAsVariant: ComInterfaces.variant = %raw("(t) => t")(Obj.magic(tdef))`
   to
   `let tdefAsVariant: ComInterfaces.variant = ComInterfaces.VComObject(tdef)`.
   The type is now correct; the value is wrapped in a real ADT
   constructor; `variantToJson` matches the new arm and returns the
   raw proxy.

### Why this is "scoped" despite the ADT change

- The ADT change is purely additive (one new constructor). No existing
  arm in `variantToJson` is modified.
- The ODBC adapter (`Bindings/Odbc.res`, `Adapters/OdbcAdapter.res`)
  uses its own type `oDBcValue` (line 240), NOT the `variant` ADT.
  Adding a constructor to `variant` does NOT affect the ODBC path.
- Other call sites that construct `variant` values only produce
  `VStr`, `VInt`, `VBool`, `VNull`, `VFloat`. They do not produce
  `VComObject` — only the four call sites do. Verified by:
  `rg -n "let \\w+: ComInterfaces\\.variant = " rescript-mcp/src/Adapters/`
  which returns exactly four matches (lines 2570, 2608, 2809, 2988).
- The only exhaustive `switch` on `variant` is `variantToJson` itself
  in `Winax.res:95`. Verified by: `rg -n "switch v \\{" rescript-mcp/src/`
  returns matches that are either JSON.t switches, oDBcValue switches,
  or the one we're modifying.
- The 4 call sites are the only places that produce a `VComObject`,
  so the new arm in `variantToJson` cannot fire for any other path.
  This is structurally guaranteed — no probe, no shared-path
  discrimination, no possibility of the v1 regression.

### Rejected alternatives

- **v1's `__p__` probe** in `variantToJson`: STOPPED with 0+13+0+2
  regression. The probe in the shared path intercepted values that
  were not intended to be discriminated. See `## v1 history`.
- **`invokeRaw` primitive**: duplicates `invoke`'s entire body for one
  behavioral flag; the existing primitive must keep working identically
  anyway — more surface, same risk.
- **Per-site `%raw` bridge bypass** at the Append call sites: bypasses
  the binding contract per-call; spreads the marshaling knowledge
  into adapter code; exactly the fragmentation the binding layer
  exists to prevent.
- **Smuggle a "VComObject" via a custom TAG number**: the `{TAG, _0}`
  format is an internal representation subject to compiler changes
  across versions. A typed constructor is the contractually correct
  shape.

## Commands you will need

| Purpose        | Command (from repo root)                                    | Expected on success                |
|----------------|--------------------------------------------------------------|------------------------------------|
| Build          | `cmd.exe /c "pnpm -C rescript-mcp build"`                    | exit 0                             |
| Tests          | `cmd.exe /c "pnpm -C rescript-mcp test"`                     | 786 passed / 10 failed (baseline)  |
| COM parity     | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:com:ddl"` | see per-step expectations          |
| ODBC parity    | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:ddl"`     | 13 matched + 2 skipped             |
| Kill Access    | `Get-Process MSACCESS -EA SilentlyContinue \| Stop-Process -Force` then `Start-Sleep -Seconds 5` | before AND after every COM run |

Parity env (PowerShell):
```powershell
$env:ACCESS_TEST_ASSUME_ACE='1'; $env:ACCESS_TEST_DB="$PWD\db\northwind.accdb"
$env:ACCESS_MCP_ALLOWED_DIRS="$PWD\db;$env:TEMP"; $env:ACCESS_MCP_READONLY='false'
```

## Scope

**In scope** (exactly these files):
- `rescript-mcp/src/Adapters/ComInterfaces.res` — add `VComObject` constructor (additive)
- `rescript-mcp/src/Adapters/ComInterfaces.resi` — mirror the constructor (additive)
- `rescript-mcp/src/Bindings/Winax.res` — add one arm to `variantToJson`
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — change exactly 4 lines (2570, 2608, 2809, 2988)
- `rescript-mcp/parity/findings.md` — resolution note appended to 040-F-001, update 038-F-005, add 042-F-001 resolution section
- `plans/README.md` — update rows 040 and 042

**Out of scope** (do NOT touch):
- `Winax.resi` — the `variantToJson` function is module-internal, not in the signature; `VComObject` lives on `ComInterfaces.variant` which is re-exported through `ComInterfaces`; the existing `Winax.resi` does not need changes.
- `Odbc.res` / `OdbcAdapter.res` — the ODBC path uses `oDBcValue`, not `variant`.
- `winaxBinding.mts` / `TsBridge.res` — `_unwrap` behavior is correct as-is.
- The v8 teardown crash (033-F-001 family) that real Appends surface — see "Known follow-up".
- `get_linked_tables.json` (plan 041's accepted skip) — do not unskip.

## Git workflow

- Branch: `rescript/038-linked-tables-sql-script` (HEAD `eeeeb1f`).
- **Two commits** per the v1 plan's structure:
  1. `feat(parity): add VComObject variant for COM-handle passthrough (plan 042 v2)`
  2. `docs(parity): resolve 038-F-005 via VComObject passthrough (plan 042 v2)`
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 0: Baseline capture

Kill MSACCESS, set parity env, run `parity:northwind:com:ddl` once, kill
MSACCESS. Record the exact tally.

**Verify**: `refresh_linked_table.json` and `recreate_linked_table.json`
both FAIL with `diff at $.error` containing `code=-2146825023`. Expected
tally: **10-11 matched + 1-2 mismatched + 0-2 errored + 2 skipped** (the
0-2 errored is the known transient exit-134 flake on `delete_table` /
`get_indexes` / `drop_index`). If the two target cases instead show
DRIVER ERROR, the harness state is bad — kill MSACCESS, wait 10s, retry
once; if it persists, STOP (environment, not code).

### Step 1: Grep-verify the v2 invariants

Before any edits, verify the structural guarantees in "Why this is scoped":

```bash
rg -n "let \w+: ComInterfaces\.variant = " rescript-mcp/src/Adapters/
```
Expect exactly 4 matches at lines 2570, 2608, 2809, 2988. If more, STOP —
the new constructor would have more producers than expected, and the
scoping guarantee weakens.

```bash
rg -n "switch v \{" rescript-mcp/src/
```
Inspect every match. Expect: the one in `Winax.res:95` (the one we're
modifying) plus JSON.t or oDBcValue switches. If any other exhaustive
switch on `variant` appears, STOP — the ADT change is wider than
assumed.

If both checks pass, proceed.

### Step 2: Apply the ADT change

`ComInterfaces.res:8-19` and `ComInterfaces.resi:11-21`: add the
`VComObject(ComInterfaces.comObject)` constructor as the last arm. The
two files must stay mirrored (verified: both files share the exact same
`type rec variant = ...` block today). Re-verify after the edit:

```bash
diff <(sed -n '/^type rec variant =/,/^$/p' rescript-mcp/src/Adapters/ComInterfaces.res) \
     <(sed -n '/^type rec variant =/,/^$/p' rescript-mcp/src/Adapters/ComInterfaces.resi)
```
Expect no output (files mirrored). If they diverge, STOP and fix.

### Step 3: Apply the `variantToJson` arm

Add the new arm to `Winax.res:94-108` exactly as in "Chosen approach"
(Approach D, item 2). Do NOT reformat the existing 11 arms. Do NOT touch
`Winax.resi` (the function is module-internal).

### Step 4: Update the 4 Append call sites

In `ComDataAdapter.res`, change:
- Line 2570: `let relAsVariant: ComInterfaces.variant = %raw("(r) => r")(Obj.magic(rel))` → `let relAsVariant: ComInterfaces.variant = ComInterfaces.VComObject(rel)`
- Line 2608: `let fieldAsVariant: ComInterfaces.variant = %raw("(f) => f")(Obj.magic(field))` → `let fieldAsVariant: ComInterfaces.variant = ComInterfaces.VComObject(field)`
- Line 2809: `let tdefAsVariant: ComInterfaces.variant = %raw("(t) => t")(Obj.magic(tdef))` → `let tdefAsVariant: ComInterfaces.variant = ComInterfaces.VComObject(tdef)`
- Line 2988: `let tdefAsVariant: ComInterfaces.variant = %raw("(t) => t")(Obj.magic(tdef))` → `let tdefAsVariant: ComInterfaces.variant = ComInterfaces.VComObject(tdef)`

The `rel`, `field`, `tdef` values are already `ComInterfaces.comObject`
types (declared as such earlier in each function). The new constructor
takes `comObject` and the type signature matches. No `Obj.magic` needed.

### Step 5: Build

`cmd.exe /c "pnpm -C rescript-mcp build"` → expect exit 0. If non-zero,
the most likely cause is the ADT mirroring — re-run the `diff` from
Step 2. If mirrored but build fails, STOP and report the build error
verbatim.

### Step 6: Shared-path regression gate (before any parity)

`cmd.exe /c "pnpm -C rescript-mcp test"`.

**Verify**: 786 passed / 10 failed, baseline unchanged (ComIntegration
and ComExecuteQuery families — pre-existing). ANY new failure → revert
and STOP. This is the 038-F-008 blast-radius lesson: `variantToJson` is
used by every `invoke`/`get`/`set` call — a mistake here breaks
everything, and the test suite is the fastest signal.

If the test count differs from 786+10, STOP. The change is affecting
more paths than the new constructor + new arm allow.

### Step 7: Targeted parity

Kill MSACCESS, `parity:northwind:com:ddl`, kill MSACCESS.

**Expected outcomes, in preference order**:
- **Best**: both target cases PASS. Tally: **12-13 matched + 0-1
  mismatched + 0-1 errored + 2 skipped**. Go to Step 8.
- **Acceptable**: one or both target cases flip from `FAIL` to `ERRORED
  exit 134`. This is the 040-F-001 Branch-4b behavior: the Append now
  actually lands, exposing the latent teardown crash. This is NOT
  success and NOT a new bug — it is the known follow-up. Per plan,
  accept it IF (a) the crash is the v8-teardown signature (no stdout,
  exit 134, `DispObject::~scalar deleting destructor` in stderr if
  visible), AND (b) `create_linked_table.json` — the case that now
  exercises a REAL Append — still PASSES, AND (c) no other
  baseline-passing case regresses. Record the shift in findings.md
  (Step 10) and go to Step 8. If the exit 134 appears on
  `create_linked_table.json` or any previously-PASS case, STOP/revert.
- **Failure**: both cases still FAIL with `-2146825023`. The passthrough
  did not take effect. Re-check that Step 4 changed the 4 lines
  correctly and that the `diff` in Step 2 still shows mirroring. If
  both check, run `pnpm -C rescript-mcp clean && pnpm -C rescript-mcp
  build` ONCE and re-run. If still failing, STOP and report with the
  exact diff at `$.error`.

### Step 8: Full COM parity + stability (3 runs)

Three consecutive `parity:northwind:com:ddl` runs, killing MSACCESS and
waiting 5s between each.

**Verify**: the Step 7 outcome (whichever was achieved) reproduces in
all 3 runs. The transient-flake category (exit 134 on
`delete_table`/`get_indexes`/`drop_index`/`recreate_linked_table`) is
pre-existing and shifts run to run — but `create_linked_table.json`,
`alter_table.json`, `create_table.json`, `create_index.json`,
`delete_query.json`, `set_query_sql.json`, `unlink_table.json` must
PASS in all 3 runs. Any PASS→ERROR regression that repeats in 2 of 3
runs → STOP and revert.

### Step 9: ODBC parity unchanged

`parity:northwind:ddl` → 13 matched + 2 skipped. The ODBC path uses
`oDBcValue`, never `variant`, so any change here means something is
deeply wrong → STOP and revert.

### Step 10: Document and commit

1. Append a resolution note to **040-F-001** in
   `rescript-mcp/parity/findings.md`: v2 design (VComObject constructor)
   landed, the diff, the parity outcome (PASS or exit-134 shift), and
   the cross-reference to the known follow-up.
2. Add a **042-F-001 resolution section** to `findings.md`: v1 stopped
   at Step 3 with a 0+13+0+2 regression. v2 replaced the shared-path
   probe with a typed ADT constructor. The regression is structurally
   impossible in v2 because the new arm only fires for `VComObject`
   values, and only 4 call sites produce them.
3. Update **038-F-005** status: RESOLVED (if both cases PASS) or
   SUPERSEDED-BY-TEARDOWN-BUG (if the exit-134 shift was accepted) —
   name the exact outcome, do not blur it.
4. Update `plans/README.md`: row 042 → DONE with one-line summary; row
   040 stays BLOCKED but append "(unblocked by 042 pending teardown
   fix)" if the exit-134 shift was accepted, or "(unblocked by 042)"
   if both cases PASS.
5. Commit(s) per "Git workflow".

## Test plan

The parity cases are the tests (live differential vs the Python oracle).
The existing suite (Step 6) is the shared-path regression gate. No new
unit tests — the behavior requires live COM, and the ODBC suite proves
the non-COM paths are untouched.

## Done criteria

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] Test suite: 786 passed / 10 failed (no new failures)
- [ ] COM parity Step 7 outcome achieved and reproduced across 3 runs:
  both target cases PASS, OR the accepted exit-134 shift with
  `create_linked_table.json` still PASS and zero repeating regressions
- [ ] ODBC parity: 13 matched + 2 skipped unchanged
- [ ] Only `ComInterfaces.res`/`.resi`, `Winax.res`, `ComDataAdapter.res`,
  `findings.md`, `plans/README.md` modified. `Winax.resi` UNCHANGED
  (verify with `git diff`). Probe scripts (if any) live in temp and
  are not committed.
- [ ] `variantToJson` diff is additive only (one new arm; no existing
  arm touched)
- [ ] ADT mirroring preserved (the `diff` from Step 2 returns no output)
- [ ] Exactly 4 Append call sites changed; all 4 use `VComObject`
- [ ] `%raw` bodies are function literals; no IIFE; no `require(`
- [ ] findings.md 040-F-001 + 042-F-001 + 038-F-005 updated; plans/README.md
  rows 040/042 updated
- [ ] Two commits on the current branch; NOT pushed

## STOP conditions

- Drift: any in-scope file at HEAD differs from the excerpts above.
- Step 1: more than 4 producers of `ComInterfaces.variant` exist, or any
  exhaustive switch on `variant` other than the one being modified.
- Step 2: `ComInterfaces.res` and `.resi` diverge after the edit.
- Step 6: ANY new test failure, or test count differs from 786+10.
- Step 7: target cases still FAIL with `-2146825023` after one
  clean+build retry.
- Step 7/8: `create_linked_table.json` or any baseline-PASS case flips
  to ERROR, repeating in 2 of 3 runs.
- Step 9: ODBC parity changes at all.
- The fix seems to require touching `Winax.resi`, `Odbc.res`,
  `OdbcAdapter.res`, `winaxBinding.mts`, or `TsBridge.res`.
- You find yourself writing a `%raw` IIFE or `require(` — STOP and
  re-read the `%raw` discipline note.
- The mental pattern resembles v1 (any probe in the shared path) — STOP
  and re-read "Why this is scoped".

## Known follow-up (explicitly NOT this plan)

Both v1's Branch-4b attempt and v2's Step 7 may surface a latent **v8
isolate teardown crash** (exit 134, `DispObject::~scalar deleting
destructor`, same family as 033-F-001) when a real Append lands a
native proxy that the release/teardown path then mishandles. This is
the SAME defect family that keeps `generate_sql` skipped and
`get_linked_tables` unfixable via `TableDefs.Item`. It is a winax
dispose-ordering problem, not a marshaling problem, and it deserves
its own plan (proposed: `043-winax-dispose-ordering`) with probe-first
methodology against the release chain in `ComSession.res:255-260` and
`WINAX_BINDING.release` / `releaseAsync`. Do NOT attempt it inside
plan 042 — it changes the teardown contract for every COM case.

## v1 history (do not repeat)

Plan 042 v1 proposed adding a `__p__` envelope probe at the TOP of
`variantToJson`:

```rescript
let maybeProxy: option<JSON.t> = %raw(
  "(v) => (v !== null && typeof v === 'object' && v.__p__ !== undefined) ? v.__p__ : null"
)(v)
switch maybeProxy {
| Some(proxy) => proxy
| None => switch v { ... existing arms ... }
}
```

Executor (medium subagent) attempted v1 on commit `eeeeb1f` and STOPPED
at Step 3 with a catastrophic regression:

| | matched | mismatched | errored | skipped |
|---|---|---|---|---|
| Baseline (Step 0) | 10 | 1 | 2 | 2 |
| After fix (Step 3) | 0 | 13 | 0 | 2 |
| After clean+build retry | 0 | 13 | 0 | 2 |

The 11 previously-passing cases all flipped to MISMATCHED. The
executor diagnosed a "bidirectional" issue (return path), but the
actual cause is different: the probe in the shared `variantToJson`
intercepted values that flowed through that function for reasons
unrelated to the four intended call sites. (Possible mechanisms: ReScript
variant boxing where runtime values carry a `__p__` field unexpectedly,
or another code path we did not audit producing envelope objects.) The
regression was fully reverted; the working tree is clean at `eeeeb1f`.

v2 closes this by moving the discrimination from a shared-path probe
to a typed ADT constructor. The new arm in `variantToJson` can only
fire for `VComObject` values, and only 4 call sites produce them. The
v1 regression is structurally impossible in v2.

## Maintenance notes

- After landing, add one line to `AGENTS.md` "Key Gotchas": COM handles
  passed through `WINAX_BINDING.invoke` args must use the typed
  `ComInterfaces.VComObject(obj)` constructor; `variantToJson` unwraps
  the `{__p__}` envelope since plan 042 v2.
- The new arm's unwrap expression must match `winaxBinding.mts:_unwrap`
  (`v.__p__ !== undefined`) — keep the two in sync if either changes.
- If a future variant needs to carry a different kind of opaque handle
  (e.g., a callback), add a new constructor rather than overloading
  `VComObject`. The constructor is the discrimination mechanism.
