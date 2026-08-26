# Plan 025: Fix the test suite (stale .mjs cleanup + count-clamping fix) — pre-024 gate

> **Executor instructions**: Two clean-up commits (cleanup then fix), a
> fresh-build green gate, README update. Do NOT touch plan-022's five
> already-modified files (Instances.res, Fakes.res,
> InstancesPlaceholderTest.res, OdbcAdapterTest.res, plans/README.md) —
> they are the verified plan-022/023 state. Do NOT commit untracked
> plans/tooling/parity/com-integration files — those are plan 024's
> territory. The five modified files from plan 022 are the baseline;
> your diff is added on top.
>
> **Environment notes (MANDATORY)**: `cmd.exe /c` wrappers for pnpm;
> `--ignore-scripts` only if install runs; green claims require
> `rescript clean` + full rebuild. The PowerShell pnpm wrapper hides
> successful output behind `RemoteException` noise.
>
> **Drift check (run first, BEFORE any edit)**:
> - `git status --short` shows ONLY the five plan-022-modified files in
>   `src/Adapters/` and `test/` plus the README, and untracked plan/
>   tooling files. **No additional dirty files in `src/` or `test/`.**
>   If there are, STOP — re-derive the plan before editing.
> - `git rev-parse --abbrev-ref HEAD` is `rescript/022-insertdata-drift`.
> - `git rev-parse HEAD` matches `1672743` (the plan-023 CsvWriter fix).
> - `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"` then full rebuild from the same state must reproduce 92/92 build + the same crash/FAIL set as plan 023 captured in `rescript-mcp/parity/test-023.log` (4 FAIL + crash at test 296). If fresh-build output is DIFFERENT, STOP — environment drifted, investigate.

## Status

- **Priority**: P1 (plan 024's clean-tree merge gate cannot pass without
  this; every pre-024 green-suite claim has been unverifiable since
  plan 015 T1)
- **Effort**: S
- **Risk**: MED (stale-artifact deletion is mechanical; the
  count-clamping fix may surface a behavior decision — see Step 4)
- **Depends on**: plan 023 (must already be committed at 1672743)
- **Category**: infrastructure
- **Methodology**: NEITHER (test-cleanup + bug investigation; no new
  product design)
- **Planned at**: commit `1672743`, 2026-08-25

## Why this matters

Plan 023 successfully removed the invalid `~header=csvHeader` arg from
`Facade.res:989` and committed it (`1672743`). The build is 92/92 green.
The suite, however, fails two ways:

1. **Stale `rescript-mcp/test/InstancesTest.res.mjs`** — a compiled
   artifact with NO matching source file. It contains tests that call
   `OdbcAdapter.asInstance(adapter)` as if it were a real function. The
   current `OdbcAdapter.res` does NOT export `asInstance`; the test
   runner crashes at test 296 with
   `TypeError: OdbcAdapter.asInstance is not a function`. The file is a
   leftover from a previous version of `InstancesPlaceholderTest.res`
   that compiled differently. `rescript clean` only clears `lib/bs/`,
   NOT test-compiled `.mjs` artifacts.

2. **4 count-clamping test failures** in `OdbcAdapterTest.res:271, 387`
   and two more, added in plan 017's commit `b060457` (e.g.
   `insert native count=-1: clamped to 0 affected`,
   `executeRawSql count=-1: clamped to 0`). The tests expect the real
   `OdbcAdapter` to clamp negative native `count` to 0 before returning
   it as `affected`. Whether the production code does this clamping
   today, and whether the test expectation matches the Python oracle,
   is unknown until Step 4 investigates.

Both issues are pre-existing from plan 015 T1 (commit `8b190f1`) and
plan 017 (commit `b060457`). Plan 023 did not introduce them, but its
acceptance gate assumed a clean baseline that was never real.

## Current state (verified 2026-08-25)

- Branch: `rescript/022-insertdata-drift` at `1672743` (plan-023 commit)
- Build: 92/92 green from clean `lib/bs`
- Suite (per `rescript-mcp/parity/test-023.log`):
  - 296 PASS before crash
  - 4 FAIL with "No message" (count-clamping)
  - Crash at test 296 in `InstancesTest.res.mjs:15`
