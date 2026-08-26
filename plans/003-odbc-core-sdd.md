# Plan 003: ODBC core — bindings + OdbcAdapter (data & schema) via SDD

> **Executor instructions**: This plan is executed through the repo's SDD
> workflow (openspec), NOT as a direct coding task. You will create an SDD
> change, drive it through propose → spec → design → tasks → apply → verify
> → archive. The apply stage itself must follow strict TDD (it is the repo
> rule: `openspec/config.yaml` → `apply: Implement tasks following strict
> TDD`). If SDD tooling/skills (sdd-propose, sdd-spec, sdd-design, sdd-tasks,
> sdd-apply, sdd-verify, sdd-archive) is available in your environment, use
> them; otherwise follow the `openspec/` conventions manually. When done,
> update this plan's status row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 0b69c82..HEAD -- src/ms_access_mcp/adapters/odbc.py src/ms_access_mcp/adapters/interfaces.py src/ms_access_mcp/adapters/odbc_schema_reader.py openspec/specs/data-access openspec/specs/schema-explorer`
> Material changes → reconcile before starting; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: plans/001-scaffold-rescript-workspace.md, plans/002-foundation-types-tdd.md
- **Category**: migration
- **Methodology**: SDD. Unlike 002, this phase makes NEW design decisions
  with no Python-prescribed answer: the FFI binding surface over the async
  `odbc` npm package, the typed row representation, the async (Promise)
  execution model, and the ODBC-error → `Errors.t` mapping. These need a
  proposal, a behavioral spec, and a modular design BEFORE implementation.
  Implementation tasks inside SDD apply are strict TDD where testable
  (fake-binding unit tests); native-driver behavior is verified by
  Windows integration tests.
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

This is the first database-interaction capability of the migration and the
core of what an AI harness will use: opening `.accdb` files, running
parameterized queries, CRUD, raw SQL, and schema introspection (tables,
queries, columns, indexes, relationships). Python implements this in
`adapters/odbc.py` (~1200 LOC) behind `IDataAdapter` + `ISchemaAdapter`.
The ReScript port must produce the same inputs/outputs/behavior, while
introducing a typed FFI boundary to the async `odbc` npm package — the
design work that justifies SDD.

## Current state

- Python oracle: `src/ms_access_mcp/adapters/odbc.py` (OdbcAdapter),
  `src/ms_access_mcp/adapters/odbc_schema_reader.py` (schema SQL),
  `src/ms_access_mcp/adapters/interfaces.py` (protocol surface below).
- Existing openspec specs to build on: `openspec/specs/data-access`,
  `openspec/specs/schema-explorer` (Python behavior specs — the parity
  baseline).
- ReScript foundation ready (plans 001-002): `Errors.res`, `Config.res`,
  `PathGuard.res`, `Logging.res`, rescript-nodejs, rescript-test.
- npm package to bind: `odbc` v2.5.x (IBM/node-odbc). Facts: promise-based
  API (`odbc.connect(connectionString)` → `Promise<Connection>`),
  `connection.query(sql, params)`, `connection.close()`,
  `beginTransaction/commit/rollback`, `odbc.pool(connectionString)`, ships
  prebuilt NAPI binaries for win32-x64 (no build tools needed). Requires
  the `Microsoft Access Driver (*.mdb, *.accdb)` ODBC driver on the machine.

### Interface surface to port (interfaces.py)

`IDataAdapter`:
`execute_query(sql, params?) -> dict`, `insert_data(table_name, data: dict|list[dict]) -> dict`,
`update_data(table_name, set_dict, where_dict?) -> dict`, `delete_data(table_name, where_dict?) -> dict`,
`export_data(sql, file_path, format="csv", **options) -> dict`, `execute_raw_sql(sql) -> int`

`ISchemaAdapter` (data-reachable subset — the rest is COM, plan 004):
`get_tables()`, `get_system_tables()`, `get_object_metadata(object_name)`,
`get_relationships()`, `get_table_schema_plan()`, `generate_sql(output_path)`,
`get_database_statistics()`, `get_queries()`, `create_query(name, sql)`,
`set_query_sql(name, sql)`, `delete_query(name)`, `create_table(table_name, columns)`,
`delete_table(table_name)`, `get_linked_tables()`, `create_linked_table(...)`,
`refresh_linked_table(...)`, `recreate_linked_table(...)`, `unlink_table(name)`,
`execute_sql_script(script_path)`, `alter_table(table_name, operations)`,
`get_indexes(table_name)`, `create_index(...)`, `drop_index(...)`,
`create_relationship(...)`, `delete_relationship(...)`

(Signature details: read `src/ms_access_mcp/adapters/interfaces.py` during
SDD explore — it is the authoritative surface.)

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install (after adding `odbc` dep) | `pnpm -C rescript-mcp install` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit tests (CI-safe) | `pnpm -C rescript-mcp test` | all pass |
| Integration tests | `pnpm -C rescript-mcp test:integration` | pass on Windows with ACE driver; skip elsewhere |

## Suggested executor toolkit

- SDD skills if present: sdd-propose, sdd-spec, sdd-design, sdd-tasks,
  sdd-apply, sdd-verify, sdd-archive (in that order for this change).
- node-odbc docs: https://github.com/IBM/node-odbc (API + connection string
  format).
- Python schema SQL oracle: `src/ms_access_mcp/adapters/odbc_schema_reader.py`.

## Scope

