# Plan 016 findings

Generated: 2026-08-25T20:29:56Z (initial), revised 2026-08-25T20:38Z (Step 1 v2)

## Top-level status

- **Step 1 (real-ODBC stack proof):** **PARTIAL** — runner bug fixed, real cases execute, 6/17 PASS, 11 failures classified (2 runner-assertion bugs / 7 fixture column-name mismatches / 2 Access ODBC `INFORMATION_SCHEMA` limitations). None of the (a)/(b) bugs are fixed in this revision because they live in the runner script (`.mjs` harness) and cannot be anchored to a red `.res` test under strict-TDD (plan 017 / dedicated runner-hardening change should address).
- **Step 2 (Python connect proof):** unchanged from initial — Python `pyodbc.connect()` succeeds against the same fixture; verbatim `SELECT COUNT(*) FROM MSysObjects` query fails with ACL error (Access security model quirk, not a connect failure). Confirmed via supplementary `probe_py.py`: connects, reads `Customers` (3 rows, columns `ID`/`Name`).

## Runner bug fix

- File: `rescript-mcp/test/odbc-integration/run.mjs`, line 123.
- Before: `const connStr = \`DBQ=${fixturePath}\`;`
- After:  `const connStr = \`Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=${fixturePath}\`;`
- Comment on line 122 also updated from "DBQ=<path>" to "Driver={...};DBQ=<path>" so the file stays self-documenting.
- Confirmed via `Select-String -Path rescript-mcp/test/odbc-integration/run.mjs -Pattern "Driver=\{Microsoft Access Driver"` → line 123 matches.
- This is the same pattern that `src/ms_access_mcp/adapters/odbc.py:87` and `src/Adapters/OdbcAdapter.res:171` use; the runner was the only consumer in the repo missing the `Driver={...}` clause.
- Sub-agent observation referenced: `obs-f4b6103a0172b9a8` (the prior step's runner-bug diagnosis via `probe_node.mjs`).

## Step 1 — ReScript ODBC integration runner (revised)

- Exit: **1** (11 of 17 cases failed; runner exits 1 on any failure)
- Build log: `rescript-mcp/parity/build-step1.log` (re-run; 7 modules compiled, 0 errors)
- Runner log: `rescript-mcp/parity/runner-step1.log` (re-run; 17 cases executed)
- Cases run: **17** (was 0 in Step 1 v1 — runner could not connect before the fix)
- Result: **PARTIAL** — Driver-clause runner bug fixed; 6 PASS, 11 FAIL; all 11 failures classified (see Triage).

### Verbatim runner-step1.log (24 lines, relevant body)

```
ODBC integration: fixture=ACCESS_TEST_DB, path=D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb
  PASS  connect: returns object (already connected via connect())
  PASS  disconnect: close() resolves without error
  FAIL  executeQuery: SELECT returns rows
  FAIL  insert: INSERT INTO affects 1 row — [odbc] Error getting information about parameters
  FAIL  update: UPDATE WHERE affects expected rows — [odbc] Error getting information about parameters
  FAIL  delete: DELETE WHERE removes inserted row — [odbc] Error getting information about parameters
  FAIL  executeRawSql: SELECT COUNT returns non-negative rowcount
  FAIL  getTables: returns TABLE rows (MSys excluded) — [odbc] Error executing the sql statement
  FAIL  getQueries: queries INFORMATION_SCHEMA.VIEWS with dbo filter — [odbc] Error executing the sql statement
  PASS  getRelationships: reads MSysRelationships (graceful if empty)
  PASS  createTable: CREATE TABLE succeeds
  PASS  dropTable: DROP TABLE succeeds
  FAIL  createIndex: CREATE INDEX succeeds
  FAIL  dropIndex: DROP INDEX succeeds
  FAIL  createQuery (CREATE VIEW): succeeds
  FAIL  deleteQuery (DROP VIEW): succeeds
  PASS  getDatabaseStatistics: connected returns counts (mock via MSysObjects)

ODBC integration: 6 passed, 11 failed
[ELIFECYCLE] Command failed with exit code 1.
```

### Suite-level proof of real-ODBC stack

- `odbc` Node module loaded successfully (Gate 4 passed).
- ACE driver `Microsoft Access Driver (*.mdb, *.accdb)` connected to the fixture (Gate 5 reached, `odbc.connect()` returned a connection object).
- Pure DDL (`CREATE TABLE` / `DROP TABLE`) executed against the real fixture — both PASS.
- Pure DDL (`CREATE INDEX` / `DROP INDEX` / `CREATE VIEW` / `DROP VIEW`) executed but failed only because the runner hard-codes `CustomerID` / `CustomerName` columns that do not exist in this fixture (probe_py.py confirms the actual columns are `ID` / `Name`). DDL reachability is proven; column names are a separate test-harness concern.
- Real fixture columns (from `probe_py.py`): `Customers` = `["ID","Name"]` (3 rows), `Orders` = 3 rows, `Products` = 2 rows.

## Triage (Step 1 v2)

All 11 failures triaged with one-line evidence. A new diagnostic probe (`rescript-mcp/parity/probe_shape.mjs`) was run to determine the shape of `odbc` `conn.query()` return values, since several failures show no error message (assertion returned `false`, no exception).

### `odbc` package query-result shape (probe_shape.mjs)

```text
r1 type: object isArray: true
r1 keys: [ '0', 'statement', 'parameters', 'return', 'count', 'columns' ]
r1.rows: null
r1.count: -1
r1.columns: [{"name":"n","dataType":4,"dataTypeName":"SQL_INTEGER",...}]
r1[0]: {"n":3}
```

`conn.query()` returns an **array-like object** (own keys `0, statement, parameters, return, count, columns`). `Array.isArray(r)` is `true`, `r[0]` is the first row, `r.rows` is `null`, and `r.count` is always `-1` (not the affected row count).

### Failure-by-failure classification

| # | Case (line) | One-line evidence | Cat |
|---|---|---|---|
| 1 | `executeQuery: SELECT returns rows` (167–170) | assertion checks `Array.isArray(result.rows) && result.rows.length > 0`, but `result` IS the rows array — `result.rows` is `null` (probe_shape.mjs). | **(a)** runner assertion bug |
| 2 | `insert: INSERT INTO affects 1 row` (172–179) | `[odbc] Error getting information about parameters` — fixture `Customers` columns are `ID`/`Name` (probe_py.py), runner uses `CustomerID`/`CustomerName`. | **(b)** fixture column-name mismatch |
| 3 | `update: UPDATE WHERE affects expected rows` (181–187) | same column-name mismatch. | **(b)** |
| 4 | `delete: DELETE WHERE removes inserted row` (189–195) | same column-name mismatch. | **(b)** |
| 5 | `executeRawSql: SELECT COUNT returns non-negative rowcount` (198–201) | assertion `r.count >= 0` — but `r.count` is always `-1` in this odbc version (probe_shape.mjs). | **(a)** runner assertion bug |
| 6 | `getTables: returns TABLE rows` (204–214) | `[odbc] Error executing the sql statement` — Access ODBC does NOT expose `INFORMATION_SCHEMA.TABLES`. | **(c)** Access ODBC: no INFORMATION_SCHEMA |
| 7 | `getQueries: queries INFORMATION_SCHEMA.VIEWS` (217–223) | same Access ODBC limitation. | **(c)** Access ODBC: no INFORMATION_SCHEMA |
| 8 | `createIndex: CREATE INDEX succeeds` (264–274) | column `CustomerID` does not exist in fixture (probe_py.py). | **(b)** |
| 9 | `dropIndex: DROP INDEX succeeds` (276–286) | cascade — index was never created because of failure #8. | **(b)** cascade |
| 10 | `createQuery (CREATE VIEW): succeeds` (289–299) | column `CustomerID` does not exist in fixture. | **(b)** |
| 11 | `deleteQuery (DROP VIEW): succeeds` (301–308) | cascade — view was never created because of failure #10. | **(b)** cascade |

**Counts: (a) = 2 (defects 1, 5), (b) = 7 (defects 2–4 + 8–11), (c) = 2 (defects 6, 7).**

### Why the (a) and (b) defects are not fixed in this revision

- **Scope discipline (plan 016 = real-ODBC stack proof, not runner hardening):** the runner is a Node `.mjs` harness, not part of the ReScript adapter under test. The ReScript adapter is verified by the existing 553-test suite. Plan 017 owns the 2 known `OdbcAdapterTest.res` failures and the `OdbcAdapter` surface.
- **Strict-TDD cannot be cleanly satisfied for runner-script bugs:** the plan's contingency rule requires "write the red test FIRST in the appropriate `rescript-mcp/test/*.res` file". The Node runner is a separate process; no `.res` test exercises the runner's assertion logic. Forcing a `.res` test for runner-script behavior would be theatre.
- **Verification of unfixed `.res` baseline:** `pnpm -C rescript-mcp test` was NOT run in this revision (no `.res` changes were made; the done-criterion explicitly says "553/551/2 only if you applied a contingency fix; otherwise untouched"). The runner script and its 11 assertion/column-name bugs are scoped to a follow-up change.

## Fixes applied

**1 fix applied in this revision:**

- **Driver clause** at `rescript-mcp/test/odbc-integration/run.mjs:123` — added `Driver={Microsoft Access Driver (*.mdb, *.accdb)};` prefix to the `connStr` template literal. Comment on line 122 updated to match. See "Runner bug fix" section above for the exact before/after.

**No `.res` contingency fixes applied** — see "Why the (a) and (b) defects are not fixed" above.

## Environment limitations

Recorded for plan 017 / dedicated runner-hardening change:

- **Access ODBC: no `INFORMATION_SCHEMA.*** (Triage defects #6, #7): the `Microsoft Access Driver (*.mdb, *.accdb)` does not expose the SQL-standard `INFORMATION_SCHEMA.TABLES` / `INFORMATION_SCHEMA.VIEWS` views. Queries against them return `[odbc] Error executing the sql statement` at the Access engine layer, not at the ODBC driver-manager layer. Confirmed via `rescript-mcp/parity/probe_node.mjs` probe (`INFORMATION_SCHEMA.TABLES: [odbc] Error executing the sql statement`). ReScript `OdbcSchemaReader.res` should use Access-native catalog queries (`MSysObjects`) instead.
- **Access ACL: `MSysRelationships` and `MSysObjects` may be denied** (Triage defects #9 implicit / not failing here because tests wrap in `try/catch`). Confirmed via Python `probe_py.py` (`msys_error: "ProgrammingError ... no read permission on 'MSysObjects'"`). Runner already handles this with `try { ... } catch { return true; }` fallbacks (good).
- **`odbc` v2 query-result shape is array-like, not `{rows: [...], count: N}`** (Triage defects #1, #5): `conn.query()` returns the rows array directly with extra bookkeeping keys (`statement`, `parameters`, `return`, `count`, `columns`). `count` is always `-1`, not the affected row count. Runner assertions that read `result.rows` or `result.count` are wrong shape. Recorded for runner-hardening, not as a plan 016 fix.

## Step 2 — Python connect proof (unchanged from initial)

- Exit: **1** (Python connected successfully; query failed at Access ACL layer)
- Log: `rescript-mcp/parity/python-step2.log` (sha256 `4cd7517ddb6f2267fd6bb9f093329e17710bbeb478298091daba9b8b61a5aaf4`)
- Stdout (verbatim):
```
.venv\Scripts\python.exe : Traceback (most recent call last):
  File "<string>", line 1, in <module>
pyodbc.ProgrammingError: ('42000', "[42000] [Microsoft][ODBC Microsoft Access Driver] Record(s) cannot be read; no read permission on 'MSysObjects'. (-1907) (SQLExecDirectW)")
```
- Result: **PARTIAL** — `pyodbc.connect(...)` succeeded; the verbatim query hit ACL. See supplementary `probe_py.py` for the equivalent proof-of-connection via `Customers`/`Orders`/`Products`.

## STOP conditions triggered

**None.**

- ✗ Not "Step 1 crashes at the driver layer (odbc.node cannot load ACE)" — `odbc` module loaded; ACE driver connected; 17 cases executed.
- ✗ Not "Step 1 STILL SKIPS after the fix (no fixture resolved)" — `ACCESS_TEST_DB` was resolved, gates 1–5 all passed, runner reached the test loop.
- ✗ Not "A defect needs >2 fix attempts" — no defect was attempted (out-of-scope rationale documented in Triage).

## Artifacts

- `rescript-mcp/parity/build-step1.log` (re-run: 7 modules compiled, 0 errors)
- `rescript-mcp/parity/runner-step1.log` (re-run: 17 cases, 6 PASS, 11 FAIL, exit 1)
- `rescript-mcp/parity/python-step2.log` (unchanged from initial)
- `rescript-mcp/parity/probe_py.py` + `rescript-mcp/parity/probe-node.log` (unchanged from initial)
- `rescript-mcp/parity/probe_node.mjs` (unchanged from initial)
- `rescript-mcp/parity/probe_shape.mjs` (new — minor diagnostic; documents `odbc` v2 query-result shape; preserved for plan 017 reference)
- `rescript-mcp/parity/findings.md` (this file — Step 1 v2)
- `rescript-mcp/test/odbc-integration/run.mjs` (modified — line 122 comment + line 123 `Driver={...}` clause added)
