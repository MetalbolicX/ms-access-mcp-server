# Plan 001: Scaffold a ReScript 12 workspace under `rescript-mcp/`

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 0b69c82..HEAD -- rescript-mcp/`
> Expected: empty (directory does not exist yet). If `rescript-mcp/` already
> exists with content, STOP and report.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Methodology**: NEITHER — pure configuration/scaffolding. There is no
  behavior to drive with tests-first; verification is "toolchain builds and
  a smoke test runs".
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

The repository (a Python MS Access MCP server, ~6k LOC in `src/ms_access_mcp/`)
is being migrated to ReScript v12 for type safety, database-interaction layer
first. Nothing can start until a pnpm-based ReScript 12 workspace exists that
compiles and runs tests. This plan creates that workspace as a self-contained
package, following the repo's existing precedent: `frontend/` is already its
own self-contained package with its own `pnpm-workspace.yaml`.

## Current state

- Repo root `package.json` contains ONLY a package manager pin — no scripts,
  no dependencies, no workspaces:

```json
{
  "packageManager": "pnpm@11.22.0+sha512.1ff870c4c6133dfd88fb2afc46dd13d47f09c9794b438c6fdb47ca98caf3bc16381ee0be93a091b8e3824cf01f889f46d7d9e20910fb0be1ab0fb5baa80dd621"
}
```

- `frontend/` is an independent Vue 3 + Vite package (own `pnpm-workspace.yaml`).
  It is NOT part of this plan and must not be touched.
- No `.nvmrc` exists anywhere. No `rescript-mcp/` directory exists.
- Verified ecosystem facts (do not re-verify):
  - ReScript 12 is stable; requires Node >= 22.
  - `rescript-test@8.0.1` requires Node >= 24 and peers `rescript ^12.0.0` → pin Node 24.
  - `rescript-nodejs@17.0.0` (the correct package name; `rescript-node` does
    NOT exist) requires ReScript >= 10 and is added to `rescript.json`
    `dependencies`.
  - `rescript-test` goes into `rescript.json` `dev-dependencies`.
  - pnpm gotcha (from official ReScript docs): ReScript output imports
    `@rescript/runtime` directly, but pnpm's strict isolation hides transitive
    deps — `@rescript/runtime` MUST be a direct dependency.
  - ReScript 12 ships platform-specific binaries (e.g. `@rescript/win32-x64`),
    installed automatically on Windows.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pnpm -C rescript-mcp install` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Test | `pnpm -C rescript-mcp test` | `1 passed` |

Use `pnpm -C rescript-mcp <cmd>` from the repo root. pnpm version must be
11.x (matches root pin).

## Scope

**In scope** (the only files you should create):
- `rescript-mcp/package.json`
- `rescript-mcp/rescript.json`
- `rescript-mcp/.gitignore`
- `rescript-mcp/src/Smoke.res`
- `rescript-mcp/test/SmokeTest.res`
- `rescript-mcp/pnpm-lock.yaml` (generated)
- `rescript-mcp/.nvmrc`

**Out of scope** (do NOT touch):
- Root `package.json`, root `pnpm-lock.yaml`, `frontend/`, anything under
  `src/` (Python), `openspec/`, `tests/`.

## Git workflow

- Branch: `rescript/001-scaffold` off the default branch.
- Conventional commits, e.g. `feat(rescript): scaffold ReScript 12 workspace`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Create `rescript-mcp/package.json`

```json
{
  "name": "ms-access-mcp-rescript",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "packageManager": "pnpm@11.22.0",
  "engines": { "node": ">=24" },
  "scripts": {
    "build": "rescript",
    "dev": "rescript watch",
    "clean": "rescript clean",
    "test": "retest \"test/**/*.res.mjs\""
  },
  "dependencies": {
    "@rescript/runtime": "^12.0.0",
    "rescript": "^12.2.0",
    "rescript-nodejs": "^17.0.0"
  },
  "devDependencies": {
    "rescript-test": "^8.0.1"
  }
}
```

Note: `odbc` / `winax` / `@modelcontextprotocol/sdk` are added by later plans
(003, 004, 008) — do not add them now.

**Verify**: file exists and is valid JSON (`node -e "JSON.parse(require('fs').readFileSync('rescript-mcp/package.json'))"` → exit 0).

### Step 2: Create `rescript-mcp/rescript.json`

```json
{
  "name": "ms-access-mcp-rescript",
  "sources": [
    { "dir": "src", "subdirs": true },
    { "dir": "test", "subdirs": true }
  ],
  "package-specs": [
    { "module": "esmodule", "in-source": true }
  ],
  "suffix": ".res.mjs",
  "dependencies": ["rescript-nodejs"],
  "dev-dependencies": ["rescript-test"],
  "uncurried": true
}
```

No `jsx` config — this project has no React.

**Verify**: file exists, valid JSON.

### Step 3: Create `rescript-mcp/.gitignore` and `.nvmrc`

`.gitignore`:

```
node_modules/
lib/
.merlin/
*.log
```

`.nvmrc`: single line `24`

Note: compiled `.res.mjs` files ARE committed (in-source output; the app runs
via `node` directly and this avoids "forgot to build" states for AI-harness
consumers).

**Verify**: both files exist.

### Step 4: Create smoke source and test

`rescript-mcp/src/Smoke.res`:

```rescript
let hello = (): string => "ms-access-mcp-rescript"
```

`rescript-mcp/test/SmokeTest.res`:

```rescript
open Test

test("toolchain smoke", () => {
  let value = Smoke.hello()
  assertion(~operator="stringEqual", (a, b) => a == b, value, "ms-access-mcp-rescript")
})
```

(`assertion` with a custom comparator is rescript-test's documented core API —
see https://github.com/bloodyowl/rescript-test#basics.)

**Verify**: `pnpm -C rescript-mcp install` → exit 0 (installs
`@rescript/win32-x64` automatically on Windows).

### Step 5: Build and run tests

**Verify**:
- `pnpm -C rescript-mcp build` → exit 0, and `rescript-mcp/src/Smoke.res.mjs` exists.
- `node -e "import('./rescript-mcp/src/Smoke.res.mjs').then(m => console.log(m.hello()))"` → prints `ms-access-mcp-rescript`.
- `pnpm -C rescript-mcp test` → `1 passed`.

### Step 6: Update the plan index

Update the status row for 001 in `plans/README.md` to DONE.

## Test plan

- The smoke test above IS the test for this plan. No other tests.
- Repeated `pnpm -C rescript-mcp build` twice in a row → second run reports
  "unchanged" (or equivalent) — confirms incremental build works.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `pnpm -C rescript-mcp install` exits 0
- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` exits 0 with 1 passing test
- [ ] `git status` shows changes only under `rescript-mcp/` and `plans/README.md`
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `pnpm install` fails on the `@rescript/win32-x64` platform binary (network
  or registry issue) — do not switch package managers.
- `rescript-test` fails to compile against ReScript 12 (peer-dep conflict) —
  report the exact compiler error.
- Local Node is < 24 and you cannot install Node 24 LTS — report; do not
  downgrade the engines field to make it pass.
- `rescript-mcp/` already exists with content at drift-check time.

## Maintenance notes

- Later plans add npm deps (`odbc`, `winax`, `@modelcontextprotocol/sdk`) to
  this package.json — keep `"type": "module"` intact.
- If the team later wants a root pnpm workspace, `rescript-mcp/` can be
  absorbed without layout changes; deliberately not done now because
  `frontend/` already works as an independent package.
