# Plan 041: Enumerate linked tables without TableDefs.Item (resolve 038-F-007)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. This plan has a **documented escape hatch**:
> if Step 3's approaches all fail, the prescribed outcome is marking the
> case skipped (Step 6) — that IS a valid completion of this plan. When
> done, update the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat ae8500f..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/parity/cases/northwind/com/ddl/get_linked_tables.json rescript-mcp/parity/runRescript.ts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: HIGH
- **Depends on**: none required; if plan 040 lands first, its named-access pattern (Step 4a) is the preferred building block here
- **Category**: bug
- **Planned at**: commit `ae8500f`, 2026-09-03

## Why this matters

`getLinkedTables` cannot enumerate DAO `TableDefs` via winax: the first
`TableDefs.Item(index)` call crashes the Node process natively (exit 134,
no stdout). The current implementation is a deliberate safe stub returning
`success: true` with an empty `linkedTables` array, so the parity case
`get_linked_tables.json` fails at `$.linked_tables` (Python returns the
setup-created `lnk_categories` entry) — but it does NOT crash, which keeps
the other 14 COM cases runnable. Any replacement must preserve that
property: **no-crash beats full-fidelity**. One fix attempt (MSysObjects
SQL) already shipped and was reverted for destabilizing the shared MSACCESS
session (038-F-008); this plan's stability gate exists because of that
lesson.

## Current state

- The stub, `rescript-mcp/src/Adapters/ComDataAdapter.res:2733-2766`
  (guard arms at :2734-2741 return Not connected / No session / No DB
  handle; then):

```rescript
Bindings.Winax.WINAX_BINDING.get(db, "TableDefs")
->Promise.then(handleResult => switch handleResult {
| Error(e) => Promise.resolve(Ok({success: false, error: Some(Errors._message(e)), linkedTables: []}))
| Ok(tableDefsJson) => {
    let tableDefs: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(tableDefsJson)
    Bindings.Winax.WINAX_BINDING.getCount(tableDefs)
    ->Promise.then(countResult => switch countResult {
    | Error(e) => Promise.resolve(Ok({success: false, error: Some(Errors._message(e)), linkedTables: []}))
    | Ok(_count) =>
      // Skip per-item iteration: winax getItem on TableDefs in this env
      // crashes the native binding (exit 134). ...
      // 038-F-005 documents the underlying issue.
      Promise.resolve(Ok({success: true, error: None, linkedTables: []}))
    })
  }
})
```

- Result shape, `rescript-mcp/src/Adapters/Interfaces.res:90-102`:

```rescript
type linkedTableInfo = {
  name: string, sourceTable: string, connectString: string,
  type_: string,  // @as "type"
  attributes: int,
}
type linkedTablesResult = { success: bool, error: option<string>, linkedTables: array<linkedTableInfo> }
```

- Python oracle `src/ms_access_mcp/adapters/dao.py:1185-1235`: iterates
  `range(db.TableDefs.Count)`, reads `db.TableDefs(i)` per index, filters
  `tdef.Attributes & 0x80000000` (dbAttachedTable bit), maps connect prefix
  to type (`ODBC;` → "ODBC", `;DATABASE=` → "Access", `Excel` → "Excel"),
  emits `{name, source_table, connect_string, type, attributes}`. Works
  because pywin32's `TableDefs(i)` default-member call is stable on this
  machine.

- The crash (038-F-007 in `rescript-mcp/parity/findings.md`):
  `WINAX_BINDING.getItem(tableDefs, VInt(0))` — which is
  `invokeAsObject(tableDefs, "Item", [VInt(0)])` per
  `rescript-mcp/src/Bindings/Winax.res:261-264` — crashes natively, with
  BOTH parallel (`Array.map`+`Promise.all`) and sequential recursive-loop
  patterns. `get(db, "TableDefs")` and `getCount(tableDefs)` do NOT crash.

- The reverted attempt (038-F-008): `SELECT Name, Connect FROM MSysObjects
  WHERE Type = 6` via `OpenRecordset` avoided the crash but correlated with
  new exit-134 errors in `delete_table`/`drop_index` on subsequent cases
  (parity tally regressed to 8+4+2+1 in 1 of 3 runs). Hypothesis: system-
  table access leaves the shared MSACCESS COM instance in a partially-locked
  state. **Do not retry MSysObjects without first addressing trust/locking
  (approach C below) — and even then, only with the stability gate.**

- Case file
  `rescript-mcp/parity/cases/northwind/com/ddl/get_linked_tables.json`:
  setup creates `lnk_categories` via `create_linked_table`; no `expected`
  block — the runner diffs against the live Python oracle. Asserted keys:
  `name, source_table, connect_string, type, attributes`.

