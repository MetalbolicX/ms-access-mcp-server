# Plan 026: Establish a Northwind read-only real-database baseline

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 3180a79..HEAD -- rescript-mcp/parity/ rescript-mcp/package.json rescript-mcp/test/ rescript-mcp/scripts/ plans/README.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans 007, 008, 016, 019, 020
- **Category**: tests
- **Methodology**: NEITHER
- **Planned at**: commit `3180a79`, 2026-08-28
- **Branch**: `rescript/026-northwind-readonly-baseline` from `3180a79` (main)

## Why this matters

Before the project can validate ODBC mutation hardening or COM facade work against a real multi-table Access database, it needs a verified read-only baseline with known schema, row counts, and SHA-256 provenance. Northwind is the canonical Access sample. Acquiring it through a trusted operator-provided path (not an arbitrary mirror) and fingerprinting it establishes the chain of custody needed for future evidence comparisons. A non-mutating parity corpus against Northwind also exercises the harness against a larger, more realistic schema than the fixture DB.

## Current state (verified at `3180a79`)

Verified 2026-08-28:

- HEAD = `3180a79`; all plans 001–025 DONE.
- ReScript suite: 678/678/0 (per `rescript-mcp/parity/test-024.log` or equivalent fresh-build gate).
- Small fixture parity: 17/17/0 (per `pnpm -C rescript-mcp parity` against `ACCESS_TEST_DB`).
- Existing parity runner `rescript-mcp/parity/run.ts` discovers all JSON files from one hard-coded cases directory; existing corpus contains mutations and fixture-specific `customers/products` assumptions.
- `cases.schema.json` requires `operation`, `args`, `variant="odbc"`, `mutating`; supports `volatileFields`.
- Non-mutating cases share pristine DB; mutating cases create per-side copies.
- `inventory_fixture.py` runs with `ACCESS_TEST_DB`; use `.venv\Scripts\python.exe`, never `uv`.
- MCP server entry is package script `server`: `node ./src/Mcp/main.mjs`.
- Exactly 12 MCP tools are registered; safe read-only subset: `list_connections`, `is_connected`, `query_data` (SELECT only), `get_tables`, `get_table_schema`, `get_queries`. `connect_access`/`disconnect_access` alter process connection state but not DB. `execute_raw_sql` is NOT considered read-only for the MCP smoke.
- Five facade ops are not registered as MCP tools: active-connection setters/getters, relationships, stats, export. They may be tested through parity but not claimed as MCP coverage.
- Raw node-odbc integration: 6 pass/11 fail due to documented ACE limitations in `parity/findings.md`; do not use its nonzero exit as this plan's success gate.
- ReScript COM modules are incomplete/unwired. Python WinComAdapter cannot guarantee read-only.
- No automated ReScript MCP stdio transport test currently exists.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Drift check | `git diff --stat 3180a79..HEAD -- rescript-mcp/parity/ rescript-mcp/package.json rescript-mcp/test/ rescript-mcp/scripts/ plans/README.md` | Zero diff in scope |
| Git status | `git status --short` | Only untracked junk files (`led.out`, `nul`) or nothing |
| ACE driver check | `Get-OdbcDriver -Name "Microsoft Access Driver (*.mdb, *.accdb)" -Platform "64-bit"` | Driver found |
| Northwind path | `Test-Path tests/integration/fixtures/northwind.accdb` | True |
| Git ignore check | `git check-ignore tests/integration/fixtures/northwind.accdb` | Reports the path |
| SHA-256 (before) | `Get-FileHash -Algorithm SHA256 tests/integration/fixtures/northwind.accdb` | Hash recorded |
| Fixture parity | `ACCESS_TEST_DB="...small_fixture.accdb" pnpm -C rescript-mcp parity` | 17/17/0 |
| Suite | `pnpm -C rescript-mcp test` | 678 passed / 0 failed |
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| SHA-256 (after) | `Get-FileHash -Algorithm SHA256 tests/integration/fixtures/northwind.accdb` | Matches before hash |

## Scope

