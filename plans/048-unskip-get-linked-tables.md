# Plan 048: Un-skip get_linked_tables — the enumeration is already implemented

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat 016ebdb..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/parity/cases/northwind/com/ddl/get_linked_tables.json`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW (worst case: the case FAILs on content and we re-skip — no production code changes)
- **Depends on**: plan 045 recommended (case previously crash-prone; enumeration is now stable per plan 043 v3 evidence but verify on a crash-free runner)
- **Category**: tests
- **Planned at**: commit `016ebdb`, 2026-09-07

## Why this matters

`get_linked_tables.json` is the last `skip: true` in the COM DDL suite. Recon at `016ebdb` shows the real DAO enumeration **already landed** (plans 042/043 lineage) — only two artifacts remain: the stale skip flag and a header comment that still describes the old "safe-empty-stub". Un-skipping either gains a passing parity case for free or produces a precise content diff that scopes the remaining plan-040 work. Either outcome beats a silent skip contaminating no tally.

## Current state

### The case — `rescript-mcp/parity/cases/northwind/com/ddl/get_linked_tables.json`

Currently:

```json
"skip": true,
"skipReason": "038-F-007 (plan 043 v3): dispose-ordering fix lands — get_linked_tables no longer exit-134s. FAIL now indicates content diff only. Plan 042 v2 + plan 040 must land to make this PASS. Until those land, keeping skip to avoid contaminating the parity tally baseline."
```

Setup creates `lnk_categories` (source `categories`, `connect_string: ";DATABASE=REPLACE_SOURCE_DB"`). `"variant": "com"`, `"mutating": true`, `"volatileFields": []`.

Status of the two named blockers: plan 042 v2 **landed** (`d4a604b`); plan 040 remains BLOCKED per README — but the enumeration itself shipped, so the skipReason's premise is stale.

### The implementation — REAL, not a stub — `rescript-mcp/src/Adapters/ComDataAdapter.res:3034+`

`getLinkedTables` (registered in `asInstance` at `:3887`): iterates `TableDefs.Count` via `winaxBinding.getItem(tableDefs, VInt(idx))` (`:3063`), filters linked tables with `(attributes & 0x80000000) !== 0` via `%raw` (`:3084`), classifies the connect-string prefix (`:3100-3108`), collects entries (`:3061`).

**The header comment at `:3022-3033` is STALE** — it still says "Plan 041 escape hatch (SKIPPED)… Returns the safe-empty stub envelope". It must be rewritten to describe the live enumeration (and drop the plan-041 escape-hatch language).

### The facade shaper — `rescript-mcp/src/Services/Facade.res:876-907`

`_shapeLinkedTablesResult` emits per entry exactly `{name, source_table, connect_string, type, attributes}` — comment at `:874` already documents "Python success has NO error key".

### The Python oracle — `src/ms_access_mcp/adapters/dao.py:1185-1235`

Per linked table: `{name, source_table, connect_string, type, attributes}` (`:1222-1230`); success envelope `{"success": True, "linked_tables": [...]}` (`:1233`); not-connected `{"success": False, "error": "Not connected"}` (`:1201`). **Field contracts match the ReScript shaper 1:1.**

### Known nuance to verify at runtime

Connect-string type classification for `";DATABASE=..."` (leading semicolon — neither `ODBC`/`Access`/`Excel` prefix): ReScript `_classifyConnectType` (`ComDataAdapter.res:420-424`) falls through to default `"ODBC"`. Python's classification lives in the same `dao.py` block — the executor compares the actual branch in Step 3 if a diff appears at `$.linked_tables[0].type`.

### Historical context (why the skip exists)

Plan 041 (`plans/041-com-get-linked-tables-enumeration.md`) chose escape-hatch Case C: Approach A (named probing) crashed natively (038-F-007 family); Approach B risked cross-case instability. The enumeration that later landed (via 042/043 work) superseded the plan-041 "current state" excerpts — plan 041 itself is historical, do not follow it.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Build parity TS | `pnpm -C rescript-mcp build:parity` | exit 0 |
| Unit suite | `pnpm -C rescript-mcp test` | 827 tests, 0 failed |
| Single case | see below | `PASS get_linked_tables.json` |

Single-case command (PowerShell, `node -e` wrapper — never invoke run.js directly):

```powershell
Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
$env:PARITY_VARIANT="com"
node -e "process.env.ACCESS_TEST_DB=require('path').resolve('D:/code/python/ms-access-mcp-server/db/northwind.accdb');process.env.ACCESS_TEST_ASSUME_ACE='1';process.argv=['node','run.js','--cases-dir=D:/code/python/ms-access-mcp-server/rescript-mcp/parity/cases/northwind/com/ddl','--case=get_linked_tables.json'];require('D:/code/python/ms-access-mcp-server/rescript-mcp/parity/dist/run.js')"
```

The case is `mutating: true` — do NOT add `--require-read-only`.

## Scope

**In scope**:

- `rescript-mcp/parity/cases/northwind/com/ddl/get_linked_tables.json` — skip flag + skipReason
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — the stale header comment at `:3022-3033` ONLY (comment text; no code changes)
- `rescript-mcp/parity/findings.md` — 038-F-007 outcome update
- `plans/README.md` — status row

**Out of scope**:

- Any behavior change to `getLinkedTables`, the shaper, or the classification function — if content diverges, that is plan 040 territory (STOP and report)
- Other case files; the ODBC linked-table stubs (ODBC has no linked-table support by design)

## Git workflow

- Branch: `rescript/048-unskip-get-linked-tables`
- Commit style: `test(parity): un-skip get_linked_tables — enumeration landed via 042/043`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Rewrite the stale header comment

At `ComDataAdapter.res:3022-3033`, replace the "safe-empty-stub / escape hatch" comment with a short accurate one: enumerates DAO TableDefs, keeps entries with the linked bit (`0x80000000`) set, classifies connect-string prefix (ODBC/Access/Excel, default ODBC), returns `{name, source_table, connect_string, type, attributes}` entries — parity oracle `dao.py:1185-1235`. No code changes.

**Verify**: `pnpm -C rescript-mcp build` → exit 0.

### Step 2: Un-skip the case

In `get_linked_tables.json`: set `"skip": false` and REMOVE the `"skipReason"` key entirely (matches how `generate_sql.json` was un-skipped at `016ebdb`).

**Verify**: JSON parses (`node -e "JSON.parse(require('fs').readFileSync('rescript-mcp/parity/cases/northwind/com/ddl/get_linked_tables.json','utf8')); console.log('ok')"` → `ok`).

### Step 3: Run the case — PASS or triage

Run the single-case command 3 times (fresh MSACCESS kill between runs).

**Verify (happy path)**: `  PASS  get_linked_tables.json` ×3 → jump to Step 4.

**If FAIL with content diff**: read the paired artifacts under the newest `rescript-mcp/parity/runs/run-*/` (`get_linked_tables-python.json` / `-rescript.json`) and compare:

- diff at `$.linked_tables[0].type` → compare `_classifyConnectType` (`ComDataAdapter.res:420-424`) against the Python branch in `dao.py:1185-1235` for the `";DATABASE="` prefix. If they disagree on the fallthrough, that is the plan-040 named-lookup/classification scope → **STOP and report** with both snippets.
- diff at `$.linked_tables[0].attributes` or `connect_string` → likewise STOP and report (contract divergence for plan 040).
- diff anywhere else → STOP and report the artifact paths.

**If ERROR (exit 134)** → plan 045 has not landed or regressed; STOP and report.

Do NOT "fix" content by editing production code in this plan.

### Step 4: Record

- Full-suite sanity: `pnpm -C rescript-mcp parity:northwind:com:ddl` → summary gains +1 matched (skipped count drops by 1); no new ERROR lines.
- Update `rescript-mcp/parity/findings.md` under `038-F-007`: enumeration live, case un-skipped, PASS (or the recorded triage outcome).
- Update the `048` row in `plans/README.md`; refresh `parity/findings.json` and commit alongside.

## Test plan

- No new unit tests (the enumeration is production code with existing coverage; this plan is harness + comment hygiene).
- Differential: `get_linked_tables.json` PASS ×3.
- Suite tallies: COM DDL skipped count 1 → 0.

## Done criteria

- [ ] Case file has `"skip": false`, no `skipReason`
- [ ] Stale stub comment replaced; `pnpm -C rescript-mcp build` exit 0
- [ ] `get_linked_tables.json` PASS ×3 (or STOP report filed with artifact evidence)
- [ ] `pnpm -C rescript-mcp parity:northwind:com:ddl` → skipped count 0, matched +1, no new ERRORs
- [ ] `pnpm -C rescript-mcp test` → 827, 0 failed
- [ ] No files outside in-scope list modified
- [ ] findings.md (038-F-007) + plans/README.md updated

## STOP conditions

- `getLinkedTables` body no longer matches the live-enumeration description (drift).
- Content diff appears (any path) — plan 040 scope; report artifacts, re-set the skip with an updated reason referencing the diff, and stop.
- Exit-134 — plan 045 prerequisite unmet; restore the skip and stop.
- The setup step (`create_linked_table` for `lnk_categories`) fails on either child — fixture or harness issue; report child stderr.

## Maintenance notes

- If plan 040 (named-lookup divergence) is ever executed, this case is its acceptance gate — keep it un-skipped from then on.
- The stale-comment rewrite matters more than it looks: the next auditor reading "safe-empty-stub" would re-plan plan 041 for work that's already done.
