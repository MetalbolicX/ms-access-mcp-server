# Plan 046: Match the execute_sql_script success envelope — omit the `error` key

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat 016ebdb..HEAD -- rescript-mcp/src/Services/Facade.res rescript-mcp/test/FacadeTest.res rescript-mcp/test/Fakes.res`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

**DONE** — success envelopes omit `error`; failure envelopes retain it.

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (verification is independent of plan 045 — this case exits 0 today)
- **Category**: bug
- **Planned at**: commit `016ebdb`, 2026-09-07

## Why this matters

The COM DDL parity case `execute_sql_script.json` is the only remaining **content** mismatch (non-crash) in `parity:northwind:com:ddl`. Both children succeed identically (`statements_executed: 3`), but the ReScript envelope carries an extra `"error": null` key that the Python oracle omits on success. The differ does a deep key comparison, so one extra key fails the whole case. One-line fix plus a test update.

## Current state

### ReScript shaping site — `rescript-mcp/src/Services/Facade.res:911-949`

`_shapeSqlScriptResult` (called from `executeSqlScript` at `Facade.res:1495`). The `Ok` branch sets `error` unconditionally:

```rescript
911: let _shapeSqlScriptResult = (r: result<Interfaces.sqlScriptResult, Errors.t>): dict<JSON.t> => {
...
933:       Dict.set(result, "error", switch error {   // ← unconditional on the Ok branch
934:         | Some(e) => JSON.String(e)
935:         | None => JSON.Null                      // ← emits "error": null on success
936:       })
```

The comment above it (`:909-910`, claiming "Python envelopes always carry all 7 keys") is **outdated** — replace it.

### Python oracle — `src/ms_access_mcp/adapters/wincom.py`

Success envelopes have exactly 6 keys, NO `error`:

```python
1110-1117:  # empty-script success — 6 keys
1137-1144:  return {
                "success": True,
                "statements_executed": executed,
                "failing_statement": None,
                "failing_line": None,
                "access_error_code": None,
                "access_error_message": None,
            }
```

Failure paths (`:1070-1078, 1081-1089, 1097-1105, 1127-1135, 1150-1158`) DO include `"error"`. There is no re-shaping in `mcp/ddl.py` — the adapter dict is the envelope. (The docstring at `:1065` says error is "always present"; the code is the oracle, not the docstring.)

### Observed diff (run `run-1788834805035-osgzqoz`)

- ReScript: 7 keys — `{success, statements_executed, failing_statement, failing_line, access_error_code, access_error_message, error: null}`
- Python: 6 keys — same minus `error`
- Both children exit 0 with valid stdout; diff reported at `$`.

### Existing tests

- `rescript-mcp/test/FacadeTest.res:2335` — `testAsync("executeSqlScript: routes to schema adapter and returns sql_script result envelope", ...)` uses fake path `/tmp/test.sql` via `Fakes.CallLog`. Check whether it asserts the `error` key on success and update to the new contract (assert ABSENCE on success).
- `rescript-mcp/test/Fakes.res` — `FakeSchemaAdapter` returns a canned `sqlScriptResult`; its shape does not need to change (the shaper, not the fake, emits the key).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit suite | `pnpm -C rescript-mcp test` | 827 tests, 0 failed |
| Single parity case (COM ddl) | see below | `PASS execute_sql_script.json` |

Single-case command (PowerShell, any cwd — use this exact `node -e` wrapper shape; do NOT invoke `node parity/dist/run.js` directly):

```powershell
Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
$env:PARITY_VARIANT="com"
node -e "process.env.ACCESS_TEST_DB=require('path').resolve('D:/code/python/ms-access-mcp-server/db/northwind.accdb');process.env.ACCESS_TEST_ASSUME_ACE='1';process.argv=['node','run.js','--cases-dir=D:/code/python/ms-access-mcp-server/rescript-mcp/parity/cases/northwind/com/ddl','--case=execute_sql_script.json'];require('D:/code/python/ms-access-mcp-server/rescript-mcp/parity/dist/run.js')"
```

Full-suite alternative: `pnpm -C rescript-mcp parity:northwind:com:ddl`.

## Scope

**In scope**:

- `rescript-mcp/src/Services/Facade.res` — the `_shapeSqlScriptResult` Ok branch + its comment
- `rescript-mcp/test/FacadeTest.res` — the ess tests (only if they assert the success `error` key)
- `rescript-mcp/parity/findings.md` — outcome note
- `plans/README.md` — status row

**Out of scope**:

- `Interfaces.sqlScriptResult` record shape (the adapter-level record keeps `error: option<string>` — only the envelope shaping changes)
- The `Error(e)` branch of `_shapeSqlScriptResult` (`:939-949`) — it emits `error` and matches Python failure paths; leave it
- Failure-path shaping (`success: false` results): Python failure dicts include `error`, so keep emitting `error` whenever `success == false` — see Step 1 rule
- Any ODBC-side or case-file changes

## Git workflow

- Branch: `rescript/046-script-envelope-parity`
- Commit style: `fix(parity): omit error key on execute_sql_script success envelope`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Make the `error` key conditional in `_shapeSqlScriptResult`

In `Facade.res`, inside the `Ok({success, error, statementsExecuted, ...})` branch:

- Emit the `"error"` key ONLY when `success == false` OR `error` is `Some(e)`.
  - `Some(e)` → `JSON.String(e)`
  - `success == false` with `None` → `JSON.Null`
  - success with `None` → key absent entirely.
- Replace the stale comment at `:909-910` with one stating the actual contract: "Python success envelopes omit `error`; failure paths always include it (wincom.py:1070-1158)."

**Verify**: `pnpm -C rescript-mcp build` → exit 0.

### Step 2: Update the facade test

In `FacadeTest.res`, find the `ess-happy` test (`:2335`). After the change, on the success path the result dict must NOT contain `error`. Update assertions:

- keep existing success/`statements_executed` assertions;
- add: `getDictStr(result, "error") == None` (or the equivalent dict-lookup used in this file — copy the accessor style from a neighboring test, e.g. `getDictBool`/`getDictStr` defined near the top of the file).

If the fake-driven result in this test represents a failure (`success: false`), keep asserting `error` presence there instead — follow the fake's canned result.

**Verify**: `pnpm -C rescript-mcp build && pnpm -C rescript-mcp test` → 827 tests, 0 failed.

### Step 3: Parity verification

Run the single-case command from "Commands you will need" (after the MSACCESS kill + env setup).

**Verify**: output line is `  PASS  execute_sql_script.json`. Then run the full COM DDL suite: `pnpm -C rescript-mcp parity:northwind:com:ddl` → the summary must show `execute_sql_script` no longer among mismatches, and no NEW mismatch/error lines (existing exit-134 errors are plan 045's scope; the stale-skip `get_linked_tables` is plan 048's).

### Step 4: Record

- Append a dated note to `rescript-mcp/parity/findings.md` (the `execute_sql_script` mismatch from plan 039/044 era is resolved by envelope alignment).
- Update the `046` row in `plans/README.md` to DONE.
- `rescript-mcp/parity/findings.json` is rewritten by the parity run — refresh and commit alongside.

**Verify**: `git status` shows only in-scope files changed.

## Test plan

- Updated unit test: `FacadeTest.res` ess-happy — asserts `error` key ABSENT on success (and unchanged behavior for the readonly-rejection test at `:2355`, which exercises the Error branch).
- Differential: `execute_sql_script.json` parity case flips FAIL → PASS.
- Regression: full unit suite 827/827; COM DDL suite tally improves by exactly 1 matched.

## Done criteria

- [x] `pnpm -C rescript-mcp build` exits 0
- [x] `pnpm -C rescript-mcp test` → 827 tests, 0 failed, with the updated success-shape assertion present
- [x] Single-case parity run prints `PASS execute_sql_script.json`
- [x] `pnpm -C rescript-mcp parity:northwind:com:ddl` summary: mismatch count for this case gone; no new ERROR lines
- [x] No files outside in-scope list modified
- [x] findings.md + plans/README.md updated

## STOP conditions

- Drift check shows `_shapeSqlScriptResult` moved or its Ok branch no longer emits `error` unconditionally (already fixed independently).
- The parity case still FAILs after the key removal with a diff NOT at `$.error` — report the actual diff; do not chase new mismatches (they belong to other plans).
- The unit suite drops below 827 passing for a reason unrelated to the ess tests.

## Maintenance notes

- Envelope parity rule of thumb going forward: Python success envelopes omit `error` (this mirrors `_shapeLinkedTablesResult`'s comment at `Facade.res:874` — "Python success has NO error key"). New shapers should follow the conditional pattern, not the all-keys pattern.
- Reviewer focus: confirm the conditional rule (`success == false || error is Some`) rather than a blanket key deletion — failure paths must keep the key.
