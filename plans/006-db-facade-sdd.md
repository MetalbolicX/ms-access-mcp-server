# Plan 006: Database facade for AI harness consumption (SDD)

> **Executor instructions**: Execute through the repo's SDD workflow
> (openspec): propose → spec → design → tasks → apply (strict TDD where
> unit-testable) → verify → archive. Use the SDD skills if available, else
> follow `openspec/` conventions manually. When done, update this plan's
> status row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 0b69c82..HEAD -- src/ms_access_mcp/mcp/ src/ms_access_mcp/services/ openspec/specs/data-access openspec/specs/schema-explorer`
> The Python `mcp/` tool modules are the output-shape oracle for the
> facade. Material changes → reconcile; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/003-odbc-core-sdd.md, plans/004-com-winax-sdd.md, plans/005-pool-services-tdd.md
- **Category**: migration
- **Methodology**: SDD. The facade is a PUBLIC API CONTRACT for AI-harness
  consumers — deciding its surface (which operations, what input/output
  JSON shapes, error surface, readonly enforcement) is design work that
  must be specified before implementation. The 23 Python `mcp/` tool
  modules define candidate operations, but selecting and shaping the
  facade subset for harness use is a decision, not a transcription.
  Implementation tasks inside apply are strict TDD with the plan-005 fakes.
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

The user's stated goal: a type-safe MS Access layer used primarily from an
AI harness. Before any MCP server exists (plan 008), the facade IS the
product — the module an agent imports and calls. It composes the
ConnectionPool, BackendSelector, and both adapters into one coherent,
JSON-in/JSON-out API with a single error taxonomy. Getting this surface
right (and stable) is what plan 008's MCP tools will transparently wrap.

## Current state

- Capabilities available (plans 003-005): `Adapters/OdbcAdapter.res`,
  `Adapters/WinComAdapter.res` (both implementing `Interfaces.res` module
  types), `Services/ConnectionPool.res`, `Services/BackendSelector.res`.
- Output-shape oracle: the 23 Python tool modules under
  `src/ms_access_mcp/mcp/` (crud.py, schema.py, raw_sql.py, vba.py,
  com.py, export.py, …) — each tool's returned dict shape is what the
  facade must reproduce for the operations it exposes.
- Config: `Config.res` already parses `ACCESS_MCP_READONLY`,
  `ACCESS_MCP_ALLOWED_DIRS` etc. (plan 002). PathGuard validates paths.
- No facade exists in ReScript yet.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit tests | `pnpm -C rescript-mcp test` | all pass |
| Integration (Windows) | `pnpm -C rescript-mcp test:integration` | pass/skip per gating |

## Suggested executor toolkit

- SDD skills (sdd-propose … sdd-archive).
- Python `mcp/` tool modules — read each tool's return-dict construction;
  those dicts are the JSON contract.

## Scope

**In scope**:
- `openspec/changes/rescript-db-facade/**` (SDD artifacts)
- `rescript-mcp/src/Services/Facade.res` (create)
- `rescript-mcp/test/FacadeTest.res` (create)
- Possibly `rescript-mcp/src/Services/JobTracker.res` IF the spec finds
  long-running operations (export/import/versioning) need async job
  tracking like Python's `services/` job tracker (see
  `tests/unit/test_job_tracker.py`) — spec must decide, default is NO.

**Out of scope**:
- MCP protocol/server (plan 008) — facade is protocol-agnostic.
- HTTP transport, auth middleware, telemetry, rate limiting, sessions.
- LLM tools (`ai_tools.py`) — remain out of scope for this wave.
- Any NEW operations not present in Python.

## Git workflow

- Branch: `rescript/006-db-facade`.
- Conventional commits, e.g. `feat(rescript): add database facade API`.

## Steps (SDD stages with gates)

### Stage 1: Propose

SDD change `rescript-db-facade`. Intent: single typed entry-point module
for all Access database operations, JSON-shaped results, designed for AI
harness consumption and later transparent MCP wrapping.

### Stage 2: Spec (gate: API contract pinned)

MUST decide, with scenarios per operation:
1. **Operation list**: the facade subset. Required minimum (derived from
   Python `mcp/connection.py`, `crud.py`, `schema.py`, `raw_sql.py`,
   `vba.py`): connect_access, disconnect, execute_query, insert_data,
   update_data, delete_data, execute_raw_sql, get_tables, get_table_schema
   (or get_object_metadata), get_relationships, get_queries, VBA
   (get/set/compile/execute), compact_repair, backup/restore. The spec may
   trim or add ONLY operations that exist in Python — cite the Python
   tool per operation.
2. **Input/output JSON shapes**: per operation, matching the Python tool's
   returned dicts (field names AND semantics — e.g. row-count fields,
   `success` booleans, message strings).
3. **Error surface**: every failure returns the plan-002 `Errors.t`
   serialized shape; no exceptions cross the facade boundary.
4. **Readonly enforcement**: `ACCESS_MCP_READONLY=true` rejects mutating
   operations — spec lists which operations are mutating.
5. **PathGuard integration**: every path argument validated before use
   (the 9 guarded arg names from plan 002: `file_path, output_path, output_dir,
   input_dir, backup_path, backup_dir, script_path, source, dest`).
6. **Connection model**: named connections via the pool; default
   connection name semantics if Python tools have one
   (`mcp/connection.py` is the oracle).
7. **Backend selection**: per-operation ODBC vs COM resolution via
   BackendSelector, with documented fallback behavior.

### Stage 3: Design

`Facade.res` as the only module consumers import. It injects pool +
selector + adapters (functor or record-of-modules) so tests use plan-005
fakes. No `Bindings/*` imports. Document why each Python tool shape was
kept or trimmed.

### Stage 4: Tasks

Sized for red-green cycles with fakes; each task names its test file first.

### Stage 5: Apply (strict TDD)

Unit tests per operation: happy path (fake adapter returns fixture rows →
assert exact JSON shape), readonly rejection, PathGuard rejection,
backend-fallback path, error propagation. RED first, always.

### Stage 6: Verify

- `pnpm -C rescript-mcp test` green.
- On Windows: integration spot-check through the REAL facade (connect to
  `ACCESS_TEST_DB`, query, schema) — proving facade → pool → adapter
  composition end-to-end.

### Stage 7: Archive

Sync artifacts; update `plans/README.md`.

## Test plan

- Unit (fakes): per-operation shape assertions, readonly, PathGuard,
  backend fallback, error propagation — every facade function covered.
- Integration: facade → real ODBC adapter round-trip on `ACCESS_TEST_DB`.
- Structural pattern: `test/ConnectionPoolTest.res` fakes +
  `test/ConfigTest.res` style.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] SDD change archived with the API contract in specs
- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` exits 0 — every facade operation has a
      shape-assertion test against fakes
- [ ] `Facade.res` imports no `Bindings/*` module
- [ ] Readonly + PathGuard enforcement tested
- [ ] `plans/README.md` status row updated

## STOP conditions

- A Python tool's output shape is ambiguous (dynamically keyed dicts that
  vary by backend) — report the specific tool; spec must pin a canonical
  shape rather than guess.
- The spec cannot decide the operation list without product input —
  report the open question with a recommended default.
- Tests need > 2 fix attempts after design is pinned.

## Maintenance notes

- This API becomes load-bearing the moment plan 008 wraps it — changes
  after archive should go through new SDD changes, not edits.
- The facade is also the parity surface for plan 007's harness; keep its
  JSON deterministic (stable key order where observable).
