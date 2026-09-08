# Plan 049: Land recreate_linked_table — crash-blocked sibling of the passing refresh case

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat 016ebdb..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/parity/cases/northwind/com/ddl/recreate_linked_table.json`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plan 045 (the case currently exit-134s; nothing here is verifiable on a crashing runner)
- **Category**: bug
- **Planned at**: commit `016ebdb`, 2026-09-07

## Why this matters

`refresh_linked_table.json` PASSES today, but its sibling `recreate_linked_table.json` dies with exit 134 (no stdout) — the 033-F-001 crash. The two operations share their contract surface (`{success, error}` on a re-pointed linked table), so once plan 045 stops the crash, recreate is expected to pass — with one targeted hard spot if it doesn't: the `resolveAttrs` probe loop, which is a known crash-pattern site (indexed `getItem` iteration). This plan verifies, fixes that one site if needed, and explicitly defers any deeper contract divergence to plan 040.

## Current state

### The case — `rescript-mcp/parity/cases/northwind/com/ddl/recreate_linked_table.json` (verbatim)

```json
{ "operation": "recreate_linked_table",
  "args": { "connection_name": "northwind", "name": "lnk_categories", "source_table": "customers", "connect_string": ";DATABASE=REPLACE_SOURCE_DB" },
  "variant": "com", "mutating": true, "volatileFields": [],
  "setup": [ { "operation": "create_linked_table",
      "args": { "connection_name": "northwind", "name": "lnk_categories", "source_table": "categories", "connect_string": ";DATABASE=REPLACE_SOURCE_DB" } } ] }
```

Note: recreate uses `name` + `source_table` (re-points `categories` → `customers`); the passing refresh case uses `table_name` instead.

### The sibling — `refresh_linked_table.json`

Same setup; args use `table_name: "lnk_categories"` + `connect_string`. **PASSES** as of `016ebdb` (COM DDL run `run-1788834805035-osgzqoz`).

### The ReScript implementation — `ComDataAdapter.res:3503-3543+`

`recreateLinkedTable` ("D6: capture old attrs, delete, create with sourceTable/connect, restore attrs"). When the caller omits `~attributes` (the parity facade does — the case args carry none, `Facade.res:1452` passes `None`), `resolveAttrs` runs an **indexed TableDefs iteration** to find the old table's attributes:

```rescript
// :3531-3543 (shape)
| None => winaxBinding.get(db, "TableDefs")
          → getCount
          → findLoop with getItem(VInt(idx))     // ← 038-F-007 crash-pattern family
