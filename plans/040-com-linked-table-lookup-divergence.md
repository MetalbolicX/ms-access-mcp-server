# Plan 040: Fix refresh/recreate linked-table named-lookup divergence (resolve 038-F-005)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. This plan is **probe-first**: Steps 1–3 are
> read-only instrumentation that determines which fix branch (4a or 4b) to
> take. Do not skip the probe. When done, update the status row for this
> plan in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat ae8500f..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/parity/runRescript.ts rescript-mcp/scripts/parity_driver.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none required; independent of plans 039 and 041 (touch the same file but different functions — if run concurrently, sequence the commits)
- **Category**: bug
- **Planned at**: commit `ae8500f`, 2026-09-03

## Why this matters

In COM parity, `refresh_linked_table.json` and `recreate_linked_table.json`
both fail because the ReScript adapter cannot find by name a linked table
that the same ReScript adapter just created in the case's setup step:
`error: "message=Item not found in this collection. | ... | code=-2146825023
| source=DAO.TableDefs"`. The Python oracle (same machine, same fixture
copy) finds it and succeeds. Until this is fixed, 2 of 15 COM DDL cases are
blocked. The mechanism is unknown; two hypotheses have been tested and
rejected (see 038-F-008, 038-F-009 in `rescript-mcp/parity/findings.md`),
so this plan starts with a diagnostic probe instead of another blind fix.

## Current state

- The failing lookup, `rescript-mcp/src/Adapters/ComDataAdapter.res:2878`
  (in `refreshLinkedTable`, guard arms precede it):

```rescript
| Some(db) => {
    Bindings.Winax.WINAX_BINDING.invokeAsObject(db, "TableDefs", [ComInterfaces.VStr(name)])
    ->Promise.then(tdefResult => { switch tdefResult {
      | Error(e) => Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
      | Ok(tdefJson) => { let tdef: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(tdefJson)
          // ... set Connect, invoke(tdef, "RefreshLink", []), sanitize write-back ...
```

  and the same named lookup at `ComDataAdapter.res:2946` inside
  `recreateLinkedTable.resolveAttrs` (on `Error` it swallows to
  `-2147483648` and continues to `Delete` at `:2966`, which then throws the
  same "Item not found").

- The setup that creates the linked table, `ComDataAdapter.res:2799-2812`
  (in `createLinkedTable`):

```rescript
Bindings.Winax.WINAX_BINDING.get(db, "TableDefs")
->Promise.then(tableDefsResult => { switch tableDefsResult {
  | Ok(tableDefsJson) => {
      let tableDefs: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(tableDefsJson)
      let tdefAsVariant: ComInterfaces.variant = %raw("(t) => t")(Obj.magic(tdef))
      Bindings.Winax.WINAX_BINDING.invoke(tableDefs, "Append", [tdefAsVariant])
```

- The WORKING precedent (relations Append passes parity),
  `ComDataAdapter.res:2568-2571` — note it is the SAME wrapping pattern:

```rescript
let relsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(relsJson)
let relAsVariant: ComInterfaces.variant = %raw("(r) => r")(Obj.magic(rel))
Bindings.Winax.WINAX_BINDING.invoke(relsHandle, "Append", [relAsVariant])
```

  (fields Append at `:2606-2609` is identical in shape.)

- Python oracle `src/ms_access_mcp/adapters/wincom.py:860-876` delegates to
  `dao.py`; `dao.py:1275-1315` `refresh_linked_table` does
  `tdef = self._dispatcher.current_db.TableDefs(name)` then
  `tdef.RefreshLink()` on the same STA dispatcher that ran the setup Append
  (`dao.py:1265` `db.TableDefs.Append(tdef)` with a real pywin32 object).

- Parity cases:
  `rescript-mcp/parity/cases/northwind/com/ddl/refresh_linked_table.json`
  and `.../recreate_linked_table.json` — both have
  `setup: [{operation: "create_linked_table", args: {name: "lnk_categories", source_table: "categories", connect_string: ";DATABASE=REPLACE_SOURCE_DB"}}]`.
  `runRescript.ts:257-278` substitutes `REPLACE_SOURCE_DB` from
  `process.env.PARITY_SOURCE_DB` and dispatches to
  `Facade.refreshLinkedTable` / `Facade.recreateLinkedTable`.
  **Setup execution path**: setup ops run through the same `_run_op`
  dispatch in the respective drivers (`parity_driver.py:507-...`,
  `runRescript.ts` pre-loop, wired by plan 035). Setup runs on the SAME
  fixture copy and the SAME process as the main op for each side
  (per-side copies `py.accdb` / `rs.accdb` under a temp scratch dir; see
  `run.mjs:163-170`).

- Rejected hypotheses (do NOT retry):
  - **038-F-009**: adding `TableDefs.Refresh` before the named lookup did
    not help and regressed `get_indexes.json` to exit 134. The collection is
    fetched fresh per call; there is no stale-cache issue.
  - **038-F-008**: unrelated, but proves MSysObjects system-table queries
    destabilize the shared MSACCESS session. Do not use MSysObjects in this
    plan's fix.

