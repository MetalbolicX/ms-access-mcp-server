# Plan 036 — Parity oracle COM fix + Facade.createQuery + ISchemaAdapter completion

## Goal

Prove COM parity for real by fixing the Python parity oracle's broken COM path,
close the latent `Facade.createQuery` runtime gap, un-skip the 3 skipped COM DDL
cases, and port the 6 missing `ISchemaAdapter` methods (linked tables + execute
SQL script) to ReScript with parity cases.

Today `parity:northwind:com:ddl` reports "6 matched" — but that compares an
**ODBC oracle against a COM subject**: `parity_driver.py:36` imports a module
that does not exist, the `ImportError` fallback silently degrades the oracle to
`OdbcAdapter`, and COM parity is therefore unproven. Additionally,
`runRescript.ts:240-241` dispatches `Facade.createQuery`, which `Facade.res`
does not export — both builds pass (TS trusts `facade.d.ts`) while any executed
`create_query` would throw `TypeError` at runtime. The passing runs never hit it
because both query cases skip before setup runs.

## Methodology

T1–T5 are harness/facade fixes gated by parity runs and the existing suite.
T6 is a STRICT TDD port of 6 methods. Behavior is pinned by the Python oracle
once it actually runs COM (`wincom.py`) — never by memory of what either side
"should" return.

- Branch: `rescript/036-parity-oracle-com-fix`
- Priority: P1 · Effort: M · Depends on: 035

## Environment quirks (binding for executors)

1. Same bindings as plan 035 §Environment quirks 1–3 (pnpm via `cmd.exe /c`,
   `.venv\Scripts\python.exe` never `uv`, kill `MSACCESS.EXE` before/after
   parity runs, pristine `db/northwind.accdb` never mutated, per-side fixture
   copies for mutating cases).
2. **CORRECTION to plan 035 quirk #4** — "Python oracle side is ALWAYS ODBC"
   was an accident, not a design. `parity_driver.py:36` imports
   `ms_access_mcp.adapters.win_com_adapter`, which does not exist (the real
   class is `WinComAdapter` in `adapters/wincom.py:45-54`), so the fallback at
   `:38-39` sets `_HAS_WINCOM=False` and `_connect` (`:112-119`) always
   constructs `OdbcAdapter`. After T1, the oracle honors
   `PARITY_VARIANT=com → WinComAdapter`. Any `com:ddl` case that matched while
   the oracle ran ODBC must be re-validated after T1.
3. The npm scripts do NOT need `PARITY_VARIANT` changes: `run.ts:195/:204`
   already injects it into both measured children from `caseObj.variant`
   (`run.ts:275`). Only the **prime spawn** (`run.ts:297-302`) misses it.

## Current state (verified at authoring time)

### Oracle defects

| # | Defect | Evidence |
|---|---|---|
| 1 | Broken import → silent ODBC degradation | `parity_driver.py:36` imports nonexistent `adapters.win_com_adapter`; `wincom.py` exists (`win32com.client` at `:187-190`); `_HAS_WINCOM=False` fallback `:38-39`; degradation at `:112-119` |
| 2 | Prime spawn env gap | `run.ts:297-302` forwards `ACCESS_TEST_DB` only; measured-child contract forwards `PARITY_VARIANT` (`run.ts:195`) |
| 3 | `generate_sql` variant-blind stub | `parity_driver.py:468-470` returns `{"success": false, "error": "Not available via ODBC"}` regardless of adapter, so COM `generate_sql` is unprovable even with a working COM oracle |

### Facade gap

- `Facade.res:849` — stale comment "No createQuery here — winax limitation
  (034-F-001)" (resolved in plan 034; adapter layer complete).
- Fully wired everywhere else: `Interfaces.resi:149`, `Interfaces.res:145`,
  `Instances.res:57`, `Composition.res:34` (ODBC instance),
  `OdbcAdapter.res:1453`, `ComDataAdapter.res:1267 → DaoAdapter:2584`,
  `runRescript.ts:240-241` dispatch, `parity/types/facade.d.ts` typing.
- Precedent to mirror: `setQuerySql` wrapper (`Facade.res:1107-1125`).

### Skipped cases (attribution correction)

- `cases/northwind/com/ddl/{delete_query,set_query_sql}.json` — skip reason
  says the Python oracle "cannot establish prerequisite state ... on either
  variant" / "query DDL is DAO-only". **Wrong attribution**: the oracle CAN do
  query DDL via DAO (`WinComAdapter.create_query`, `wincom.py:1555`; also
  `dao.py:365`) once defect #1 is fixed.
