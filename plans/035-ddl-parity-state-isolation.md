# Plan 035 — DDL Parity State Isolation (034-F-004)

## Goal

Make the 18 DDL parity case files (`cases/northwind/ddl/` + `cases/northwind/com/ddl/`)
self-contained so every case passes (or is explicitly skipped) on a fresh per-side
fixture copy — closing 034-F-004.

Today only 3/9 ODBC DDL and 2/9 COM DDL cases match. The failures are NOT
implementation defects: delete/drop/set cases reference objects (`ParityTest_Tmp`,
`ParityTest_IX`, `qry_ParityTest`) that a fresh copy never contains, one case sends
an args shape the Python oracle does not understand, and `generate_sql` diverges
by contract (ODBC: unsupported; COM: pre-existing native teardown crash 033-F-001).

## Methodology

HARNESS BUGFIX — behavior is pinned by the Python oracle
(`src/ms_access_mcp/adapters/odbc.py`) and the existing parity runner
(`parity/run.ts`). No adapter source changes are in scope except where a case
exposes a genuine ReScript bug. Every change is gated by re-running the parity
scripts; unit suite must stay 770/770.

- Branch: `rescript/035-ddl-parity-setup`
- Priority: P2 · Effort: M · Depends on: 034

## Environment quirks (binding for executors)

1. Same bindings as plan 034 §Environment quirks (pnpm via `cmd.exe /c` with
   logs, `.venv\Scripts\python.exe` never `uv`, fresh-build-only green gates,
   kill `MSACCESS.EXE` before/after parity runs, `ACCESS_TEST_ASSUME_ACE='1'`).
2. Per-side fixture copies are allocated per mutating case in
   `run.ts` (`mkdtempSync` scratch under `%TEMP%\parity-007-*`). The pristine
   `db/northwind.accdb` must never be mutated — verify after every run.
3. `parity:northwind:ddl` and `parity:northwind:com:ddl` no longer pass
   `--require-read-only` (fixed in plan 034 T7); all 18 DDL cases are
   `mutating: true` and use per-side copies.
4. Python oracle side is ALWAYS ODBC (`parity_driver.py` → `OdbcAdapter`); the
   `variant` field only switches the ReScript side. Cross-variant divergences
   (e.g. DAO exposing the PK index where ODBC does not) must be handled via
   `volatileFields`, not by "fixing" one side blindly.

## Current state (verified at authoring time)

### Failing matrix (from T7 runs, findings.json)

| Case | ODBC ddl/ | COM com/ddl/ | Root cause |
|---|---|---|---|
| create_table | PASS | PASS | — |
| create_index | PASS | PASS | — |
| get_indexes | PASS | MISMATCH `$.count` exp 0 act 1 | ReScript-COM DAO lists 1 index on `Customers` (PK), Python-ODBC lists 0 — genuine cross-variant divergence |
| delete_table | ERROR | ERROR | `DROP TABLE ParityTest_Tmp` — table never created on the fresh copy |
| drop_index | ERROR | ERROR | `DROP INDEX ParityTest_IX ON Customers` — index never created |
| delete_query | ERROR | ERROR | `QueryDefs.Delete qry_ParityTest` — query never created |
| set_query_sql | ERROR | ERROR | `QueryDefs("qry_ParityTest")` — query never created |
| alter_table | ERROR | MISMATCH `$.operations[0].error` exp `'name'` act DAO `'' is not a valid name` | case sends `{"action","column":{name,type,size,nullable}}`; Python oracle expects a different (flat?) op dict — KeyError `'name'` recorded as per-op error; ReScript reads the missing key as `""` and executes DDL with an empty identifier |
| generate_sql | ERROR (`rescript: Not available via ODBC` vs `expected: null`) | ERROR (native crash, exit 134) | ODBC: both sides return documented `{success:false,error:"Not available via ODBC"}` envelopes but the runner still reports DRIVER — child/runner error contract mismatch. COM: 033-F-001 `MultiIsolatePlatform::DisposeIsolate` teardown crash, pre-existing |

### Harness touchpoints for setup ops

- `parity/run.ts` (`dist/run.js:187-215`) — per-case loop; `mutating` decides
  per-side copies; children receive the case path and parse the JSON themselves,
  so a new `setup` field is visible to both children WITHOUT runner data plumbing.
- `rescript-mcp/scripts/parity_driver.py:418-483` — Python op dispatch
  (`if operation == ...` chain). A setup loop reuses this dispatch verbatim.
