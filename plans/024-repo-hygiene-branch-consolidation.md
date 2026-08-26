# Plan 024: Repo hygiene — commit plans/tooling/artifacts + consolidate branch chain to main

> **Executor instructions**: Mechanical housekeeping. No source-code
> behavior changes. Two commits (one content catch-up, one consolidation
> merge) plus a fresh-build green gate. When done, update
> `plans/README.md` row 024 and the dependency note.
>
> **Environment notes (MANDATORY)**: same as plan 023 — use `cmd.exe /c`
> wrappers for pnpm; `--ignore-scripts` if install fails on winax; green
> claims require `rescript clean` + full rebuild.
>
> **Drift check (run first)**: HEAD of `rescript/022-insertdata-drift`
> must contain plan 023's commit (the drift-reconcile close-out). Suite
> must be 554/554/0 on a fresh build. On mismatch, STOP.

## Status

- **Priority**: P1 (plan 007 cannot start on an uncommitted tree; every
  prior cycle's "green suite" claims are unverifiable until this lands)
- **Effort**: S
- **Risk**: MED (touching git history shape: branch consolidation)
- **Depends on**: plan 023
- **Category**: infrastructure
- **Methodology**: NEITHER (repo hygiene, no behavior change)
- **Planned at**: commit `f55e50a` + plan 023 commit, 2026-08-25

## Why this matters

Every SDD cycle in this repo (002–006, 015–022) left artifacts uncommitted:
all 20 plan files under `plans/`, the ReScript build configs
(`rescript.json`, `tsconfig.mjs.json`, `pnpm-workspace.yaml`, `.nvmrc`),
the parity artifacts (`rescript-mcp/parity/fixture-inventory.md`,
`findings.md`), the fixture-inventory script (`rescript-mcp/scripts/`),
and the COM integration runner (`rescript-mcp/test/com-integration/`).
Additionally, four stacked branches (`017 → 015-T1 → 021 → 022/023`)
carry 7 commits ahead of `main` (`6613e89`) that were never merged.
Consequences already observed this session: plans' "current state"
sections drifted from reality, green-suite claims ran against cached
`lib/bs` output, and executor agents could not tell which files were
committed truth versus session leftovers.

## Current state

Verified 2026-08-25:

- `main` = `6613e89`. Linear chain on top:
  `b060457` (017) → `8b190f1` (015 T1) → `9af4a78`, `de6e176`, `f55e50a`
  (021) → plan-023 commit (022+023 close-out).
- Branches: `rescript/017-odbc-test-fixes` (b060457),
  `rescript/015-instance-types-and-producers` (8b190f1),
  `rescript/021-housekeeping` (f55e50a),
  `rescript/022-insertdata-drift` (f55e50a + plan 023 commit).
- Untracked-but-critical: `plans/*.md` (20 files),
  `rescript-mcp/rescript.json`, `rescript-mcp/tsconfig.mjs.json`,
  `rescript-mcp/pnpm-workspace.yaml`, `rescript-mcp/.nvmrc`,
  `rescript-mcp/scripts/`, `rescript-mcp/parity/*.md` + probes,
  `rescript-mcp/test/com-integration/`, root `pnpm-workspace.yaml`,
  `openspec/changes/archive/2026-08-23-rescript-odbc-core/`.
- Untracked junk to DELETE (or gitignore): `fix_*.js`, `fix_tests*.js/py`,
  `test_backslash.js`, `test_crypto.mjs`, `test_sha256.mjs`,
  `rescript-mcp/test-cp1252.js`, `verify-report-slice-3h2.md`,
  `gentleman-guardian-angel/`, `openspec/verify-envelope*.yaml`.
- Modified `.atl/` cache files: never commit (agent-tool state).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Fresh build | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"` then `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-024.log 2>&1"` | exit 0 |
| Suite | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-024.log 2>&1"` | 554/554/0 |
| Merge check | `git merge --no-ff rescript/022-insertdata-drift` (on main) | clean, no conflicts |

## Scope

**In scope**:
- One catch-up commit on `rescript/022-insertdata-drift` for the
  untracked critical files listed in Step 1
- Deleting (not committing) the junk files listed in Step 2
- Fast-consolidation merge of the branch chain into `main` (Step 3)
- Branch cleanup (delete the 4 stacked branches after merge)
- `plans/README.md` row 024 → DONE + dependency note update
- `.gitignore` additions if any junk-pattern recurs (e.g. `fix_*.js`)

**Out of scope**:
- Rewriting history, rebasing, force-push
- Merging to remote (`git push` is the user's call)
- Any source-code change
- Committing `.atl/` caches or `lib/bs` build output
- Opening PRs (local consolidation only; the stacked-PR review flow can
  be replayed later from main if wanted — the commits themselves are the
  review units)

## Git workflow

- All commits on `rescript/022-insertdata-drift`, then merge to `main`.

## Steps

### Step 1: Catch-up commit (critical untracked files)

Stage exactly:

```
plans/*.md                       (all 22 files, including this one)
pnpm-workspace.yaml              (root)
rescript-mcp/rescript.json
rescript-mcp/tsconfig.mjs.json
rescript-mcp/pnpm-workspace.yaml
rescript-mcp/.nvmrc
rescript-mcp/scripts/
rescript-mcp/parity/fixture-inventory.md
rescript-mcp/parity/findings.md
rescript-mcp/parity/probe_node.mjs
rescript-mcp/parity/probe_py.py
rescript-mcp/parity/probe_shape.mjs
rescript-mcp/test/com-integration/
openspec/changes/archive/2026-08-23-rescript-odbc-core/
```

Do NOT stage: `fix_*`, `fix_tests*`, `test_backslash.js`,
`test_crypto.mjs`, `test_sha256.mjs`, `test-cp1252.js`,
`verify-report-slice-3h2.md`, `gentleman-guardian-angel/`,
`openspec/verify-envelope*.yaml`, `.atl/`, `lib/`, `node_modules/`,
`rescript-mcp/parity/*.log`.

Commit: `chore(repo): catch-up plans, build configs, parity artifacts, com-integration runner`

Body: "Session-level catch-up. Plans 001–024 were executed against an
uncommitted working tree; this commit brings plan files, ReScript build
configs, parity artifacts, and the COM integration runner into git so
future cycles can trust git state. Junk scratch files from prior agent
iterations are deleted in the same plan, not committed."

### Step 2: Delete junk

```powershell
Remove-Item fix_closing.js, fix_tests.js, fix_tests.py, fix_tests2.js, fix_tests3.js, fix_tests4.js, test_backslash.js, test_crypto.mjs, test_sha256.mjs, verify-report-slice-3h2.md -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force gentleman-guardian-angel -ErrorAction SilentlyContinue
Remove-Item rescript-mcp/test-cp1252.js, openspec/verify-envelope.yaml, openspec/verify-envelope-3f.yaml -ErrorAction SilentlyContinue
```

Add to `rescript-mcp/.gitignore` (or root `.gitignore`) if not present:
`parity/*.log`. No commit needed separately — fold into Step 1's commit
if trivial, else a tiny second commit `chore(repo): drop scratch files`.

### Step 3: Consolidate branches to main

```powershell
git checkout main
git merge --no-ff rescript/022-insertdata-drift -m "merge: plans 016/017/021/022/023 + plan 015 T1 (instance types)"
git branch -d rescript/017-odbc-test-fixes rescript/015-instance-types-and-producers rescript/021-housekeeping rescript/022-insertdata-drift
```

The chain is linear, so `--no-ff` produces one merge commit and zero
conflicts. If ANY conflict appears, STOP — the tree drifted.

### Step 4: Fresh-build green gate on main

On `main` after merge:

```powershell
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-024.log 2>&1"
cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-024.log 2>&1"
```

Required: build exit 0 (92/92); suite exit 0, 572/572/0. This is the
FIRST trustworthy green state in the repo's history — flag it in the
README dependency note.

### Step 5: README

Row 024 → DONE. Update the dependency-notes section: "Plans 015-T2..T6
resume from main after plan 024. All suite claims from plans 003-017
pre-date plan 024's fresh-build gate; treat only 572/572/0 on main as
authoritative."

## Test plan

The fresh-build green gate in Step 4 IS the test plan.

## Done criteria

- [ ] `git status` on main: clean except `.atl/` caches
- [ ] `git branch` shows only `main` (+ any pre-existing unrelated branches)
- [ ] Fresh build 92/92, suite 554/554/0, both from clean `lib/bs`
- [ ] `git log --oneline main -10` shows the merged chain
- [ ] `plans/README.md` row 024 DONE

## STOP conditions

- Merge conflicts in Step 3 → STOP (tree drifted; investigate).
- Fresh-build gate fails on main → STOP; do NOT mark DONE; the merge
  is already local-only so recovery is `git checkout rescript/022-insertdata-drift`
  + re-diagnose.
- Any junk file turns out to be referenced by a test → restore it,
  commit it, note it.

## Maintenance notes

- After this plan, ALL future plans must begin their drift check with
  `git status` expecting a CLEAN tree. A dirty tree at plan start is
  itself a STOP.
- The stacked-PR review trail for 021/022/023 can be replayed later by
  re-branching from main's history if reviewers want per-commit PRs;
  the merge preserves every commit.