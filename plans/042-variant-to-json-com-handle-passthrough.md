# Plan 042: variantToJson COM-handle passthrough (unblocks 040-F-001, resolves 038-F-005)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat e5ff1e5..HEAD -- rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Bindings/Winax.resi rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/src/Adapters/ComInterfaces.res rescript-mcp/src/Adapters/ComInterfaces.resi`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S (the core change is ~5 lines; the verification and the
  two-phase rollout are the real work)
- **Risk**: MED (touches `variantToJson` — the marshaling chokepoint used
  by ~60 call sites in `Winax.res`. All call sites pass variants; the
  change is additive for a currently-degenerate case, but the shared-path
  nature demands the regression gates in Steps 2 and 5)
- **Depends on**: nothing; unblocks plan 040 (refresh/recreate,
  038-F-005). Plan 041 is already SKIPPED and unaffected.
- **Category**: bug
- **Planned at**: commit `e5ff1e5`, 2026-09-04

## Why this matters

Plan 040's probe (finding **040-F-001** in `rescript-mcp/parity/findings.md:972-1024`)
proved the root cause of 038-F-005: every `Append` of a COM handle through
`WINAX_BINDING.invoke` silently no-ops because `variantToJson` erases the
handle to `null` before it reaches winax. Three call sites are affected
(`ComDataAdapter.res:2570`, `:2809`, `:2988`). The relations Append (:2570)
is masked by its read path; the two linked-table Appends are fatal: the
linked table never lands in `TableDefs`, so the parity cases
`refresh_linked_table.json` and `recreate_linked_table.json` fail with
"Item not found in this collection" (DAO scode `-2146825023`).

The standalone winax probe (040-F-001, probes in `$TEMP\probe040` on the
probing session) proved that passing the **raw proxy** (not the
`{__p__: ...}` envelope) to `Append` works perfectly: Count 80→81, named
lookup succeeds, `RefreshLink` succeeds. The only thing between that
success and the adapter is `variantToJson`.

This plan makes the minimal binding-layer change that the probe evidence
supports: teach `variantToJson` to pass through COM handles. It does NOT
attempt the teardown-ordering bug (see "Known follow-up" — deliberately
out of scope).

## Current state

- **The chokepoint** `rescript-mcp/src/Bindings/Winax.res:94-108`:

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

  No variant constructor carries a COM handle, so any call site that
  smuggles one via `%raw("(t) => t")(Obj.magic(tdef))` (the established
  workaround, e.g. `ComDataAdapter.res:2809`) produces a value with no
  recognizable `TAG` at runtime; the compiled switch falls through and
  emits `JSON.Null`.

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

  Mirrored in `ComInterfaces.resi:11-21`. **Adding a constructor requires
  touching both files** — this is why Approach A below was chosen over
  adding `VComObject`: the ADT is the published marshaling contract and
  changing it ripples through `Interfaces.res` consumers, the ODBC adapter
  (`OdbcAdapter.res` also constructs `variant` values), and any exhaustive
  switch on the type. A localized probe in `variantToJson` changes zero
  type surfaces.

- **The three Append call sites** (all the same pattern):
  - `ComDataAdapter.res:2570-2571` — relations Append (`createRelationship`)
  - `ComDataAdapter.res:2809-2810` — linked-table Append (`createLinkedTable`)
  - `ComDataAdapter.res:2988-2989` — linked-table Append (`recreateLinkedTable`)

- **Why `invoke`/`get` themselves are fine**: `TsBridge.winaxInvokeMethod`
  (`src/Js/winaxBinding.mts:44-50`) calls `(_unwrap(obj))[method](...args)`.
  `_unwrap` (`winaxBinding.mts:23-28`) unwraps the OUTER object but passes
  `args` through verbatim. The only mutator of args is `variantToJson` in
  the ReScript layer (`Winax.res:208` in `invoke`). Fix there and the args
  arrive intact.

