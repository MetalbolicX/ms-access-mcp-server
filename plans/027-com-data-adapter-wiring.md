# Plan 027: Wire a COM-backed data adapter through the facade and parity harness

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d96ae3c..HEAD -- rescript-mcp/src/ rescript-mcp/parity/ rescript-mcp/scripts/parity_driver.py rescript-mcp/test/ plans/README.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.
>
> **Precondition**: plan 026's verification changes (modified
> `parity/run.ts`, `parity/runRescript.{ts,mjs}`, `scripts/parity_driver.py`,
> `package.json`, `parity/findings.md`, new `parity/cases/northwind/` and
> `test/northwind-stdio/`) may be uncommitted at `d96ae3c`. If `git status
> --short` shows them dirty, STOP and ask the operator whether to commit them
> before branching — this plan assumes they land on `main` first.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH (COM STA threading, real-Access dependency)
- **Depends on**: plans 026 (Northwind baseline), 012 (COM adapter port), 003 (interfaces), 006 (facade)
- **Category**: migration
- **Methodology**: STRICT TDD (unit tests with module-typed fakes precede adapter implementation, per plan 005 pattern)
- **Planned at**: commit `d96ae3c`, 2026-08-29
- **Branch**: `rescript/027-com-data-adapter-wiring` from `main`

## Why this matters

The ReScript facade is the product; Python is only the behavioral oracle. Today the composition root **ignores** `comAvailable` (`Composition.res:116-143`), the MCP server **hardcodes** `~comAvailable=false` (`Server.res:452-457`), and tools accept `use_com`/`backend` but never route on them. Five COM modules exist (`ComDbProps`, `ComVba`, `ComUi`, `ComSession`, `ComInterfaces`) but none implements `Interfaces.DATA_ADAPTER`/`SCHEMA_ADAPTER`, so no MCP tool can ever reach a COM backend. Consequences already measured: ODBC `get_relationships` returns `count: 0` because `MSysRelationships` is not readable via ACE ODBC (finding 026-F-003), while the Python COM oracle returns all 4 Northwind relationships. Until this plan lands, the ReScript server cannot match the Python implementation's schema capabilities on real databases, and mutation hardening has no COM path to compare against.

## Current state (verified at `d96ae3c` + 026 working tree)

- **Interfaces** (`rescript-mcp/src/Adapters/Interfaces.res:108-149`) define two module types the COM adapter must implement:

```rescript
module type DATA_ADAPTER = {
  type t
  let connect: (t, string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>
  let executeQuery: (t, string, ~params: array<JSON.t>=?) => Promise.t<result<queryResult, Errors.t>>
  let insertData: (t, string, dict<JSON.t>) => Promise.t<result<mutationResult, Errors.t>>
  let updateData: (t, string, dict<JSON.t>, ~where: option<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>
  let deleteData: (t, string, ~where: option<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>
  let executeRawSql: (t, string) => Promise.t<result<int, Errors.t>>
  let exportData: (t, string, string, ~format: option<string>=?, ~options: dict<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>
}

module type SCHEMA_ADAPTER = {
  type t
  let connect: (t, string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>
  let getTables: t => Promise.t<result<array<tableInfo>, Errors.t>>
  let getSystemTables: t => Promise.t<result<array<tableInfo>, Errors.t>>
  let getObjectMetadata: (t, string) => Promise.t<result<dict<JSON.t>, Errors.t>>
  let getRelationships: t => Promise.t<result<array<relationshipInfo>, Errors.t>>
  let getTableSchemaPlan: t => Promise.t<result<(array<tableSchema>, unknownMetadata), Errors.t>>
  let generateSql: (t, string) => Promise.t<result<ddlResult, Errors.t>>
  let getDatabaseStatistics: t => Promise.t<result<dict<JSON.t>, Errors.t>>
  let getQueries: t => Promise.t<result<array<queryInfo>, Errors.t>>
  // ... DDL ops follow
}
```

