# Plan 002: Port foundation types — Errors, Config, PathGuard, Logging (strict TDD)

> **Executor instructions**: Follow this plan step by step. This plan is
> **strict TDD**: for every behavior, write the failing test FIRST, run it to
> see it fail, then write the minimal implementation to make it pass, then
> refactor. Never write implementation before a failing test exists. Run every
> verification command and confirm the expected result before moving on. If
> anything in "STOP conditions" occurs, stop and report. When done, update
> this plan's status row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 0b69c82..HEAD -- src/ms_access_mcp/config.py src/ms_access_mcp/path_guard.py src/ms_access_mcp/logging.py openspec/specs/path-guard openspec/specs/api-key-auth`
> If any of these changed since this plan was written, re-read them and
> reconcile the "Current state" excerpts before proceeding; on a material
> mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/001-scaffold-rescript-workspace.md
- **Category**: migration
- **Methodology**: STRICT TDD. All behavior is already fully specified by the
  Python implementation (plus `openspec/specs/path-guard` and
  `openspec/specs/api-key-auth`) — no new design decisions are needed, so
  red-green-refactor against the ported test cases is the correct driver.
  This matches the repo's own SDD rule: "apply: Implement tasks following
  strict TDD" (`openspec/config.yaml`).
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

These four modules are the base layer every later phase (ODBC adapter, COM
adapter, pool, facade) imports: the error taxonomy, environment
configuration with API-key entropy validation, the path security guard, and
logging. They are pure logic with zero native dependencies, which makes them
the ideal first real port and the proof that the toolchain + TDD loop works.
Behavior must be 1:1 with Python — same env vars, same defaults, same
validation rules, same rejection semantics.

## Current state

Python sources being ported (behavior contracts):

- `src/ms_access_mcp/config.py` — env parsing + validation
- `src/ms_access_mcp/path_guard.py` — path security
- `src/ms_access_mcp/logging.py` — logging setup
- ReScript workspace exists at `rescript-mcp/` (plan 001) with
  `rescript-nodejs` and `rescript-test` working.

### Contract A — API key validation (config.py)

- `MIN_KEY_LENGTH = 32` (config.py:68)
- `MIN_ENTROPY = 3.0` bits/char (config.py:69)
- Entropy is **Shannon entropy over character frequencies**:
  `_shannon_entropy()` at config.py:40-53 — count frequency of each char,
  sum `-p * log2(p)` over all chars.
- Validation at config.py:88-94: key must be >= 32 chars AND entropy >= 3.0,
  otherwise `ValueError`.

### Contract B — env vars (config.py)

| Variable | Default | Type |
|----------|---------|------|
| `ACCESS_MCP_API_KEY` | — (required for construction) | string |
| `ACCESS_MCP_HOST` | `"127.0.0.1"` | string |
| `ACCESS_MCP_PORT` | `8000` | int |
| `ACCESS_MCP_ALLOWED_DIRS` | user home dir | semicolon-separated list |
| `ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS` | `false` | bool |
| `ACCESS_MCP_SESSION_SECRET` | `""` | string |
| `ACCESS_MCP_SESSION_COOKIE_NAME` | `"mcp_session"` | string |
| `ACCESS_MCP_SESSION_MAX_AGE` | `3600` | int |
| `ACCESS_MCP_READONLY` | `false` | bool |
| `ACCESS_MCP_RATE_LIMIT_MAX_ATTEMPTS` | `5` | int |
| `ACCESS_MCP_RATE_LIMIT_WINDOW_SECONDS` | `60` | int |

`ServerConfig` fields: `api_key, host, port, allowed_dirs,
preserve_trusted_locations, session_secret, session_cookie_name,
session_max_age, readonly, rate_limit_max_attempts,
rate_limit_window_seconds`.

### Contract C — PathGuard (path_guard.py)

- `__init__(allowed_dirs)` (lines 28-29): each dir is resolved
  (`Path(d).resolve()`) — on Windows this also normalizes case.
