# Plan 007: Differential parity harness — ReScript vs Python (verification infra)

> **Executor instructions**: Follow this plan step by step. This plan is
> NOT test-driven and NOT spec-driven: it builds verification
> infrastructure that compares two existing implementations (the Python
> original and the ReScript port from plans 002-006). The harness is
> written AFTER the thing it checks exists, by definition. Run every
> verification command before moving on. If anything in "STOP conditions"
> occurs, stop and report. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 0b69c82..HEAD -- src/ms_access_mcp/ rescript-mcp/src/`
> If either side changed materially since this plan was written, re-check
> the facade operation list before proceeding.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/003-odbc-core-sdd.md, plans/004-com-winax-sdd.md, plans/005-pool-services-tdd.md, plans/006-db-facade-sdd.md, plans/015-facade-composition-root-sdd.md, plans/016-odbc-stack-proof-inventory.md, plans/017-odbc-adapter-test-fixes-tdd.md, plans/018-parity-harness-plan-amendments.md, plans/023-finish-drift-reconcile-csvwriter.md, plans/024-repo-hygiene-branch-consolidation.md
- **Category**: tests
- **Methodology**: NEITHER. This is a verification harness: its "tests"
  assert equivalence of two existing implementations, so red-green TDD
  does not apply (there is no new behavior to drive out), and SDD does not
  apply (the contract — "outputs match Python" — is already fully defined
  by the Python code itself). The harness needs careful engineering, not a
  spec phase. Its own correctness is proven by mutation testing (Step 5).
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

The migration's acceptance bar is 1:1 behavior: same inputs, same outputs,
same errors. Unit tests in each phase verify ported cases, but only a
differential harness proves equivalence continuously and mechanically —
run both implementations against the same `.accdb` fixtures with the same
arguments, normalize, diff. This becomes the regression gate for every
future change to either implementation, and the evidence base for
declaring the ReScript port production-ready.

## Current state

- Python original: `src/ms_access_mcp/` — runnable via the venv
  (`.venv/`), tools importable as modules; `.venv\Scripts\python.exe -m
  pytest` works (NOT `uv` — uv is not installed).
- ReScript port: `rescript-mcp/` with `Services/Facade.res` (plan 006)
  exposing JSON-shaped operations; compiled output runnable via `node`.
- Fixture convention: `ACCESS_TEST_DB` env var → `.accdb` file (Python
  side: `tests/integration/conftest.py`).
- No parity tooling exists on either side.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build ReScript | `pnpm -C rescript-mcp build` | exit 0 |
| Run parity suite | `pnpm -C rescript-mcp parity` | `N cases, 0 mismatches` |

## Suggested executor toolkit

- Node script (`.mjs`) driving the ReScript facade via dynamic `import()`
  of compiled modules.
- Python driven via `.venv\Scripts\python.exe <script>` with JSON on stdout
  (do NOT parse human-oriented CLI output; write a small driver script that
  calls the Python modules directly and prints JSON). `uv` is NOT installed
  on this machine; the repo venv is authoritative.

**Environment quirks (binding for all runners on this machine)**:
- All `pnpm` invocations MUST use `cmd.exe /c "cd /d ... && pnpm ..."` —
  the PowerShell pnpm wrapper hides successful output behind
  `RemoteException` noise, which agents historically misread as failure.
- If `pnpm install` fails on `winax`/`node-gyp` (Python not installed for
  native build), use `pnpm install --ignore-scripts`; native binaries
  already exist on this machine.
- The Python child uses `.venv\Scripts\python.exe`, never `uv`.

## Scope

**In scope**:
- `rescript-mcp/parity/` — harness: case definitions (JSON), runners
  (`runPython.mjs` invoking `.venv\Scripts\python.exe`, `runRescript.mjs`),
  normalizer, differ, reporter.
- `rescript-mcp/parity/cases/*.json` — one file per facade operation.
- `rescript-mcp/scripts/parity_driver.py` — Python-side driver that
  executes an operation against the real Python adapters and prints JSON.
- `rescript-mcp/package.json` — add `"parity": "node parity/run.mjs"` script.

**Out of scope**:
- Any behavior fixes in either implementation (a mismatch is a REPORT,
  fixed in the owning phase's code, not patched in the harness).
- MCP protocol testing (plan 008), HTTP/UI.

## Git workflow

- Branch: `rescript/007-parity-harness`.
- Conventional commits, e.g. `test(rescript): add differential parity harness`.

## Steps

### Step 0: Hygiene gate (REQUIRED before any parity run)

Parity runs are meaningless unless BOTH sides build from clean sources.
Verify before any case runs:
- (a) `git status` on the working branch is clean (no uncommitted `src/`
  or `test/` changes).
- (b) `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"` + full build exits 0.
- (c) The full ReScript suite passes from the fresh build (no cached
  `lib/bs` artifacts — see plan 024's authoring rule #7 for why this
  matters).
- (d) `git log main` contains the consolidation merge from plan 024
  (currently `bf8f9d0`) AND the plan-015 merge to main (currently
  `9724b2b`).

Any failure → STOP; parity on a dirty tree produces un-debuggable diffs.

### Step 1: Case format + case files

Define `parity/cases/<operation>.json`:
`{ "operation": "execute_query", "args": {...}, "variant": "odbc", "mutating": true|false }`.
The `mutating` field is derived from the 5-op mutating registry:
`insert_data, update_data, delete_data, execute_raw_sql, export_data` →
`true`; all other facade ops → `false`. Author cases for every facade
operation (plan 006's list), 2-3 per operation (happy + error + edge
where meaningful). Cases reference a fixture `.accdb` via `ACCESS_TEST_DB`.

**Case authoring MUST use `rescript-mcp/parity/fixture-inventory.md`**
(produced by plan 016) as the ground truth for table names, columns, and
row counts; do not invent table names. Plan 016's inventory confirms
3 user tables (`Customers` 3 rows, `Orders` 3 rows, `Products` 2 rows).

**Verify**: JSON schema of all case files validates (`node parity/run.mjs --lint-cases` → exit 0).

### Step 2: Python driver

`scripts/parity_driver.py`: reads case JSON (arg), executes the equivalent
Python call path (facade-equivalent service/adapter calls, NOT the MCP
layer), prints `{"ok": ..., "result": ...}` JSON to stdout. Run via
`.venv\Scripts\python.exe rescript-mcp/scripts/parity_driver.py <case.json>`.

**Verify**: for `get_tables` case, driver prints valid JSON with a table list.

### Step 3: ReScript driver + normalizer + differ

`parity/runRescript.mjs`: imports compiled `Facade` output, executes the
case, prints the same envelope. Normalizer (shared): sort object keys,
normalize Windows path separators and drive-letter case, float tolerance
(1e-9), normalize timestamps to ISO, drop volatile fields (recorded in a
`volatileFields` list in the case file — e.g. timings, temp paths).
**Numbers: int-valued floats canonicalize to integer form BEFORE comparison
(`1.0` → `1`); float tolerance 1e-9 applies only to non-int-valued floats.**
Rationale: Python `json.dumps(1)` vs `json.dumps(1.0)` — `1` ≠ `"1.0"` even
though they're numerically equal; canonicalizing at the JSON layer avoids
the noise on every count-bearing operation.

**Number drift precedent (binding)**: during plan 022 the repo carried a
signature drift where the ReScript interface declared `insertData: ...,
dict<JSON.t>` while some test callers wrapped values as `JSON.Object(...)`.
Parity cases MUST be authored against the CURRENT post-plan-022 shapes:
`insertData` takes `dict<JSON.t>` on both sides (Python oracle: `dict`,
ReScript adapter: `dict<JSON.t>`); `exportData` returns `mutationResult`
on both sides. Any case that constructs `JSON.Object(...)` wrappers for
`insertData` on the ReScript side is testing dead code — flag and skip.

Differ: deep-compare normalized JSON; on mismatch, print path-to-diff +
both values.

**Verify**: `node parity/run.mjs --case cases/get_tables.json` runs both
sides and reports `MATCH` or the precise diff.

### Step 4: Full suite + reporter

`parity/run.mjs` iterates all cases, runs the ReScript and Python
children against PER-SIDE FIXTURE COPIES (one copy for Python, one for
ReScript) when the case is `mutating: true`; for non-mutating cases
(`execute_query`, `get_tables`, etc.), both children may share the
pristine fixture. The runner compares OUTPUT ENVELOPES only, never
database state. All 17 v1 facade operations are ODBC — v1 cases carry
`"variant": "odbc"` only; COM-variant cases arrive with future facade
phases, the skip logic returns then. Keep the off-Windows ODBC-driver
skip.

The runner sets, for BOTH child processes, the following env vars:
- `ACCESS_TEST_DB` — absolute path to
  `tests/integration/fixtures/test_db.accdb` (always explicit; the
  ReScript runner's fallback path differs).
- `ACCESS_MCP_ALLOWED_DIRS` — fixture directory + temp export directory,
  semicolon-separated (the user-home default would reject the
  `D:\code\...` fixture on both sides).
- `ACCESS_MCP_READONLY=false`.
- `ACCESS_TEST_ASSUME_ACE=1`.

`parity/run.mjs` prints summary `N cases, M mismatches`, exits non-zero
on any mismatch. Add `"parity"` script to package.json.

**Verify**: `pnpm -C rescript-mcp parity` on Windows with `ACCESS_TEST_DB`
set → all cases MATCH (or the mismatches are reported precisely — see
Step 6 if any).

### Step 5: Prove the harness detects mismatches (mutation test)

Temporarily break one ReScript output (e.g. rename a response field in
`Facade.res`, run parity, observe the mismatch report, revert). The
harness MUST fail when behavior differs — a parity harness that always
says MATCH is worse than none.

**Verify**: mutation run reports the injected mismatch; revert lands
clean (`git diff` empty after revert).

### Step 6: Triage any real mismatches

For each real mismatch found in Step 4: record it in
`parity/findings.md` (operation, diff, suspected side). Fix in the owning
code (Python is the oracle — ReScript side is wrong by default), one
commit per fix, re-run parity.

**Verify**: `pnpm -C rescript-mcp parity` → 0 mismatches.

## Test plan

- The parity suite IS the test plan; the mutation check (Step 5) is its
  self-test.
- CI-safety: off-Windows the runner skips COM cases and ODBC cases
  without the driver — exit 0 with `skipped` summary.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `pnpm -C rescript-mcp parity` runs end-to-end (Windows: full suite;
      elsewhere: clean skips, exit 0)
- [ ] Every facade operation from plan 006 has at least one case file
- [ ] Mutation check (Step 5) performed and documented in the PR
      description
- [ ] 0 unresolved mismatches, or each recorded in `parity/findings.md`
      with owner + status
- [ ] `plans/README.md` status row updated

## STOP conditions

- A facade operation has NO deterministic Python output (e.g. embeds
  timestamps or random IDs with no normalization rule possible) — record
  it in `volatileFields` and note it in findings; if the whole operation
  is nondeterministic, report before excluding it.
- The Python driver cannot import/call a path equivalent to the facade
  operation (e.g. logic lives only inside MCP tool decorators) — report
  the specific operation.
- More than 3 real mismatches in Step 4 — report the list before fixing;
  systematic mismatches may indicate a phase-006 spec gap, not 1:1 bugs.

## Maintenance notes

- New facade operations (future SDD changes) MUST add parity cases —
  note this in plan 006's follow-ups and in `parity/README` (create as
  part of Step 4).
- The harness is Windows-primary; cross-platform CI runs only the
  skip-path. Do not delete the skip logic to "fix" CI.
