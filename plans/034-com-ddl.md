# Plan 034 — COM DDL (Stub Elimination)

## Goal

Implement the full DDL surface on `ComDataAdapter` — currently 10 stubs at
`rescript-mcp/src/Adapters/ComDataAdapter.res:1145-1220` — mirroring the
Python DAO oracle (`src/ms_access_mcp/adapters/dao.py`), and extend the
parity harness so DDL operations are differentially verified for both the
COM and ODBC variants.

Scope locked with user: **Core + both extras** — the 10 COM DDL stubs,
`getIndexes` (closes the 032 stub), and ODBC-variant DDL parity cases.

## Methodology

STRICT TDD — behavior is fully specified by the Python oracle (`dao.py`)
and the existing `SCHEMA_ADAPTER` interface (`Interfaces.res:135-148`).
Same pattern as plans 031-033: fake-backed unit tests + real-COM
probe-gated tests, red-green against rescript-test. Tests are written
first, always.

- Branch: `rescript/034-com-ddl`
- Priority: P1 · Effort: L · Depends on: 033b

## Environment quirks (binding for executors)

1. Clean-tree precondition: `git status` must show zero uncommitted
   `src/`/`test/` changes at plan start. Dirty tree is a STOP.
2. pnpm via `cmd.exe /c` wrapper with log files (PowerShell wrapper hides
   output). Python parity driver runs via `.venv\Scripts\python.exe`,
   never `uv`.
3. Fresh-build verification only: `rescript clean` + full rebuild + test
   is the ONLY trustworthy green gate. Cached `lib/bs` is not evidence.
   `rescript clean` does NOT clear `rescript-mcp/test/*.mjs` — delete
   stale compiled test artifacts when test source shape changes.
4. Kill stale `MSACCESS.EXE` processes before parity runs; verify 0
   leftovers after (`Get-Process MSACCESS`). Access teardown after
   `Quit()` takes ~2-3 s — wait before orphan checks.
5. Mutating DDL cases run against per-side fixture copies (Access holds
   an exclusive lock on `.accdb`); the pristine `db/northwind.accdb` is
   never mutated.