- Open hypothesis (untested): the `Append` call "succeeds" (returns Ok) but
  the marshaled variant does not carry a usable COM dispatch pointer, so
  DAO either appends a broken entry or silently no-ops. The relations/fields
  Append sites use the identical wrapper — but their parity cases read back
  via different paths (`getRelationships`/`getIndexes` iterate through
  freshly-fetched collections from a *reloaded* state in the case files),
  so a silent no-op Append could be masked there while being fatal here.

## Commands you will need

| Purpose        | Command (from repo root)                                                        | Expected on success                |
|----------------|----------------------------------------------------------------------------------|------------------------------------|
| Build          | `cmd.exe /c "pnpm -C rescript-mcp build"`                                        | exit 0                             |
| Tests          | `cmd.exe /c "pnpm -C rescript-mcp test"`                                         | exit 1 with exactly the 9 known unique failures; 787/12 totals |
| COM parity     | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:com:ddl"`                     | both target cases PASS             |
| ODBC parity    | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:ddl"`                         | 13 matched + 2 skipped             |
| Kill Access    | `Get-Process MSACCESS -EA SilentlyContinue \| Stop-Process -Force` then `Start-Sleep -Seconds 3` | before AND after every COM run |

Parity env (PowerShell):
```powershell
$env:ACCESS_TEST_ASSUME_ACE='1'; $env:ACCESS_TEST_DB="$PWD\db\northwind.accdb"
$env:ACCESS_MCP_ALLOWED_DIRS="$PWD\db;$env:TEMP"; $env:ACCESS_MCP_READONLY='false'
```

## Scope

**In scope**:
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — probe instrumentation
  (temporary), and the fix in `refreshLinkedTable` (:2864-2922),
  `recreateLinkedTable` (:2926-3045), and/or `createLinkedTable`
  (:2770-2860) depending on probe outcome.
- A throwaway probe script under the OS temp dir (NOT committed), e.g.
  `%TEMP%\opencode\probe-tddefs.js`.

**Out of scope** (do NOT touch):
- The relations Append (:2568-2571) and fields Append (:2606-2609) sites —
  they pass parity today; even if the probe implicates the shared wrapper
  pattern, fix it ONLY at the linked-table call sites first.