- **Composition ignores COM** (`rescript-mcp/src/Services/Composition.res:116-143`) — `makeRealFactory(~comAvailable)` accepts the flag but always builds `OdbcAdapter` and hardcodes `adapterType = "odbc"`; `realFactory = makeRealFactory(~comAvailable=false)` at the bottom.
- **Server hardcodes COM off** (`rescript-mcp/src/Mcp/Server.res:452-457`):

```rescript
let facade = Facade.make(
  ~factory=Composition.realFactory,
  ~comAvailable=false,  // HARD-CODED
  ~readonly=Config.readonly,
  ~allowedDirs=Config.allowedDirs,
)
```

- **Tools parse but drop `use_com`** (`rescript-mcp/src/Mcp/Tools.res:60-66, 85-93`): `connectAccessSchema` includes `use_com` and `backend`; handlers extract them and pass to `Facade.connectAccess(~useCom?, ~backend?)`, but nothing downstream selects a COM adapter.
- **Facade contract** (`rescript-mcp/src/Services/Facade.res:46-53`): record `t` carries `factory: bindingFactory`, `comAvailable: bool`, `readonly: unit => bool`. `assertNotReadonly` (`:60-71`) guards mutations. `BackendSelector.backend` is the backend discriminant — verify it has a `com` variant; if not, adding one is in scope.
- **COM interop exists**: `rescript-mcp/src/Bindings/Winax.res` (+ `.resi`) — winax (Node Windows Automation) FFI is already bound. `JsCom.res(.mjs)` provides runtime support. No npm dependency changes expected; confirm `winax` is in `package.json` dependencies — if missing, STOP and report (binding without package is drift).
- **Existing COM modules** (do not restructure them): `ComInterfaces.res` (COM types), `ComSession.res` (Access.Application lifecycle), `ComDbProps.res`, `ComVba.res`, `ComUi.res`. They are standalone; this plan adds a new adapter that *uses* `ComSession` for lifecycle.
- **Python oracle**: `src/ms_access_mcp/adapters/win_com_adapter.py` implements `connect/disconnect/is_connected/execute_query/get_tables/get_system_tables/get_queries/get_table_schema_plan/get_relationships/get_database_statistics/generate_sql/save_database/compile_vba` plus CRUD. Its `com_dispatcher.py` serializes all COM calls on a single STA thread — the ReScript side needs the same serialization guarantee.
- **Parity harness**: `parity/run.ts` reads case JSONs but **never consumes the `variant` field** (verified: no `variant` reference in `run.ts` or `parity_driver.py` dispatch). All 26 existing cases say `"variant": "odbc"`. Adding `variant` threading is in scope.
- **Northwind baseline** (plan 026, DONE): `db/northwind.accdb`, 8 tables, 9/9 read-only parity via `pnpm -C rescript-mcp parity:northwind`. Cases live in `rescript-mcp/parity/cases/northwind/`.
- **Suite gate**: 678/678 ReScript tests; 17/17 fixture parity. Both must stay green.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Drift check | `git diff --stat d96ae3c..HEAD -- rescript-mcp/src/ rescript-mcp/parity/ rescript-mcp/scripts/parity_driver.py rescript-mcp/test/ plans/README.md` | Zero diff, or only the 026 files noted in the precondition |
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit tests | `pnpm -C rescript-mcp test` | 678 + new tests pass |
| Parity harness build | `pnpm -C rescript-mcp build:parity` | exit 0 |
| Fixture parity | `$env:ACCESS_TEST_ASSUME_ACE='1'; pnpm -C rescript-mcp parity` | 17 matched, 0 mismatched |
| Northwind parity (ODBC) | `$env:ACCESS_TEST_ASSUME_ACE='1'; $env:ACCESS_TEST_DB='<abs path>\db\northwind.accdb'; pnpm -C rescript-mcp parity:northwind` | 9/9 |
| Northwind parity (COM) | same + `parity:northwind:com` script (added by this plan) | new corpus passes on Windows with Access installed |
| Python oracle ops | `.venv\Scripts\python.exe` | never `uv` |