```

Fallback value `-2147483648` (`0x80000000`). Whether plan 045's Step 3 conversion (this loop is inside `recreateLinkedTable`, one of the listed functions) already covers these releases — check the live code first in Step 1.

### Python oracle

`src/ms_access_mcp/adapters/dao.py:1358-1372` (recreate path: read old tdef attrs → `TableDefs.Delete` → `CreateTableDef` → `Append`). Envelope contract on success/failure: `{success, error?}` — refresh already matches, so recreate's shape is presumed aligned (verified at runtime in Step 2).

### Crash evidence

`run-1788834805035-osgzqoz/recreate_linked_table-rescript.json`: exit 134, no stdout, stderr = `RemoveEnvironmentCleanupHook ... (env) != nullptr` + `DispObject::`scalar deleting destructor'` — the 033-F-001 signature (plan 045's scope).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit suite | `pnpm -C rescript-mcp test` | 827 tests, 0 failed |
| Single case | see below | `PASS recreate_linked_table.json` ×3 |

Single-case command (PowerShell, `node -e` wrapper; case is mutating — no `--require-read-only`):

```powershell
Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
$env:PARITY_VARIANT="com"
node -e "process.env.ACCESS_TEST_DB=require('path').resolve('D:/code/python/ms-access-mcp-server/db/northwind.accdb');process.env.ACCESS_TEST_ASSUME_ACE='1';process.argv=['node','run.js','--cases-dir=D:/code/python/ms-access-mcp-server/rescript-mcp/parity/cases/northwind/com/ddl','--case=recreate_linked_table.json'];require('D:/code/python/ms-access-mcp-server/rescript-mcp/parity/dist/run.js')"
```

## Scope

**In scope**:

- `rescript-mcp/src/Adapters/ComDataAdapter.res` — ONLY the `recreateLinkedTable` / `resolveAttrs` release conversions if Step 2 shows they're still async `release`
- `rescript-mcp/parity/findings.md`, `plans/README.md` — recording

**Out of scope**:

- Any contract/behavior change to `recreateLinkedTable` (delete/create/attrs semantics) — content divergence is plan 040's named-lookup scope
- `refreshLinkedTable` (passing — do not touch)
- The case JSON (no edits; it is correct)
- Plan 045's broader release sweep (if recreate still crashes after THIS plan's targeted conversion, that's a plan 045 regression — report there)

## Git workflow

- Branch: `rescript/049-recreate-linked-table` (or fold into plan 045's branch if executed back-to-back by the same operator — record which in the README row)
- Commit style: `fix(winax): releaseSyncAwait in recreateLinkedTable attrs probe` (if Step 3 needed) else `docs(parity): recreate_linked_table verified post-045`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Preconditions + live-code check

1. Confirm plan 045's README row is DONE. If not → STOP (prerequisite).
2. Read `ComDataAdapter.res` `recreateLinkedTable` (~`:3503+`). If plan 045 Step 3 already converted its releases to `releaseSyncAwait`, note it and skip Step 3.

**Verify**: plan 045 DONE; current release style inside `recreateLinkedTable` recorded (converted or not).

### Step 2: Verify on the crash-free runner

Run the single-case command 3 times.

**Verify (happy path)**: `  PASS  recreate_linked_table.json` ×3 → skip to Step 4.

If **exit-134 ERROR** persists → Step 3. If **content FAIL** → STOP conditions (plan 040 scope), do not improvise.

### Step 3 (conditional): Convert the `resolveAttrs` probe releases

Inside `recreateLinkedTable`'s `resolveAttrs` `None` arm (TableDefs get → getCount → findLoop getItem chain, `:3531-3543` shape): convert every `Bindings.Winax.WINAX_BINDING.release(...)->ignore` to `releaseSyncAwait(...)->ignore` — same mechanical edit as plan 045 Step 3, scoped to this function only (including the per-iteration `td` handle release and the final `tableDefs` handle release). Then rebuild and re-run the case 3×.

**Verify**:
1. `pnpm -C rescript-mcp build` → exit 0
2. `pnpm -C rescript-mcp test` → 827, 0 failed
3. Single-case ×3 → PASS ×3 (if STILL exit-134 after this → STOP: plan 045's settle mechanism has a gap; report with evidence)

### Step 4: Record

- Full COM DDL suite: `pnpm -C rescript-mcp parity:northwind:com:ddl` → `recreate_linked_table` counted as matched; no new ERRORs; expected suite end-state after plans 045-049: **14 matched + 0 skipped + 0 errored** (with `execute_sql_script` from 046) — 15/15 once 048 also lands.
- findings.md: 038-F-005 / recreate outcome note.
- plans/README.md row → DONE; refresh `parity/findings.json`.

## Test plan

- No new unit tests (production semantics unchanged; parity is the test).
- Differential: `recreate_linked_table.json` PASS ×3.
- Regression: suite 827/827; full COM DDL tally improves by 1 matched.

## Done criteria

- [ ] `recreate_linked_table.json` PASS ×3
- [ ] `pnpm -C rescript-mcp test` → 827, 0 failed
- [ ] `pnpm -C rescript-mcp parity:northwind:com:ddl` → no ERROR lines; recreate counted matched
- [ ] No files outside in-scope list modified
- [ ] findings.md + plans/README.md updated

## STOP conditions

- Plan 045 not DONE.
- Content FAIL (diff at `$.error` or anywhere) — plan 040 named-lookup scope; report the paired artifacts and stop.
- Exit-134 persisting after Step 3 — plan 045 regression; report.
- The live `recreateLinkedTable` code no longer matches the excerpt shape (drift since `016ebdb`).

## Maintenance notes

- `refresh` and `recreate` now both pass → plan 040's remaining reason to exist is the `get_linked_tables` classification nuance (see plan 048 STOP conditions). If 048 also passes without 040, propose marking plan 040 REJECTED-superseded in README with rationale.