- `is_allowed(path)` (lines 31-43):
  - Rejects if path starts with `\\` or `//` (UNC) — lines 33-34.
  - `Path.resolve()`s the path (follows symlinks), then checks it is inside
    any resolved allowed dir via `relative_to` — lines 36-42.
- `validate(path)` (lines 45-52): raises `ValueError` whose message includes
  the path and the allowed list.
- `validate_tool_args` (lines 55-86): validates any tool argument named
  `file_path, output_path, output_dir, input_dir, backup_path, backup_dir,
  script_path, source, dest` (declared at lines 6-16).

### ReScript conventions to match

- Result-style error handling: define `Errors.res` with a variant error type
  and helpers; later phases map native errors into it. Follow
  `@rescript/core`-era idioms; ReScript 12 ships `Stdlib` built in.
- Use `rescript-nodejs` (`NodeJs.Process` for env, `NodeJs.Path` for
  resolve/join, `NodeJs.Os` for home dir). Its README:
  https://github.com/TheSpyder/rescript-nodejs — prefer binding to the
  promise version of APIs where available.
- Test style exemplar: `rescript-mcp/test/SmokeTest.res` from plan 001
  (`open Test`, `test(...)`, `assertion` with comparator).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Test (all) | `pnpm -C rescript-mcp test` | all pass |
| Test (one file) | `pnpm -C rescript-mcp exec retest test/ConfigTest.res.mjs` | all pass |

## Suggested executor toolkit

- rescript-test API reference: https://github.com/bloodyowl/rescript-test
  (test/testAsync/assertion/throws; assertion shorthands are written per-type
  by the caller).
- Python sources under `src/ms_access_mcp/` are the parity oracle — read the
  three files listed above before coding.

## Scope

**In scope**:
- `rescript-mcp/src/Errors.res` (create)
- `rescript-mcp/src/Config.res` (create)
- `rescript-mcp/src/PathGuard.res` (create)
- `rescript-mcp/src/Logging.res` (create)
- `rescript-mcp/test/ErrorsTest.res`, `ConfigTest.res`, `PathGuardTest.res`,
  `LoggingTest.res` (create)

**Out of scope** (do NOT touch):
- `rescript-mcp/src/Smoke.res`, any `Bindings/`, `Adapters/`, `Services/`
  (later plans), Python sources, `openspec/`.
- Session secret signing / rate limiting logic — only their CONFIG parsing
  is in scope; behavior lives in later phases.

## Git workflow

- Branch: `rescript/002-foundation-tdd`.
- One commit per red-green-refactor cycle or per module; conventional
  commits, e.g. `feat(rescript): port Config with entropy validation`.

## Steps

### Step 1: Errors.res (TDD)

Red: `test/ErrorsTest.res` — define the expected error variant shape and its
serialization to a JSON-friendly dict (fields the Python error dicts use:
`error`, `error_type`, `details`). Cases: at minimum `ConfigError(string)`,
`PathGuardError(string)`, `DatabaseError(string)`, `ValidationError(string)`.
Green: implement `Errors.res`. Refactor: add `toDict` / `toJson` helper.

**Verify**: `pnpm -C rescript-mcp build` → exit 0; tests pass with the
expected assertions.

### Step 2: Shannon entropy + key validation (TDD)

Red: `test/ConfigTest.res` cases, in this order:
1. entropy of `"a" * 32` (32 identical chars) computes to `0.0`
2. entropy of a 32-char string with 32 distinct chars is `log2(32) = 5.0`
3. entropy of `"aabb"` = `1.0` (p=0.5 for two chars)
4. key validation rejects 31-char key (length rule)
5. key validation rejects 32 chars of `"a"` (entropy rule, entropy = 0 < 3.0)
6. key validation accepts a mixed 32+ char key with entropy >= 3.0

Green: `Config.res` — `shannonEntropy: string -> float` (use
`Float.log2`; if unavailable in Stdlib, compute `Js.Math.log(x) /. Js.Math.log(2.0)`)
and `validateApiKey: string -> result<string, Errors.t>`.