## Scope

**In scope** (create/modify only these):

- `rescript-mcp/src/Adapters/ComDispatch.res` (create) — serial promise queue for COM calls
- `rescript-mcp/src/Adapters/ComDataAdapter.res` (create) — `DATA_ADAPTER` + `SCHEMA_ADAPTER` over winax/DAO
- `rescript-mcp/src/Services/Composition.res` — honor `~comAvailable` + backend in `makeRealFactory`
- `rescript-mcp/src/Services/BackendSelector.res` — add `com` variant if absent
- `rescript-mcp/src/Mcp/Server.res` — derive `comAvailable` from platform + winax probe instead of hardcoded `false`
- `rescript-mcp/parity/run.ts`, `parity/runRescript.ts`, `scripts/parity_driver.py` — thread case `variant` to both children
- `rescript-mcp/parity/cases/northwind/com/*.json` (create) — COM-variant read-only corpus
- `rescript-mcp/parity/cases.schema.json` — extend `variant` enum with `"com"`
- `rescript-mcp/package.json` — add `parity:northwind:com` script; add `winax` dependency if missing (see STOP conditions)
- `rescript-mcp/test/ComDispatchTest.res`, `rescript-mcp/test/ComDataAdapterTest.res` (create) — unit tests with fakes
- `rescript-mcp/parity/findings.md` — record 027-F-xxx mismatches
- `plans/README.md` — update row 027

**Out of scope** (do NOT touch):

- Any file under `src/ms_access_mcp/` **except** `scripts/parity_driver.py` (variant threading only — no behavior changes to the oracle)
- `rescript-mcp/src/Adapters/OdbcAdapter.res` — ODBC path must stay bit-identical in behavior
- `ComUi.res`, `ComVba.res`, `ComDbProps.res` internals — the new adapter may *call* `ComSession`, not refactor these
- MCP tool schemas beyond what's listed (no new tools, no removed tools)
- Mutation parity cases for COM — write operations stay out until ODBC mutation hardening lands
- HTTP transport, auth, UI plans

## Git workflow

- Branch: `rescript/027-com-data-adapter-wiring` from `main`.
- Conventional commits, one per step (house style from `git log`: `feat(rescript-mcp): …`, `test(rescript-mcp): …`, `fix(parity): …`).
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 1: `ComDispatch` — serialized COM call queue