- `parity/runRescript.ts:143-280` — ReScript op dispatch (`runOperation`).
  Same: a setup loop reuses `runOperation`.
- `parity/cases.schema.json` — operation enum (26 entries; `create_query` is
  EXCLUDED per the now-resolved 034-F-001 — it must be re-added, see T2).
- `parity/dist/runRescript.ts` comment `// DDL operations (034 plan) — skip
  create_query (winax limitation, 034-F-001)` — stale, 034-F-001 is resolved.

## Tasks

### T1 — Canonical args audit + `alter_table` case fix

1. Read the LIVE Python oracle shapes (never trust memory):
   - `odbc.py` `alter_table` (~:973) — exact per-operation dict keys for
     `add_column` / `drop_column` / `modify_column` / `rename_table` /
     `rename_column`.
   - `odbc.py` `create_table` (:727) — column dict keys (`name`, `type`,
     `size`, `nullable` — confirmed by passing create_table cases).
2. Fix `cases/northwind/{ddl,com/ddl}/alter_table.json` `operations[0]` to the
   Python-canonical shape. Prefer an `add_column` on `Customers` (ODBC-safe;
   `rename_*` actions are DAO-only and would diverge by contract).
3. Verify the ReScript side consumes the same shape: trace
   `runRescript.ts` → `Facade.alterTable` → `OdbcAdapter.alterTable` /
   `ComDataAdapter.alterTable` op-dict parsing (`ComDataAdapter.res:1962+`,
   `processOps`). If the parsers disagree with the Python shape, align the
   ReScript parser (this is the one legitimate adapter-code change).
4. Green gate: `alter_table.json` matches on BOTH variants.

### T2 — `setup` mechanism in the harness

1. `cases.schema.json`: add optional
   `setup: {type: "array", items: {type: "object"}}` — a list of
   `{operation, args}` steps run before the main op. Add `create_query` back
   to the operation enum (034-F-001 is resolved; COM `createQuery` works).
   Schema rule: cases with `setup` MUST be `mutating: true` (lint-enforced).
2. `run.ts`: treat setup presence as mutating regardless of the flag —
   `const mutating = caseObj.mutating === true || Array.isArray(caseObj.setup)`
   — so a mislabeled case can never mutate the shared pristine fixture.
3. `parity_driver.py`: before the main dispatch, loop `caseObj.setup` through
   the same op chain. On setup failure: stderr `SETUP <operation>: <msg>`,
   exit 1 (surfaces as the existing errored/driver-failure path — never as a
   silent mismatch).
4. `runRescript.ts`: same loop via `runOperation`. Same failure contract.
   Also delete the stale "skip create_query" comment and add the
   `create_query` routing to `runOperation` + `FacadeModule` typing
   (`Facade.createQuery` — verify it exists; if the Facade lacks it, wire
   `schemaAdapterForName` like `setQuerySql` does).
5. Unit-cover the setup loop where cheap (the drivers are TS/Python children —
   a full unit harness is out of scope; parity green is the gate).

### T3 — Rewrite state-dependent cases with `setup`

Both variants (ddl/ and com/ddl/) get identical bodies except `variant`:

| Case | setup | main op |
|---|---|---|
| `delete_table.json` | `create_table ParityTest_Tmp (ID LONG/Counter, Name VARCHAR(100))` | `delete_table ParityTest_Tmp` |
| `drop_index.json` | `create_index ParityTest_IX on Customers (CustomerID)` | `drop_index ParityTest_IX on Customers` |
| `delete_query.json` | `create_query qry_ParityTest = SELECT ... FROM Customers` | `delete_query qry_ParityTest` |
| `set_query_sql.json` | `create_query qry_ParityTest = SELECT CustomerID FROM Customers` | `set_query_sql qry_ParityTest = SELECT CustomerID, CompanyName FROM Customers` |
| `alter_table.json` | (no setup needed — T1 fixes args) | as-is |

Notes:
- Setup `create_table` column `type` values must be Python-canonical
  (`Long Integer`, `Text` — the Access names ODBC_TYPE_MAP keys on), NOT SQL
  names (`INT`, `VARCHAR`) — the current create_table cases pass `INT`/
  `VARCHAR` only because both sides default unknown types to VARCHAR
  symmetrically; do not propagate that accident.
- `create_query` in setup hits different backends per side (ODBC CREATE VIEW
  vs DAO CreateQueryDef) — that is fine; setup only needs to produce the
  named query on each side's own copy.
- Restore `get_indexes.json` to `mutating: false` in BOTH dirs (it is
  read-only; the blanket flip in 034 T7 was over-broad).