- `WINAX_BINDING` itself (`Bindings/Winax.res`) — if the fix requires a new
  binding primitive, that is a STOP condition (new binding surface = new
  design decision, out of this plan's STRICT-TDD scope).
- Python files, case files, `runRescript.ts`, `parity_driver.py` — the
  divergence is provably on the ReScript side (Python succeeds on the same
  fixture copy).
- MSysObjects-based approaches (rejected, 038-F-008).
- `TableDefs.Refresh` (rejected, 038-F-009).

## Git workflow

- Branch: continue on `rescript/038-linked-tables-sql-script`.
- Commit style (from `git log`): conventional commits, e.g.
  `fix(parity): unwrap COM dispatch pointer in linked-table Append (plan 040)`.
- Probe script lives in temp; never committed.
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 1: Probe — does the setup Append land the TableDef?

Write a standalone Node probe script (temp dir, not committed) that uses
the project's winax binding to reproduce exactly what the parity case does,
against a scratch COPY of the fixture:

1. Copy `db/northwind.accdb` to `%TEMP%\probe-northwind.accdb`.
2. In Node: connect via the same code path the runner uses (look at
   `rescript-mcp/parity/runRescript.ts` for how it builds the facade, or
   simpler: `require` the built adapter directly and call connect →
   createLinkedTable with the case's args → then attempt the named lookup).
3. After `createLinkedTable` returns, log: `TableDefs.Count` before/after,
   and whether `TableDefs("lnk_categories")` (named access) throws.
4. Also log what `invoke(tableDefs, "Append", [variant])` returns and
   whether inspecting the returned collection shows the new name.

**Verify**: the probe prints Count-before, Count-after, and named-lookup
result. Interpretation:
- **Count increments but named access fails** → collection-write worked,
  named-lookup marshaling is broken → go to Step 4a.
- **Count does NOT increment** → Append silently no-ops despite Ok → the
  variant marshaling loses the COM pointer → go to Step 4b.
- **Probe itself crashes (exit 134)** → STOP (the probe path itself hits
  the winax crash family; report output and stop).

### Step 2: Confirm against Python on the same fixture copy

Run the Python oracle equivalent (via `.venv\Scripts\python.exe` +
`parity_driver.py` or a 10-line inline script using `wincom.py`) against
another fresh copy of the fixture: create → count → named lookup.

**Verify**: Python shows Count incremented and named access succeeds. If
Python ALSO fails, the fixture/env is at fault, not the adapter → STOP and
report (the divergence claim would be false).

### Step 3: Decide the fix branch

Record the probe outcome in the eventual commit message. No code change yet.

**Verify**: you have a written one-line verdict:
`Branch 4a (lookup-side)` or `Branch 4b (Append-side)`.

### Step 4a: Lookup-side fix (named access marshaling)

Replace the named lookup in both `refreshLinkedTable` (:2878) and
`recreateLinkedTable.resolveAttrs` (:2946) with a two-step pattern: fetch
the collection (`get(db, "TableDefs")` → `%raw` wrap), then
`WINAX_BINDING.getItem(tableDefs, ComInterfaces.VStr(name))` (getItem
accepts a variant key; DAO `Item` accepts name OR index). Keep all existing
error mapping. Do NOT add `Refresh` (rejected). Release the collection
handle after the lookup.

**Verify**: build exit 0 → Step 5.

### Step 4b: Append-side fix (variant marshaling)

In `createLinkedTable` (:2810-2812) and `recreateLinkedTable`'s Append
(:2989-2991), change the variant construction to pass the raw dispatch
pointer instead of the JS wrapper object. Try in order, verifying after
each (build + single-case parity run):

1. `let tdefAsVariant: ComInterfaces.variant = %raw("(t) => t && t.__p__ ? t.__p__ : t")(Obj.magic(tdef))`
2. If still failing: `let tdefAsVariant: ComInterfaces.variant = Obj.magic(%raw("h => h.__p__")(tdef))`

Only change the two linked-table Append sites. Do not touch relations/fields.

**Verify**: build exit 0 → Step 5.

### Step 5: Targeted parity

Kill MSACCESS, wait 3s, set env, run `parity:northwind:com:ddl`, kill
MSACCESS after.

**Verify**: `refresh_linked_table.json` and `recreate_linked_table.json`
both **PASS**. Expected tally: **12 matched + 2 mismatched + 0 errored +
1 skipped** (remaining mismatches: get_linked_tables — plan 041, and
execute_sql_script — plan 039, unless 039 already landed, then 13+1+0+1).
Any NEW errored case (exit 134 on a case that was PASS) → STOP/revert.

### Step 6: Full gates + stability

Run test suite (baseline 787/12, 9 unique known failures) and ODBC parity
(13+2 unchanged). Then the **3-run stability gate**: kill MSACCESS, wait
3-5s, run COM parity three times with kills between. Both target cases PASS
in all 3 runs; no new errored-case pattern (variance in
`delete_table`/`get_indexes`/`drop_index` exit-134 is pre-existing flake;
if YOUR change correlates with 2+ errored in 2 of 3 runs → revert and
record as a new finding, mirroring 038-F-008).

### Step 7: Document and commit

Append a RESOLVED note (or a new finding if reverted) under `038-F-005` in
`rescript-mcp/parity/findings.md`, including the probe verdict and which
branch fixed it. Update `plans/README.md` row. Commit.

## Test plan

The parity cases are the tests (live differential vs Python oracle).
Existing suite (Step 6) is the regression gate. No new unit tests — the
behavior requires live COM.

## Done criteria

- [ ] Probe verdict recorded in commit message (`4a` or `4b`)
- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] Test suite: 787 passed / 12 failed, 9 unique = known baseline
- [ ] COM parity: `refresh_linked_table.json` + `recreate_linked_table.json` PASS; tally 12+2+0+1 (or 13+1+0+1 if plan 039 landed first)
- [ ] ODBC parity: 13 matched + 2 skipped unchanged
- [ ] 3-run stability gate passes
- [ ] Only in-scope files modified (`git status`); probe script not committed
- [ ] `plans/README.md` status row updated

## STOP conditions

- The code excerpts in "Current state" don't match (drift).
- The probe crashes with exit 134, or Python ALSO fails on the same fixture
  copy (env/fixture problem, not adapter).
- Both fix branches (4a AND 4b, both variants of each) fail to flip the
  cases after one attempt each — do not start a third improvisation round;
  report probe output and revert to `ae8500f` state for these functions.
- The fix appears to require a new `WINAX_BINDING` primitive or changes to
  `Bindings/Winax.res` (new binding surface = design decision, out of scope).
- The fix appears to require touching relations/fields Append sites to stay
  consistent — report the finding, don't expand scope.
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- If 4b is the fix, the relations/fields Append sites likely have the same
  latent defect but are masked by their read paths. A reviewer should decide
  whether to align them in a follow-up — deliberately deferred here to keep
  blast radius small.
- Whatever the probe reveals about winax variant marshaling belongs in
  `AGENTS.md` "Key Gotchas" — it is exactly the kind of non-obvious FFI
  fact future agents need. Update AGENTS.md if the fix changes the
  established wrapper convention.
- Interacts with plan 041 (getLinkedTables): both touch TableDefs interop.
  If this plan lands 4a successfully, plan 041 should prefer the same
  named-access pattern for its enumeration attempts.
