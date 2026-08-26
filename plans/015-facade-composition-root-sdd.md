# Plan 015: Facade adapter composition root — real adapters injectable (SDD)

> **Executor instructions**: Execute through the repo's SDD workflow, COMPACT
> form: propose+spec (one merged artifact) → design → tasks → apply (strict
> TDD) → verify → archive. Use the SDD skills (`sdd-propose` may be skipped;
> the merged propose+spec artifact is written by `sdd-spec` with a short
> intent header). When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**: this plan was written against an UNCOMMITTED
> working tree (plans 003–006 artifacts are not committed; HEAD is `2bbff3a`).
> Verify the "Current state" excerpts against the LIVE files before
> proceeding: `rescript-mcp/src/Services/Facade.res` (binding type near lines
> 14–36), `rescript-mcp/src/Adapters/Interfaces.res` (module types near lines
> 127–168), `rescript-mcp/test/Fakes.res`. On mismatch, STOP.
>
> **Drift reconciliation (2026-08-25, post-sdd-explore)**: this plan was
> amended against the live tree (HEAD `b060457` on
> `rescript/017-odbc-test-fixes` after plan 017, working tree still
> contains uncommitted plans 003–006 artifacts). Engram observation
> `#1048` documents five concrete corrections incorporated below:
>
> 1. `SCHEMA_ADAPTER` has **22 methods**, not 18. Plan prose and
>    illustrative snippets updated.
> 2. The Fakes coupling in `Facade.res` is **broader than lines 17–22**:
>    `adapterForName` (line ~90) and `schemaAdapterForName` (line ~102)
>    return Fake types, and CRUD/schema operations call
>    `Fakes.FakeOdbcAdapter.*` / `Fakes.FakeSchemaAdapter.*` directly at
>    multiple sites (e.g. lines 406, 473, 526, 630). All such sites must
>    be migrated alongside the binding re-type.
> 3. `OdbcSchemaReader.res` is **NOT** a self-taking module with `type t`
>    and `make`. It is a query seam (`issueQuery`) plus
>    connection-based relationship helpers
>    (`createRelationship(~conn=...)`, `deleteRelationship(~conn=...)`,
>    `readRelationships(~query=...)`). The schema instance record cannot
>    be derived by closure-capture alone; design must decide whether
>    (a) the schema instance is a thin wrapper around `OdbcAdapter.t`
>    that delegates relationship ops to `OdbcSchemaReader` with the
>    adapter's current connection, or (b) introduce a separate schema
>    state type that holds its own connection. Plan 015 default: **(a)**.
> 4. Signature mismatch: `Interfaces.DATA_ADAPTER.insertData` takes
>    `dict<JSON.t>`, while `OdbcAdapter.insertData` takes `JSON.t`. This
>    is a **pre-existing interface-vs-impl drift** that affects the
>    instance-record derivation. Two options: (a) derive the instance
>    record from `OdbcAdapter.insertData`'s actual signature and add a
>    follow-up to reconcile the interface; (b) reconcile the interface
>    first as a separate small commit. Plan 015 default: **(a)** —
>    preserve current product behavior, log the interface drift as a
>    follow-up.
> 5. Connector-string boundary: `OdbcAdapter.connect` expects an
>    incoming string containing `DBQ`, **appends** `;DRIVER=<value>`
>    (defaulting to `{Microsoft Access Driver (*.mdb, *.accdb)}` and
>    overridable via `ACCESS_MCP_ODBC_DRIVER`), and optionally appends
>    `;PWD=<password>`. It does NOT build the `Driver=...;DBQ=...;`
>    form. Python (`odbc.py:87`) and the Node runner
>    (`run.mjs:123`, plan 016) construct the full `Driver=...;DBQ=...;`
>    string. **The composition root must NOT construct a `Driver;DBQ`
>    string** — pass `DBQ=<path>` only and let `OdbcAdapter.connect`
>    append the driver clause. Plan 015 default documented.
>
> **Design corrections (2026-08-25, post-apply attempt + plan 022)**:
> Two assumptions baked into design artifact `sdd/facade-composition-root/design`
> (Engram #1055) were verified FALSE by execution:
>
> 6. `insertData` shape: design §1.1 declared the instance field as
>    `(string, JSON.t)` citing "live product signature". The LIVE
>    `OdbcAdapter.insertData` (`OdbcAdapter.res:215`) accepts
>    `dict<JSON.t>`. The interface (`Interfaces.res:116`) also declares
>    `dict<JSON.t>` — it was correct all along. Plan 022 reverted
>    `Instances.res` to `dict<JSON.t>` and reverted the test callers'
>    `JSON.Object(record)` wrappers. **Executors: derive instance fields
>    from `Interfaces.res`, full stop.** The "live product beats
>    interface" escape hatch in this plan's original Stage 1 text is
>    rescinded — when they disagree, STOP and re-plan.
> 7. `exportData` shape: design §1.1 referenced a non-existent
>    `Interfaces.exportResult` type. The live return type is
>    `mutationResult` (`Interfaces.res:120`). Plan 022 reverted
>    `Instances.res`, `Fakes.res`, and `InstancesPlaceholderTest.res`
>    accordingly. T1's committed `Instances.res` (commit `8b190f1`,
>    amended) already carries both corrections.
>
> Additionally, the first apply attempt (Engram #1058) showed an
> executor-discipline failure: the apply agent rewrote
> `OdbcAdapter.insertData`'s signature, stubbed batch insert, and dropped
> `~password`/`~params` labeled args in `asInstance` — none of which the
> design authorized. **Executor rule (binding for all future apply work):
> the design artifact's verbatim snippets are the contract. Any deviation
> is a STOP condition, not an improvisation opportunity.**

## Status

- **Priority**: P1 (hard blocker for plan 007's ReScript parity driver)
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/003, 004, 005, 006 (all DONE), 021, 022, 023
  (drift reconciliation; T1 is already committed at `8b190f1` and
  carries plan 022's corrected shapes). Soft-depends on plan 016 for the
  final real-DB smoke step (unit work is independent). Plan 024 lands the
  consolidated state on main.
- **Status note (2026-08-25)**: SDD phases 1–5 (explore→propose→spec→
  design→tasks) are COMPLETE with Engram artifacts #1048/#1051/#1053/
  #1054/#1055/#1056. Apply phase T1 committed; T2–T6 pending. Resume
  after plan 023 commits the drift-reconcile close-out and plan 024
  consolidates branches to main. The task list (Engram #1056) remains
  the apply playbook — with the two design corrections above applied.
- **Category**: migration
- **Methodology**: SDD (compact). Justification: this introduces a NEW typed
  binding surface — value-level adapter instance records — consumed by plan
  007's parity driver and plan 008's MCP composition root. That seam decision
  must be pinned before implementation (repo classification rule: "FFI
  binding surfaces, async models, public API contracts" are SDD). The 17
  public facade operation signatures DO NOT change; behavior is already
  pinned by the 553-test suite, so apply runs strict TDD under a green suite.
- **Planned at**: commit `2bbff3a` + uncommitted plans-003–006 working tree,
  2026-08-25

## Why this matters

Plan 006's facade types its per-connection binding with TEST FAKE types, so
the real `OdbcAdapter` cannot be injected — `Facade.make(~factory=<real>)`
cannot compile as typed. Plan 007's parity harness must drive the ReScript
facade with REAL adapters against a real `.accdb`; plan 008's MCP server
needs the same wiring. This plan introduces value-level adapter instance
types (record-of-closures — the representation already chosen by plan 006's
design, decision E: "closure-capture handles; codebase has zero
first-class-module usage") and a real composition factory, without changing
any public facade operation signature.

## Current state

- `rescript-mcp/src/Services/Facade.res` — the facade (17 ops, ~1900 lines).
  The problem, at lines ~14–36:

```rescript
type binding = {
  dataAdapter: Fakes.FakeOdbcAdapter.t,      // ← TEST FAKE type
  schemaAdapter: Fakes.FakeSchemaAdapter.t,  // ← TEST FAKE type
  dbPath: string,
  adapterType: string,
}

type bindingFactory = (
  ~backend: option<BackendSelector.backend>,
  ~dbPath: string,
  ~password: string,
) => Promise.t<result<binding, Errors.t>>
```

  **Drift (post-explore):** the Fakes coupling is broader than the binding
  declaration. `adapterForName` (line ~90) and `schemaAdapterForName`
  (line ~102) return Fake types; CRUD/schema operations call
  `Fakes.FakeOdbcAdapter.*` / `Fakes.FakeSchemaAdapter.*` directly at
  multiple sites (e.g. lines 406, 473, 526, 630). All such sites are
  IN SCOPE for this plan alongside the binding re-type.

- `rescript-mcp/src/Adapters/Interfaces.res` — module types `DATA_ADAPTER`
  (9 operation methods plus `type t`, total 10 lines) and `SCHEMA_ADAPTER`
  (22 operation methods plus `type t` plus 3 lifecycle methods), near lines
  127–168. Every method returns `Promise.t<result<'a, Errors.t>>`.
  **Drift:** plan originally said "18 methods"; actual is 22. Comments in
  `Fakes.res` / `FakesTest.res` calling it "18" are stale — the live fake
  already implements all 22.
- `rescript-mcp/src/Adapters/OdbcAdapter.res` — REAL data adapter. A MODULE
  whose functions take `self: t`; `type t = {mutable connection:
  option<Bindings.Odbc.connection>, mutable dbPath: option<string>}` (near
  lines 40–44). No `.resi`. Has a default `Driver={Microsoft Access Driver
  (*.mdb, *.accdb)}` overridable via `ACCESS_MCP_ODBC_DRIVER` and a
  `password` arg.
  **Drift:** `OdbcAdapter.insertData` takes `JSON.t` (not
  `dict<JSON.t>` as `Interfaces.DATA_ADAPTER.insertData` declares).
  Plan 015 keeps the existing product signature; interface reconciliation
  is a follow-up.
- `rescript-mcp/src/Adapters/OdbcSchemaReader.res` — REAL schema helpers.
  **Not** a self-taking adapter module. Has `issueQuery` (a query seam)
  and connection-based relationship helpers
  (`createRelationship(~conn=...)`, `deleteRelationship(~conn=...)`,
  `readRelationships(~query=...)`). No `type t`, no `make`. The design
  phase must decide whether schema instance is a wrapper around
  `OdbcAdapter.t` (default) or a new schema state type.
- `rescript-mcp/test/Fakes.res` — `FakeOdbcAdapter`, `FakeComAdapter`,
  `FakeSchemaAdapter`; self-taking-module pattern (`make(~name=?) => t`,
  functions take `self: t`). `FakeSchemaAdapter` already implements all 22
  schema methods (despite stale comments saying "18").
- `rescript-mcp/test/FacadeTest.res` — injects a fake `bindingFactory`
  (`makeFakeFactory` near line 43) producing fake-typed bindings. This test
  file WILL be migrated to the new instance injection (expected refactor;
  suite stays green throughout).
- Constraint honored since plan 006: `Facade.res`, `Config.res`,
  `PathGuard.res` import NO `Bindings/*` modules. The new composition module
  (this plan) is the ONE new src module allowed to import
  `Adapters.OdbcAdapter` / `Adapters.OdbcSchemaReader` (transitively
  Bindings) — that is what a composition root is.
- Suite baseline: 553 tests / 551 pass / 2 known failures (see plan 017 —
  they are fixed there; this plan must not add new failures).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit tests | `pnpm -C rescript-mcp test` | 553 tests, 551 pass, 2 known failures (unchanged) |
| ODBC integration smoke | `pnpm -C rescript-mcp test:integration:odbc` | skip-clean without env; real run with `ACCESS_TEST_DB` + `ACCESS_TEST_ASSUME_ACE=1` |

## Scope

**In scope**:
- `rescript-mcp/src/Adapters/Interfaces.res` (add instance record types) — or
  a new `Adapters/Instances.res`; the DESIGN phase pins the home.
- `rescript-mcp/src/Adapters/OdbcAdapter.res` (add `asInstance` for data)
- `rescript-mcp/src/Adapters/OdbcSchemaReader.res` (add `asInstance` for
  schema, bridging connection-based relationship helpers to the schema
  instance record — likely by taking the `OdbcAdapter.t` as the connection
  source)
- `rescript-mcp/src/Services/Facade.res` (re-type `binding` + `bindingFactory`
  + remove `Fakes.*` references at all sites: lines 90, 102, 406, 473, 526,
  630, plus any newly discovered by design)
- `rescript-mcp/src/Services/Composition.res` (create — real factory; design
  pins the exact name/location)
- `rescript-mcp/test/Fakes.res` (add `asInstance` producers for the fakes)
- `rescript-mcp/test/FacadeTest.res` (migrate injection to instances)
- New tests for the instance producers and the real factory (unit, fakes)
- Engram SDD artifacts under `sdd/facade-composition-root/*`

**Out of scope**:
- Any change to the 17 public facade operation signatures or output shapes.
- Any change to adapter behavior (adapters keep their module functions; only
  ADD `asInstance` wrappers).
- `Interfaces.DATA_ADAPTER.insertData` signature reconciliation (real fix is
  `dict<JSON.t>` vs current `JSON.t`; preserved as a follow-up plan; this
  plan derives the instance record from the LIVE `OdbcAdapter.insertData`
  signature, NOT the interface declaration).
- Plan 007 harness code; plan 008 MCP wiring.
- The 2 known test failures (plan 017 owns them).
- Python source.

## Git workflow

- Branch: `rescript/015-facade-composition-root`.
- Conventional commits, e.g. `feat(rescript): add adapter instance types and composition root`.

## Steps (SDD stages, compact)

### Stage 1: Propose + Spec (ONE merged Engram artifact)

`sdd/facade-composition-root/proposal-spec`. Must pin:
1. **Instance types** (illustrative seed — design finalizes signatures,
   derived VERBATIM from the live `DATA_ADAPTER` (9 operation methods) and
   `SCHEMA_ADAPTER` (22 operation methods) module types in
   `Adapters/Interfaces.res`):

```rescript
// Illustrative — do not copy blindly; derive each field signature from
// Interfaces.res module types. Schema instance has 22 fields.
// (Plan 022 correction: insertData is dict<JSON.t>, NOT JSON.t.)
type dataAdapterInstance = {
  connect: (string, ~password: string=?) => Promise.t<result<bool, Errors.t>>,
  disconnect: unit => Promise.t<result<unit, Errors.t>>,
  isConnected: unit => Promise.t<result<bool, Errors.t>>,
  executeQuery: (string, ~params: array<JSON.t>=?) => Promise.t<result<queryResult, Errors.t>>,
  insertData: (string, dict<JSON.t>) => Promise.t<result<mutationResult, Errors.t>>,
  updateData: (string, dict<JSON.t>, ~where: option<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>,
  deleteData: (string, ~where: option<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>,
  executeRawSql: string => Promise.t<result<int, Errors.t>>,
  exportData: (string, string, ~format: option<string>=?, ~options: option<dict<JSON.t>>=?) => Promise.t<result<mutationResult, Errors.t>>,
}
type schemaAdapterInstance = {
  // 22 methods — see live SCHEMA_ADAPTER in Interfaces.res
  connect, disconnect, isConnected: ...,
  getTables, getSystemTables, getObjectMetadata, getRelationships,
  getTableSchemaPlan, generateSql, getDatabaseStatistics, getQueries,
  createQuery, setQuerySql, deleteQuery,
  createTable, deleteTable, alterTable,
  getIndexes, createIndex, dropIndex,
  createRelationship, deleteRelationship: ...,
}
```

2. **Producers**: `OdbcAdapter.asInstance(t)` (data), schema instance is
   derived as a wrapper around `OdbcAdapter.t` (default per drift
   reconciliation item 3) that delegates relationship ops to
   `OdbcSchemaReader` using the adapter's current connection,
   `Fakes.FakeOdbcAdapter.asInstance(t)`,
   `Fakes.FakeSchemaAdapter.asInstance(t)` — each wraps the module's
   self-taking functions as closures over `t`.
3. **Facade re-typing**: `binding` uses the instance types; `bindingFactory`
   signature otherwise unchanged. ALL `Fakes.*` references in
   `Facade.res` are removed (not only at lines 17–22 — see drift
   reconciliation item 2 and "Scope" above for the full site list).
4. **Composition root**: a src module (e.g. `Services/Composition.res`)
   exposing `realFactory: Facade.bindingFactory` that resolves the backend via
   `BackendSelector`, constructs real adapter `t` values, wraps via
   `asInstance`. It is the only new src module permitted to import adapter
   modules (and transitively Bindings). The connection string passed to
   `OdbcAdapter.connect` MUST be `DBQ=<path>` ONLY — `OdbcAdapter`
   appends the `;DRIVER=<value>` clause itself and an optional
   `;PWD=<password>` (see drift reconciliation item 5). Passing a
   pre-built `Driver=...;DBQ=...;` string would double-append the driver.
5. **Smoke gate**: an env-gated end-to-end check (facade + realFactory +
  fixture DB) that skip-cleans like `test/odbc-integration/run.mjs`.

### Stage 2: Design (Engram `sdd/facade-composition-root/design`)

Decide:
- Home of instance types (extend `Interfaces.res` vs new
  `Adapters/Instances.res`).
- Exact field signatures (verbatim from live `DATA_ADAPTER` / `SCHEMA_ADAPTER`,
  with `insertData` using `JSON.t` per the live product, not `dict<JSON.t>`
  per the interface declaration).
- Error/edge semantics of `asInstance` (none expected — pure wrapping).
- Schema adapter shape (default: wrapper around `OdbcAdapter.t` that delegates
  relationship ops to `OdbcSchemaReader` using the adapter's current
  connection; alternative: separate schema state type).
- Connection string contract: `realFactory` passes `DBQ=<path>` to
  `OdbcAdapter.connect`; `OdbcAdapter` is the connection-string boundary
  (it appends `;DRIVER=<value>` and optional `;PWD=<password>`).
- Composition module name and public surface (default:
  `Services/Composition.res` exposing `realFactory: Facade.bindingFactory`).
- How the smoke gate is invoked (a `.mjs` script under
  `test/odbc-integration/` extending the existing runner, vs a new script).
- Document why: record-of-closures per plan-006 design decision E.

### Stage 3: Tasks (Engram `sdd/facade-composition/tasks`)

Two strict-TDD slices suggested:
- **Slice 1**: instance types + `asInstance` producers (real + fakes) + migrate
  `Facade.res` binding + migrate `FacadeTest.res` injection. Red: a test that
  constructs an instance from a fake and asserts a call passes through;
  instance-producer tests for all four producers. Suite stays green
  throughout (refactor under green — migrate tests in the same slice).
- **Slice 2**: `Composition.res` real factory (unit-tested with injected
  backend resolution) + env-gated real-DB smoke through the FACADE
  (connect → getTables → queryData → disconnect).

### Stage 4: Apply (strict TDD)

Tests first, always. Runner: `pnpm -C rescript-mcp test`.

### Stage 5: Verify

Build 0; suite = 553+/551+ (2 known failures unchanged, no new); greps below;
smoke passes with env set (or skip-cleans without it).

### Stage 6: Archive

Engram `sdd/facade-composition/archive-report`; flip `plans/README.md` row.

## Test plan

- Instance producer tests: fake→instance passthrough (each of the 4
  producers constructs; ≥1 method call round-trips; call log records).
  Schema instance producer covers all **22 schema methods** (count per
  `Interfaces.res:142–168`; see drift reconciliation item 1).
- Composition factory unit test: with `comAvailable` injected, AUTO resolves
  per BackendSelector rules and returns instance-typed binding. The
  connection string passed to `OdbcAdapter.connect` is `DBQ=<path>` only
  (no `;DRIVER=` clause — that is appended by `OdbcAdapter.connect`).
- FacadeTest: all 51 existing facade tests pass unchanged in BEHAVIOR
  (injection mechanism changes, assertions do not). All `Fakes.*`
  references at lines 90, 102, 406, 473, 526, 630 removed.
- Smoke (env-gated): facade connect/getTables/queryData/disconnect against
  `ACCESS_TEST_DB`. Verifies real adapter wiring end-to-end.
- Structural pattern: `test/FacadeTest.res` existing helpers.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` — 553+ tests, 551+ pass, exactly the 2 known
      failures (no new failures)
- [ ] `grep -n "Fakes" rescript-mcp/src/Services/Facade.res` → no matches
- [ ] `grep -rn "Bindings" rescript-mcp/src/Services/Facade.res
      rescript-mcp/src/Config.res rescript-mcp/src/PathGuard.res` → no matches
      (the composition module is exempt — it IS the root)
- [ ] `rescript-mcp/src/Services/Composition.res` (or design-pinned name)
      exists and exports `realFactory: Facade.bindingFactory`
- [ ] Smoke: with `ACCESS_TEST_DB` + `ACCESS_TEST_ASSUME_ACE=1` set, facade
      round-trip succeeds; without env, skip-clean exit 0
- [ ] SDD artifacts persisted in Engram under `sdd/facade-composition/*`
- [ ] `plans/README.md` status row updated

## STOP conditions

- An adapter method's signature cannot be expressed as a closure field
  (e.g. needs functors/first-class modules) — report; do not force.
- Migrating `FacadeTest.res` breaks more than 5 tests structurally —
  indicates deeper coupling than this plan assumed; report.
- The real-DB smoke reveals adapter bugs — record in findings; fix ONLY if
  trivial (≤2 attempts); otherwise report (they belong to a strict-TDD fix,
  not this plan).
- Instance-type design cannot keep `Facade.res` free of `Bindings/*` imports.

## Maintenance notes

- Plan 007's ReScript driver imports the compiled facade + the composition
  factory from src (NOT from test/). Keep `realFactory` exported and stable.
- Plan 008's MCP composition root reuses this module; do not duplicate
  wiring there.
- Future adapters (COM/DAO instances) add their own `asInstance` producers —
  keep the instance record shapes frozen once landed (they are a seam
  contract); extending them is a new SDD change.
