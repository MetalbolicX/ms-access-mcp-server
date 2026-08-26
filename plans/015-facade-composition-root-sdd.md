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

> **Resume amendment (2026-08-26, post-024/025 consolidation)**:
> Plan 015 is now **resume-only**. The five SDD planning phases
> (explore → propose → spec → design → tasks) are already COMPLETE with
> Engram artifacts that the apply phase must use as ground truth:
>
> | Phase | Engram observation id | Topic key |
> |---|---|---|
> | Explore | #1048 | `sdd/facade-composition-root/explore` |
> | Drift reconciliation | #1050 | `sdd/facade-composition-root/drift` |
> | Explore verification | #1051 | `sdd/facade-composition-root/verify` |
> | Proposal + spec | #1053 | `sdd/facade-composition-root/proposal-spec` |
> | Spec (deep) | #1054 | `sdd/facade-composition-root/spec` |
> | Design | #1055 | `sdd/facade-composition-root/design` |
> | Tasks | #1056 | `sdd/facade-composition-root/tasks` |
>
> **Apply phase executes ONLY T2–T6** (T1 is already committed at
> `8b190f1` and amended by `96afc2d`). The drift reconciliation items
> 1–5 above are RESOLVED. The design corrections 6–7 are RESOLVED in the
> live `rescript-mcp/src/Adapters/Instances.res` on `main`.
>
> **Critical pre-apply note for the executor**: design artifact #1055's
> §1.1 was authored BEFORE plans 022/024/025 reconciled the drift. Two
> type signatures in §1.1 are STALE; the live `Instances.res` on `main`
> is the authority:
>
> 1. `insertData` field type: design §1.1 declares `(string, JSON.t)`;
>    live `Instances.res:34` declares `(string, dict<JSON.t>)`. Use the
>    live shape. The producer closure `(table, data) => insertData(t,
>    table, data)` infers `data: dict<JSON.t>` from the LIVE
>    `OdbcAdapter.insertData` signature; this is correct.
> 2. `exportData` return type: design §1.1 declares `exportResult`;
>    live `Instances.res:38` (and `Interfaces.res:120`) declare
>    `mutationResult`. Use the live shape.
>
> All other field signatures in §1.1 are still authoritative. The
> producer closures in §1.2/§1.4/§1.6 are still authoritative. The
> migration order in §4 (6 commits) is still authoritative for T2–T6.
>
> **Environment (MANDATORY)**: `cmd.exe /c` wrappers for pnpm; fresh
> build requires `rescript clean` + full rebuild. Cached `lib/bs` is not
> evidence. Plan 025's "green" gate was a false positive from cached
> artifacts; plan 024's fresh build exposed `Instances.res:34` drift
> (fixed at `96afc2d`).

## Status

