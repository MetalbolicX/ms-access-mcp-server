# Plan 039 (REVISED v2): Implement executeSqlScript via a structured-error winax binding (resolve 038-F-006)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **This revision supersedes the original plan.** Three prior attempts
> failed on compositional mistakes, not on one fundamental blocker. Every
> failure mode is now mapped to a proven pattern inside this same codebase.
> Do NOT deviate from the prescribed patterns — each one exists because a
> specific alternative was observed to crash or fail.
>
> **Drift check (run first)**: `git diff --stat ae8500f..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/src/Adapters/ComSession.res rescript-mcp/src/Bindings/Winax.res rescript-mcp/src/Bindings/Winax.resi rescript-mcp/parity/runRescript.ts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (touches the shared connect path in ComSession.res — the
  038-F-008 lesson applies; the stability gate is mandatory, and Step 3
  has its own regression check BEFORE any adapter work)
- **Depends on**: none (baseline is `ae8500f`; parity 10 matched + 3
  mismatched + 0-1 errored + 1 skipped, where the 0-1 errored is the known
  `recreate_linked_table.json` exit-134 flake)
- **Category**: bug
- **Originally planned at**: `ae8500f`, 2026-09-03; **revised** 2026-09-04
  after 3 reverted attempts
- **Scope (v2)**: `Bindings/Winax.res` + `Bindings/Winax.resi` +
  `Adapters/ComSession.res` + `Adapters/ComDataAdapter.res`. The original
  single-file scope (`ComDataAdapter.res` only) is **provably insufficient**
  — see "Failure history".

## Failure history (why v2 looks like this)

Three implementation attempts were made and reverted. Six distinct failure
modes were observed. Each fix below is a pattern that already works in this
repo:

| # | Observed failure | Root cause | Prescribed fix (precedent) |
|---|------------------|------------|-----------------------------|
| 1 | `accessErrorCode` always `null` through `WINAX_BINDING.invoke` | `Bindings/Winax.res:211-214` catch reduces the JS Error to a string via `exnMessage(e)` -> `mapDispatchError(msg, None, None, None)`. The numeric `.number` is destroyed before any caller sees it | New `invokePreservingError` variant inside the module (Step 1) |
| 2 | Native crash with `%raw` helper (`exit 134`) | ReScript's `%raw` wraps the JS as `EXPR(e)`; an IIFE like `(() => { ... })()` returns an object which the wrapper then *invokes* with `(e)` -> crash. Documented at `ComDataAdapter.res:57-59` | `%raw` bodies MUST be function literals `(e) => { ... }`. Proven at `ComDataAdapter.res:2810` |
| 3 | `The value invokePreservingError can't be found in Bindings.Winax` | A free top-level `let` in a `.res` file with a sibling `.resi` is stripped from the module's exports unless declared in the `.resi` | Declare the new function inside the `WINAX_BINDING` module AND add it to the module type in BOTH `Winax.res` and `Winax.resi` (Step 1) |
| 4 | Binding worked in isolation but failed under the harness | Attempt inlined `%raw("(p) => import(p)")("winax")`; dynamic `import()` does not compose with the harness runner context | Reuse the module-local `_importWinax(())` (declared `Winax.res:51`) — only reachable from inside the module, which is why the helper must live there |
| 5 | `require is not defined` | `parity/dist/runRescript.js` runs ESM; `require('fs')` in a `%raw` throws | Use `NodeJs.Fs.readFileSync` — proven at `ComDbProps.res:236`, `ComDbProps.res:390` |
| 6 | ADO `Open()` on the session connection -> exit 134, 3 cases regressed | The session's `adoConn` is an orphan `createObject("ADODB.Connection")` (`ComSession.res:201`), never opened; opening a second connection while Access holds the `.accdb` destabilizes the session | Do NOT open a connection at all. Mirror Python: take `accessApp.CurrentProject.Connection` (`wincom.py:214`), which is already open (Step 2) |

Additional hard-won facts:

