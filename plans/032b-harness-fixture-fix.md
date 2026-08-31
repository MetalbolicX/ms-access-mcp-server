# Plan 032b: Fix parity harness fixture default for the northwind cases

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 86e7892..HEAD -- rescript-mcp/package.json rescript-mcp/parity/ plans/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P0 (closes the last COM parity error and unblocks plans 033/034)
- **Effort**: S
- **Risk**: LOW (script-only change; verified the COM adapter already works)
- **Depends on**: plans/032-schema-reads.md (DONE, tip `86e7892`)
- **Category**: bug
- **Planned at**: commit `86e7892`, 2026-08-31

## Why

Plan 032 added `_getTablesImpl` (real DAO TableDefs iteration) and shipped 6
real-COM tests against `tests/integration/fixtures/test_db.accdb` — all
passing. The parity case `get_table_schema-Customers.json` (in
`cases/northwind/com/`) was reported as still erroring with
`rescript: Table 'Customers' not found`, recorded as
`032-F-001 follow-up: getTableSchemaPlan per-table schema still stubbed`.

That attribution was wrong. Live investigation (Console.log instrumentation
in `_getTablesImpl`, standalone invocation of `dist/runRescript.js` with
`ACCESS_TEST_DB` set) proved:

1. The COM adapter's `getTables` correctly returns PascalCase names on
   Northwind (`Customers`, `Orders`, `Products`, ...).
2. `Facade.getTableSchema` correctly finds the table and returns the full
   11-field schema for `Customers` (CustomerID, CompanyName, ...).
3. The COM parity case passes when `ACCESS_TEST_DB=db/northwind.accdb`.

The actual root cause: **the parity harness ignores `--cases-dir` when
choosing the fixture.** `dist/run.js:62` uses
`process.env.ACCESS_TEST_DB ?? REPO_FIXTURE`, where `REPO_FIXTURE` is
`tests/integration/fixtures/test_db.accdb`. The `--cases-dir` flag only
changes which case JSON files run, not the fixture. So running
`pnpm parity:northwind:com` (which uses `cases/northwind/com/` but does
NOT set `ACCESS_TEST_DB`) runs the Northwind cases against the lowercase
`customers` table in test_db.accdb — `Facade.getTableSchema` looks for
`Customers`, doesn't find it, returns "Table 'Customers' not found". The
harness treats this as a DRIVER error.

Fix is in the harness scripts, not the adapter. This plan tightens the
two parity scripts and documents the requirement.

## Current state (verified at `86e7892`)

### The parity harness bug

`rescript-mcp/parity/dist/run.js:62`:
```js
const fixture = process.env.ACCESS_TEST_DB ?? REPO_FIXTURE;
```

`dist/run.js:97` builds `ACCESS_MCP_ALLOWED_DIRS` from `dirname(fixture)`,
so the PathGuard happily allows the fixture — but `fixture` defaults to
the lowercase-table `test_db.accdb`, not `db/northwind.accdb`.

### The script gap

`rescript-mcp/package.json`:
```
"parity:northwind": "node ./parity/dist/run.js --cases-dir=rescript-mcp/parity/cases/northwind --require-read-only",
"parity:northwind:com": "pnpm build:parity && node parity/dist/run.js --cases-dir=rescript-mcp/parity/cases/northwind/com --require-read-only",
```

Neither sets `ACCESS_TEST_DB`. To run Northwind cases, the operator must
export `ACCESS_TEST_DB=db/northwind.accdb` before invoking — easy to miss,
easy to misinterpret as a parity failure.

### What `dist/run.js` does NOT need

Do NOT modify `dist/run.js`. The harness code is correct given a correct
`fixture`. Fix the wrapper scripts so they pass the right `fixture` via
the env var.

## Commands

| Purpose | Command | Expected on success |
|---|---|---|
| Verify default ODBC parity still passes | `pnpm -C rescript-mcp parity:northwind` | 6 matched / 0 mism / 3 errored (unchanged) |
| Verify COM parity with proper fixture | `pnpm -C rescript-mcp parity:northwind:com` | **≥ 4 matched / ≤ 2 mism / 0 errored** (was 4/1/1) |
| Full suite | `pnpm -C rescript-mcp clean:all && pnpm -C rescript-mcp test` | 734+ pass, 0 fail |
| Drift check | `git status --short` | only in-scope files modified |

## Scope

**In scope**:
- `rescript-mcp/package.json` — update `parity:northwind` and `parity:northwind:com` scripts to inject `ACCESS_TEST_DB` (and `ACCESS_MCP_ALLOWED_DIRS` for safety)
- `plans/032b-harness-fixture-fix.md` — this file
- `rescript-mcp/parity/findings.md` — supersede the `032-F-001` follow-up note; record the actual root cause and resolution
- `plans/README.md` — row 032b DONE