- Working recordset idiom for reference (used elsewhere, does not crash):
  `_executeQueryImpl` at `ComDataAdapter.res:404-461`
  (`invokeAsObject(db, "OpenRecordset", [VStr(sql)])` → `get(rs, "EOF")` →
  per-field reads → `invoke(rs, "MoveNext", [])` → `_closeRecordset(rs)` at
  ~:130).

## Commands you will need

| Purpose        | Command (from repo root)                                                        | Expected on success                |
|----------------|----------------------------------------------------------------------------------|------------------------------------|
| Build          | `cmd.exe /c "pnpm -C rescript-mcp build"`                                        | exit 0                             |
| Tests          | `cmd.exe /c "pnpm -C rescript-mcp test"`                                         | exit 1 with exactly the 9 known unique failures; 787/12 totals |
| COM parity     | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:com:ddl"`                     | see per-step expectations          |
| ODBC parity    | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:ddl"`                         | 13 matched + 2 skipped             |
| Kill Access    | `Get-Process MSACCESS -EA SilentlyContinue \| Stop-Process -Force` then `Start-Sleep -Seconds 3` | before AND after every COM run |

Parity env (PowerShell):
```powershell
$env:ACCESS_TEST_ASSUME_ACE='1'; $env:ACCESS_TEST_DB="$PWD\db\northwind.accdb"
$env:ACCESS_MCP_ALLOWED_DIRS="$PWD\db;$env:TEMP"; $env:ACCESS_MCP_READONLY='false'
```

## Scope

**In scope**:
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — `getLinkedTables` body
  (:2733-2766) only, plus at most one small module-level helper.
- `rescript-mcp/parity/cases/northwind/com/ddl/get_linked_tables.json` —
  ONLY if taking the Step 6 escape hatch (add `skip`/`skipReason`; the
  schema fields exist since plan 035).
- `rescript-mcp/parity/findings.md` — status note under 038-F-007.

**Out of scope** (do NOT touch):
- `Bindings/Winax.res` — a new binding primitive is a design decision; STOP.
- `getTables`, `_executeQueryImpl`, relations/fields code paths.
- The Python side (oracle is correct).
- `volatileFields` on the case file — masking the diff is not a fix; the
  only accepted masking outcome is the Step 6 skip with reason.
- MSysObjects WITHOUT the trust precondition (rejected by 038-F-008).

## Git workflow

- Branch: continue on `rescript/038-linked-tables-sql-script`.
- Commit style (from `git log`): conventional commits, e.g.
  `fix(parity): enumerate linked tables via named probes (plan 041)` or, for
  the escape hatch, `chore(parity): skip get_linked_tables pending winax fix (plan 041)`.
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 1: Confirm the stub state and baseline

Kill MSACCESS, set parity env, run `parity:northwind:com:ddl` once, kill
MSACCESS.

**Verify**: `get_linked_tables.json` = FAIL at `$.linked_tables` (NOT
ERROR), and no exit-134 on any case in this run. If the stub itself is
crashing, the codebase has drifted — STOP.

### Step 2: Choose approach order

Try in this order, one at a time, each with full verification (Steps 3-5)
before trying the next:

- **Approach A — named probing** (preferred, especially if plan 040 landed
  its 4a fix): enumerate candidate names without `Item(index)`. Source of
  names: the user-table list from the adapter's own table enumeration
  (`getTables`-equivalent path already in this file) UNION any names the
  session created. For each candidate name, `getItem(tableDefs,
  VStr(name))` (named access is proven non-crashing — the linked-table ops
  use it). Read `Attributes` per hit; filter `0x80000000`; read `Name`,
  `SourceTableName`, `Connect` via the `%raw("h => h.__p__.X")` pattern
  used at `:2893`. Caveat: if DAO hides linked tables from the name source,
  Approach A cannot see them — detect this by probing the known setup name
  `lnk_categories` and STOP to Approach B if even that probe misses.
- **Approach B — trusted MSysObjects** (the 038-F-008 idea, gated): FIRST
  establish why MSysObjects destabilized the session. In a throwaway probe
  script (temp dir, not committed), run the MSysObjects OpenRecordset
  against a scratch fixture copy, close the recordset explicitly
  (`invoke(rs, "Close", [])` + `release(rs)`), then run a `delete_table`-
  equivalent DAO op in the SAME process. If the follow-up op is clean, the
  038-F-008 regression was a resource-leak (unclosed recordset), and the
  fix is the MSysObjects query PLUS guaranteed close/release on every exit
  path (including catch arms). If the follow-up op still destabilizes,
  abandon Approach B.
