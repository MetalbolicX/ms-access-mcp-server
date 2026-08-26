# Plan 022: Reconcile insertData drift — minimal (Option A)

> **Executor instructions**: One bug, three small edits. Strict TDD: RED
> first, GREEN next, VERIFY last. Touch only the files named below. After
> verification, update this plan's status row in `plans/README.md`.
>
> **Drift check (run first)**: HEAD must be `f55e50a` on branch
> `rescript/021-housekeeping`. Cut new branch `rescript/022-insertdata-drift`
> off `f55e50a` (the previous `rescript/022-interface-drift-reconcile`
> branch has no commits and can be deleted).

## Status

- **Priority**: P1 (unblocks plan 021's build + plan 015's apply)
- **Effort**: XS
- **Risk**: LOW (3 small edits; restores product behavior to match the
  interface and the live adapter)
- **Depends on**: plan 021 (`rescript/021-housekeeping` at `f55e50a`)
- **Category**: bug
- **Methodology**: STRICT TDD. RED test exists implicitly — the build
  currently fails at `OdbcAdapterTest.res:91` with `This has type:
  JSON.t But it's expected to have type: dict<JSON.t>`. The fix makes
  the build pass and the test compile.

## Why this matters

Plan 015's design #1055 §3 Q1 made an incorrect assumption: it claimed
the LIVE product `OdbcAdapter.insertData` accepts `JSON.t`, when in fact
it accepts `dict<JSON.t>`. Plan 015's Instances.res was written to match
the assumption (JSON.t), and plan 017's commit `b060457` made test
callers pass `JSON.Object(record)` to satisfy the WRONG shape. The
interface declaration is correct; the test callers and Instances.res are
wrong.

The build now fails because the test code's `JSON.Object(record)` calls
don't match `OdbcAdapter.insertData`'s actual `dict<JSON.t>` parameter.

Reconciling back to the interface (Option A — minimal) is:
- `Instances.res:34` — revert field from `JSON.t` to `dict<JSON.t>`
- `Instances.res:5-6` — remove the misleading comment about "JSON.t per live OdbcAdapter"
- `OdbcAdapterTest.res` — revert callers from `JSON.Object(record)` to `record`

## Current state (verified by plan 022 first attempt #1063)

- `rescript-mcp/src/Adapters/OdbcAdapter.res` `insertData` accepts `dict<JSON.t>` (LIVE PRODUCT — correct)
- `rescript-mcp/src/Adapters/Interfaces.res:116` declares `dict<JSON.t>` (CORRECT, matches live)
- `rescript-mcp/src/Adapters/Instances.res:34` declares `(string, JSON.t) => ...` (WRONG)
- `rescript-mcp/test/OdbcAdapterTest.res:91,127,161,...` callers pass `JSON.Object(record)` (WRONG)
- Build error at `OdbcAdapterTest.res:91:49-67`: `JSON.t` vs `dict<JSON.t>`
- 74/92 modules compile; 18 missing because the abort stops the build mid-compile

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-022.log 2>&1"` | exit 0, 92/92 modules |
| Unit suite | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-022.log 2>&1"` | exit 0, 553+/553/0 |

## Scope

**In scope**:
- `rescript-mcp/src/Adapters/Instances.res` — revert `insertData` field to `dict<JSON.t>`; remove misleading comment
- `rescript-mcp/test/OdbcAdapterTest.res` — revert all `JSON.Object(record)` callers in `insertData` calls back to `record` (or equivalent direct dict)

**Out of scope**:
- `rescript-mcp/src/Adapters/Interfaces.res` — already correct, do NOT touch
- `rescript-mcp/src/Adapters/OdbcAdapter.res` — already correct, do NOT touch
- Any other adapter implementation
- Plan 015 T2-T6 work (resume after this lands)
- Any `_importOdbc` or aggregator work (done in plan 021)

## Git workflow

- Branch: `rescript/022-insertdata-drift` (off `f55e50a`)
- 1 commit expected:
  - `fix(rescript): reconcile insertData drift — revert Instances + test callers to dict<JSON.t>`

## Steps

### Step 1: RED (verify current build failure)

```powershell
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-022-red.log 2>&1"
"build exit=$LASTEXITCODE"
```

Read the log via the Read tool. Confirm: exit 1, error at `OdbcAdapterTest.res:91` with `This has type: JSON.t But it's expected to have type: dict<JSON.t>`. If the build succeeds, STOP and report — the bug is already fixed.

### Step 2: Identify all `JSON.Object(record)` call sites in `OdbcAdapterTest.res`

