# Plan 005: ConnectionPool & backend services (strict TDD)

> **Executor instructions**: This plan is **strict TDD**: write the failing
> test FIRST, run it red, implement minimally, refactor. Run every
> verification command before moving on. If anything in "STOP conditions"
> occurs, stop and report. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 0b69c82..HEAD -- src/ms_access_mcp/services/connection.py src/ms_access_mcp/services/backend_selector.py tests/unit/test_connection_pool.py tests/unit/test_connection_service.py tests/unit/test_connection_service_alias.py tests/unit/test_backend_selector.py`
> Material changes → reconcile; on mismatch, STOP.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/003-odbc-core-sdd.md, plans/004-com-winax-sdd.md
- **Category**: migration
- **Methodology**: STRICT TDD. Pool lifecycle and backend selection are
  deterministic, side-effect-injectable logic whose behavior is fully
  specified by the Python implementation and its unit tests (which use
  fakes the same way this plan will). No new architecture decisions —
  the adapter seams from 003/004 are already fixed. Classic
  red-green-refactor territory.
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

The Python server keeps named Access connections alive across tool calls
(`services/connection.py`, with alias support) and chooses the ODBC vs COM
backend per operation (`services/backend_selector.py`). Every MCP tool and
the AI-harness facade (plans 006, 008) sits on top of these services. Ported
with fakes first, this phase also proves the `Interfaces.res` seams from
003/004 compose correctly — without needing a real database in CI.

## Current state

- Python oracle: `src/ms_access_mcp/services/connection.py` (ConnectionPool),
  `src/ms_access_mcp/services/backend_selector.py` (factory choosing
  OdbcAdapter vs WinComAdapter — logic around line 142).
- Python unit tests naming the behaviors to port:
  `tests/unit/test_connection_pool.py`, `test_connection_service.py`,
  `test_connection_service_alias.py`, `test_backend_selector.py`,
  `test_backend_selector_dao.py`.
- ReScript adapter module types exist in
  `rescript-mcp/src/Adapters/Interfaces.res` (plans 003/004); unit-test
  fakes pattern established in plan 003.
- READ the two Python services and the five test files before coding —
  they are the behavioral oracle; this plan does not duplicate every
  assertion, it points at them.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Test | `pnpm -C rescript-mcp test` | all pass |

## Suggested executor toolkit

- rescript-test `createTestWith(~setup, ~teardown)` for pool-isolation
  between tests (see https://github.com/bloodyowl/rescript-test).
- Python oracles listed above.

## Scope

**In scope**:
- `rescript-mcp/src/Services/ConnectionPool.res` (create)
- `rescript-mcp/src/Services/BackendSelector.res` (create)
- `rescript-mcp/test/ConnectionPoolTest.res`, `BackendSelectorTest.res` (create)

**Out of scope**:
- Real-database behavior (integration tests live with plans 003/004).
- The facade (plan 006) and MCP wiring (plan 008).
- Rate limiting / sessions — those are HTTP-mode concerns, deferred.

## Git workflow

- Branch: `rescript/005-pool-services-tdd`.
- One commit per red-green cycle; conventional commits, e.g.
  `feat(rescript): port ConnectionPool lifecycle`.

## Steps

### Step 1: Fake adapters test fixture (TDD enabler)

Red: a test that constructs fake ODBC/COM adapter modules implementing the
plan-003 `Interfaces.res` module types, recording calls (connect/disconnect
invocations) in a mutable log. Green: `test/Fakes.res` (test-only helper
module; lives under `test/`, never imported by `src/`).

**Verify**: `pnpm -C rescript-mcp test` — fixture test passes.

### Step 2: ConnectionPool lifecycle (TDD)

Red (port cases from `test_connection_pool.py`):
1. first connect creates + stores a connection
2. connect twice with same name/alias → reuses, does not create a second
3. disconnect removes it; is_connected flips false
4. disconnect unknown name → error result (match Python's behavior —
   check the test file for the exact expectation)
5. get on nonexistent name → error
Green: implement `ConnectionPool.res` with `make`, `connect`,
`disconnect`, `get`, `isConnected`, all `Promise<result<_, Errors.t>>`
following the plan-003 async convention.
Refactor: alias map separate from connection map if Python models it so
(`test_connection_service_alias.py` is the oracle).

**Verify**: all pool cases pass.

### Step 3: Aliases (TDD)

Red: cases from `test_connection_service_alias.py` — register alias,
resolve by alias, alias collision behavior, disconnect by alias. Green:
extend pool. 

**Verify**: alias cases pass.

### Step 4: BackendSelector (TDD)

Red: cases from `test_backend_selector.py` (+ `_dao.py`): selection rules
for data-only vs COM-requiring operations, Windows/COM-availability
detection input (inject a `~comAvailable: bool` — do NOT detect the
platform at module load), fallback to ODBC when COM unavailable, readonly
mode constraints if Python enforces them there. Green: implement
`BackendSelector.res` as pure decision logic returning which adapter
type/instance to use.
Refactor: decision table explicit (match-style) rather than nested ifs.

**Verify**: `pnpm -C rescript-mcp test` — everything green.

## Test plan

- Every case enumerated in Steps 2-4, plus the fakes fixture from Step 1.
- Structural pattern: `test/ConfigTest.res`; oracles are the five Python
  test files — port their assertions, don't invent new behavior.
- Verification: `pnpm -C rescript-mcp test` → all pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` exits 0
- [ ] Pool: create/reuse/disconnect/alias behaviors match the five Python
      oracle test files
- [ ] BackendSelector: pure logic, injected `~comAvailable`, no
      platform detection at module load
- [ ] `src/Services/*` imports only `Errors`, `Config`, `Interfaces` —
      no `Bindings/*` imports (grep to confirm)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Python oracle tests encode behavior that contradicts this plan's steps —
  the ORACLE WINS; report the discrepancy and follow the Python tests.
- A pool behavior requires real-connection side effects to test — report;
  do not weaken the fake seam.
- Tests need > 2 fix attempts — report verbatim failures.

## Maintenance notes

- Plan 006 (facade) composes this pool; plan 008 (MCP) exposes it as
  tools. Keep the pool's public API stable once merged.
- If Python's pool has max-connection limits or eviction, port them here —
  check `connection.py` during Step 2; if absent, do not invent them.