**In scope** (create/modify only these):
- `rescript-mcp/parity/run.ts` — add `--cases-dir` and `--require-read-only` CLI flags
- `rescript-mcp/parity/cases/northwind/*.json` — create nine Northwind parity cases
- `rescript-mcp/test/northwind-stdio/run.mjs` — create MCP stdio smoke runner
- `rescript-mcp/package.json` — add `parity:northwind` and `test:integration:northwind:stdio` scripts
- `rescript-mcp/parity/northwind-provenance.md` — create provenance document
- `rescript-mcp/parity/northwind-inventory.md` — create normalized inventory (no local paths/secrets)
- `rescript-mcp/parity/README.md` — update to document northwind corpus
- `rescript-mcp/parity/findings.md` — update with 026-F-xxx mismatches if any
- `plans/README.md` — append row 026

**Out of scope** (do NOT touch):
- Any file under `src/ms_access_mcp/`
- Any file under `rescript-mcp/src/`
- `rescript-mcp/parity/cases/fixture/` (existing corpus)
- Any mutation or Access COM work
- `rescript-mcp/parity/cases/fixture/` existing cases
- Product source files

## Git workflow

- Branch: `rescript/026-northwind-readonly-baseline`, cut from `main` at `3180a79`.
- Four conventional commits:
  1. `feat(parity): add --cases-dir and --require-read-only to parity runner`
  2. `feat(parity): add northwind read-only corpus (9 cases)`
  3. `feat(test): add northwind stdio integration smoke`
  4. `chore(parity): record northwind provenance and baseline inventory`
- Do NOT push or open a PR.

## Steps

### Step 0: Pre-flight — operator-provided Northwind gate

**STOP if no trusted Northwind file is supplied.**

The operator must provide or create Northwind through:
- Installed Access's template UI ("Create from Template" → "Northwind")
- Another trusted local source (e.g. an operator-owned `.accdb` already on disk)

There is no verified official unattended Microsoft `.accdb` download in 2026. Do NOT download from an arbitrary mirror.

Canonical ignored location: `tests/integration/fixtures/northwind.accdb`.
Root `.gitignore` already ignores `*.accdb`, `*.mdb`, `*.laccdb`.

Verify:
```powershell
Test-Path tests/integration/fixtures/northwind.accdb  # must be True
git check-ignore tests/integration/fixtures/northwind.accdb  # must report path
git ls-files --error-unmatch tests/integration/fixtures/northwind.accdb  # must FAIL (not tracked)
Get-OdbcDriver -Name "Microsoft Access Driver (*.mdb, *.accdb)" -Platform "64-bit"  # must find ACE
```

Copy (do not move) the operator-provided file to `tests/integration/fixtures/northwind.accdb` if it is not already there.

Record SHA-256 before any checks:
```powershell
Get-FileHash -Algorithm SHA256 tests/integration/fixtures/northwind.accdb
```

Expected: canonical tables `Customers`, `Orders`, `Products`, `Order Details` (case-insensitive exact names) are present. If absent, STOP and report edition/schema rather than improvising cases.

### Step 1: Add CLI flags to `parity/run.ts`

Read `rescript-mcp/parity/run.ts` fully before editing.

Add two new CLI flags to the argument parser (use the existing flag library):

- `--cases-dir=<relative-path>` (default: `parity/cases/fixture`)
- `--require-read-only` (flag, no value)

Behavior:
- `--cases-dir`: resolve the path relative to `rescript-mcp/` cwd. If directory does not exist, abort with error. Load all `*.json` files from that directory (non-recursive).
- `--require-read-only`: before opening either DB side, iterate all loaded cases. If any case has `mutating: true`, print the case name and abort with exit 1. This guard runs before any DB connection is opened.

Preserve all existing default behavior exactly when neither flag is provided.

**Verify**:
```powershell
pnpm -C rescript-mcp build
node rescript-mcp/parity/dist/run.js --cases-dir=parity/cases/northwind --require-read-only
# should abort cleanly before opening DB when no cases exist yet
```

### Step 2: Add package scripts

Read `rescript-mcp/package.json` before editing.