- `cases/northwind/com/ddl/generate_sql.json` — skipped for 033-F-001 COM
  teardown crash (ReScript exit 134, `MultiIsolatePlatform::DisposeIsolate`,
  post-serialization). A pragmatic driver-side workaround un-skips it.

### Missing ISchemaAdapter surface (Python → ReScript)

- `interfaces.py:70-77`: `get_linked_tables`, `create_linked_table`,
  `refresh_linked_table`, `recreate_linked_table`, `unlink_table`,
  `execute_sql_script` — no ReScript counterpart in `Interfaces.resi`.
- `execute_sql_script` Python impl: `persistence.py:370-387` tool →
  `wincom.py:1046-1119`: `_parse_script_lines` (strip SQL comments, split on
  semicolons, keep line numbers) then executes each statement via **ADO**
  (`self._dispatcher.ado_conn.Execute`, `:1112-1116` — the docstring claiming
  DAO is wrong). Error envelope:
  `{success, statements_executed, failing_statement, failing_line,
  access_error_code, access_error_message}` via `_extract_com_error`.
  ODBC path raises `NotImplementedError` (`odbc.py:483-485`,
  `com_only_mixin.py:440-442`).
- ReScript dispatch surface is `Facade.res` alone (`runRescript.mjs:27-35`
  imports only Facade + Composition) — every ported method needs:
  Interfaces entry → adapter impl → Composition wiring → Facade op →
  `runOperation` branch → schema enum → both driver dispatches → case files.

## Tasks

### T1 — Oracle COM path (3 fixes)

1. `parity_driver.py:36` — change import to
   `from ms_access_mcp.adapters.wincom import WinComAdapter`. Verify with a
   `python -c` probe that `_HAS_WINCOM` would be `True`.
2. `run.ts:297-302` — add `PARITY_VARIANT: variant` to the prime spawn's
   forwarded env (match the measured-child contract at `:195`).
3. `parity_driver.py:468-470` — remove the variant-blind stub; dispatch
   `adapter.generate_sql` when the adapter is `WinComAdapter`; keep the
   documented `"Not available via ODBC"` envelope for `OdbcAdapter`.
4. Immediately re-run `parity:northwind:com:ddl` and **triage every change**.
   The oracle flip (ODBC→COM) intentionally changes expected outputs;
   previously-green cases may mismatch. Each mismatch is either (a) cross-
   variant contract divergence → `volatileFields` with a comment, (b) ReScript
   COM adapter bug → STRICT TDD fix, or (c) Python adapter bug → record as a
   finding. This triage IS the COM parity proof — do not skip it.

### T2 — `Facade.createQuery`

1. Add the wrapper to `Facade.res` mirroring `setQuerySql`
   (`Facade.res:1107-1125`); replace the stale `:849` comment with a pointer
   to plan 034 (resolution) and plan 036 (wiring).
2. Unit test first (STRICT TDD): Facade-level test asserting `createQuery`
   routes to the composed instance and shapes the `ddlResult` envelope
   (follow the existing `setQuerySql` Facade test pattern).

### T3 — Un-skip COM query cases

- `cases/northwind/com/ddl/delete_query.json` and `set_query_sql.json`: remove
  `skip`/`skipReason` (setup `create_query` now works via DAO on both sides).
- ODBC variants keep their skip (ACE ODBC truly cannot `CREATE VIEW` with
  bracketed identifiers — that limitation is real and stays documented).

### T4 — 033-F-001 pragmatic workaround (un-skip COM `generate_sql`)

1. `runRescript.ts` (and built `runRescript.mjs`): in the parity child only,
   after the result is serialized to stdout (and the 5s COM teardown sleep),
   call `process.exit(0)`. Emit a stderr note
   (`"clean exit after serialization — 033-F-001 teardown crash avoided"`).
   The crash is post-serialization teardown, so the envelope is already
   delivered.
2. Un-skip `cases/northwind/com/ddl/generate_sql.json`.
3. Runner contract check: a child that produces NO stdout must still be
   classified DRIVER-error (so the `exit(0)` cannot mask a genuine crash that
   prevents serialization). Add/verify this behavior.
4. 033-F-001 stays OPEN in findings.md — the proper fix (winax proxy disposal
   ordering vs isolate teardown) remains desirable; this workaround only
   unblocks parity measurement.

### T5 — Verification + docs + memory hygiene

1. findings.md: correct the 034-F-004 entry's "oracle cannot establish
   prerequisite state" attribution (cause was defect #1, not a driver
   limitation on the oracle side); record 036-F-001 (broken oracle import),
   036-F-002 (prime-spawn env gap), and the 033-F-001 workaround decision.
2. plans/README.md: correct row 035's false "Facade.createQuery added" claim;
   row 036 → DONE with final counts.