- **Priority**: P1 (hard blocker for plan 007's ReScript parity driver)
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/003, 004, 005, 006 (DONE), 021, 022, 023 (drift
  reconciliation DONE), 024 (consolidation DONE; main is at `5fbe4ed`),
  025 (stale `.mjs` + count-clamp + Instances.res type fix DONE).
  Soft-depends on plan 016 for the final real-DB smoke step (unit work
  is independent).
- **Status note (2026-08-26, post-consolidation)**: SDD phases 1–5
  (explore→propose→spec→design→tasks) are COMPLETE with Engram artifacts
  #1048/#1051/#1053/#1054/#1055/#1056. Apply phase T1 is COMMITTED at
  `8b190f1` (Instances.res added) and amended by `96afc2d` (insertData
  corrected to `dict<JSON.t>`). Apply phases T2–T6 remain pending;
  resume on `main` at `5fbe4ed`. Fresh-build green baseline: **572/572/0
  on main, build 92/92** (verified after plan 024). Plan 015's apply
  phase must preserve that baseline; any new failure is a STOP.
- **Category**: migration
- **Methodology**: SDD (compact, resume-only). Justification: this
  introduces a NEW typed binding surface — value-level adapter instance
  records — consumed by plan 007's parity driver and plan 008's MCP
  composition root. That seam decision is already pinned in Engram
  artifacts #1053–#1056. The 17 public facade operation signatures DO
  NOT change; behavior is already pinned by the 572-test baseline, so
  apply runs strict TDD under a green suite.
- **Planned at**: commit `5fbe4ed` on `main`, 2026-08-26
  (originally planned at `2bbff3a` on 2026-08-25; resumed after
  plans 022/023/025/024 closed the pre-007 gate).

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
  `password` arg. `insertData: (adapter, table, record: dict<JSON.t>)`
  matches `Interfaces.res:116`.
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
- Suite baseline: **572/572/0 on `main` at `5fbe4ed`** (post-plan-024
  fresh-build gate, post-plan-025 stale-`.mjs` + count-clamp fix, and
  post-`96afc2d` Instances.res type correction). Plan 015 must NOT
  introduce new failures or change this baseline downward.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Clean | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && node_modules\.bin\rescript clean"` | exit 0 |
| Build | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp build > rescript-mcp\parity\build-015.log 2>&1"` | exit 0 |
| Unit tests | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test > rescript-mcp\parity\test-015.log 2>&1"` | exit 0, 572/572/0 (no change from main baseline) |
| ODBC integration smoke | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server && pnpm -C rescript-mcp test:integration:odbc"` | skip-clean without env; real run with `ACCESS_TEST_DB` + `ACCESS_TEST_ASSUME_ACE=1` |

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
- The `insertData` signature reconciliation between `Interfaces.res` and
  `OdbcAdapter.res` (already aligned at `dict<JSON.t>` after `96afc2d`; this
  plan derives the instance record from `Interfaces.res` verbatim, which now
  matches the live `OdbcAdapter.insertData`).
- Plan 007 harness code; plan 008 MCP wiring.
- Any pre-existing test changes (the 572/572/0 baseline on `main` is
  frozen; plan 015 must not introduce or fix unrelated failures).
- Python source.

## Git workflow

- Branch: `rescript/015-facade-composition-root`.
- Conventional commits, e.g. `feat(rescript): add adapter instance types and composition root`.

## Steps (SDD stages, compact — RESUME ONLY)

### Stages 1–3: COMPLETE (use existing Engram artifacts)

| Phase | Artifact | Status |
|---|---|---|
| Explore | Engram #1048 (`sdd/facade-composition-root/explore`) | DONE |
| Drift reconciliation | Engram #1050 (`sdd/facade-composition-root/drift`) | DONE |
| Explore verification | Engram #1051 (`sdd/facade-composition-root/verify`) | DONE |
| Proposal + spec (merged) | Engram #1053 (`sdd/facade-composition-root/proposal-spec`) | DONE |
| Spec (deep) | Engram #1054 (`sdd/facade-composition-root/spec`) | DONE |
| Design | Engram #1055 (`sdd/facade-composition-root/design`) | DONE (with two stale type claims superseded by live `Instances.res`; see amendment above) |
| Tasks | Engram #1056 (`sdd/facade-composition-root/tasks`) | DONE (apply playbook for T2–T6) |

The executor MUST read #1055 and #1056 before starting any code change.
The 6-commit migration order in #1055 §4 is authoritative.

### Stage 4: Apply (T2–T6, strict TDD, fresh-build gate)

**Branch**: `rescript/015-facade-composition-root-resume` cut from
`main` at `5fbe4ed`. Branch top after T2–T6 lands at the apply commit;
plan 024's other branches (017/015-T1/021/022/025) are already deleted.

**Six commits in this order** (from #1055 §4):

1. **T2 — instance types + `Adapters.res` registration**:
   `chore(rescript): add Instances.res module with data + schema record types`
   - NOTE: this is the work that was committed at `8b190f1` and amended
     by `96afc2d`. **Verify T1's commit is on `main`**; if yes, this
     commit is **SKIPPED** and T2 starts at step 2 below. The apply
     phase's pre-flight check must confirm: `git log --oneline
     rescript-mcp/src/Adapters/Instances.res | head -2` shows both
     `8b190f1` AND `96afc2d`.

2. **T3 — `asInstance` producers**:
   `feat(rescript): add asInstance producers to OdbcAdapter + Fakes`
   - 4 producers: `OdbcAdapter.asInstance`, `OdbcSchemaReader` is NOT
     modified (consumed only by Composition), `Fakes.FakeOdbcAdapter.asInstance`,
     `Fakes.FakeSchemaAdapter.asInstance` (22 fields).
   - Producer closures use `data: dict<JSON.t>` for `insertData` (matches
     live OdbcAdapter); return `mutationResult` for `exportData` (matches
     live Interfaces.res:120).
   - RED-first: `test/InstancesTest.res` (already exists at 8b190f1 path)
     gets 4 producer-passthrough tests; schema producer test asserts all
     22 fields. The stale `InstancesTest.res.mjs` artifact is already
     deleted (plan 025).

3. **T4 — migrate `FacadeTest.res` injection**:
   `test(rescript): migrate FacadeTest to use instance injection`
   - `makeFakeFactory` (and `badFactory`, readonly facades) construct fakes
     and wrap with `asInstance`. No assertion changes.
   - RED-first: existing facade tests stay green throughout the wrap.

4. **T5 — re-type `Facade.binding` + remove 17 `Fakes.*` references**:
   `refactor(rescript): re-type Facade.binding to instance types; remove Fakes references`
   - Single atomic commit per REQ-CROSS-3 (#1056 atomicity rule):
     `Facade.res` + `FacadeTest.res` change together so suite stays green.
   - Sites: lines 18, 19, 90, 102, 406, 461, 473, 526, 541, 597, 630, 685,
     740, 780, 817, 872, 968 — verify each by re-reading `Facade.res` before
     editing (line numbers drift between sessions).
   - `connectAccess` and the disconnect path drive
     `binding.dataAdapter.connect("DBQ=" ++ dbPath, ~password)` /
     `disconnect()` ONCE per lifecycle (not twice — schema shares the same
     `OdbcAdapter.t` connection).

5. **T6 — `Services/Composition.res`**:
   `feat(rescript): add Services/Composition.res with realFactory + asSchemaInstance`
   - Sole new src module importing adapters + transitively `Bindings`.
   - `asSchemaInstance(dataT: OdbcAdapter.t)` wraps the same `dataT` with
     22 fields; relationship ops (`createRelationship`, `deleteRelationship`)
     delegate to `OdbcSchemaReader` using `dataT.connection` read AT CALL TIME.
   - `realFactory` is `makeRealFactory(~comAvailable=false)`. Connection
     string is `DBQ=<path>` only — `OdbcAdapter.connect` owns the
     `;DRIVER=`/`;PWD=` append.

6. **T7 — env-gated smoke** (renamed T6 in original #1056; sequential):
   `test(rescript): add env-gated smoke for Composition.res`
   - `test/CompositionSmokeTest.res` env-gated via `TsBridge.getEnv`.
   - With `ACCESS_TEST_DB` + `ACCESS_TEST_ASSUME_ACE=1`: connect → getTables
     → queryData → disconnect round-trip asserts all Ok.
   - Without env: skip-clean exit 0.

### Stage 5: Verify

- Fresh build (`rescript clean` + full rebuild) exits 0, 92/92 modules.
- Fresh suite exits 0, **572/572/0** (no change from `main` baseline).
- Grep gates after T5:
  - `grep -n Fakes rescript-mcp/src/Services/Facade.res` → 0 matches
  - `grep -rn Bindings rescript-mcp/src/Services/Facade.res
    rescript-mcp/src/Config.res rescript-mcp/src/PathGuard.res` → 0 matches
    (Composition.res is exempt — it IS the root)
- Smoke: with env, round-trip succeeds; without env, skip-clean exit 0.
- Any new test failure or count regression → STOP, do NOT mark DONE.

### Stage 6: Archive

- Engram `sdd/facade-composition-root/archive-report` (obs 1064's
  follow-up); flip `plans/README.md` row 015 to DONE.
- Final-state handoff to orchestrator: commit hashes, fresh-build gate
  result, grep-gate result, smoke result, any deviations from #1055 (the
  two stale type claims corrected to live Instances.res shapes).
- Delete the resume branch after merge (or leave for chain strategy in
  plan 018's pre-007 wiring).

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

- [ ] Fresh `rescript clean` + full rebuild → `pnpm -C rescript-mcp build` exits 0
- [ ] Fresh `pnpm -C rescript-mcp test` — **572/572/0**, no regressions from `main`
      baseline (`5fbe4ed`); capture actual count if it differs
- [ ] `grep -n "Fakes" rescript-mcp/src/Services/Facade.res` → no matches
- [ ] `grep -rn "Bindings" rescript-mcp/src/Services/Facade.res
      rescript-mcp/src/Config.res rescript-mcp/src/PathGuard.res` → no matches
      (the composition module is exempt — it IS the root)
- [ ] `rescript-mcp/src/Services/Composition.res` exists and exports
      `realFactory: Facade.bindingFactory`
- [ ] T1 already-committed check passes: `git log --oneline
      rescript-mcp/src/Adapters/Instances.res | head -2` shows `8b190f1` AND
      `96afc2d`
- [ ] Smoke: with `ACCESS_TEST_DB` + `ACCESS_TEST_ASSUME_ACE=1` set, facade
      round-trip succeeds; without env, skip-clean exit 0
- [ ] Six commits land in the #1055 §4 order (skip T1 if already on main)
- [ ] SDD archive-report persisted in Engram; `plans/README.md` row 015 → DONE

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
