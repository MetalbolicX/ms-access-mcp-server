# Plan 023: Finish plan 022 — CsvWriter `~header` fix + commit + fresh-build verify

> **Executor instructions**: One bug fix + one commit + one verification pass.
> Strict TDD discipline: the build error IS the red state. Do NOT expand
> scope. Do NOT start plan 015 T2 work. When done, update `plans/README.md`
> rows 022 and 023.
>
> **Environment notes (MANDATORY — read first)**:
> - Use `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp <cmd> > rescript-mcp\parity\<log>.log 2>&1"` for ALL pnpm
>   calls. The PowerShell pnpm wrapper hides successful output behind
>   `RemoteException` noise. Read logs with the Read tool.
> - If `pnpm install` is needed and fails on `winax`/`node-gyp`/`Python`:
>   use `pnpm -C rescript-mcp install --ignore-scripts`. Native binaries are
>   already present from prior installs.
> - "Green suite" claims are ONLY valid after `cmd.exe /c "cd /d
>   D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"` + full rebuild. Cached `lib/bs` output is not evidence.
>
> **Drift check (run first)**: HEAD must be `f55e50a` on branch
> `rescript/022-insertdata-drift`. `git status --short` must show EXACTLY
> these 5 modified files and nothing else in `src/` or `test/`:
> `plans/README.md`, `rescript-mcp/src/Adapters/Instances.res`,
> `rescript-mcp/test/Fakes.res`,
> `rescript-mcp/test/InstancesPlaceholderTest.res`,
> `rescript-mcp/test/OdbcAdapterTest.res`. Verify `Instances.res:33` reads
> `insertData: (string, dict<JSON.t>)` and `OdbcAdapterTest.res` contains
> zero `JSON.Object(` wrappers inside `insertData` calls. On mismatch, STOP.

## Status

- **Priority**: P1 (unblocks plan 015 apply resume)
- **Effort**: XS
- **Risk**: LOW (one argument dropped; behavior unchanged — `serializeWithHeaders` always emits headers by design)
- **Depends on**: plan 021 (`f55e50a`), plan 022 v3/v4 working-tree state
- **Category**: bug
- **Methodology**: STRICT TDD (existing build failure is the red state)
- **Planned at**: commit `f55e50a` + uncommitted plan-022 working tree, 2026-08-25

## Why this matters

Plan 022 reverted the `insertData`/`exportData` drift (5 single-record
caller reverts + 3 batch-test rewrites + Fakes exportData + placeholder
test fix). The build progressed 74/92 → 88/92 but now blocks at
`rescript-mcp/src/Services/Facade.res:989`: it passes `~header=csvHeader`
to `Adapters.CsvWriter.serializeWithHeaders`, whose signature
(`CsvWriter.res:77-81`) accepts only `(headers, rows, ~delimiter)`. This
is a pre-existing authoring drift, masked until now because the build
never compiled `Facade.res` cleanly from scratch. It is the last known
blocker between the plan-022 working tree and a fresh-build green suite.

## Current state

Verified 2026-08-25 on branch `rescript/022-insertdata-drift`:

- `Facade.res:982-989`:
  ```rescript
  let csvDelimiter = delimiter->Belt.Option.getWithDefault(",")
  let csvHeader = header->Belt.Option.getWithDefault(true)
  let content = if format == "csv" {
    Adapters.CsvWriter.serializeWithHeaders(
      q.columns,
      rows,
      ~delimiter=csvDelimiter,
      ~header=csvHeader
    )
  ```
- `CsvWriter.res:77-81`:
  ```rescript
  let serializeWithHeaders = (
    headers: array<string>,
    rows: array<array<string>>,
    ~delimiter: string=",",
  ): string => {
  ```
  The function ALWAYS emits the header row (line 82: `let headerLine =
  serializeRow(headers, ~delimiter)`). The `~header` argument is invalid
  and was never a supported parameter.
- Build: exit 1, 88/92 modules, single hard error at `Facade.res:985:27-65`.

## Commands you will need

| Purpose | Command (cmd.exe wrapper) | Expected |
|---|---|---|
| Build | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-023.log 2>&1"` | exit 0, 92/92 |
| Fresh build | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"` then the build command above | exit 0 |
| Suite | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-023.log 2>&1"` | exit 0, 554/554/0 |

## Scope

**In scope**:
- `rescript-mcp/src/Services/Facade.res` — one edit at line 989
- The commit that captures plan 022 v3/v4's working-tree edits PLUS this fix
- `plans/README.md` rows 022 → DONE, 023 → DONE

**Out of scope**:
- Adding `~header` support to `CsvWriter.serializeWithHeaders` (separate
  design decision; the facade's `header` parameter and `csvHeader`
  variable become unused — see step 2)