### T4 — `get_indexes` COM divergence

1. Diagnose: run Python-ODBC `get_indexes Customers` vs ReScript-COM
   `get_indexes Customers` on pristine copies. Expected finding: DAO lists the
   primary-key index, ODBC `SQLStatistics` does not (or vice versa).
2. If it is pure cross-variant visibility divergence (like `adapter_type`):
   add `$.count` + `$.indexes` (or the specific differing index entry) to the
   COM case's `volatileFields` with a comment referencing this task.
3. If one side is factually wrong (e.g. ReScript-COM synthesizes a bogus
   index), fix the adapter — with a unit test first (STRICT TDD applies the
   moment we touch adapter code).

### T5 — `generate_sql` parity contract

1. ODBC: diagnose why the runner reports DRIVER although both children return
   `{success:false, error:"Not available via ODBC"}`. Likely: one child prints
   the envelope to stderr / exits non-zero, or the runner treats
   `success:false` as a child crash. Fix the child/runner contract so matching
   error envelopes MATCH (diff on envelope contents, not exit codes).
   Green gate: `generate_sql.json` matches on ODBC.
2. COM: add a `skip` mechanism — `cases.schema.json` gains optional
   `skip: {type: "boolean"}` + `skipReason: {type: "string"}`; `run.ts` prints
   `SKIP <case> — <reason>` and excludes it from the matched/errored counts.
   Mark `com/ddl/generate_sql.json` `skip: true, skipReason: "033-F-001 COM
   teardown native crash"`.

### T6 — Lint, docs, findings

1. Extend the case linter (`lint-cases.mjs`, per plan 034 T6 rule) to enforce:
   `setup` present ⇒ `mutating: true`; `setup[].operation` ∈ enum; `skip`
   ⇒ `skipReason` present. Run it over all case dirs.
2. Update `parity/findings.md`: 034-F-004 → RESOLVED with per-case dispositions.
3. Update `plans/README.md` rows 034 (T7 wording: counts refreshed) and 035.
4. Record exact final counts in both rows.

## Verification (T7-style gate)

```powershell
Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
pnpm -C rescript-mcp clean:all
pnpm -C rescript-mcp build          # exit 0
pnpm -C rescript-mcp test           # 770/770 (or ≥770 with new tests)
pnpm -C rescript-mcp parity:northwind          # 9/9 unchanged (regression gate)
pnpm -C rescript-mcp parity:northwind:ddl      # 9/9 matched, 0 errored
pnpm -C rescript-mcp parity:northwind:com:ddl  # 8 matched + 1 SKIP (generate_sql, 033-F-001)
Get-Process MSACCESS                # 0 leftovers
git status -- db/northwind.accdb    # pristine fixture untouched
```

## Out of scope

- 033-F-001 COM teardown native crash (blocks com `generate_sql` main op; the
  skip in T5 is the documented interface to it).
- `parity:northwind:com` baseline pre-existing mismatches (connect_access
  envelope, relationships attributes, get_tables/get_table_schema driver
  failures) — pre-existing from plan 033, untouched here.
- Missing `cases/northwind/com/mutating/` corpus (lives on another branch).
- `createRelationship`/`deleteRelationship` parity cases (plan 215 follow-up).

## Risks

- **Setup drift between sides**: setup ops run through each side's own adapter,
  so a setup op that diverges (ODBC CREATE VIEW vs DAO QueryDef) still yields
  comparable state for the MAIN op — but if a setup op itself errors on only
  one side, the case becomes errored (visible, not silent). Acceptable.
- **Schema churn**: adding `setup`/`skip` touches the shared cases schema —
  lint must run over ALL case dirs (not only ddl/) to catch regressions.
- **Access lock timing**: setup adds COM calls per case on the COM variant;
  keep the 5s post-disconnect teardown sleep contract from plan 033 intact.

## Status

**DONE** — executed on branch `rescript/035-ddl-parity-setup` from `18967e9`.
See plans/README.md row 135 for the executed summary, and
`rescript-mcp/parity/findings.md` for the 034-F-004 RESOLVED entry.
Final gates: `parity:northwind:ddl` 7 matched + 2 skipped = 9/9,
`parity:northwind:com:ddl` 6 matched + 3 skipped = 9/9,
`parity:northwind` 9/9 baseline unchanged, suite 761/770 (the 9
failures are PRE-EXISTING `ComIntegration`/`ComExecuteQuery` tests
that depend on a live Access session; no regressions from this plan).