- The recursive statement loop must be `let rec recurse = ...` (a plain
  `let recurse` that calls itself fails with "The value recurse can't be
  found").
- The parity diff reports the first **alphabetically-sorted** key
  difference, so `$.access_error_code` differing does NOT imply other
  fields match. Expect `error` / `failing_statement` / `failing_line` /
  `statements_executed` to need matching too — see Step 0 and Step 4b.
- Python's `error` field for COM failures is the pywin32 `com_error` tuple
  repr, e.g. `(-2147352567, 'Exception occurred.', (0, 'DAO.TableDef', 'Invalid argument.', 'jeterr40.chm', 5003001, -2146825287), None)` (observed in the
  `recreate_linked_table.json` finding). Step 0 determines the exact
  construction; Step 4b mirrors it.

## Why this matters

`executeSqlScript` is the last plan-038 method without a real
implementation. The parity case `execute_sql_script.json` currently
mismatches at `$.access_error_code` (Python: `-2147217900`, ReScript stub:
`null`). Python itself FAILS the injected script (the harness writes a
deliberate-failure script at runtime — `runRescript.ts:284-301`), so parity
means reproducing the same structured failure, not a success. Both sides
must run the SAME ADO connection type (`CurrentProject.Connection`) so the
provider error surface is identical — this is why Step 2 is required for
parity, not merely a nice-to-have.

## Current state

- **The stub** `rescript-mcp/src/Adapters/ComDataAdapter.res:3076-3126`:
  guard triple (Not connected / No session / No DB handle) then a hardcoded
  failure envelope with `accessErrorCode: None`. Guards stay verbatim; only
  the final `| Some(_db) =>` arm body is replaced.

- **The binding defect** `rescript-mcp/src/Bindings/Winax.res:201-217`:

```rescript
let invoke: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>> = (
  ((obj, method, args) => {
    _importWinax(())
      ->Promise.then(m => {
        let rawMod = TsBridge.unwrapWinaxModule(m)
        let rawArgs: array<JSON.t> = Array.map(args, v => variantToJson(v))
        let value: JSON.t = TsBridge.winaxInvokeMethod(rawMod, obj, method, rawArgs)
        Promise.resolve(Ok(value))
      })
      ->Promise.catch(e => {
        let msg = exnMessage(e)
        Promise.resolve(Error(mapDispatchError(msg, None, None, None)))  // scode destroyed HERE
      })
  }): ...
)
```

  `_importWinax` (`Winax.res:51`) and `variantToJson` (`Winax.res:73`) are
  module-locals — the new variant MUST live inside the module to reuse them
  (failure modes 3 and 4).

- **Module type declarations** exist in BOTH `Winax.res` (top of file,
  `module type WINAX_BINDING = { ... }`) and `Winax.resi` (lines 4-30).
  Both must gain the new type + function signature. The `.resi` also ends
  with `module WINAX_BINDING: WINAX_BINDING` (line 33).

- **The orphan ADO connection** `rescript-mcp/src/Adapters/ComSession.res:200-209`:

```rescript
// Step 8: ADODB.Connection — best-effort
Bindings.Winax.WINAX_BINDING.createObject("ADODB.Connection")
  ->Promise.then(adoResult => {
    switch adoResult {
    | Error(_) => { session.handles.adoConn = None }
    | Ok(adoConn) => { session.handles.adoConn = Some(adoConn) }
    }
    session.isConnected = true
    Promise.resolve(Ok(true))
  })
```

- **Python's pattern** `src/ms_access_mcp/adapters/wincom.py:214`:
  `self._dispatcher._ado_conn = self._dispatcher._access_app.CurrentProject.Connection`
  — already open, bound to the live DB, and the exact error surface parity
  needs. `execute_sql_script` (`wincom.py:1053-1158`) iterates parsed
  statements calling `ado.Execute(text)`, and on failure fills the envelope
  from `self._extract_com_error(e)`.

- **Result shape** `Interfaces.res:104-112` (unchanged):
  `{success, error, statementsExecuted, failingStatement, failingLine, accessErrorCode, accessErrorMessage}`.

- **Statement parser**: `parseScriptLines` at `ComDataAdapter.res:241`
  returns `{statements: [{text, line}]}` — already committed, reuse as-is.

- **fs precedent**: `ComDbProps.res:236` — `NodeJs.Fs.readFileSync(path)` +
  `NodeJs.Buffer.toString`. ESM-safe; never `require('fs')` in `%raw`.

- **Parity baseline** (verified by direct harness run at `ae8500f`):
  10 matched + 3 mismatched + 0-1 errored + 1 skipped. The 3 mismatches:
  `execute_sql_script` (this plan), `refresh_linked_table` / `recreate_linked_table`
  (plan 040), `get_linked_tables` (plan 041). The 1 skipped is
  `generate_sql` (033-F-001). The flaky errored is `recreate_linked_table`
  exit 134.

## Commands you will need

| Purpose        | Command (from repo root)                                    | Expected on success                |
|----------------|--------------------------------------------------------------|------------------------------------|
| Build          | `cmd.exe /c "pnpm -C rescript-mcp build"`                    | exit 0 (warnings are fine)         |
| Tests          | `cmd.exe /c "pnpm -C rescript-mcp test"`                     | 787 passed / 12 failed (9 unique known) |
| COM parity     | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:com:ddl"` | see per-step expectations          |
| ODBC parity    | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:ddl"`     | 13 matched + 2 skipped             |
| Kill Access    | `Get-Process MSACCESS -EA SilentlyContinue \| Stop-Process -Force` then `Start-Sleep -Seconds 3` | before AND after every COM run |

Parity env (PowerShell):
```powershell
$env:ACCESS_TEST_ASSUME_ACE='1'; $env:ACCESS_TEST_DB="$PWD\db\northwind.accdb"
$env:ACCESS_MCP_ALLOWED_DIRS="$PWD\db;$env:TEMP"; $env:ACCESS_MCP_READONLY='false'
```

## Scope

**In scope** (exactly these files):
- `rescript-mcp/src/Bindings/Winax.res` — add `preservedError` type +
  `invokePreservingError` INSIDE the `WINAX_BINDING` module; add both to
  the `module type WINAX_BINDING` declaration in this file.
- `rescript-mcp/src/Bindings/Winax.resi` — mirror the module-type additions.
- `rescript-mcp/src/Adapters/ComSession.res` — replace the orphan ADO
  creation (Step 8 block, lines ~200-209) with the CurrentProject chain +
  fallback.
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — replace the
  `executeSqlScript` stub arm (plus, if needed for Step 4b, one small
  module-level error-format helper).
- `rescript-mcp/parity/findings.md` — 038-F-006 resolution note.
- `plans/README.md` — row 039 status.

**Out of scope** (do NOT touch):
- `Interfaces.res` / `Interfaces.resi` — the result shape is already right.
- The existing `invoke`/`invokeAsObject` catch arms — the new variant is
  additive; changing the existing error mapping risks 50+ call sites.
- `OdbcAdapter.res`, parity runner/driver files, case JSON files.
- `volatileFields` on the case — masking a diff is NOT an accepted outcome
  of this plan; only the operator may decide that (STOP condition instead).

## Git workflow

- Branch: `rescript/038-linked-tables-sql-script`.
- **Two commits** (bisectable):
  1. `feat(parity): add invokePreservingError winax binding variant (plan 039)`
     — Step 1 only. Additive, no behavior change.
  2. `feat(parity): implement executeSqlScript via CurrentProject ADO connection (plan 039)`
     — Steps 2-7.
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 0: Read the Python error contract (no code changes)

Read `src/ms_access_mcp/adapters/wincom.py` `_extract_com_error` (search
for `def _extract_com_error`) and `execute_sql_script` (:1053-1158).
Record EXACTLY:
- how `error` is built (observed elsewhere as the `com_error` tuple repr
  `(-2147352567, 'Exception occurred.', (0, 'DAO.TableDef', 'Invalid argument.', 'jeterr40.chm', 5003001, -2146825287), None)`),
- how `access_error_code` is built (scode, from `com_error.args[2][5]` or
  `.args[0]` depending on shape),
- how `access_error_message` is built.

These three constructions are the Step 4b templates. If the observed
`recreate` finding format differs from what you read, trust the code.

**Verify**: you have written down the three constructions (they go into the
Step 4b helper).

### Step 1: The binding variant (commit 1)

In `Bindings/Winax.res`, inside `module type WINAX_BINDING = { ... }` (top
of file), add to the signature:

```rescript
// Plan 039: structured-error invoke — preserves .number/.description for
// accessErrorCode parity. See invokePreservingError impl below the type.
type preservedError = {
  message: string,
  number: option<int>,
  code: option<int>,
  hresult: option<int>,
  description: option<string>,
  source: option<string>,
}
let invokePreservingError: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, preservedError>>
```

(If the compiler rejects the inline record type in the module type,
declare `preservedError` at the top of the file, BEFORE the module type,
and reference it — then mirror the same placement in the `.resi`.)

Inside `module WINAX_BINDING: WINAX_BINDING = { ... }`, add the
implementation after the existing `invoke` (ends ~line 217):

```rescript
// invokePreservingError — same call path as invoke, but the catch returns
// the structured COM error instead of flattening it to a string. Needed
// for accessErrorCode parity (plan 039); invoke itself is untouched.
let invokePreservingError: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, preservedError>> = (
  (obj: ComInterfaces.comObject, method: string, args: array<ComInterfaces.variant>) => {
    _importWinax(())
      ->Promise.then(m => {
        let rawMod = TsBridge.unwrapWinaxModule(m)
        let rawArgs: array<JSON.t> = Array.map(args, v => variantToJson(v))
        let value: JSON.t = TsBridge.winaxInvokeMethod(rawMod, obj, method, rawArgs)
        Promise.resolve(Ok(value))
      })
      ->Promise.catch(e => {
        // FUNCTION LITERAL — never an IIFE (ComDataAdapter.res:57-59).
        // Walks the {RE_EXN_ID, _1} envelope exactly like _exnMessage.
        let captured: preservedError = %raw(
          "(e) => { var inner = (e && typeof e === 'object' && e._1 && typeof e._1 === 'object') ? e._1 : e; var numOrNull = function(v) { return (typeof v === 'number' && v !== 0) ? v : null; }; var strOrNull = function(v) { return (typeof v === 'string' && v.length > 0) ? v : null; }; if (!inner || typeof inner !== 'object') { return { message: 'Unknown error', number: null, code: null, hresult: null, description: null, source: null }; } return { message: (inner.message !== undefined && inner.message !== null && inner.message !== '') ? String(inner.message) : 'Unknown error', number: numOrNull(inner.number), code: numOrNull(inner.code), hresult: numOrNull(inner.hresult), description: strOrNull(inner.description), source: strOrNull(inner.source) }; }"
        )(e)
        Promise.resolve(Error(captured))
      })
  }: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, preservedError>>
)
```

Mirror the type + signature additions in `Bindings/Winax.resi` inside
`module type WINAX_BINDING` (lines 4-30).

**Verify**: `cmd.exe /c "pnpm -C rescript-mcp build"` -> exit 0. Then run
the full test suite -> 787/12 baseline unchanged. Then one COM parity run
-> baseline tally unchanged (this commit changes nothing behaviorally).
Commit 1.

### Step 2: Session ADO connection via CurrentProject (regression-critical)

In `ComSession.res`, replace the Step 8 block (lines ~200-209) so the
session takes Access's own open connection instead of an orphan
`ADODB.Connection`. The Python pattern is a chained property read:
`accessApp.CurrentProject.Connection`.

1. `Bindings.Winax.WINAX_BINDING.get(accessApp, "CurrentProject")` — if
   `Ok`, wrap the JSON handle with the `%raw("v => ({ __p__: v })")`
   envelope convention used throughout `ComDataAdapter.res`.
2. Then `get(cpObj, "Connection")` — same treatment; store in
   `session.handles.adoConn`.
3. If EITHER get fails, fall back to the existing
   `createObject("ADODB.Connection")` (the current code) so connect can
   never regress relative to baseline. `adoConn = None` remains the final
   fallback.
4. `session.isConnected = true` and `Promise.resolve(Ok(true))` stay
   exactly as after the existing block.

NOTE: if `get` does not surface `CurrentProject` (property vs method
dispatch difference in winax), try
`invokeAsObject(accessApp, "CurrentProject", [])` / `invokeAsObject(cpObj, "Connection", [])`
as the alternate probe. Use whichever returns `Ok`; keep the fallback.
Do NOT call `.Open()` on anything — that is failure mode 6.

**Verify**: build exit 0; full test suite 787/12 unchanged. Then COM parity
(expect: NO regressions vs baseline — every case that passed at baseline
still passes; `execute_sql_script` still FAILs, which is fine, the adapter
is still a stub). This step touches the shared connect path: if ANY
baseline-passing case regresses here, STOP before Step 3 and report —
the session change is not safe on this machine.

### Step 3: The executeSqlScript body

In `ComDataAdapter.res`, replace only the final `| Some(_db) =>` arm of
`executeSqlScript` (lines ~3110-3121). Logic in order:

1. **ADO handle**: `ComSession.getHandles(session).adoConn`. If `None`,
   failure envelope `error: Some("No ADO connection")`, all else None/0.
2. **Read the script**: `NodeJs.Fs.readFileSync(scriptPath)` ->
   `NodeJs.Buffer.toString` (precedent `ComDbProps.res:236`). Wrap in
   `try/catch`-equivalent error handling; on failure return a failure
   envelope with the fs message (Python returns
   `File not found: <path>` — mirror that string for the not-found case:
   check existence with `NodeJs.Fs.existsSync` first and emit exactly
   `"File not found: " ++ scriptPath`).
3. **Parse**: `parseScriptLines(rawSql)` (`:241`). Empty statements ->
   SUCCESS envelope `statementsExecuted: 0`, rest None (matches Python
   `wincom.py:1109-1117`).
4. **Iterate sequentially** with `let rec recurse = (idx, count) => ...`
   (the `rec` keyword is mandatory — a prior attempt failed without it).
   Per statement:
   `Bindings.Winax.WINAX_BINDING.invokePreservingError(ado, "Execute", [ComInterfaces.VStr(entry.text)])`.
   - `Ok(_)` -> `recurse(idx + 1, count + 1)`
   - `Error(perr)` -> failure envelope:
     `success: false`, `statementsExecuted: count`,
     `failingStatement: Some(entry.text)`, `failingLine: Some(entry.line)`,
     `error` / `accessErrorCode` / `accessErrorMessage` per Step 4b.
5. Loop end -> success envelope with the final count.

**Verify**: build exit 0; test suite 787/12 unchanged.

### Step 4: Targeted parity — first WITHOUT message mirroring

Kill MSACCESS, parity env, `parity:northwind:com:ddl`, kill MSACCESS.

**Expected**: `execute_sql_script.json` either PASSES outright or FAILs at
`$.error` / `$.access_error_message` (string-format difference between
winax fields and pywin32's formatting). A diff at `$.access_error_code`
with any value other than `-2147217900` means the scode extraction is
wrong — inspect with a temporary stderr log from the `%raw` capture, fix,
re-run (2 attempts max, then STOP).
A diff at `$.statements_executed` or `$.failing_statement` means the two
sides are erroring on DIFFERENT statements — that implies the ADO
connection differs from Python's; re-check Step 2 used
`CurrentProject.Connection` (not the fallback), then STOP if confirmed.
Any OTHER case newly errored (exit 134) -> STOP (session instability;
the Step 2 change is the suspect — be ready to revert everything after
commit 1).

### Step 4b: Mirror the Python error strings

Using the Step 0 templates, build `error`, `accessErrorCode`,
`accessErrorMessage` from `perr`:
- `accessErrorCode: perr.number` (the scode),
- `accessErrorMessage` and `error` formatted exactly as
  `_extract_com_error` builds them (likely the com_error tuple repr —
  construct with string concatenation from `perr.number` /
  `perr.description` / `perr.source`; a small module-level helper
  `_pyComErrorRepr` is acceptable and expected).

**Verify**: re-run COM parity. `execute_sql_script.json` **PASS**. Final
tally: **11 matched + 3 mismatched + 0-1 errored + 1 skipped** (the 0-1 is
the known `recreate_linked_table` flake; 3 mismatches belong to plans
040/041). If the string cannot be made to match after 2 formatting
attempts, STOP and report the exact two strings — do NOT touch
`volatileFields` (operator decision).

### Step 5: ODBC parity unchanged

**Verify**: `parity:northwind:ddl` -> 13 matched + 2 skipped.

### Step 6: Stability gate (3 runs — mandatory)

Three consecutive COM parity runs, killing MSACCESS + 3-5s wait between.
`execute_sql_script.json` PASS in all 3; no baseline-passing case regresses
in 2 of 3 runs (single-run flakes on `delete_table`/`get_indexes`/
`drop_index`/`recreate_linked_table` are pre-existing; a NEW pattern that
tracks this change means revert — 038-F-008 lesson).

### Step 7: Document and commit (commit 2)

Append a RESOLVED note to `038-F-006` in `rescript-mcp/parity/findings.md`:
implementation path (binding variant + CurrentProject connection + message
mirroring), the exact scode observed, verification tallies. Update
`plans/README.md` row 039 -> DONE. Commit 2 per the message above.

## Test plan

The parity case is the test (live differential vs the Python oracle; the
harness injects the deliberate-failure script). The existing suite is the
regression gate for the shared-path change (Step 2). No new unit tests —
behavior requires live COM.

## Done criteria

- [ ] Commit 1 (binding variant) additive: build + tests + parity all at baseline after it
- [ ] Commit 2: `execute_sql_script.json` PASS in 3 consecutive COM parity runs
- [ ] Final COM tally: 11 matched + 3 mismatched + 0-1 errored (known flake only) + 1 skipped
- [ ] Test suite: 787 passed / 12 failed, 9 unique = known baseline
- [ ] ODBC parity: 13 matched + 2 skipped unchanged
- [ ] Only the 6 in-scope files modified (`git status`)
- [ ] findings.md + plans/README.md updated
- [ ] No `%raw` IIFE anywhere in the diff
- [ ] No `require(` anywhere in the diff
- [ ] No `.Open(` call on any ADO connection in the diff

## STOP conditions

- Drift: any in-scope file at HEAD differs from the excerpts above.
- Step 1 build/type errors persist after 2 attempts (the module-type
  placement may need the before-type declaration variant — try that once).
- Step 2 regresses ANY baseline-passing parity case (session change unsafe
  here) — revert working tree to commit 1 and report.
- Step 4: `$.access_error_code` diff with a value other than `-2147217900`
  after 2 attempts.
- Step 4: `$.statements_executed` / `$.failing_statement` mismatch
  confirming the fallback orphan connection is in use.
- Step 4b: error strings unmatched after 2 formatting attempts (report both
  strings verbatim; volatileFields is the operator's call, not yours).
- Any new exit-134 pattern that tracks this change across the stability
  gate.
- You find yourself needing a file outside the in-scope list.

## Maintenance notes

- After landing, add two lines to `AGENTS.md` "Key Gotchas": (1) `%raw`
  bodies must be function literals, never IIFEs; (2) new `Winax` exports
  require mirroring in BOTH `Winax.res` module type and `Winax.resi`.
- The orphan-ADO fallback in `ComSession.res` can be deleted once
  `CurrentProject.Connection` proves stable across a few sessions of use —
  leave a `// TODO(plan 039 follow-up)` comment.
- Plans 040/041 do NOT depend on this plan; if this plan STOPs at Step 2,
  dispatch them independently.