Create `rescript-mcp/src/Adapters/ComDispatch.res`. All winax COM calls are synchronous and must never interleave (Access COM is STA; concurrent calls corrupt apartment state — this mirrors Python's `com_dispatcher.py` single-thread serialization). Implement a FIFO promise queue:

- `let enqueue: (unit => 'a) => Promise.t<'a>` — runs thunks strictly one at a time, in order.
- Rejection of one thunk must not stall the queue.

**Verify**: `pnpm -C rescript-mcp build` → exit 0.

### Step 2: `ComDispatch` unit tests (STRICT TDD note)

Write `test/ComDispatchTest.res` first (concurrency ordering, error isolation, FIFO order under interleaved enqueues), then confirm Step 1 satisfies them. Model the test structure after `test/ComSessionTest.res`.

**Verify**: `pnpm -C rescript-mcp test` → 678 + new ComDispatch tests pass.

### Step 3: `ComDataAdapter` — data + schema adapter over DAO

Create `rescript-mcp/src/Adapters/ComDataAdapter.res` implementing `Interfaces.DATA_ADAPTER` and `Interfaces.SCHEMA_ADAPTER`. Behavior must match the Python oracle `src/ms_access_mcp/adapters/win_com_adapter.py`:

- `connect` opens `Access.Application` via `ComSession`, opens the db, returns `Ok(true)`; honor `~password`.
- `executeQuery` — DAO `CurrentDb().OpenRecordset(sql)`; rows as arrays of column dicts matching the `queryResult` shape OdbcAdapter produces (same envelope — parity diff compares against Python, not ODBC).
- `insertData`/`updateData`/`deleteData` — mirror Python's method semantics exactly (parameter binding via DAO `QueryDef` parameters where the oracle does so; otherwise escaped literals — check the oracle before choosing).
- `getTables`/`getSystemTables` — DAO `TableDefs` filtered by system-object attributes (match oracle's filter).
- `getRelationships` — DAO `Relations` (this is the capability ODBC lacks; the 026-F-003 motivation).
- `getQueries` — DAO `QueryDefs` excluding system queries.
- `getDatabaseStatistics` — file stats + object counts; match oracle key names exactly.
- `getTableSchemaPlan`/`generateSql` — implement only if the oracle's implementation is straightforward via DAO; otherwise return the same "not available" error envelope shape the ODBC adapter returns (`OdbcAdapter.res:960-962` pattern) and record a 027-F-xxx finding. Do not improvise a partial DDL surface.
- **Every** COM touch goes through `ComDispatch.enqueue`.
- On non-Windows platforms, `connect` returns a platform error envelope (same shape as Python's COM-unavailable error).

**Verify**: `pnpm -C rescript-mcp build` → exit 0. `pnpm -C rescript-mcp test` → all pass (adapter not yet instantiated by anything).

### Step 4: `ComDataAdapter` unit tests with fakes

Write `test/ComDataAdapterTest.res` using the module-typed fake pattern from plan 005: stub the winax binding layer (inject a fake COM object graph — DAO TableDefs/Relations/Recordset doubles) and assert the adapter's envelopes match oracle-shaped fixtures. Cover: connect success/failure, executeQuery row shaping, empty-table schema, relationships mapping, readonly-guard interaction (adapter itself is not readonly-aware; facade owns that).

**Verify**: `pnpm -C rescript-mcp test` → all pass.

### Step 5: Composition + backend selection

- `BackendSelector.res`: add a `com` variant if none exists.
- `Composition.res makeRealFactory`: when `~comAvailable=true` and the resolved backend is `com`, construct `ComDataAdapter` (+ its schema instance) and set `adapterType = "com"`; otherwise keep the exact current ODBC path. `realFactory` signature stays the same; the flag at the bottom changes to read a probe (next step).
- `Server.res:452-457`: replace hardcoded `~comAvailable=false` with a probe: `process.platform == "win32"` **and** winax loads (`try require("winax")` via the existing binding) — cache the probe result; never probe per-connection.

**Verify**: `pnpm -C rescript-mcp build` → exit 0. `pnpm -C rescript-mcp test` → all pass. ODBC behavior unchanged: fixture parity 17/17 and northwind 9/9 still green (run both).

### Step 6: Thread `variant` through the parity harness

- `parity/cases.schema.json`: extend `variant` enum to `["odbc", "com"]`.
- `parity/run.ts`: read `caseObj.variant` (default `"odbc"` for back-compat), pass it to both children via a CLI arg or env var (`PARITY_VARIANT=com`).
- `parity/runRescript.ts`: on `variant=com`, call `Facade.connectAccess` with `~backend="com"` (match the actual connectAccess signature).
- `scripts/parity_driver.py`: on `variant=com`, instantiate `WinComAdapter` instead of `OdbcAdapter`. Read the driver's existing adapter-construction site and make the minimal dispatch change — nothing else in the oracle changes.
- `pnpm build:parity` after `.ts` edits.

**Verify**: `pnpm -C rescript-mcp build:parity` → exit 0; existing corpora still 17/17 and 9/9 (default variant path untouched).

### Step 7: COM parity corpus against Northwind

Create `parity/cases/northwind/com/` with the read-only subset, each with `"variant": "com"`, mirroring the ODBC Northwind cases: `connect_access` (backend com), `get_tables`, `get_table_schema-Customers`, `get_relationships`, `get_queries`, `query_data-SelectTop5Customers`. Reuse `volatileFields` from their ODBC twins. `get_relationships` under COM must **not** volatilize `count`/`relationships` — matching Python COM's full relationship list is the point; the expectation is parity with the oracle, and any residual diff becomes a 027-F-xxx finding.

Add `parity:northwind:com` to `package.json`, modeled on `parity:northwind` (post-026 path form: `--cases-dir=rescript-mcp/parity/cases/northwind/com --require-read-only`).

**Verify** (Windows with MS Access installed): run the COM corpus → all cases matched. Record every mismatch in `parity/findings.md` as `027-F-xxx` with reproduction; the corpus must end green.

### Step 8: Findings, docs, index

- `parity/findings.md`: add a `027-com-wiring` section — final counts, any 027-F-xxx entries, and explicitly note whether 026-F-003 (ODBC relationships count 0) is now covered by the COM path.
- `plans/README.md`: update row 027 status.

**Verify**: `git status --short` shows only in-scope files.

## Test plan

- New unit tests: `ComDispatchTest.res` (ordering, FIFO, error isolation), `ComDataAdapterTest.res` (envelope shapes vs oracle fixtures, connect paths, relationships mapping, platform-gate error).
- Structural patterns: `test/ComSessionTest.res` for COM module tests; plan 005's module-fake approach for adapter tests.
- Existing suites that must not regress: `pnpm -C rescript-mcp test` (678 + new), fixture parity 17/17, ODBC Northwind 9/9.
- Real-COM validation is gated on Windows + installed MS Access; on any other environment the COM corpus must skip cleanly (exit 0 with a skip line), same convention as the ACE gate in `parity/run.ts:72-80`.

## Done criteria

ALL must hold:

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` exits 0; ComDispatch + ComDataAdapter tests exist and pass
- [ ] Fixture parity 17/17 and ODBC Northwind 9/9 unchanged
- [ ] `parity:northwind:com` corpus passes against `db/northwind.accdb` on Windows with Access
- [ ] `get_relationships` under COM returns the 4 Northwind relationships (026-F-003 resolved via COM path, or an explicit 027-F-xxx explains the residual)
- [ ] `Server.res` no longer contains a hardcoded `comAvailable=false` at the facade construction site
- [ ] No files outside the in-scope list modified (`git status`)
- [ ] `plans/README.md` row 027 updated

## STOP conditions

Stop and report back (do not improvise) if:

- `winax` is not in `rescript-mcp/package.json` dependencies or fails to load — the binding exists but the runtime package may be missing; report before installing anything.
- The `Interfaces` module types in `Current state` don't match the live code (drift).
- The Python oracle's CRUD methods use parameter binding that DAO `QueryDef` cannot express from JavaScript — report the exact method and choose the oracle's exact fallback rather than inventing one.
- `Facade.connectAccess` does not actually accept/route `~backend` or `~useCom` (evidence was from `Server.res` callback, not facade internals) — wiring the facade routing becomes part of the plan only after reporting.
- The COM corpus cannot reach green after recording findings — do not volatilize your way to green without operator sign-off.
- The fix appears to require touching any out-of-scope file.

## Maintenance notes

- ODBC mutation hardening (next planned work) now has a COM reference path: any mutation envelope change must keep both adapters aligned with the Python oracle, or parity will catch it per-variant.
- Reviewers should scrutinize: (1) every COM call in `ComDataAdapter` goes through `ComDispatch.enqueue` — grep for direct `Winax`/`JsCom` calls in the adapter and reject any; (2) the `comAvailable` probe is evaluated once, not per connection; (3) the ODBC code path in `Composition.makeRealFactory` is byte-identical in behavior.
- Explicitly deferred: COM mutation parity cases, COM DDL (`generateSql` full parity), `save_database`/`compile_vba` MCP exposure, and any UI/VBA tool wiring — those belong to follow-up plans once this adapter lands.
