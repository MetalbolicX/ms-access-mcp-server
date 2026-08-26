# Plan 009: UI assessment — decision memo only (direction audit)

> **Executor instructions**: This plan produces a DECISION MEMO, not code.
> Do not write source, do not write tests. Follow the steps, produce
> `docs/rescript-ui-assessment.md`, update `plans/README.md`. If anything
> in "STOP conditions" occurs, stop and report.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/008-mcp-stdio-sdd.md (the memo evaluates UI options
  against a working ReScript MCP server)
- **Category**: direction
- **Methodology**: NEITHER. This is a direction audit / decision spike:
  there is no behavior to test-drive and no implementation to specify.
  The deliverable is a recommendation with evidence and effort estimates.
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

The Python server ships a server-rendered web UI (login page, dashboard,
ER diagram — `src/ms_access_mcp/templates/`, spec'd in
`openspec/specs/web-dashboard`), and the repo ALSO contains an
independent Vue 3 frontend (`frontend/` — Vite, Element Plus, Vue Flow,
own pnpm workspace) whose relationship to the SSR pages is unclear. The
user said UI is checked "at the end": before anyone migrates template
rendering to ReScript, this memo must establish whether the SSR UI is even
needed in the AI-harness-first deployment model, or whether the existing
Vue frontend or the MCP clients themselves already cover the use case.

## Current state

- Python SSR: `src/ms_access_mcp/templates/` (login, dashboard,
  er_diagram, unified explorer — see `tests/unit/test_ssr_*`), served by
  FastAPI/Jinja2 in HTTP mode only.
- `frontend/`: Vue 3.5 + Vite 8 + Element Plus + AlpineJS + Vue Flow,
  private package, Vitest. What it talks to (if anything) is part of what
  the memo must establish.
- ReScript side (post plan-008): stdio MCP server + facade; NO HTTP
  transport, no SSR.
- openspec specs: `openspec/specs/web-dashboard`, `openspec/specs/http-transport`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| n/a | read-only investigation | memo file exists |

## Scope

**In scope**:
- `docs/rescript-ui-assessment.md` (create — the ONLY file you write)

**Out of scope**:
- ALL code: no `rescript-mcp/src/**`, no `frontend/**`, no Python changes.

## Steps

### Step 1: Establish what the SSR UI actually does

Read `src/ms_access_mcp/templates/*` and the handlers serving them; read
`openspec/specs/web-dashboard`. List each page's function (login/session,
dashboard stats, ER diagram, explorer) and which MCP tool data it renders.

**Verify**: memo section 1 lists every page with its data source and
dependency on HTTP mode (auth, sessions).

### Step 2: Establish what `frontend/` is and whether it's alive

Read `frontend/package.json`, its router/views (top level only), and any
API client code. Determine: does it call the Python HTTP server, the MCP
server, or nothing? Check `git log --oneline -10 -- frontend/` for
activity.

**Verify**: memo section 2 answers: purpose, integration point, alive or
dormant, with evidence (file:line, commit dates).

### Step 3: Map UI options for the ReScript deployment

Evaluate exactly four options against "AI harness as primary consumer":
A. No UI at all (MCP clients are the interface) — effort, what's lost.
B. Keep Python HTTP+SSR UI running alongside the ReScript stdio server —
   operational cost of two runtimes, drift risk.
C. Port SSR pages to the ReScript side (HTTP transport becomes a
   prerequisite → reopens plan-008's out-of-scope list) — effort estimate
   in phases.
D. Point the existing Vue `frontend/` at a future ReScript HTTP transport
   — effort, and whether Vue Flow/Element Plus already cover dashboard
   and ER diagram needs.

**Verify**: memo section 3 has a table: option | effort (S/M/L) | risk |
what it buys | what it loses.

### Step 4: Recommend + define the trigger

Pick ONE recommended option with rationale tied to the AI-harness-first
goal. Define the concrete trigger that would reopen UI work (e.g. "user
requests dashboard access outside MCP clients").

**Verify**: memo section 4 states recommendation + trigger in <= 10 lines.

### Step 5: Deliver

Write `docs/rescript-ui-assessment.md` with sections 1-4; update
`plans/README.md` status row.

**Verify**: file exists, `git status` shows only the memo + plans/README.md.

## Test plan

- None — decision memo. Review quality bar: every claim has a file:line
  or commit-date evidence pointer.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `docs/rescript-ui-assessment.md` exists with sections 1-4
- [ ] Every factual claim carries evidence (path:line or commit ref)
- [ ] Exactly one recommended option, with a reopen trigger
- [ ] No code files modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

- `frontend/` turns out to be actively developed against a live backend —
  report; the option analysis needs the user in the loop before a
  recommendation.
- The SSR UI encodes behavior not covered by any openspec spec — report
  the gap rather than guessing.

## Maintenance notes

- If the recommendation is ever actioned, it starts as a NEW SDD change
  (likely reopening HTTP transport) — never as edits riding on this memo.