Add two scripts:
```json
"parity:northwind": "node ./parity/dist/run.js --cases-dir=parity/cases/northwind --require-read-only",
"test:integration:northwind:stdio": "node ./test/northwind-stdio/run.mjs"
```

### Step 3: Create nine Northwind corpus cases

Create directory `rescript-mcp/parity/cases/northwind/`.

Create exactly these nine JSON files, all with `variant:"odbc"`, `mutating:false`, and minimal/no `volatileFields`. Never hide `rows`, fields, errors, or object names:

1. `get_tables.json`
2. `get_table_schema-Customers.json`
3. `get_table_schema-Orders.json`
4. `get_table_schema-Products.json`
5. `get_queries.json`
6. `get_relationships.json`
7. `get_database_statistics.json`
8. `query_data-SelectTop5Customers.json`
9. `execute_raw_sql-CountOrders.json`

Schema per `cases.schema.json`:
```json
{
  "operation": "<opName>",
  "args": { ... },
  "variant": "odbc",
  "mutating": false,
  "volatileFields": []
}
```

For `query_data-SelectTop5Customers.json`:
```json
{
  "operation": "query_data",
  "args": {
    "connection_name": "northwind",
    "sql": "SELECT TOP 5 * FROM [Customers]"
  },
  "variant": "odbc",
  "mutating": false,
  "volatileFields": []
}
```

For `execute_raw_sql-CountOrders.json` (SELECT-only):
```json
{
  "operation": "execute_raw_sql",
  "args": {
    "connection_name": "northwind",
    "sql": "SELECT COUNT(*) AS [row_count] FROM [Orders]"
  },
  "variant": "odbc",
  "mutating": false,
  "volatileFields": []
}
```

Do not include lifecycle or mutation cases.

**Verify**:
```powershell
node rescript-mcp/parity/dist/run.js --cases-dir=parity/cases/northwind --require-read-only
# must pass the guard without opening DB (0 cases loaded is also acceptable if directory is empty, but with 9 cases it must pass)
```

### Step 4: Create `test/northwind-stdio/run.mjs`

Create directory `rescript-mcp/test/northwind-stdio/`.

Create `run.mjs` using SDK v1.29 imports:

```javascript
// @ts-check
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

async function main() {
  const projectRoot = join(__dirname, "..", "..");
  const allowedDirs = process.env.ACCESS_MCP_ALLOWED_DIRS || "";
  const testDb = process.env.ACCESS_TEST_DB || "";

  const transport = new StdioClientTransport({
    command: "node",
    args: ["./src/Mcp/main.mjs"],
    cwd: projectRoot,
    env: {
      ...process.env,
      ACCESS_MCP_READONLY: "true",
      ACCESS_TEST_DB: testDb,
      ACCESS_MCP_ALLOWED_DIRS: allowedDirs,
    },
  });

  const client = new Client({ name: "northwind-stdio-test", version: "1.0.0" }, {});
  let passed = false;

  try {
    await client.connect(transport);

    // List tools and assert required subset
    const { tools } = await client.listTools();
    const toolNames = tools.map((t) => t.name);
    const requiredTools = ["list_connections", "is_connected", "query_data", "get_tables", "get_table_schema", "get_queries", "connect_access", "disconnect_access"];
    for (const name of requiredTools) {
      if (!toolNames.includes(name)) {
        throw new Error(`Required tool not found: ${name}`);
      }
    }

    // connect_access
    const dbPath = testDb; // operator must set ACCESS_TEST_DB to northwind.accdb
    await client.callTool("connect_access", { database_path: dbPath, name: "northwind", backend: "odbc" });

    // get_tables
    const tablesResult = await client.callTool("get_tables", { connection_name: "northwind" });
    if (tablesResult.isError) throw new Error(`get_tables failed: ${tablesResult.content}`);

    // get_table_schema Customers
    const schemaResult = await client.callTool("get_table_schema", { table_name: "Customers", connection_name: "northwind" });
    if (schemaResult.isError) throw new Error(`get_table_schema failed: ${schemaResult.content}`);

    // query_data SELECT TOP 5
    const queryResult = await client.callTool("query_data", {
      connection_name: "northwind",
      sql: "SELECT TOP 5 * FROM [Customers]",
    });
    if (queryResult.isError) throw new Error(`query_data failed: ${queryResult.content}`);
    const queryText = typeof queryResult.content === "string" ? queryResult.content : JSON.stringify(queryResult.content);
    if (!queryText.toLowerCase().includes("success")) {
      throw new Error(`query_data did not return success envelope: ${queryText}`);
    }

    // disconnect_access
    await client.callTool("disconnect_access", { name: "northwind" });

    passed = true;
  } finally {
    await client.close();
    // Hard timeout enforcement
    if (!passed) {
      console.error("Northwind stdio smoke FAILED");
      process.exit(1);
    }
    console.log("Northwind stdio smoke PASSED");
  }
}

// 30-second timeout
const timeout = setTimeout(() => {
  console.error("Northwind stdio smoke TIMEOUT (>30s)");
  process.exit(1);
}, 30000);

main().then(() => {
  clearTimeout(timeout);
  process.exit(0);
}).catch((err) => {
  clearTimeout(timeout);
  console.error(err.message);
  process.exit(1);
});
```

