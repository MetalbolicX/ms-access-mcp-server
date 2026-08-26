# Plan 018: Amend plan 007 for six parity-harness design holes (plan revision)

> **Executor instructions**: This plan edits ONE file —
> `plans/007-parity-harness.md`. No code, no tests, no other files. Make the
> six amendments below precisely, keeping plan 007's existing structure and
> voice. When done, update this plan's status row in `plans/README.md` (and
> plan 007's "Depends on" row per amendment 7).
>
> **Drift check (run first)**: read `plans/007-parity-harness.md` and confirm
> the line anchors in "Current state" roughly match (file is 189 lines;
> steps 1–6 at lines ~88–149). If plan 007 was already amended or restructured,
> STOP and report.

## Status

- **Priority**: P1 (correctness of plan 007's execution)
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plan 016 (its fixture inventory path is referenced by
  amendment 5); plan 015 (its composition factory is referenced by amendment
  3's driver design). Write AFTER both, or write now and verify references
  at 007-execution time.
- **Category**: docs
- **Methodology**: NEITHER. Decision/plan-revision work; nothing to drive
  out with tests, no new code contract.
- **Planned at**: commit `2bbff3a` + uncommitted plans-003–006 working tree,
  2026-08-25

## Why this matters

Plan 007 was written on 2026-08-18 against assumptions that investigation
has since falsified (`uv` availability, driver/fixture environment, the
ReScript runner's fixture fallback path) and it omits three design decisions
that would each cause wasted executor cycles mid-build (number
canonicalization, DB-state isolation, env pinning). Amending the plan NOW —
before any 007 execution — is cheap; discovering each hole mid-Step-4 is
not.

## Current state

Facts established by investigation on 2026-08-25 (all verified on this
machine):

1. **`uv` is NOT installed** — `.venv/Scripts/python.exe` works (pyodbc
   functional). Plan 007 says `uv run python` at its toolkit section
   (~line 63–65) and Step 2 (~line 105).
2. **Number canonicalization gap** — plan 007's Step 3 normalizer
   (~lines 109–118) specifies sorted keys, path normalization, float
   tolerance, timestamp normalization, volatile fields — but NOT
   int-valued-float→int canonicalization. Python emits `1` (int) where the
   ReScript `JSON.Number(float_of_int(...))` path can emit `1.0`; if the
   differ canonicalizes via re-serialization (e.g. Python `json.dumps`),
   `json.dumps(1.0)` → `"1.0"` ≠ `json.dumps(1)` → `"1"` — noise mismatch
   on nearly every count-bearing operation.
3. **DB-state isolation unaddressed** — mutating cases (`insert_data`,
   `update_data`, `delete_data`, `execute_raw_sql`, `export_data`) running
   both sides against the SAME `.accdb` mean the second side sees the first
   side's mutations. Steps 1/4 (~lines 90–130) have no isolation story.
4. **Env pinning unaddressed** — PathGuard on BOTH sides defaults
   `ACCESS_MCP_ALLOWED_DIRS` to the user home; the repo lives on
   `D:\code\...` → both sides would REJECT the fixture path. Additionally
   the ReScript ODBC runner's fixture fallback is
   `rescript-mcp/test/fixtures/test_db.accdb` (≠ the Python convention
   `tests/integration/fixtures/test_db.accdb`), so `ACCESS_TEST_DB` must
   always be set explicitly.
5. **Fixture contents unknown** — plan 007 Step 1 (~line 90) says "Author
   cases ... Cases reference a fixture `.accdb`" without a ground-truth
   inventory. Plan 016 now produces one at
   `rescript-mcp/parity/fixture-inventory.md`.
6. **COM variants are moot for v1** — all 17 v1 facade operations are
   ODBC-safe; plan 007 Step 4 (~lines 122–126) carries COM-skip machinery
   that adds complexity with no v1 cases to skip.

Also: plan 007's Status "Depends on" (~line 22) lists 003–006 only; the new
pre-work plans (015–018) are its real gate.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Verify plan 007 unamended | `Select-String -Path plans/007-parity-harness.md -Pattern "uv run"` | ≥2 matches (before), 0 matches (after) |
| Markdown sanity | (read the amended file end-to-end) | steps still ordered 1–6, no broken tables |

## Scope

**In scope**:
- `plans/007-parity-harness.md` (the six amendments + dependency update)
- `plans/README.md` (this plan's status row; plan 007's Depends-on cell —
  may already be updated by the README reconciliation)

**Out of scope**:
- Any code under `src/`, `rescript-mcp/src/`, `rescript-mcp/test/`,
  `rescript-mcp/parity/` (which does not exist yet — 007 creates it).
- Plans 015/016/017 content.
- Any OTHER plan file.

## Git workflow

- Branch: `rescript/018-parity-plan-amendments`.
- Conventional commit, e.g. `docs(plans): amend plan 007 parity harness for verified environment + isolation design`.

## Steps

### Amendment 1: Replace the Python driver invocation

In `plans/007-parity-harness.md`, replace every `uv run python` occurrence
(toolkit ~line 63–65; Step 2 ~line 105) with `.venv\Scripts\python.exe` and
note: "uv is not installed on the target machine; the repo venv is
authoritative."

**Verify**: `Select-String -Path plans/007-parity-harness.md -Pattern "uv run"` → 0 matches.

### Amendment 2: Number canonicalization rule (Step 3 normalizer)

Extend the Step 3 normalizer spec with: "Numbers: int-valued floats
canonicalize to integer form BEFORE comparison (`1.0` → `1`); float
tolerance 1e-9 applies only to non-int-valued floats." Add the rationale
inline (Python `json.dumps(1)` vs `json.dumps(1.0)`).

**Verify**: the Step 3 text contains "int-valued" (case-insensitive).

### Amendment 3: DB-state isolation (Steps 1 + 4)

Add to Step 1: cases carry `"mutating": true|false` (derived from the
5-op mutating registry: `insert_data, update_data, delete_data,
execute_raw_sql, export_data`). Add to Step 4: before EACH mutating case,
the runner copies the fixture `.accdb` to a per-side temp path (one copy for
the Python child, one for the ReScript child); both children receive their
own copy via `ACCESS_TEST_DB`; the differ compares OUTPUT ENVELOPES only,
never database state. Non-mutating cases may share the pristine fixture.

**Verify**: Step 4 text mentions per-side copies and envelope-only
comparison.

### Amendment 4: Env pinning (Step 3/4 — runner responsibility)

Add a step/sub-step: the parity runner sets, for BOTH child processes:
`ACCESS_TEST_DB` (absolute path to
`tests/integration/fixtures/test_db.accdb` — always explicit, because the
ReScript runner's fallback path differs), `ACCESS_MCP_ALLOWED_DIRS`
(fixture directory + temp export directory, semicolon-separated — the
user-home default would reject the `D:\code\...` fixture on both sides),
`ACCESS_MCP_READONLY=false`, `ACCESS_TEST_ASSUME_ACE=1`.

**Verify**: Step 3 or 4 text names all four env vars.

### Amendment 5: Fixture inventory input (Step 1)

Add to Step 1: "Case authoring MUST use `rescript-mcp/parity/fixture-
inventory.md` (produced by plan 016) as the ground truth for table names,
columns, and row counts; do not invent table names."

**Verify**: Step 1 references `fixture-inventory.md`.

### Amendment 6: COM variants moot for v1 (Step 4)

Simplify Step 4: all 17 v1 facade operations are ODBC — v1 cases carry
`"variant": "odbc"` only; replace the COM-skip machinery with a one-line
note ("COM-variant cases arrive with future facade phases; the skip logic
returns then"). Keep the off-Windows ODBC-driver skip.

**Verify**: Step 4 no longer carries COM-skip logic beyond the one-line note.

### Amendment 7: Dependencies

Update plan 007's Status "Depends on" to:
`plans/015-facade-composition-root-sdd.md, plans/016-odbc-stack-proof-inventory.md, plans/017-odbc-adapter-test-fixes-tdd.md, plans/018-parity-harness-plan-amendments.md, plans/023-finish-drift-reconcile-csvwriter.md, plans/024-repo-hygiene-branch-consolidation.md` (keep the 003–006 entries).

**Verify**: the Depends-on line lists 015–018, 023, 024.

### Amendment 8: Pre-parity hygiene gate (NEW — from session findings)

Add a new step BEFORE plan 007's Step 1: "Hygiene gate. Parity runs are
meaningless unless BOTH sides build from clean sources. Verify:
(a) `git status` on the working branch is clean (no uncommitted `src/` or
`test/` changes); (b) `cmd.exe /c "rescript clean"` + full build exits 0;
(c) the full suite passes from the fresh build (no cached `lib/bs`);
(d) `git log main` contains the consolidation merge from plan 024.
Any failure → STOP; parity on a dirty tree produces un-debuggable diffs."

**Verify**: plan 007 has a "Hygiene gate" step before its Step 1.

### Amendment 9: Environment quirks section (NEW — from session findings)

Add to plan 007's toolkit/environment section:
"(a) All `pnpm` invocations on this machine MUST use the `cmd.exe /c`
wrapper — the PowerShell pnpm wrapper hides successful output behind
`RemoteException` noise, which agents historically misread as failure.
(b) If `pnpm install` fails on `winax`/`node-gyp` (Python not installed),
use `pnpm install --ignore-scripts`; native binaries already exist.
(c) The Python child uses `.venv\Scripts\python.exe` (amendment 1), never
`uv`."

**Verify**: plan 007's environment section names all three quirks.

### Amendment 10: Number drift precedent (NEW — from session findings)

Add to plan 007's normalizer section (extending amendment 2): "Precedence
warning: during plan 022 the repo carried a signature drift where the
interface declared `dict<JSON.t>` while some callers wrapped values as
`JSON.Object(...)`. Parity cases MUST be authored against the CURRENT
post-plan-022 shapes (insertData takes `dict<JSON.t>` on both sides);
any case that constructs `JSON.Object` wrappers for `insertData` on the
ReScript side is testing dead code."

**Verify**: plan 007 references the insertData shape constraint.

## Test plan

- Document-only: the "tests" are the per-amendment Verify checks plus one
  end-to-end read of the amended file for structural integrity (steps still
  1–6, tables intact, no orphaned references).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] All TEN amendments present in `plans/007-parity-harness.md`
- [ ] `Select-String -Path plans/007-parity-harness.md -Pattern "uv run"` → 0
- [ ] `git status` shows changes only to `plans/007-parity-harness.md` (+
      the README row/cell for this plan)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Plan 007's structure has drifted from the line anchors (already amended
  or restructured) → report; re-derive anchor points before editing.
- An amendment conflicts with an EXECUTED portion of plan 007 (i.e. 007
  already started) → report; amendments must precede execution.

## Maintenance notes

- These amendments encode verified environment facts as of 2026-08-25
  (machine: Windows, ACE driver installed, uv absent, `.venv` functional).
  If the execution environment changes, re-verify amendments 1 and 4 first.
- Plan 007 executors should read amendments 2–4 as binding design decisions,
  not suggestions.
