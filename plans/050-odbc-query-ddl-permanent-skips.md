# Plan 050: Mark the ODBC delete_query / set_query_sql skips as permanent

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat 016ebdb..HEAD -- rescript-mcp/parity/cases/northwind/ddl/delete_query.json rescript-mcp/parity/cases/northwind/ddl/set_query_sql.json`
> If either file changed since this plan was written, compare the "Current
> state" excerpts against the live files before proceeding.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: docs
- **Planned at**: commit `016ebdb`, 2026-09-07

## Why this matters

Two ODBC DDL parity cases sit permanently skipped for a driver limitation, but their skipReasons read as if they were temporary states ("Access ODBC driver cannot CREATE VIEW…"). The COM variants of the exact same operations run un-skipped and pass. Making the permanence explicit prevents future sessions from re-investigating a settled limitation, and keeps the tally honest: ODBC DDL is 13 matched + 2 permanent skips, and that is its ceiling by design.

## Current state

### The two case files

`rescript-mcp/parity/cases/northwind/ddl/delete_query.json`:

```json
"skip": true,
"skipReason": "Access ODBC driver cannot CREATE VIEW via SQL (brackets in identifier rejected as 'is not a valid name'); query DDL is DAO-only"
```

Args: `query_name: "qry_ParityTest"`; setup runs `create_query` with `SELECT CustomerID, CompanyName FROM Customers`.

`rescript-mcp/parity/cases/northwind/ddl/set_query_sql.json`:

```json
"skip": true,
"skipReason": "Access ODBC driver cannot CREATE VIEW via SQL (brackets in identifier rejected); query DDL is DAO-only"
```

Args: `query_name: "qry_ParityTest"`, `sql: "SELECT CustomerID, CompanyName FROM Customers"`; setup runs `create_query` with `SELECT CustomerID FROM Customers`.

### Why the skips can never lift (settled diagnosis)

Query DDL in Access requires `CREATE VIEW` / `DROP VIEW` over ODBC; the ACE driver rejects the bracketed identifiers (`'[name]' is not a valid name`). The Python oracle itself cannot establish the prerequisite state (the setup `create_query` fails the same way on ODBC), so the case is unmatchable on BOTH sides of the differential — recorded originally in plan 035 (`plans/035-ddl-parity-state-isolation.md`, the 034-F-004 state-isolation work).

### The COM variants are the parity vehicle

`rescript-mcp/parity/cases/northwind/com/ddl/delete_query.json` and `set_query_sql.json` exist, carry `"variant": "com"`, have NO skip flag, and PASS (verified in the `run-1788834805035-osgzqoz` COM DDL run at `016ebdb`: both among the 10 matched).

### Tally baseline

`pnpm -C rescript-mcp parity:northwind:ddl` → `15 cases, 13 matched, 0 mismatched, 0 errored, 2 skipped`. This plan must not change that line except (optionally) how the skip line prints.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Case lint | `pnpm -C rescript-mcp lint:cases` | exit 0 |
| ODBC DDL parity | `pnpm -C rescript-mcp parity:northwind:ddl` | `15 cases, 13 matched, 0 mismatched, 0 errored, 2 skipped` |

## Scope

**In scope**:

- `rescript-mcp/parity/cases/northwind/ddl/delete_query.json` — skipReason text only
- `rescript-mcp/parity/cases/northwind/ddl/set_query_sql.json` — skipReason text only
- `rescript-mcp/parity/findings.md` — one clarifying note
- `plans/README.md` — status row

**Out of scope**:

- The `skip` flags themselves (stay `true`)
- The COM variants, the runner, any adapter code
- Removing the cases from the suite (the skipped case still documents the driver limitation)

## Git workflow

- Branch: `rescript/050-odbc-query-ddl-permanent-skip` (or fold into the 046-049 batch if the same operator runs them together)
- Commit style: `docs(parity): mark ODBC query-DDL skips permanent`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Reword both skipReasons

Replace each skipReason with a permanent phrasing, e.g.:

> `"PERMANENT skip — Access ODBC (ACE) driver cannot CREATE VIEW with bracketed identifiers ('is not a valid name'), so query DDL is DAO-only and the setup cannot establish prerequisite state on either side. The COM variant (cases/northwind/com/ddl/<same-name>.json) is the parity vehicle for this operation and passes."`

Keep it to one string; `<same-name>` = the respective file name.

**Verify**: both files parse: `node -e "for (const f of ['delete_query','set_query_sql']) { JSON.parse(require('fs').readFileSync('rescript-mcp/parity/cases/northwind/ddl/'+f+'.json','utf8')); } console.log('ok')"` → `ok`.

### Step 2: Lint + tally

**Verify**:
1. `pnpm -C rescript-mcp lint:cases` → exit 0
2. `pnpm -C rescript-mcp parity:northwind:ddl` → exactly `15 cases, 13 matched, 0 mismatched, 0 errored, 2 skipped` (skip lines now print the PERMANENT wording)

### Step 3: Record

- One-line note in `rescript-mcp/parity/findings.md` (permanent-skip rationale references plan 035's original diagnosis).
- Update the `050` row in `plans/README.md` → DONE.

## Test plan

- No tests. Gates are lint + unchanged tally.

## Done criteria

- [ ] Both skipReasons contain "PERMANENT"
- [ ] `pnpm -C rescript-mcp lint:cases` exit 0
- [ ] `pnpm -C rescript-mcp parity:northwind:ddl` tally unchanged (13/0/0/2)
- [ ] No files outside in-scope list modified
- [ ] findings.md + plans/README.md updated

## STOP conditions

- Either COM variant is skipped or failing at execution time — the "COM is the parity vehicle" claim would be false; report.
- The ODBC DDL tally differs from the baseline line above.
- Drift check shows the case files already reworded.

## Maintenance notes

- If the runner ever gains a `"skipKind": "permanent"` schema field (cases.schema.json), migrate these two first — the string prefix is the interim convention.