- File existence verified:
  - `rescript-mcp/test/InstancesTest.res.mjs` EXISTS (orphan, no source)
  - `rescript-mcp/test/InstancesPlaceholderTest.res` EXISTS (current
    source, only 19 lines, just type-shape check)
  - `rescript-mcp/test/OdbcAdapterTest.res:271, 387` HAS count-clamp tests
  - `rescript-mcp/src/Adapters/OdbcAdapter.res` has NO `asInstance` export

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Clean | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"` | exit 0 |
| Build | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-025.log 2>&1"` | exit 0 |
| Suite | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-025.log 2>&1"` | 0 failures, exit 0 |
| Audit stale .mjs | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp\test && dir /b *.mjs"` | list every compiled .mjs |

## Scope

**In scope**:
- One commit deleting stale `test/*.mjs` artifacts with no matching
  `.res` source
- One commit (or fold into cleanup commit if trivial) fixing the 4
  count-clamping failures — either adapter code or test expectations,
  whichever is correct
- Fresh-build green gate from `lib/bs` empty
- README dependency note: replace "554/554/0" with the ACTUAL count
  observed at the green gate, if it differs from 554
- `plans/README.md` row 025 → DONE

**Out of scope**:
- Reverting or rebasing plan-022 / plan-023 commits
- Touching the five plan-022-modified files (`Instances.res`,
  `Fakes.res`, `InstancesPlaceholderTest.res`, `OdbcAdapterTest.res`,
  `plans/README.md`) EXCEPT to fix the 4 count-clamping tests
- Adding new tests or new product behavior
- Committing `lib/`, `node_modules/`, `.atl/`, plans/build-config/
  parity/com-integration files (plan 024)
- Merging to main

## Git workflow

- Branch: `rescript/025-fix-test-suite`, cut from
  `rescript/022-insertdata-drift` at `1672743`.
- Two commits:
  1. `chore(rescript): delete stale test/.mjs artifacts that crash the test runner`
  2. `fix(rescript): clamp negative native count to 0 in OdbcAdapter insert/executeRawSql`
     (subject line may change if investigation reveals the fix belongs
     in the test, not the adapter — see Step 4)
- Do NOT push or open a PR.

## Steps

### Step 1: Audit stale `test/*.mjs` files

Run the `dir /b *.mjs` command. For EACH `.mjs` file, check whether a
matching `.res` source file exists. Use this exact check:

```
For each test/*.mjs file:
  base = filename minus .res.mjs
  if exists test\<base>.res       -> KEEP (matched)
  else                              -> DELETE (orphan)
```

Expected orphans to delete (verified pre-plan):
- `rescript-mcp/test/InstancesTest.res.mjs` (no `InstancesTest.res`)
- Anything else surfaced by the audit

Do NOT delete `test/*.mjs` files that have matching `.res` sources —
those are the test runner's legitimate compiled outputs and will be
re-generated by the test build step.

### Step 2: First commit (cleanup)

```powershell
git add -u rescript-mcp/test/
git commit -m "chore(rescript): delete stale test/.mjs artifacts that crash the test runner"
```

Body: "Plan 025. `rescript-mcp/test/InstancesTest.res.mjs` (and any
other orphans surfaced by the audit) had no matching .res source. The
artifact referenced OdbcAdapter.asInstance(...) which is not exported
by the current source; the test runner crashed at test 296. `rescript
clean` only clears lib/bs/, not test-compiled artifacts. Plan-024 gate
requires a clean suite; this is the first step."

### Step 3: Re-run fresh-build to isolate count-clamping failures

After the cleanup commit:

```powershell
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-025a.log 2>&1"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-025a.log 2>&1"
```

Capture the ACTUAL remaining FAIL set. Expected: only the 4
count-clamping failures. If other failures appear that plan-023 did not
predict, STOP — investigate before continuing.

### Step 4: Investigate the count-clamping failures

Read in this order:

1. The 4 failing test cases in `rescript-mcp/test/OdbcAdapterTest.res`
   (search `Pattern "clamped" or "count=-1"`). Capture each test's
   exact expectation: what the test asserts the function returns when
   the fake ODBC driver reports `count: -1`.

2. The Python oracle (`src/ms_access_mcp/data/odbc.py` or similar —
   search for the `count` / `affected` mapping). Confirm whether the
   Python adapter clamps negative counts.