- **The `%raw` discipline** (mandatory, from plan 039's failure history):
  `%raw` bodies must be function literals `(e) => { ... }`, never IIFEs —
  see the warning at `ComDataAdapter.res:57-59`.

## Chosen approach (of the four from 040-F-001 §Resolution paths)

**Approach A — `variantToJson` passthrough probe.** Before the switch,
detect a COM-handle envelope and return the inner proxy:

```rescript
let variantToJson: ComInterfaces.variant => JSON.t = (v: ComInterfaces.variant) => {
  // Plan 042: COM handles smuggled as variants arrive as {__p__: rawProxy}
  // envelopes (the ComInterfaces.comObject convention). Pass the raw proxy
  // through untouched — winax needs the dispatch pointer, not a wrapper.
  // FUNCTION LITERAL — never an IIFE (ComDataAdapter.res:57-59).
  let maybeProxy: option<JSON.t> = %raw(
    "(v) => (v !== null && typeof v === 'object' && v.__p__ !== undefined) ? v.__p__ : null"
  )(v)
  switch maybeProxy {
  | Some(proxy) => proxy
  | None =>
    switch v {
    | ComInterfaces.VBool(b) => JSON.Boolean(b)
    // ... existing arms unchanged ...
    }
  }
}
```

Rejected alternatives (040-F-001 lists all four; the reasons here are
recorded so the executor doesn't re-litigate them):
- **B (`invokeRaw` primitive)**: duplicates `invoke`'s entire body for one
  behavioral flag; the existing primitive must keep working identically
  anyway — more surface, same risk.
- **C (direct `%raw` bridge call at the Append sites)**: bypasses the
  binding contract per-call; spreads the marshaling knowledge into adapter
  code; exactly the fragmentation the binding layer exists to prevent.
- **D (`VComObject` ADT constructor)**: the "correct" long-term shape but
  touches the published ADT in `ComInterfaces.res`/`.resi`, forces
  re-audit of every `switch v` on `variant` (ODBC adapter included), and
  is a larger design decision than this bug warrants. **If the maintainers
  later adopt D, the probe in A stays harmless** (a `VComObject` payload
  would not carry `__p__` at the top level).

## Commands you will need

| Purpose        | Command (from repo root)                                    | Expected on success                |
|----------------|--------------------------------------------------------------|------------------------------------|
| Build          | `cmd.exe /c "pnpm -C rescript-mcp build"`                    | exit 0                             |
| Tests          | `cmd.exe /c "pnpm -C rescript-mcp test"`                     | 787 passed / 12 failed (9 unique known) |
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
- `rescript-mcp/src/Bindings/Winax.res` — the `variantToJson` passthrough
  (Approach A), ~6 lines added, zero lines removed.
- `rescript-mcp/parity/findings.md` — resolution note appended to
  040-F-001 and 038-F-005.
- `plans/README.md` — rows 040 and 042.

**Out of scope** (do NOT touch):
- `ComInterfaces.res` / `ComInterfaces.resi` — no ADT change (Approach D
  rejected; see above).
- The three Append call sites in `ComDataAdapter.res` — they are already
  correct modulo the bridge bug; do NOT change them in this plan. If the
  passthrough alone does not flip the parity cases, that is a STOP
  condition, not an invitation to edit the call sites.
- `winaxBinding.mts` / `TsBridge.res` — `_unwrap` behavior is correct as-is.
- The v8 teardown crash (033-F-001 family) surfaced by 040-F-001's Branch
  4b attempt — see "Known follow-up".
- `get_linked_tables.json` (plan 041's accepted skip) — do not unskip.

## Git workflow

- Branch: `rescript/038-linked-tables-sql-script` (HEAD `e5ff1e5`).
- **One commit** for the binding change, then a second for the parity
  confirmation + docs if the first lands cleanly (keeping the docs separate
  keeps the binding change bisectable):
  1. `fix(parity): pass COM handles through variantToJson (plan 042)`
  2. `docs(parity): resolve 038-F-005 via variantToJson passthrough (plan 042)`
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 0: Baseline capture

Kill MSACCESS, set parity env, run `parity:northwind:com:ddl` once, kill
MSACCESS. Record the exact tally.

**Verify**: `refresh_linked_table.json` and `recreate_linked_table.json`
both FAIL with `diff at $.error` containing `code=-2146825023`. Expected
tally: **11 matched + 2 mismatched + 0-1 errored + 2 skipped** (the 0-1
errored is the known transient exit-134 flake on `delete_table` /
`get_indexes` / `drop_index` / `recreate_linked_table`). If the two target
cases instead show DRIVER ERROR, the harness state is bad — kill MSACCESS,
wait 10s, retry once; if it persists, STOP (environment, not code).

### Step 1: The `variantToJson` passthrough

Apply Approach A to `Winax.res:94-108` exactly as shown in "Chosen
approach". Do NOT reformat the existing arms. Do NOT touch `Winax.resi`
(the function is module-internal — confirmed: `Winax.resi` does not export
`variantToJson`, so no signature change is needed; verify this by grepping
`variantToJson` in `Winax.resi` — expect zero hits; if it IS exported,
STOP, the surface is wider than this plan assumes).

**Verify**: `cmd.exe /c "pnpm -C rescript-mcp build"` -> exit 0.

### Step 2: Shared-path regression gate (before any parity)

`cmd.exe /c "pnpm -C rescript-mcp test"`.

**Verify**: 787 passed / 12 failed, 9 unique known failures (ComIntegration
495-500, ComExecuteQuery 645-647 family). ANY new failure -> revert and
STOP. This is the 038-F-008 blast-radius lesson: `variantToJson` is used by
every `invoke`/`get`/`set` call — a mistake here breaks everything, and the
test suite is the fastest signal.

### Step 3: Targeted parity

Kill MSACCESS, `parity:northwind:com:ddl`, kill MSACCESS.

**Expected outcomes, in preference order**:
- **Best**: both target cases PASS. Tally: **13 matched + 0 mismatched +
  0-1 errored + 2 skipped**. Go to Step 4.
- **Expected-possible**: one or both target cases flip from `FAIL at
  $.error` to `ERRORED exit 134`. This is the 040-F-001 Branch-4b behavior:
  the Append now actually lands, exposing the latent teardown crash. This
  is NOT success and NOT a new bug — it is the known follow-up. Per plan,
  accept it IF (a) the crash is the v8-teardown signature (no stdout, exit
  134, `DispObject::~scalar deleting destructor` in stderr if visible), AND
  (b) `create_linked_table.json` — the case that now exercises a REAL
  Append — still PASSES, AND (c) no other baseline-passing case regresses.
  Record the shift in findings.md (Step 6) and go to Step 4. If the exit
  134 appears on `create_linked_table.json` or any previously-PASS case,
  STOP/revert.
- **Failure**: both cases still FAIL with `-2146825023`. The passthrough
  did not take effect (compiled-output staleness, wrong site, or the
  envelope shape differs from `{__p__: ...}` at these call sites). Run
  `pnpm -C rescript-mcp clean && pnpm -C rescript-mcp build` ONCE and
  re-run. If still failing, STOP and report with the exact diff at
  `$.error`.

### Step 4: Full COM parity + stability (3 runs)

Three consecutive `parity:northwind:com:ddl` runs, killing MSACCESS and
waiting 5s between each.

**Verify**: the Step 3 outcome (whichever was achieved) reproduces in all
3 runs. The transient-flake category (exit 134 on
`delete_table`/`get_indexes`/`drop_index`/`recreate_linked_table`) is
pre-existing and shifts run to run — but `create_linked_table.json`,
`alter_table.json`, `create_table.json`, `create_index.json`,
`delete_query.json`, `set_query_sql.json`, `unlink_table.json` must PASS in
all 3 runs. Any PASS->ERROR regression that repeats in 2 of 3 runs -> STOP
and revert.

### Step 5: ODBC parity unchanged

`parity:northwind:ddl` -> 13 matched + 2 skipped. The ODBC path never
touches `variantToJson`, so any change here means something is deeply
wrong -> STOP and revert.

### Step 6: Document and commit

1. Append a resolution note to **040-F-001** in
   `rescript-mcp/parity/findings.md`: Approach A landed, the diff, the
   parity outcome (PASS or exit-134-shift), and the cross-reference to the
   known follow-up.
2. Update **038-F-005** status: RESOLVED (if both cases PASS) or
   SUPERSEDED-BY-TEARDOWN-BUG (if the exit-134 shift was accepted) — name
   the exact outcome, do not blur it.
3. Update `plans/README.md`: row 042 -> DONE with one-line summary; row 040
   stays BLOCKED but append "(unblocked by 042 pending teardown fix)" if
   the exit-134 shift was accepted, or "(unblocked by 042)" if both cases
   PASS.
4. Commit(s) per "Git workflow".

## Test plan

The parity cases are the tests (live differential vs the Python oracle).
The existing suite (Step 2) is the shared-path regression gate. No new unit
tests — the behavior requires live COM, and the ODBC suite proves the
non-COM paths are untouched.

## Done criteria

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] Test suite: 787 passed / 12 failed, 9 unique = known baseline
- [ ] COM parity Step 3 outcome achieved and reproduced across 3 runs:
  both target cases PASS, OR the accepted exit-134 shift with
  `create_linked_table.json` still PASS and zero repeating regressions
- [ ] ODBC parity: 13 matched + 2 skipped unchanged
- [ ] Only `Winax.res`, `findings.md`, `plans/README.md` modified
  (`git status` — probe scripts, if any, live in temp and are not committed)
- [ ] `variantToJson` diff is additive only (no existing arm touched)
- [ ] `%raw` bodies are function literals; no IIFE; no `require(`
- [ ] findings.md 040-F-001 + 038-F-005 updated; plans/README.md rows
  040/042 updated

## STOP conditions

- Drift: any in-scope file at HEAD differs from the excerpts above.
- `Winax.resi` DOES export `variantToJson` (grep finds it) — the change
  surface is wider than planned.
- Step 2 shows ANY new test failure.
- Step 3: target cases still FAIL with `-2146825023` after one
  clean+build retry.
- Step 3/4: `create_linked_table.json` or any baseline-PASS case flips to
  ERROR, repeating in 2 of 3 runs.
- Step 5: ODBC parity changes at all.
- The fix seems to require touching `ComInterfaces.res`/`.resi`,
  `winaxBinding.mts`, `TsBridge.res`, or the Append call sites.
- You find yourself writing a `%raw` IIFE or `require(` — STOP and re-read
  the `%raw` discipline note.

## Known follow-up (explicitly NOT this plan)

040-F-001's Branch-4b attempt and this plan's Step 3 both surface a latent
**v8 isolate teardown crash** (exit 134, `DispObject::~scalar deleting
destructor`, same family as 033-F-001) when a real Append lands a native
proxy that the release/teardown path then mishandles. This is the SAME
defect family that keeps `generate_sql` skipped and `get_linked_tables`
unfixable via `TableDefs.Item`. It is a winax dispose-ordering problem,
not a marshaling problem, and it deserves its own plan (proposed:
`043-winax-dispose-ordering`) with probe-first methodology against the
release chain in `ComSession.res:255-260` and `WINAX_BINDING.release` /
`releaseAsync`. Do NOT attempt it inside plan 042 — it changes the
teardown contract for every COM case.

## Maintenance notes

- After landing, add one line to `AGENTS.md` "Key Gotchas": COM handles
  passed through `WINAX_BINDING.invoke` args must be `{__p__: proxy}`
  envelopes; `variantToJson` passes them through verbatim since plan 042.
- If the maintainers later adopt the `VComObject` ADT constructor
  (Approach D), remove the probe — but only after auditing every
  `switch v` over `variant` in the repo (ODBC adapter included).
- The probe pattern (`v.__p__ !== undefined`) is the same envelope check
  `winaxBinding.mts:_unwrap` uses — keep the two in sync if either changes.