6. Parity scripts inject `ACCESS_TEST_ASSUME_ACE='1'` exactly (literal
   `1` — the runner's gate is strict).

## Current state (verified at authoring time)

### Python oracle — DAO adapter (`src/ms_access_mcp/adapters/dao.py`)

| Method | Line | Behavior |
|---|---|---|
| `create_table` | 856-905 | Jet DDL via `db.Execute(sql, DAO_DB_FAIL_ON_ERROR)`; col defs `[name] TYPE` + `NOT NULL` when autoincrement/primary_key/required; appends `PRIMARY KEY ([pk_col])` when an autoincrement or PK column exists |
| `delete_table` | 907-938 | Walks `db.Relations` in reverse, deletes any relation where `rel.Table` or `rel.ForeignTable` equals the target, then `DROP TABLE [name]` |
| `create_index` | 940-980 | `CREATE [UNIQUE] INDEX [name] ON [table] ([cols]) [WITH IGNORE NULL]` |
| `drop_index` | 982-1010 | `DROP INDEX [name] ON [table]` — the `ON [table]` clause is REQUIRED in Jet SQL |
| `alter_table` | 1012-1077 | Batch with per-op results `{action, success, error?}`; overall `success = all(per-op)`; unknown action → per-op `Unknown action: {action}`; per-op failures do NOT abort the batch |
| `_alter_table_add_column` | 1079-1096 | `ALTER TABLE [t] ADD COLUMN [name] TYPE [NOT] NULL` (explicit `NULL` when nullable) |
| `_alter_table_drop_column` | 1098-1104 | `ALTER TABLE [t] DROP COLUMN [name]` |
| `_alter_table_modify_column` | 1106-1123 | `ALTER TABLE [t] ALTER COLUMN [name] TYPE [NOT] NULL` |
| `_alter_table_rename_table` | 1125-1131 | DAO object model: `db.TableDefs(t).Name = new_name` |
| `_alter_table_rename_column` | 1133+ | DAO object model: `Field.Name` assignment |
| `_access_sql_type` | 536-549+ | `Text→VARCHAR(size)`, `Long Integer→INTEGER`, `Integer→SMALLINT`, `Byte→BYTE`, `Currency→MONEY`, `Single→SINGLE`, `Double→DOUBLE`, + remaining entries — executor reads the FULL map from the live file before implementing |
| `get_indexes` | 339 | DAO `TableDefs(t).Indexes` collection read |
| `create_query` / `set_query_sql` / `delete_query` | 365/381/396 | DAO QueryDefs (CreateQueryDef / `.SQL` assignment / Delete) |

Python ODBC adapter supports for parity (oracle side is always ODBC):
`create_query`/`set_query_sql`/`delete_query` (odbc.py:681/694/710),
`create_table` (762), `delete_table` (772), `alter_table` (973),
`get_indexes` (1044), `create_index` (1062), `drop_index` (1095),
`create_relationship` (1127), `delete_relationship` (1166).
`rename_*` actions are DAO-object-model-only — NOT available via ODBC.

### ReScript current state

- `Interfaces.res:135-148` — `SCHEMA_ADAPTER` already declares the full
  DDL surface. `Instances.res:45-68` — `schemaAdapterInstance` record
  has all DDL closures. No interface changes needed.
- `ComDataAdapter.res` stubs:
  - `generateSql` :1145 → `"COM generateSql not implemented"`
  - `createQuery` :1175, `setQuerySql` :1179, `deleteQuery` :1183 → stubs
  - `createTable` :1187, `deleteTable` :1191 → stubs
  - `alterTable` :1195 → **fake success** `Ok(Dict.make())` — worst
    offender; must be fixed before any caller relies on it
  - `getIndexes` :1199 → `Ok([])` stub (032 deferral)
  - `createIndex` :1205, `dropIndex` :1210, `createRelationship` :1214,
    `deleteRelationship` :1218 → stubs
- `ComDbProps.res:1398-1459` — `exportSchemaDdl` already implemented
  (writes `ddl_tables.sql` + `ddl_relationships.sql`).
- `OdbcAdapter.res:1207-1506` — ODBC DDL implemented (createTable,
  deleteTable, alterTable, createIndex, dropIndex, createRelationship,
  deleteRelationship, createQuery/deleteQuery via views);
  `generateSql` :960 returns "Not available via ODBC" (matches Python
  odbc.py:480). ODBC DDL has NEVER been parity-tested.
- `Composition.res:123-183` — `makeRealFactory` routes `useCom` to the
  COM adapter via `asInstance` (ComDataAdapter.res:1227+). Facade and
  BackendSelector routing proven in plan 033.

### Parity harness gaps

- `scripts/parity_driver.py` — 16 ops dispatched; NO DDL ops.
- `parity/runRescript.mjs` + `runRescript.ts` — same 16 cases; no DDL.
- `parity/types/facade.d.ts` — no DDL facade methods.
- `parity/cases.schema.json:26` — operation enum lacks DDL ops; the
  mutating-registry description (line 43, currently "5-op mutating
  registry") must gain the DDL ops.

## Tasks

### T1 — Type map + table DDL

1. RED: unit tests for `_accessSqlType` (every entry in the live Python
   map), `createTable` SQL construction (NOT NULL rules, PRIMARY KEY
   clause, bracket quoting), `deleteTable` reverse-relations cleanup —
   against fakes, asserting the exact SQL strings handed to Execute.
2. GREEN: implement `_accessSqlType` + `createTable` + `deleteTable` in
   `ComDataAdapter` using `ComSession.getCurrentDb()` (single source of
   truth — do NOT re-derive the Database handle), DAO `Execute` via the
   established `_mutateImpl` pattern (`DAO_DB_FAIL_ON_ERROR` semantics),
   and `Relations` collection iteration via `getCount`/`getItem` +
   reverse-index deletion.
3. Real-COM probe-gated tests: create → verify via getTables → drop on a
   fixture copy; drop a relation-referenced table.

### T2 — Index DDL + read-back

1. RED: `createIndex` SQL (UNIQUE, WITH IGNORE NULL), `dropIndex`
   (`ON [table]` required), `getIndexes` shape mirroring
   `Interfaces.indexInfo`.
2. GREEN: implement via `Execute` + DAO `Indexes` collection iteration
   (same pattern proven in 032 `TableDefs` work). Closes the 032 `Ok([])`
   stub.
3. Real-COM round-trip: create index → `getIndexes` sees it → drop →
   gone.

### T3 — alterTable batch

1. RED: per-op envelope `{success, operations: [{action, success, error?}]}`;
   unknown-action error string; overall success = all ops succeed;
   per-op failure does not abort the batch.
2. GREEN: add/drop/modify column via Jet DDL; `rename_table` via
   `TableDef.Name` and `rename_column` via `Field.Name` using
   `WINAX_BINDING.set` (primitive completed in plan 028).
3. Real-COM probe-gated test on a fixture copy covering all five actions
   plus one unknown action.

### T4 — Query DDL

1. RED: `createQuery`/`setQuerySql`/`deleteQuery` envelopes.
2. GREEN: DAO QueryDefs via `invokeAsObject` for `CreateQueryDef`,
   `.SQL` set, `QueryDefs.Delete`. Verify against dao.py:365-396
   semantics (read the live oracle bodies first).

### T5 — generateSql

STOP-gated: read Python oracle dao.py:356 (`generate_schema_sql`) and
the MCP tool path (`mcp/schema.py:111` generate_sql) FIRST. If the
oracle's envelope diverges from `ComDbProps.exportSchemaDdl`'s shape,
STOP and record the divergence in `parity/findings.md` before
implementing. Otherwise implement `generateSql` delegating to the
existing export path. ODBC variant stays "Not available via ODBC"
(parity expects the divergence between variants here, like
`adapter_type`).

### T6 — Parity harness extension

1. Add DDL ops to all four touchpoints: `scripts/parity_driver.py`
   (`_shape_*`/`_*_op` for create_table, delete_table, create_index,
   drop_index, alter_table, get_indexes, create_query, set_query_sql,
   delete_query), `runRescript.mjs` + `runRescript.ts` (same ops routed
   through the Facade), `types/facade.d.ts`, `cases.schema.json`
   (operation enum + mutating registry).
2. COM variant: new `parity/cases/northwind/com/ddl/` directory
   (mutating cases — separate from the `--require-read-only` guarded
   `com/`) + `parity:northwind:com:ddl` package script injecting
   `ACCESS_TEST_DB` and `ACCESS_TEST_ASSUME_ACE='1'`, without
   `--require-read-only`.
3. ODBC variant: new `parity/cases/northwind/ddl/` directory +
   `parity:northwind:ddl` script (same env injection, ODBC driver).
   This closes the never-parity-tested ReScript ODBC DDL gap.
4. Case-file authoring rules:
   - NO `rename_*` actions (unsupported by the Python ODBC oracle).
   - Before authoring alter_table cases, read odbc.py:973-1060 and
     verify which actions the ODBC oracle supports; cases use only the
     intersection of ODBC-oracle and COM-implementation support.
   - Expected envelopes come from the Python oracle, verified by
     running the driver, never hand-copied from ReScript output.
   - FFI args (columns arrays, nested dicts) cross as `{TAG,_0}`
     envelopes — use the established `jsToJsonT`/`jsToJsonDict` helpers
     and remember the 033b `_formatValue`/`_unwrapTag` lesson.
   - `lint-cases.mjs` must pass on the new case files.

### T7 — Verification + docs

1. Fresh-build gate: `rescript clean` + full rebuild + full test run.
2. All parity scripts green with exact counts recorded:
   `parity:northwind`, `parity:northwind:com`,
   `parity:northwind:com:mutating`, `parity:northwind:com:ddl`,
   `parity:northwind:ddl`.
3. Zero `MSACCESS.EXE` leftovers after the parity suite.
4. Update `plans/README.md` 034 row and `parity/findings.md` with exact
   results; record any findings as `034-F-xxx` with reproduction and
   owner.

## Explicitly out of scope

- MCP tool-surface expansion (the 12-tool decision from plan 008/009
  stands; reopening it is a new SDD change).
- UI operations (`rename_form`, `rename_report`, `rename_macro`,
  `rename_module`) — no ReScript interface exists.
- VBA operations.
- `getQueries` DAO QueryDefs iteration (separate 032 follow-up;
  `createQuery`/`deleteQuery` round-trips may exercise QueryDefs but the
  read-side stub stays).
- `create_relationship`/`deleteRelationship` COM implementations remain
  out of scope ONLY if already implemented — verify at execution start;
  the stubs at :1214/:1218 are IN scope if still present.

## Risks / gotchas

- **Fake-success `alterTable` (:1195)** must be eliminated before any
  parity case or caller depends on it — it silently reports success for
  no-ops today.
- **Jet DDL quirks**: `DROP INDEX` requires `ON [table]`; `WITH IGNORE
  NULL` placement; `ALTER COLUMN` cannot change some properties —
  Python oracle error strings govern; error TEXT may diverge between
  pyodbc and DAO — if byte-for-byte matching fails, normalize in
  `normalize.mjs` with justification, never `volatileFields` on
  `success`.
- **RecordsAffected-style property quirks**: DDL statements report no
  affected rows; do not read `RecordsAffected` after DDL Execute.
- **Exclusive lock**: COM variant requires per-side fixture copies
  (established in plan 033's `run.ts` change); DDL mutating cases follow
  the same path.
- **`{TAG,_0}` FFI envelopes**: all nested case args flow through the
  jsToJson helpers; new arg shapes (arrays of columnSchema dicts) must
  be probed before case authoring.

## Success criteria

- Suite green from a fresh build: 741 + new tests, 0 failed.
- All five parity scripts pass with exact counts recorded in
  `plans/README.md` and `parity/findings.md`.
- Zero DDL stubs remain in `ComDataAdapter.res` (grep gate: no
  `"COM .* not implemented"` and no `Ok(Dict.make())` from `alterTable`;
  intent: no DDL-surface stubs, internal helpers excluded).
- No `MSACCESS.EXE` orphans after the full parity suite.