Do NOT call any mutation tool or `execute_raw_sql` through MCP in this smoke.

**Verify** (requires `ACCESS_TEST_DB` set to northwind.accdb path):
```powershell
$env:ACCESS_TEST_DB="D:\code\python\ms-access-mcp-server\tests\integration\fixtures\northwind.accdb"
$env:ACCESS_MCP_ALLOWED_DIRS="D:\code\python\ms-access-mcp-server\tests\integration\fixtures"
node rescript-mcp/test/northwind-stdio/run.mjs
# exit 0
```

### Step 5: Run inventory_fixture.py against Northwind

```powershell
$env:ACCESS_TEST_DB="D:\code\python\ms-access-mcp-server\tests\integration\fixtures\northwind.accdb"
.venv\Scripts\python.exe rescript-mcp/scripts/inventory_fixture.py
```

Record output. Create two tracked documents:

**`rescript-mcp/parity/northwind-provenance.md`**:
```markdown
# Northwind Provenance

- **Acquisition date**: <YYYY-MM-DD>
- **Source method**: <e.g. "Access template UI", "operator-provided">
- **Edition**: <if known, e.g. "Access 365 Northwind 365">
- **Basename**: northwind.accdb
- **SHA-256 (before)**: <hash>
- **SHA-256 (after)**: <hash>
- **Operator verification**: canonical tables confirmed present: Customers, Orders, Products, Order Details
- **Note**: COM objects were NOT inventoried because WinComAdapter cannot guarantee read-only on the original file.
```

**`rescript-mcp/parity/northwind-inventory.md`**:
```markdown
# Northwind Inventory (Normalized)

## Tables

| Table | Row count |
|-------|-----------|
| Customers | <N> |
| Orders | <N> |
| Products | <N> |
| Order Details | <N> |

## Schema fields (Customers)

| Field | Type |
|-------|------|
| CustomerID | TEXT |
| CompanyName | TEXT |
| ... | ... |

(Include field names and Access data types for all four canonical tables.)

## Notes
- COM objects NOT inventoried (WinComAdapter cannot guarantee read-only on original)
- No credentials, connection strings, or local paths recorded in this document
```

### Step 6: Run Northwind parity

```powershell
$env:ACCESS_TEST_DB="D:\code\python\ms-access-mcp-server\tests\integration\fixtures\northwind.accdb"
pnpm -C rescript-mcp parity:northwind
```

Record exact pass/mismatch/error counts. Any mismatches become `026-F-xxx` findings. Do NOT fix them. Ledger every mismatch/error in `rescript-mcp/parity/findings.md` under a `## Plan 026 Findings` section:

```
## Plan 026 Findings

### 026-F-001
- **Description**: <what mismatch>
- **Reproduction**: <case + args>
- **Owner**: <deferred to which plan>
```

### Step 7: Run stdio smoke