**Out of scope** (deferred):
- Real `getTableSchemaPlan` per-table adapter method. `Facade.getTableSchema`
  currently uses `getTables + Array.find` (works for all parity cases). A
  proper `getTableSchemaPlan` (returning `Interfaces.tableSchema[]` with
  `columnSchema[]`, `primaryKey`, `foreignKeys`, `indexes`,
  `unknownMetadata`) belongs in plan 032c (a separate cleanup) once plan
  033 (mutations) is in flight.
- The two pre-existing COM parity mismatches (`connect_access.json`,
  `get_relationships.json`) — these are separate issues (the hardcoded
  `adapter_type: "odbc"` in `Facade.res:238` for connect; and DAO
  `Relations` iteration not yet implemented). Tracked in findings.
- Harness refactor to auto-pick the fixture from cases-dir name (e.g.
  `cases/northwind/` → `db/northwind.accdb`). Out of scope here — script
  injection is the minimum viable fix and matches the existing convention
  used by other scripts that need an env var.

## Steps

### Step 1: Update `parity:northwind` and `parity:northwind:com` in `package.json`

Replace the existing scripts:

```json
"parity:northwind": "cross-env-shell ACCESS_TEST_DB=$REPO_ROOT/db/northwind.accdb node ./parity/dist/run.js --cases-dir=rescript-mcp/parity/cases/northwind --require-read-only",
"parity:northwind:com": "pnpm build:parity && cross-env-shell ACCESS_TEST_DB=$REPO_ROOT/db/northwind.accdb node parity/dist/run.js --cases-dir=rescript-mcp/parity/cases/northwind/com --require-read-only",
```

Notes on the shell-prefix choice:
- `cross-env-shell` works on Windows, macOS, and Linux without quoting
  headaches; it sets env vars without polluting `process.env` of the parent.
- Alternative if `cross-env-shell` is not present: `node -e "process.env.ACCESS_TEST_DB=...; require('./parity/dist/run.js')"` — uglier.
- The `dist/run.js` reads `process.env.ACCESS_TEST_DB` and falls back to
  `REPO_FIXTURE`; the `$REPO_ROOT` here is the npm script's working dir,
  which is the repo root when pnpm invokes the script. Verify by adding
  `console.log(REPO_ROOT)` if needed; for the current setup pnpm sets
  cwd to the package directory, which is `rescript-mcp/`. So `$REPO_ROOT`
  would resolve to `rescript-mcp/db/northwind.accdb` — wrong.
- Better: pass the absolute path explicitly using `$(pwd)` or the package
  directory:

```json
"parity:northwind": "cross-env-shell ACCESS_TEST_DB=$(node -e \"console.log(require('path').resolve('db/northwind.accdb'))\") node ./parity/dist/run.js --cases-dir=rescript-mcp/parity/cases/northwind --require-read-only",
```

Actually the simplest portable approach: have `cross-env-shell` set
`ACCESS_TEST_DB` and use a relative path that `dist/run.js` resolves via
`process.cwd()`. Since pnpm invokes scripts with cwd = package dir
(`rescript-mcp/`), and `dist/run.js` uses `process.env.ACCESS_TEST_DB ?`
` REPO_FIXTURE` (where REPO_FIXTURE is repo-root-relative
`tests/integration/fixtures/test_db.accdb`), we need an ABSOLUTE path
or a path that the harness resolves correctly.

The cleanest: use `cross-env-shell` with `ACCESS_TEST_DB=$INIT_CWD/db/northwind.accdb`
(pnpm sets `INIT_CWD` to the directory pnpm was invoked from — the repo
root when running from the top-level `pnpm parity:northwind`). Verify
this works on this machine:

```bash
cd rescript-mcp && pnpm run --silent -- node -e "console.log(process.env.INIT_CWD)"
```

If `INIT_CWD` is undefined or wrong, fall back to a hardcoded absolute
path discovered by `node -e`:

```json
"parity:northwind": "node -e \"process.env.ACCESS_TEST_DB=require('path').resolve(__dirname,'db','northwind.accdb');require('./parity/dist/run.js')\" -- --cases-dir=rescript-mcp/parity/cases/northwind --require-read-only",
```

This is robust: `__dirname` in the inline node script is the package dir
(`rescript-mcp/`); it resolves `db/northwind.accdb` against that.
Then `require('./parity/dist/run.js')` executes the harness with the env
var already set.

Apply the same pattern to both parity scripts. The `cross-env` package
may not be installed — `node -e` with `require()` is dependency-free.