```powershell
Select-String -Path rescript-mcp/test/OdbcAdapterTest.res -Pattern "OdbcAdapter.insertData.*JSON\.Object" | Select-Object LineNumber
```

List every line that needs reverting. Record them.

### Step 3: GREEN (three edits)

**Edit A**: `rescript-mcp/src/Adapters/Instances.res` — revert `insertData` field.

Find line 35:
```rescript
  insertData: (string, JSON.t) => Promise.t<result<mutationResult, Errors.t>>,
```

Change to:
```rescript
  insertData: (string, dict<JSON.t>) => Promise.t<result<mutationResult, Errors.t>>,
```

**Edit B**: `rescript-mcp/src/Adapters/Instances.res` — remove misleading comment.

Lines 5-6:
```rescript
// NOTE: insertData takes JSON.t per live OdbcAdapter (NOT dict<JSON.t>
// per the stale Interfaces declaration — interface drift tracked separately).
```

Replace with (or delete entirely):
```rescript
// insertData takes dict<JSON.t> per the live OdbcAdapter + Interfaces DATA_ADAPTER.
```

**Edit C**: `rescript-mcp/test/OdbcAdapterTest.res` — revert all `JSON.Object(record)` callers in `OdbcAdapter.insertData` calls.

For each line found in Step 2, change:
```rescript
adapter->OdbcAdapter.insertData("Products", JSON.Object(record))
```
back to:
```rescript
adapter->OdbcAdapter.insertData("Products", record)
```

Use Edit tool with `replaceAll: true` if the pattern is consistent. Verify the line count matches what Step 2 found.

### Step 4: VERIFY

```powershell
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && ..\node_modules\.bin\rescript.exe clean"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-022-green.log 2>&1"
"build exit=$LASTEXITCODE"
```

Read the green build log. Expected: exit 0, **92/92 modules compiled**.

Then run the suite:
```powershell
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-022.log 2>&1"
"test exit=$LASTEXITCODE"
```

Read the test log. Expected: exit 0 with **553+/553/0**.

Get the last 15 lines of test-022.log to see the summary.

### Step 5: Commit + update README

Commit the change:
```
fix(rescript): reconcile insertData drift — revert Instances + test callers to dict<JSON.t>

Plan 022 strict-TDD reconciliation (Option A — minimal). Plan 015 design
#1055 §3 Q1 made an incorrect assumption: it claimed the LIVE product
OdbcAdapter.insertData accepts JSON.t, when in fact it accepts
dict<JSON.t>. The interface declaration is correct. Plan 015 commit
8b190f1 wrote Instances.dataAdapterInstance.insertData with JSON.t;
plan 017 commit b060457 made test callers wrap as JSON.Object(record).

This commit reverts to the correct interface-aligned shape:

- rescript-mcp/src/Adapters/Instances.res:35 — insertData field now takes dict<JSON.t>
- rescript-mcp/src/Adapters/Instances.res:5-6 — comment corrected to reflect interface + live product
- rescript-mcp/test/OdbcAdapterTest.res — JSON.Object(record) wrappers in insertData calls reverted to record

Build now compiles 92/92 modules. Suite runs 553+/553/0 cleanly. No behavior
change; product behavior was always dict<JSON.t>.
```

Update `plans/README.md` row 022 TODO → DONE.

## Test plan

- The RED phase IS the test (the build error IS the failing test).
- Build success after the fix proves the interface and tests align.
- Suite pass proves no regression.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `cmd.exe /c "...pnpm -C rescript-mcp build..."` exits 0 with 92/92 modules
- [ ] `cmd.exe /c "...pnpm -C rescript-mcp test..."` exits 0 with 553+/553/0
- [ ] `git status` shows changes only to `Instances.res` and `OdbcAdapterTest.res`
- [ ] `git log` shows one commit on `rescript/022-insertdata-drift`
- [ ] `plans/README.md` row 022 DONE

## STOP conditions

- Build fails for a DIFFERENT reason after the fix → STOP and report.
- Suite has FEWER passes than 553 after the fix → STOP and report (regression).
- More than 5 distinct call sites need reverting → STOP and report; don't chase dozens of callers without approval.
- The reversion conflicts with the test assertions (e.g. tests actually depend on JSON.Object wrapping) → STOP and report; that means Option A is wrong and we need Option B.

## Maintenance notes

- After this lands, plan 015 apply resumes from `f55e50a` PLUS this branch (1 commit ahead).
- The `dict<JSON.t>` shape is the FROZEN contract for `insertData` from now on. Changing to `JSON.t` later is a new SDD change.
- Plan 015's design #1055 §3 Q1 should be amended in a follow-up to note the incorrect assumption that drove this plan.