3. Engram: correct observation 1199 (falsely records `Facade.createQuery` as
   landed in plan 035).

### T6 — Port 6 `ISchemaAdapter` methods (STRICT TDD)

1. **Unit tests first** for each method (patterns: `OdbcAdapterDdlTest.res`
   and the plan 034 COM DDL test patterns).
2. **Linked tables ×5** (`get/create/refresh/recreate/unlink_linked_table`):
   mirror the Python implementations (locate via the method names at
   `interfaces.py:70-76` in `dao.py`/wincom delegation — read the LIVE code,
   never trust memory). ReScript: DaoAdapter impls + `Interfaces.res`/
   `.resi` + `Instances.res` + `Composition.res` wiring + `Facade.res` ops +
   `runOperation` branches (`runRescript.ts`) + `parity_driver.py` dispatch +
   `cases.schema.json` enum additions. ODBC side gets com-only
   `NotImplementedError`-equivalent error envelopes matching the Python
   `ComOnlyAdapterMixin` contract (`com_only_mixin.py:440-442`).
3. **`execute_sql_script`**: ReScript COM impl with a parser mirroring
   `_parse_script_lines` (comment stripping, semicolon split, line-number
   tracking) and per-statement execution; envelope shape as Python's
   (including `statements_executed`, `failing_statement`, `failing_line`).
   If ADO-vs-DAO error codes diverge, normalize `access_error_code` via
   `volatileFields` — but keep `failing_line`/`failing_statement` exact.
4. **Parity cases**: success paths on the COM variant (+`mutating: true` —
   linked-table and script ops mutate state); ODBC error-parity cases
   asserting both sides return matching not-supported envelopes.
5. Case lint must pass over ALL dirs (schema enum churn).

## Verification (gate)

```powershell
Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
pnpm -C rescript-mcp clean:all
pnpm -C rescript-mcp build          # exit 0
pnpm -C rescript-mcp test           # >=761 passed; exactly the 9 pre-existing
                                    # COM-env failures; 0 new failures
pnpm -C rescript-mcp parity:northwind          # 9/9 matched (regression gate)
pnpm -C rescript-mcp parity:northwind:ddl      # 7 matched + 2 skipped (unchanged)
pnpm -C rescript-mcp parity:northwind:com:ddl  # 9/9 matched, 0 skipped, 0 errored
Get-Process MSACCESS                # 0 leftovers
git status -- db/northwind.accdb    # pristine fixture untouched
```

Plus T6: all new cases matched on their variants; new unit tests green.

## Out of scope

- **Plans 037a–037e** (IUiAdapter port, 89 unique methods): 037a DbProperties
  (2) → 037b VBA (19) → 037c Macros (8) → 037d Forms/Reports/Controls (50,
  largest; heavy `volatileFields`, UI side-effect case design) → 037e
  Versioning/persistence (12). Python backing for reference: `UiOperations`
  (~1558 ln), `VbaOperations` (~552), `VersioningIo` (~657), `dao.py`
  (~1286), tool modules `com.py`/`vba.py`/`macros.py`/`reports.py`/
  `persistence.py`/`db_properties.py`.
- 033-F-001 proper fix (winax dispose ordering vs isolate teardown).
- `parity:northwind:com` baseline pre-existing mismatches (connect_access
  envelope, relationships attributes, etc.).
- `createRelationship`/`deleteRelationship` parity cases.

## Risks

- **Oracle flip is behavior-changing by design**: T1.4 triage can surface real
  COM divergences that expand scope. Timebox the triage; anything that is a
  genuine adapter gap becomes a findings entry + follow-up, not silent
  `volatileFields` masking.
- **`process.exit(0)` could mask real crashes**: mitigated by the T4.3 runner
  contract (missing stdout ⇒ DRIVER error) — verify explicitly.
- **ADO vs DAO error-code divergence** on `execute_sql_script` parity.
- **COM prime-spawn instances**: forwarding `PARITY_VARIANT` to the prime
  spawn means COM cases may open a second Access instance — keep the 5s
  post-disconnect teardown sleep contract from plan 033 intact.
- **Fixture mutation**: all new T6 cases must be `mutating: true`; the
  implicit-mutating rule (`Array.isArray(setup)` ⇒ mutating) already guards
  mislabeled cases.

## Status

**TODO** — authored 2026-09-02 (post-035 research: scout passes
`ses_f9b864972ffeJp79eygE3YIUjP`, `ses_f9b81572dffecnNvgayvyyWZYf` + direct
verification of the broken import, missing `PARITY_VARIANT` forwarding, and
`Facade.res:849` gap). Not started.