```powershell
$env:ACCESS_TEST_DB="D:\code\python\ms-access-mcp-server\tests\integration\fixtures\northwind.accdb"
$env:ACCESS_MCP_ALLOWED_DIRS="D:\code\python\ms-access-mcp-server\tests\integration\fixtures"
pnpm -C rescript-mcp test:integration:northwind:stdio
```

Required: exit 0.

### Step 8: SHA-256 verification

```powershell
Get-FileHash -Algorithm SHA256 tests/integration/fixtures/northwind.accdb
```

Must match hash from Step 0 exactly. If different, STOP — file was modified.

### Step 9: Verify git ignore state

```powershell
git check-ignore tests/integration/fixtures/northwind.accdb
git ls-files --error-unmatch tests/integration/fixtures/northwind.accdb
```

Must report path (ignore), then fail/not list (not tracked).

### Step 10: Run existing suite + fixture parity (regression gate)

```powershell
pnpm -C rescript-mcp test
# 678 passed / 0 failed

pnpm -C rescript-mcp parity   # existing fixture env
# 17/17/0
```

If either regresses, STOP.

### Step 11: Run `parity:types`

```powershell
pnpm -C rescript-mcp parity:types
```

exit 0 expected.

## Test plan

- New test: `test/northwind-stdio/run.mjs` smoke (Step 7).
- No new unit tests.
- Existing suite regression gate (Step 10) must hold.

## Done criteria

- [ ] `git status --short` shows only the new in-scope files + untracked junk (`led.out`, `nul`)
- [ ] `git diff --stat 3180a79..HEAD -- rescript-mcp/parity/ rescript-mcp/package.json rescript-mcp/test/ rescript-mcp/scripts/ plans/README.md` shows only new files in scope
- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` exits 0; 678 passed / 0 failed
- [ ] Existing fixture parity `pnpm -C rescript-mcp parity` = 17/17/0
- [ ] Northwind parity `pnpm -C rescript-mcp parity:northwind` records exact counts (mismatch exit allowed only when fully ledgered)
- [ ] `pnpm -C rescript-mcp test:integration:northwind:stdio` exits 0
- [ ] `pnpm -C rescript-mcp parity:types` exits 0
- [ ] SHA-256 before/after matches
- [ ] `git check-ignore tests/integration/fixtures/northwind.accdb` reports path; `git ls-files --error-unmatch ...` fails
- [ ] `northwind-provenance.md` and `northwind-inventory.md` exist under `rescript-mcp/parity/`
- [ ] `rescript-mcp/parity/findings.md` updated with `026-F-xxx` entries if any mismatches
- [ ] `plans/README.md` row 026 appended with status TODO, phase 26, methodology NEITHER, priority P1, effort M, depends 007, 008, 016, 019, 020

## STOP conditions

Stop and report back if:

- No trusted/operator-provided Northwind file is available.
- Missing any of the four canonical required tables (`Customers`, `Orders`, `Products`, `Order Details`).
- Northwind file is tracked in git (not ignored).
- Before/after SHA-256 hash differs.
- Any Northwind case has `mutating: true` or the `--require-read-only` guard fails to abort before DB open.
- Stdio smoke invokes a mutation tool or `execute_raw_sql` through MCP.
- The implementation appears to require changes to product source under `rescript-mcp/src/` or `src/ms_access_mcp/`.
- COM/Access.Application is opened against the original Northwind file.
- More than 10 mismatches/errors or harness crash: record partial evidence and stop, do not fix.
- Existing fixture parity (17/17/0) or ReScript suite (678/678/0) regresses.
- Any secrets, credentials, or linked-table connection strings appear in inventory output: redact and stop before committing.
- Drift check shows changes to in-scope paths since `3180a79`.

## Maintenance notes

- 026 is the evidence gate for future ODBC mutation hardening (planned) and COM facade/MCP plans (planned). No arbitrary Northwind mirror, no product fixes, no COM opening of original.
- If the operator cannot provide a trusted Northwind file, this plan remains in TODO indefinitely. Do not download from an arbitrary mirror.
- Every mismatch/error found in Step 6 must be recorded as `026-F-xxx` before this plan can be marked DONE, even if the mismatch is "expected ACE limitation".