**Verify**: tests 1-6 pass.

### Step 3: env parsing (TDD)

Red: cases for the Contract B table — every default when env is unset;
`"true"/"false"`/`"1"/"0"` bool parsing; int parsing for port/max-age/
rate-limit values (invalid int → ConfigError); semicolon split of
`ACCESS_MCP_ALLOWED_DIRS`; fallback to home dir. Env access must be
injectable: implement `Config.fromEnv: (~getEnv: string -> option<string>=?) => ...`
with the default reading `NodeJs.Process`, so tests pass a fake `getEnv`
closure — no process mutation needed.
Green: implement `fromEnv` returning `result<ServerConfig.t, Errors.t>`
(record matching Contract B field names).

**Verify**: all Contract B cases pass.

### Step 4: PathGuard (TDD)

Red: `test/PathGuardTest.res` cases:
1. `\\server\share\db.accdb` rejected (UNC, backslash form)
2. `//server/share/db.accdb` rejected (UNC, forward-slash form)
3. path inside allowed dir accepted
4. `allowed/../outside.accdb` resolves outside → rejected (traversal)
5. `allowed/sub/../db.accdb` resolves inside → accepted
6. on Windows, differing drive-letter case (`D:\Code` vs `d:\code`) still
   matches (resolve normalizes case)
7. `validate` on a rejected path returns `Error(PathGuardError(msg))` where
   msg contains BOTH the path and the allowed dirs
Green: `PathGuard.res` with `make: array<string> -> t`,
`isAllowed: t -> string -> bool`, `validate: t -> string -> result<string, Errors.t>`.
Use `NodeJs.Path.resolve`. For case-insensitive comparison on Windows,
compare lowercased resolved paths (Python relies on Windows `resolve()`
case normalization).
NOTE (deliberate deviation): `validate_tool_args` is a Python decorator
pattern; in ReScript later phases call `PathGuard.validate` explicitly, so
only port the arg-name constant list `guardedArgNames` and test it.

**Verify**: cases 1-7 pass.

### Step 5: Logging.res (TDD)

Red: cases — log level parsing (`ACCESS_MCP_LOG_LEVEL` env, default `info`,
accepts `debug|info|warn|error`), and that `log` calls format
`[LEVEL] message`. Keep it minimal: a leveled logger module, no external deps.
Green: implement. Refactor: none.

**Verify**: `pnpm -C rescript-mcp test` → all tests (Smoke + Errors +
Config + PathGuard + Logging) pass.

## Test plan

- New test files listed in Scope; every behavior in Contracts A-C is covered
  by at least one named case above (happy path + each rejection rule +
  defaults + parsing edge cases).
- Structural pattern: `test/SmokeTest.res` (plan 001).
- Verification: `pnpm -C rescript-mcp test` → all pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` exits 0, all tests pass
- [ ] All Contract B env vars parsed with exact defaults
- [ ] Key validation enforces length >= 32 AND Shannon entropy >= 3.0
- [ ] PathGuard rejects UNC paths, traversal escapes; validate error
      contains path + allowed dirs
- [ ] No files outside the in-scope list modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Drift check shows config.py/path_guard.py changed materially.
- A test needs > 2 fix attempts to go green — report the failure verbatim.
- You find Python behavior NOT captured by the contracts above (e.g. an env
  var or validation rule missing from this plan) — report instead of
  inventing behavior.
- `rescript-nodejs` lacks a binding you need for env/path (unlikely —
  Process/Path are core) — report; do not hand-roll raw `%raw` JS without
  approval.

## Maintenance notes

- Phases 003+ MUST map native errors (ODBC/COM) into `Errors.t` — keep the
  variant open to extension via new constructors, not `any`.
- `Config.fromEnv`'s injectable `getEnv` is the seam all later unit tests
  use; don't remove it.
- Float equality in entropy tests: compare with a small epsilon (1e-9), not
  `==`.