- **Approach C — escape hatch**: skip the case (Step 6).

### Step 3: Implement the chosen approach

Keep the guard arms and the `{success, error, linkedTables}` envelope
exactly as-is. Every recordset/collection handle opened must be released on
EVERY exit path (success, error, catch). `release(h)` returns `unit` — wrap
in a statement block returning `Promise.resolve()` when chaining in a
`->Promise.then(_ => ...)` (this exact type error bit a previous attempt:
"has type: unit, expected: Promise.t<'a>").

For `type_`, reuse the existing module-level `_classifyConnectType` (already
in this file). For `attributes`, emit the DAO value read from the TableDef
(Approach A) or `-2147483648` (0x80000000, Approach B — MSysObjects rows
with Type=6 are definitionally linked).

**Verify**: build exit 0. Fix type errors by matching neighboring Promise-
chain style; do not restructure.

### Step 4: Targeted parity

Kill MSACCESS, run COM parity, kill MSACCESS.

**Verify**: `get_linked_tables.json` PASS, and no other case newly ERRORs.
Expected tally: **11 matched + 3 mismatched + 0 errored + 1 skipped**
(mismatches: refresh/recreate — plan 040, execute_sql_script — plan 039;
adjust if those landed). Diff-at-`$.linked_tables` with REAL data (array
contents mismatch, not crash) is acceptable as a fallback milestone but not
"done" — record what differs and continue only if the diff is a field
mapping issue (e.g. `source_table` unavailable in MSysObjects), not a
session-stability issue.

### Step 5: Full gates + 3-run stability

Test suite (787/12, 9 unique known failures), ODBC parity (13+2
unchanged), then three consecutive COM parity runs with MSACCESS kills +
3-5s waits between. **The case must be PASS (or the accepted field-level
diff from Step 4) in all 3 runs, with zero new errored cases attributable
to this change.** One clean run proves nothing (038-F-008 lesson).

### Step 6: Escape hatch — skip the case

If Approaches A and B both fail: add to the case file
`"skip": true, "skipReason": "038-F-007: winax TableDefs.Item(i) native crash (exit 134); MSysObjects approach destabilizes shared MSACCESS session (038-F-008). ODBC parity (13+2) covers the op contract; COM enumeration deferred to a winax dispose-ordering plan."`
The runner respects `skip`/`skipReason` since plan 035
(`run.ts` skip short-circuit + summary counter; schema in
`cases.schema.json`). Expected tally after skip: **10 matched + 3
mismatched + 0 errored + 2 skipped**.

### Step 7: Document and commit

Update finding 038-F-007 status in `rescript-mcp/parity/findings.md`
(RESOLVED + how, or SKIPPED + why, including probe results). Update
`plans/README.md` row. Commit per the message style above.

## Test plan

The parity case is the test. Existing suite is the regression gate. No new
unit tests (requires live COM).

## Done criteria

Either **FIXED**:
- [ ] `get_linked_tables.json` PASS (or documented field-level diff) in 3 consecutive COM parity runs
- [ ] No new errored cases across those 3 runs
- [ ] Test suite 787/12 with 9 unique known failures; ODBC parity 13+2
- [ ] Build exit 0; only in-scope files modified
- [ ] findings.md + plans/README.md updated

Or **SKIPPED** (accepted outcome):
- [ ] Case file has `skip: true` with the prescribed `skipReason`
- [ ] COM parity tally 10+3+0+2; ODBC parity 13+2 unchanged
- [ ] Test suite baseline unchanged
- [ ] findings.md 038-F-007 marked with skip rationale + the two rejected approaches

## STOP conditions

- The stub excerpt doesn't match the live code (drift).
- Even the baseline stub run shows exit-134 crashes (env regression — kill
  MSACCESS, retry once; if it persists, the machine state is bad, not the
  code).
- Approach A's `lnk_categories` probe misses a table the setup provably
  created (name source incomplete) → abandon A immediately.
- Approach B's probe shows follow-up DAO ops still destabilize even with
  explicit Close/release → abandon B immediately.
- Any approach requires a new `WINAX_BINDING` primitive.
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- If plan 040 lands its 4a fix first, reuse its named-access pattern here —
  consistency in TableDefs interop matters more than local elegance.
- Whatever this plan concludes about winax collection iteration belongs in
  `AGENTS.md` "Key Gotchas" (the file already documents the recursive-
  release crash family). Update it if a new non-obvious fact is established.
- Long-term resolution of the underlying winax dispose-ordering crash
  family (033-F-001, which also keeps `generate_sql` skipped) would likely
  obsolete this whole plan — if a winax fix ever lands, re-enable the case
  and revisit the enumeration.
