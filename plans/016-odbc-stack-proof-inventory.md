# Plan 016: Prove the real ODBC stack + inventory the fixture DB (verification gate)

> **Executor instructions**: Follow this plan step by step. This plan is NOT
> test-driven and NOT spec-driven: it runs EXISTING verification
> infrastructure against a real database for the first time and produces a
> fixture inventory consumed by plan 007. Run every verification command and
> confirm the expected result before moving on. If anything in "STOP
> conditions" occurs, stop and report — do not improvise. When done, update
> this plan's status row in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 0b69c82..HEAD --
> src/ms_access_mcp/adapters/ tests/integration/` — must be empty. Also
> confirm live facts: `Test-Path tests/integration/fixtures/test_db.accdb`
> → True; `Get-OdbcDriver | Where-Object { $_.Name -match "accdb" }` lists
> `Microsoft Access Driver (*.mdb, *.accdb)`. On mismatch, STOP.

## Status

- **Priority**: P1 (plan 007 builds on this proof; run it FIRST — it is
  cheaper than plan 015 and de-risks it)
- **Effort**: S
- **Risk**: MED (unknown what the never-run integration runner reveals)
- **Depends on**: plans/003 (ODBC core + integration runner), 006 (fixture
  conventions). Independent of 015/017 — may run in parallel with either.
- **Category**: tests
- **Methodology**: NEITHER. Verification infrastructure: it proves two
  existing implementations against a real database; there is no new behavior
  to drive out and no new contract to specify. CONTINGENCY: any product bug
  discovered is fixed under a bounded strict-TDD mini-cycle INSIDE this plan
  (write the red test first, fix minimally); more than 2 fix attempts on the
  same bug → STOP and report.
- **Planned at**: commit `2bbff3a` + uncommitted plans-003–006 working tree,
  2026-08-25

## Why this matters

Every ODBC integration runner in this repo has SKIPPED since it was written:
the `ACCESS_TEST_ASSUME_ACE` flag was never set on this machine. Meanwhile
the machine HAS the ACE driver and a fixture `.accdb` exists. Plan 007
(parity harness) stacks both implementations on this unproven path — if the
ReScript→odbc→ACE chain has a latent bug, parity runs would drown in
infrastructure failures that look like parity mismatches. This plan runs the
existing runners for real, once, and produces the fixture inventory that
plan 007's case authoring needs (real table names, columns, row counts).

## Current state

Verified facts on this machine (2026-08-25):

- ACE ODBC driver installed: `Microsoft Access Driver (*.mdb, *.accdb)`
  (also `*.mdb` variants). Confirmed via `Get-OdbcDriver` AND via pyodbc:
  `[d for d in pyodbc.drivers() if 'accdb' in d.lower()]` returns it.
- Fixture exists: `tests/integration/fixtures/test_db.accdb`.
  Contents UNKNOWN (no inventory has ever been produced) — that is the
  second deliverable of this plan.
- `rescript-mcp/node_modules/odbc` present (IBM node-odbc 2.5.x).
- Python: `.venv/Scripts/python.exe` works; `import pyodbc` OK.
  **`uv` is NOT on PATH** — use `.venv\Scripts\python.exe` directly.
- ReScript ODBC integration runner: `rescript-mcp/test/odbc-integration/run.mjs`
  (winax-free; gated). Its fixture fallback path is
  `rescript-mcp/test/fixtures/test_db.accdb` — **NOT** the Python fixture
  location. Verified skip message:
  `"ODBC integration skipped: no fixture resolved (ACCESS_TEST_DB unset, and
  D:\code\python\ms-access-mcp-server\rescript-mcp\test\fixtures\test_db.accdb
  not found). Set ACCESS_TEST_ASSUME_ACE=1 ... to enable."`
  → `ACCESS_TEST_DB` must ALWAYS be set explicitly for the ReScript side.
- Runner entry: `pnpm -C rescript-mcp test:integration:odbc`.
- Suite baseline: 553 tests / 551 pass / 2 known failures (plan 017 owns
  those; this plan must not add new failures).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit tests | `pnpm -C rescript-mcp test` | 553 / 551 / 2 known (unchanged) |
| ODBC integration (real) | see Step 1 (env + `pnpm -C rescript-mcp test:integration:odbc`) | exit 0, real cases run (not skipped) |
| Python proof | see Step 2 (`.venv\Scripts\python.exe` one-liner) | prints JSON with table count |

## Scope

