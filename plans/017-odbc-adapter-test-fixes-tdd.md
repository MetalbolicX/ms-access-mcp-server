# Plan 017: Fix the two pre-existing OdbcAdapterTest failures (strict TDD)

> **Executor instructions**: This plan is **strict TDD**: the RED tests
> already exist and are failing — your job is triage, then the minimal fix,
> then green. Run every verification command before moving on. If anything
> in "STOP conditions" occurs, stop and report. When done, update this plan's
> status row in `plans/README.md`.
>
> **Drift check (run first)**: run `pnpm -C rescript-mcp test` and confirm
> the suite is 553 tests / 551 pass / 2 fail, and that the 2 failures are
> exactly the two tests named in "Current state" below. If the counts or
> names differ, the tree has drifted — STOP.

## Status

- **Priority**: P2 (hygiene; unblocks a fully green suite before parity work)
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (parallel-safe with 015 and 016 — touches only
  `rescript-mcp/test/OdbcAdapterTest.res` and possibly
  `rescript-mcp/src/Adapters/OdbcAdapter.res`, which 015 only appends
  `asInstance` to)
- **Category**: bug
- **Methodology**: STRICT TDD. The behavior is fully specified (Python oracle
  + the failing tests' own names); red state already exists; classic
  minimal-fix territory with no new design decisions.
- **Planned at**: commit `2bbff3a` + uncommitted plans-003–006 working tree,
  2026-08-25

## Why this matters

The suite has carried 2 failing tests since plan 003 (accepted then as
"pre-existing baseline"; re-accepted by plans 005/006). Both sit on
`connect`/`disconnect` — exactly the operations plan 007's parity harness
exercises hardest. Starting a differential harness on top of a red suite
means every parity session begins by re-litigating whether red means
"parity mismatch" or "that old known failure". Fixing them first gives
plan 007 a clean signal: any red is a real finding.

## Current state

- The two failing tests, BY NAME (indices shifted across sessions —
  currently ~461/462 of 553; the NAME is the stable identifier), both in
  `rescript-mcp/test/OdbcAdapterTest.res`:
  1. `connect missing file: returns Ok or Error without throwing`
  2. `disconnect: succeeds and is idempotent`
- Failure signature for BOTH (from `pnpm -C rescript-mcp test`):

```
FAIL - Correct assertion count
  operator: planned
  left:  1
  right: 0
```

- Precedent: the plan-005 correction round fixed four sibling tests
  (227/229/230/243 in the then-numbering, `ConnectionPoolTest.res`) with
  the IDENTICAL signature. Root cause there: a branch called
  `cb(~planned=1, ())` while firing ZERO `assertion(...)` calls — the fix
  was adding the missing `assertion(...)` before the `cb` in that branch.
- Python oracle for behavior:
  - `disconnect` idempotency: `src/ms_access_mcp/services/connection.py`
    (`disconnect` at ~lines 222–237 — idempotent for the default name) and
    `tests/unit/test_connection_service.py` (`test_disconnect_idempotent_*`).
  - `connect` on missing file: `src/ms_access_mcp/adapters/odbc.py`
    (connect error path — returns/raises per adapter contract; the ReScript
    test's own name pins the contract: "returns Ok or Error without
    throwing").
- Suite baseline: 553 / 551 / 2 (the 2 = these tests).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Full suite | `pnpm -C rescript-mcp test` | BEFORE: 553/551/2 → AFTER: 553/553/0 |
| Filtered re-run | `pnpm -C rescript-mcp test 2>&1 \| Select-String "connect missing file\|succeeds and is idempotent"` | both PASS |

## Scope

**In scope**:
- `rescript-mcp/test/OdbcAdapterTest.res` (the two tests — expected fix site)
- `rescript-mcp/src/Adapters/OdbcAdapter.res` (ONLY if triage classifies a
  test as a PRODUCT bug; minimal fix)

**Out of scope**:
- Any other test file; any other adapter; the facade; Fakes.
- Refactoring the test file's helpers beyond what the two fixes require.
- The 51 facade tests; the connection-pool tests (already fixed).

## Git workflow

- Branch: `rescript/017-odbc-test-fixes`.
- Conventional commits, e.g. `fix(rescript): repair planned-assertion mismatches in OdbcAdapterTest`
  (or `fix(rescript-odbc): ...` if the product adapter changes).

## Steps

### Step 1: Reproduce and capture

Run the full suite; capture the exact failure output for both tests (the
`operator: planned, left, right` block and surrounding lines).

**Verify**: both failures reproduced with the signature above; recorded
verbatim for the commit message / findings.

### Step 2: Triage EACH test (evidence, not assumption)

Read both test bodies in `OdbcAdapterTest.res`. For each, classify:

- **(a) Test-harness bug** — a branch calls `cb(~planned=N)` with ≠N
  `assertion(...)` calls (the established pattern), OR an async branch is
  unreachable (e.g. `Promise.catch` swallows a resolved path). Expected
  classification given the signature and precedent.
- **(b) Product bug** — the adapter's observable behavior diverges from the
  Python oracle (e.g. connect THROWS on a missing file instead of returning
  `Error(...)`; disconnect is not idempotent).

Write the classification + one-line evidence for each into the commit
message.

**Verify**: classification recorded; if (b), quote the exact divergence
(actual vs oracle-expected).

### Step 3: Fix

- (a) → fix the TEST: add the missing `assertion(...)` (match the
  plan-005 correction pattern: `assertion(~operator="equal", (a, b) => a == b,
  <observed>, <expected>)` before `cb(~planned=N, ())`), or repair the
  unreachable branch. Do NOT weaken what the test asserts.
- (b) → fix the PRODUCT minimally under red-green: the test is already red;
  change `OdbcAdapter.res` until it goes green; behavior must match the
  Python oracle, not merely the test.

**Verify**: filtered re-run — both tests PASS.

### Step 4: Full suite green

**Verify**: `pnpm -C rescript-mcp test` → 553 tests / 553 pass / 0 fail.
This is the repo's FIRST fully green suite since plan 003 — flag it in the
commit message.

## Test plan

- No NEW tests; the two existing red tests ARE the test plan.
- Guard: `git diff` touches ONLY the two in-scope files.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` → 553/553/0
- [ ] Both target tests pass by NAME (verified via filtered re-run)
- [ ] `git status` shows changes only in the two in-scope files
- [ ] Triage classification for each test recorded in the commit message
- [ ] `plans/README.md` status row updated

## STOP conditions

- A step's verification fails twice after a reasonable fix attempt.
- Triage shows a failure is a structural limitation of the rescript-test
  async pattern (the case cannot be expressed) → report with evidence;
  we may need to re-write the test shape entirely (decision required).
- The product fix requires touching files beyond the two in-scope files.
- The two failures turn out to have DIFFERENT root causes than the two
  classifications above (e.g. a flaky ordering issue) → report.

## Maintenance notes

- After this lands, ANY red in the suite is a real regression — plans 007+
  can treat red as blocking.
- The plan-005/006 archives recorded these 2 failures as accepted baseline;
  this plan supersedes those acceptance notes. Mention in the archive
  notes if plans get re-archived.
- If plan 015 (composition root) runs in parallel and touches
  `OdbcAdapter.res` (appending `asInstance` only), rebase is trivial.