### Step 2: Verify both parity scripts

Default ODBC subset (unchanged behavior):
```bash
pnpm -C rescript-mcp parity:northwind
```
Expect: 6 matched / 0 mism / 3 errored (baseline preserved).

COM subset (the new behavior):
```bash
pnpm -C rescript-mcp parity:northwind:com
```
Expect: **≥ 4 matched / ≤ 2 mism / 0 errored.** Specifically:
- `connect_access.json` — still FAILS (hardcoded `adapter_type: "odbc"` in Facade.res:238 — separate bug, out of scope; recorded in findings).
- `get_queries.json` — PASSES.
- `get_relationships.json` — status depends on whether DAO Relations iteration is done (currently stub returns Ok([]) — likely STILL FAILS, expected since plan 032 didn't implement it; record in findings).
- `get_table_schema-Customers.json` — **was ERROR, now PASSES.**
- `get_tables.json` — PASSES (unchanged).
- `query_data-SelectTop5Customers.json` — PASSES (unchanged).

### Step 3: Update `plans/README.md` row 032b

Mark 032b DONE with final SHA, one-line note about the harness fixture
fix. Renumber subsequent: 033 mutations, 034 DDL (unchanged from prior
plan).

### Step 4: Update `rescript-mcp/parity/findings.md`

Replace the 032-F-001 entry's "Follow-up: per-table schema..." paragraph
with the actual resolution: "Plan 032b: parity harness fixture default
fixed in `package.json`. COM parity case `get_table_schema-Customers.json`
now PASSES (was misattributed to a missing `getTableSchemaPlan`
implementation). The COM adapter's `getTables` was correct all along —
the harness was running Northwind cases against the lowercase test_db.accdb
fixture."

Add 032b-F-001 with: "Parity harness fixture default. Recorded
2026-08-31. The `--cases-dir=rescript-mcp/parity/cases/northwind[/com]`
flags don't override the default fixture; `dist/run.js` falls back to
`tests/integration/fixtures/test_db.accdb`. Scripts fixed in plan 032b
by injecting `ACCESS_TEST_DB` via inline `node -e`."

## Done criteria

- [ ] `pnpm -C rescript-mcp parity:northwind` runs without exporting
      `ACCESS_TEST_DB` and produces the same baseline as before
      (6/0/3 ODBC subset).
- [ ] `pnpm -C rescript-mcp parity:northwind:com` runs without exporting
      `ACCESS_TEST_DB` and produces **0 errored** for the COM subset
      (the `get_table_schema-Customers.json` case flips from ERROR to PASS).
- [ ] `pnpm -C rescript-mcp test` ≥ 734 passing, 0 failing.
- [ ] No MSACCESS.EXE orphan after suite.
- [ ] `parity/findings.md` updated: 032-F-001 follow-up superseded;
      032b-F-001 recorded.
- [ ] `plans/README.md` row 032b → DONE.
- [ ] Conventional commits, no push, no PR.

## STOP conditions

- The parity harness returns a non-zero exit code unrelated to the
  documented mismatches (`connect_access`, `get_relationships`).
- `parity:northwind` baseline regresses (6/0/3 → anything worse).
- `pnpm -C rescript-mcp test` regression.
- The inline `node -e` script fails to find `db/northwind.accdb` (path
  resolution issue); in that case, switch to the `cross-env-shell`
  pattern OR to a hardcoded absolute path discovered via
  `git rev-parse --show-toplevel`.

## Maintenance notes

- Future parity scripts that need a different fixture must set
  `ACCESS_TEST_DB` explicitly via inline `node -e` (or `cross-env-shell`).
  The harness default of `tests/integration/fixtures/test_db.accdb` is
  intentional — it's the canonical "always-available" fixture.
- The two pre-existing COM mismatches (`connect_access`, `get_relationships`)
  are tracked separately and have their own resolution paths (not in 032b):
  - `connect_access.json` adapter_type: hardcoded "odbc" in Facade.res:238
    should read `binding.adapterType` (which is set correctly by the
    factory).
  - `get_relationships.json`: DAO Relations iteration not implemented;
    belongs in plan 033 (mutations) since Relations are needed for FK
    cascading.
- `getTableSchemaPlan` per-table adapter method: still stub returning
  empty `Interfaces.tableSchema[]`. `Facade.getTableSchema` works around
  it via `getTables + find`. A clean `getTableSchemaPlan` implementation
  belongs in a follow-up plan (032c) that iterates `TableDef.Fields`
  per table and reads `Type`/`Size`/`Required`/`DefaultValue`/
  `Attributes`. Not blocking parity; not blocking mutations.