**In scope**:
- `rescript-mcp/parity/fixture-inventory.md` (create — the inventory artifact)
- `rescript-mcp/scripts/inventory_fixture.py` (create — small generator
  script; lives beside plan 007's future `parity_driver.py`)
- Bounded strict-TDD fixes for bugs this plan DISCOVERS, only if trivial
  (≤2 attempts each; red test first)
- A findings note (`rescript-mcp/parity/findings.md`, create) for anything
  discovered and not fixed

**Out of scope**:
- Plan 007 harness code (cases, runners, normalizer, differ).
- COM integration (`test/com-integration/run.mjs`) — deferred; all 17 v1
  facade ops are ODBC (see plan 018 amendment 6).
- Any refactor of the runners themselves.
- Python source changes (a discovered Python-side defect is a FINDING, not a
  fix — Python is the oracle).

## Git workflow

- Branch: `rescript/016-odbc-stack-proof`.
- Conventional commits, e.g. `test(rescript): real-ODBC stack proof + fixture inventory`.

## Steps

### Step 1: Run the ReScript ODBC integration runner for real

PowerShell (exact):

```powershell
$env:ACCESS_TEST_DB = "D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb"
$env:ACCESS_TEST_ASSUME_ACE = "1"
pnpm -C rescript-mcp test:integration:odbc
```

**Verify**: exit 0 AND the output shows real cases executed (no "skipped"
summary). Record per-case pass/fail in `rescript-mcp/parity/findings.md`.

### Step 2: Python-side connect proof

```powershell
.venv\Scripts\python.exe -c "import pyodbc, json; c = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};Dbq=D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb;'); cur = c.cursor(); cur.execute('SELECT COUNT(*) FROM MSysObjects'); print(json.dumps({'connected': True, 'msys_objects': cur.fetchone()[0]})); c.close()"
```

**Verify**: prints `{"connected": true, "msys_objects": <N>}` with N > 0.

### Step 3: Fixture inventory

Write `rescript-mcp/scripts/inventory_fixture.py`: connects via pyodbc
(same connection string as Step 2; DB path from `ACCESS_TEST_DB` env with
the tests/integration/fixtures default), reads `MSysObjects` /
`INFORMATION_SCHEMA`-equivalent metadata, and writes
`rescript-mcp/parity/fixture-inventory.md` containing: user tables (name,
type), columns per table (name, type, nullable), row counts per table,
saved queries (name), relationships if derivable, and the file's byte size.
Run it with `.venv\Scripts\python.exe`.

**Verify**: `rescript-mcp/parity/fixture-inventory.md` exists and documents
≥1 user table with ≥1 column. If there are ZERO user tables → STOP (see
STOP conditions).

### Step 4: Triage any failures from Step 1

For each failing case: classify (a) test/runner bug, (b) ReScript adapter
bug, (c) environment/driver issue. Only (a)/(b) are fixable here, under the
strict-TDD contingency (red test first, ≤2 attempts). (c) → findings + STOP.
Unfixed items → `rescript-mcp/parity/findings.md` with owner + status.

**Verify**: re-run Step 1; either exit 0 or every remaining failure is
recorded in findings.md with a triage classification.

## Test plan

- This plan's "tests" are Steps 1–2 commands with expected outputs.
- Any contingency fix adds a red-first unit test in the appropriate
  `rescript-mcp/test/*.res` file; suite must return to 553/551/2 (or better).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] Step 1 executed with env set; per-case results recorded (pass, or
      findings.md entries)
- [ ] Step 2 Python proof output captured (connected: true)
- [ ] `rescript-mcp/parity/fixture-inventory.md` exists, documents ≥1 user
      table with columns and row counts
- [ ] `pnpm -C rescript-mcp test` unchanged: 553 / 551 / 2 known failures
- [ ] `rescript-mcp/parity/findings.md` exists (even if empty of open items)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Step 1 crashes with driver-level errors (e.g. odbc module cannot load the
  ACE driver) after 2 remediation attempts → report; plan 007's real-DB
  premise fails.
- Fixture has ZERO user tables → the fixture is too thin for parity cases;
  report (a richer fixture must be authored — product decision).
- Fixture file is corrupt / cannot be opened by either side → report.
- pyodbc connect fails despite the driver being registered → report.
- A discovered defect needs >2 fix attempts → record in findings.md and
  stop this plan.

## Maintenance notes

- Plan 018 (amendments) references this plan's inventory file as the case-
  authoring input; plan 007 Step 1 consumes it.
- If the fixture is ever regenerated, re-run Step 3 to refresh the inventory.
- COM stack proof is deliberately deferred (v1 parity is ODBC-only); revisit
  when a future facade phase adds COM operations.