- Any plan 015 T2-T6 work
- Any other file

## Git workflow

- Stay on branch `rescript/022-insertdata-drift`
- ONE commit capturing all 6 modified files:
  `fix(rescript): reconcile insertData/exportData drift; drop invalid ~header arg in Facade exportCsv`

## Steps

### Step 1: Reproduce the red state

```powershell
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-023-red.log 2>&1"
```

Read the log. Confirm exit 1 with the single `~header=csvHeader` error at
`Facade.res`. If a DIFFERENT error appears first, STOP and report — new
drift surfaced.

### Step 2: Fix

In `rescript-mcp/src/Services/Facade.res`:

1. Remove `~header=csvHeader` from the `serializeWithHeaders` call
   (line 989).
2. Prefix the now-unused local: rename `csvHeader` to `_csvHeader` at
   line 983 with a comment `// reserved: header toggle not yet supported
   by CsvWriter.serializeWithHeaders (plan 023)`.

Do NOT touch `CsvWriter.res`. Do NOT remove the `header` parameter from
the facade operation's public signature (it is part of the 17-op public
surface pinned by plan 006).

### Step 3: Verify — fresh build + full suite

```powershell
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-023-green.log 2>&1"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-023.log 2>&1"
```

Read both logs via the Read tool. Required outcomes:
- Build: exit 0, `Compiled 92 modules` (or higher; must NOT be 74 or 88).
- Suite: exit 0, `# Ran 554 tests` (553 + plan 021's
  `OdbcImportDynamicTest`), `# 554 passed`, `# 0 failed`.
- The batch-rewritten tests from plan 022 v3 pass: search the log for
  `insert batch (array)` and `insert batch mid-batch failure` — all PASS.

If the suite shows FEWER than 554 passing, STOP and report the delta.

### Step 4: Commit

```powershell
git add rescript-mcp/src/Services/Facade.res rescript-mcp/src/Adapters/Instances.res rescript-mcp/test/OdbcAdapterTest.res rescript-mcp/test/Fakes.res rescript-mcp/test/InstancesPlaceholderTest.res plans/README.md
git commit -m "fix(rescript): reconcile insertData/exportData drift; drop invalid ~header arg in Facade exportCsv" -m "Plan 022 (v3/v4) + plan 023 combined close-out: - Instances.res: insertData field reverted to dict<JSON.t>; exportData returns mutationResult; comments corrected to match the LIVE product - OdbcAdapterTest.res: 5 single-record JSON.Object wrappers reverted; 3 batch tests rewritten to iterate insertData per row (live product is single-record-only) - Fakes.res: exportData returns mutationResult - InstancesPlaceholderTest.res: exportData wrapper uses mutationResult shape - Facade.res:989: dropped invalid ~header arg (CsvWriter.serializeWithHeaders always emits headers); csvHeader local renamed to _csvHeader with a reserved-intent comment Fresh build: 92/92 modules. Suite: 554/554/0 (includes plan 021's OdbcImportDynamicTest)."
```

### Step 5: README

Update `plans/README.md`: row 022 → DONE (note "completed via plan 023"),
row 023 → DONE.

## Test plan

- The build error is the red test. Fresh-build success is the green proof.
- Suite must show 554/554/0 from a clean rebuild (not cached `lib/bs`).

## Done criteria

- [ ] Fresh build (after `rescript clean`) exits 0, 92/92 modules
- [ ] Suite exits 0, 554/554/0
- [ ] `git show --stat HEAD` lists exactly the 6 files in Step 4
- [ ] `Select-String -Path rescript-mcp/src/Services/Facade.res -Pattern "~header=csvHeader"` → 0 matches
- [ ] `plans/README.md` rows 022 and 023 are DONE

## STOP conditions

- Build fails with a NEW error after the `~header` fix (a 4th drift
  family) → STOP, commit nothing, report. The drift-cascade pattern is
  itself a finding; do not keep chasing without re-planning.
- Suite shows any failure → STOP, report the failing test names.
- The batch rewrites from plan 022 v3 fail → STOP, report; the rewrite
  logic needs re-review.

## Maintenance notes

- After this plan, `main` still sits at `6613e89`; the branch chain
  `017 → 015-T1 → 021 → 022/023` is consolidated by plan 024.
- Plan 015 apply resumes from this commit. Its T2 producer snippets MUST
  use the corrected `Instances.res` signatures (dict<JSON.t>,
  mutationResult) — see plan 015's "Design corrections" section.
- If the `header` toggle is ever wanted in CSV export, that is a new SDD
  change touching `CsvWriter.serializeWithHeaders` + facade op; the
  `_csvHeader` local is the marker.