**In scope**:
- `openspec/changes/rescript-odbc-core/**` (SDD artifacts)
- `rescript-mcp/src/Bindings/Odbc.res` (FFI layer ONLY)
- `rescript-mcp/src/Adapters/Interfaces.res` (adapter module types)
- `rescript-mcp/src/Adapters/OdbcAdapter.res`
- `rescript-mcp/src/Adapters/OdbcSchemaReader.res` (schema SQL port)
- `rescript-mcp/package.json` (+`odbc` dep, +`test:integration` script)
- `rescript-mcp/test/**` unit tests + `rescript-mcp/test/integration/**`
- Fixture: reuse Python convention — `ACCESS_TEST_DB` env var pointing to a
  `.accdb`, mirroring `tests/integration/conftest.py`.

**Out of scope**:
- COM-only operations (VBA, forms, macros, compact/repair) — plan 004.
- Connection pooling — plan 005.
- MCP tool layer — plan 008.
- Export strategies beyond `csv` if Python's default path is CSV — match
  Python behavior only.

## Git workflow

- Branch: `rescript/003-odbc-core`.
- SDD artifacts land first (propose/spec/design/tasks), then apply commits
  per TDD cycle. Conventional commits, e.g.
  `feat(rescript): bind node-odbc connect/query`.

## Steps (SDD stages with gates)

### Stage 1: Propose (gate: change proposal accepted)

Create SDD change `rescript-odbc-core`. Intent: typed ODBC data+schema
adapter for MS Access with Python-parity behavior. Scope from this plan.
During explore, read the Python files listed in "Current state" and record
the exact dict shapes `execute_query`/`insert_data`/etc. return (they are
the output contract).

### Stage 2: Spec (gate: behavioral spec with scenarios)

Spec MUST decide and pin, with scenarios:
1. **Row representation**: typed mapping of ODBC rows/columns into
   JSON-serializable values (null/bool/int/float/string/datetime-as-ISO —
   match whatever Python returns to tools).
2. **Async model**: all adapter functions return
   `Promise<result<'a, Errors.t>>`.
3. **Error mapping**: ODBC/native errors → `Errors.t` (DatabaseError with
   message parity where Python surfaces ODBC messages).
4. **Parameter binding**: `?`-style params, array form, matching pyodbc
   behavior incl. None → NULL.
5. **Schema SQL parity**: the schema queries ported from
   `odbc_schema_reader.py` (tables, columns, indexes, relationships,
   queries, linked tables).
6. **Connection string**: `Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=<path>`
   construction, including read-only flag handling.
7. Per-operation input/output scenarios for every IDataAdapter and
   ISchemaAdapter method above (happy + error paths).

### Stage 3: Design (gate: modular design doc)

Must specify: `Bindings/Odbc.res` as the ONLY module allowed to touch the
`odbc` npm package (`@module`/`@send`/`@new` externals); dependency
injection seam for unit tests (adapter takes a module-typed connection
factory so tests inject a fake); module types in `Adapters/Interfaces.res`
mirroring the Python protocol split; transaction semantics.

### Stage 4: Tasks (gate: small independently verifiable tasks)

Break design into tasks sized for red-green-refactor cycles. Each task
names its test file first.

### Stage 5: Apply (strict TDD where testable)

- Unit tests (fake connection module): every adapter method's logic —
  SQL building, param marshaling, result shaping, error mapping — tested
  against injected fakes. RED first, always.
- `Bindings/Odbc.res` externals are type-declarations; their runtime
  correctness is proven by integration tests, not unit fakes.
- Add `odbc` to `rescript-mcp/package.json` dependencies; `test:integration`
  script runs retest on `test/integration/**` files.

### Stage 6: Verify (gate: proof)

- All unit tests pass: `pnpm -C rescript-mcp test`.
- On a Windows machine with the ACE ODBC driver and `ACCESS_TEST_DB` set to
  a real `.accdb`: `pnpm -C rescript-mcp test:integration` passes —
  connect, CRUD round-trip, schema introspection.
- Off-Windows or without driver: integration tests SKIP cleanly (mirror
  Python's `com_integration` marker pattern), exit 0.

### Stage 7: Archive

Sync artifacts per openspec conventions, then update `plans/README.md`.

## Test plan

- Unit (fake binding): SQL builder cases (insert single + batch, update
  with/without where, delete), param marshaling (None → NULL, dates),
  row → JSON mapping (null/int/float/string/datetime), error mapping
  (native error → DatabaseError with message), each schema operation's
  result shaping.
- Integration (Windows + ACE driver + ACCESS_TEST_DB): connect/disconnect,
  execute_query round-trip, insert→query→update→delete cycle,
  get_tables/get_indexes/get_relationships against the fixture,
  execute_raw_sql rowcount.
- Structural pattern: `test/ConfigTest.res` (plan 002) for unit style;
  integration style mirrors Python `tests/integration/` fixtures.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] SDD change archived under `openspec/changes/` (or its archive location)
- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` exits 0 (unit, with fakes)
- [ ] `Bindings/Odbc.res` is the only file importing the `odbc` package
      (`grep -r "@module" rescript-mcp/src` shows `odbc` only there)
- [ ] On Windows+ACE: `test:integration` passes; elsewhere it skips with
      exit 0
- [ ] `plans/README.md` status row updated

## STOP conditions

- The `odbc` npm package fails to install its prebuilt binary on Windows —
  report the install log; do not switch libraries.
- Python's returned dict shapes for any method cannot be determined from
  `odbc.py` — report; do not invent output shapes.
- SDD spec cannot resolve a design question listed in Stage 2 without more
  information — report the specific question.
- Integration tests need > 2 fix attempts after unit tests are green.

## Maintenance notes

- The module-type seam in `Adapters/Interfaces.res` is what plan 004 (COM
  adapter) implements and plan 005 (pool) injects — keep it dependency-free.
- If node-odbc's pool proves better than a hand-rolled pool later, plan 005
  decides; do not couple the adapter to `odbc.pool` now.