3. The ReScript `OdbcAdapter` paths exercised by these tests: locate
   the `insertData` and `executeRawSql` implementations in
   `rescript-mcp/src/Adapters/OdbcAdapter.res`. Trace where `count` (or
   `affected`) flows from the driver response to the result record.

**Decision rule**:
- If Python clamps AND current ReScript doesn't → fix the adapter
  (add `max(0, count)` or equivalent)
- If Python doesn't clamp AND tests assert clamping → fix the tests
  (delete or rewrite the 4 expectations to match Python behavior)
- If Python AND tests disagree on the clamping direction → STOP — flag
  for design decision, do not pick silently

Document the decision with file:line citations in the commit body.

### Step 5: Second commit (fix)

Based on Step 4's decision. Conventional commit subject reflects the
direction:

- If adapter fix: `fix(rescript): clamp negative native count to 0 in OdbcAdapter insert and executeRawSql paths`
- If test fix: `test(rescript): align count-clamping expectations with Python oracle (no clamping)`

### Step 6: Fresh-build green gate (REQUIRED)

```powershell
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-025b.log 2>&1"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-025b.log 2>&1"
```

Required: build exit 0 (92/92); suite exit 0 with **zero FAIL** and
**zero crash**. Capture the ACTUAL total pass count (e.g. 577/577 or
whatever it is — do NOT assume 554). If it differs from 554, plan 024's
gate text must be updated in Step 7.

### Step 7: README reconcile

- Update row 025 → DONE.
- Update the dependency-notes "Pre-007 gate" section: replace "554/554/0"
  with the actual green count from Step 6 (e.g. "577/577/0").
- Update plan 024's "Fresh-build green gate" text in
  `plans/024-repo-hygiene-branch-consolidation.md` if the count is
  not 554.
- No other README changes.

## Test plan

The Step 6 fresh-build green gate IS the test plan. Capture both logs.

## Done criteria

- [ ] Branch `rescript/025-fix-test-suite` exists with exactly 2 commits
      on top of `1672743`
- [ ] `git status --short` shows only untracked plan/tooling/parity
      files (not `src/` or `test/` dirty)
- [ ] `git log --oneline rescript/025-fix-test-suite ^rescript/022-insertdata-drift` shows 2 commits
- [ ] Fresh build 92/92 from empty `lib/bs`
- [ ] Fresh suite 0 FAIL, 0 crash; pass count captured
- [ ] README row 025 DONE and dependency note updated with actual count
- [ ] Plan 024 updated if count is not 554

## STOP conditions

- The drift-check baseline doesn't reproduce (test-025a.log shows
  different failures than test-023.log predicted) → STOP; investigate
  environment drift.
- Step 4's decision rule hits the "Python AND tests disagree"
  branch → STOP; surface to user for product decision, do not pick.
- Step 4 reveals the clamping tests were written for hypothetical
  future Python behavior (not current) → STOP; surface to user, the
  fix likely extends plan 022's drift cascade.
- A new unrelated test failure surfaces after the cleanup commit (e.g.
  flaky network test, Windows-only ODBC edge case) → STOP; do not fold
  unrelated fixes into plan 025.
- Fresh-build green gate fails in Step 6 → STOP; do NOT mark DONE;
  surface the actual log tail.

## Maintenance notes

- **The `rescript clean` does-not-clean-test/.mjs gap is a repo-wide
  gotcha.** Add to `plans/README.md` authoring standards (next amend):
  "Test-compiled `.mjs` artifacts under `rescript-mcp/test/` are NOT
  cleared by `rescript clean`. Use `cmd.exe /c "cd rescript-mcp/test
  && del /q *.mjs"` before a true fresh-build, OR commit the cleanup
  as part of any plan that touches test source shape."
- **The five plan-022-modified files remain on this branch as
  baseline.** Plan 024's branch consolidation will pick them up.
- **Don't promote the count-clamping decision into a behavior change.**
  If Python doesn't clamp, the right answer is to align the tests, not
  to "improve" the adapter beyond Python parity. Plan 007's whole
  point is 1:1 parity.
- **Count audit**: record the actual green count and the date in
  `rescript-mcp/parity/test-025b.log` so plan 024's merge gate can
  reference it.