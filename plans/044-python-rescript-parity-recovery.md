# Plan 044: Recover and Complete Python-to-ReScript Parity

The work is blocked by broken boundary contracts and unreliable verification, not a proven need for another lookup algorithm. First make failures observable, then fix handle representation and ownership, and only then resume live parity. This document is a plan, not evidence that any fix has passed.

## Status

| Field | Value |
|---|---|
| Status | READY FOR REVIEW; not executed |
| Priority | P0 recovery, then P1 completion |
| Effort | L overall, divided into independently verified work units |
| Risk | High for native COM lifetime; low for portable contract tests |
| Category | Correctness, testing, lifecycle, delivery process |
| Planned at | `c8fe6a2`, branch `rescript/038-linked-tables-sql-script`, 2026-09-06 |
| Snapshot caveat | `ComDataAdapter.res` also has an uncommitted 109-addition/109-deletion release sweep |
| Dependencies | Reconcile attempts 040, 042, 043; do not treat their DONE labels as verified prerequisites |

The audit was read-only on source. No build, test, native probe, or parity run was performed for this plan. Citations refer to the observed working tree, not necessarily a clean checkout of the stamped commit.

## Quick Path

1. Preserve the current work and establish the exact migration inventory.
2. Repair the test and harness gates before collecting more live acceptance results.
3. Add failing portable tests for handle identity, returned errors, and production cleanup sequencing.
4. Correct the smallest affected boundary and lifecycle paths; verify database postconditions on isolated copies.
5. Finish skipped/stubbed operations, then pass every in-scope suite three consecutive times without crashes or hidden skips.

Do not run another full COM loop to search for a lucky green result. Do not execute this plan concurrently with another agent changing the same adapter, bridge, or harness.

## Why This Has Taken So Long

The repeated loop has been: change a symptom, obtain a successful response or occasional clean tally, declare a dependency resolved, then discover the underlying defect in the next operation.

The earlier orchestration contributed directly: it skipped the required create/read-back probe, treated a success envelope as proof of an append, called intermittent crashes environmental without controlled evidence, froze the binding layer as correct, and directed index iteration despite the existing native-iteration failure history. It later expanded a surgical release change to 109 sites while still ignoring the returned promises. Commits and plan statuses were accepted despite failed runtime gates.

Operational mistakes added delay: repeated full Windows suites, root-versus-subproject install confusion, incorrect working paths and CLI arguments, and tests rerun without comparing failure identities. These are process failures, not evidence that ReScript or DAO needs a different architecture.

### Prioritized Findings

| ID | Evidence | Impact | Effort | Fix Risk | Confidence |
|---|---|---|---|---|---|
| F1 | `winaxBinding.mts:23-29,74-79`; `ComDataAdapter.res:2784-2789,2929-2937,3029-3037,3094-3099` | Already-enveloped handles are wrapped again; COM operations receive the wrong object | M | Medium | High, static |
| F2 | `Winax.res:271-284`; `ComDataAdapter.res:2791-2817,2897-2908,3091-3122,3189-3190` | Resolved `Error` results are discarded; failed mutations can report success | M | Medium | High, static |
| F3 | `ComSession.res:170-171,181-186,270-322`; ignored adapter release promises | Missing `currentDb` cleanup and inconsistent ordering undermine ownership and shutdown | M | High | High for code; native crash causality unproven |
| F4 | `ComSessionTest.res:104-134`; `ComDdlTest.res:1535-1718` | Selected tests simulate success instead of exercising production behavior; live error branches log without direct failure assertions | M | Low | High |
| F5 | `parity/run.ts:172-205,295-342,398-404` | Nonzero exits with JSON can be accepted; overwritten findings and global process kills weaken evidence and safety | M | Medium | High |
| F6 | `ComDataAdapter.res:2743-2764`; COM DDL skip files; `Server.res:319-391`; `plans/README.md:257-261` | A real empty-success stub and unverified skips remain; facade parity is not full Python feature parity | M-L | Medium | High |
| F7 | Current 109/109 diff; plan and commit history 040-043 | Broad unverified edits and premature completion claims repeatedly invalidate the next investigation | S process work | Low | High |

### Boundary Contract: The First Defect to Prove

All adapter references below are under `rescript-mcp/src/Adapters/`; bridge files are under `rescript-mcp/src/Js/` and `rescript-mcp/src/Bindings/`.

| API | Existing runtime return | Correct caller behavior |
|---|---|---|
| `get` on a COM-valued property | Raw proxy; bridge `getProperty` does not wrap | Wrap once when converting that property to an opaque handle |
| `invokeAsObject` / `getItem` | `comObject` containing `{__p__: proxy}` | Consume the returned handle directly; do not wrap again |
| `VComObject(handle)` conversion | Extracts one envelope level | Native argument must be the original proxy, not another envelope |

`winaxBinding.mts:74-79` explicitly wraps object-returning calls. `Winax.res:293-301` returns that value as `ComInterfaces.comObject`, even where callers misleadingly name it `tdefJson`. In `createLinkedTable`, line 2789 wraps it again. One-level `setProperty` then writes properties onto the inner plain envelope, not the native object. The `VComObject` arm at `Winax.res:125-138` also strips only once.

This proves a representation defect. It does NOT prove whether a particular native `Append` rejected, ignored, or crashed on that argument. Capture that result after fixing F2. Correct callers already exist at `ComDataAdapter.res:484-489`, consuming `getItem` results directly. Relationship/field paths at `2551-2556` and `2587-2595` show the same rewrapping pattern and belong in the bounded audit.

The correct repair is not recursive unwrapping everywhere, arbitrary property probing on callable COM proxies, or treating malformed handles as `JSON.Null`. Preserve one explicit envelope contract and test its boundary.

### Error and Lifetime Contracts

Bindings catch COM exceptions into resolved `Error(...)` values. A subsequent `Promise.then(_ => ...)` still runs. A trailing `Promise.catch` does not handle these typed errors. In recreate, an ignored `Delete` result can lead to `CreateTableDef`; in refresh, an ignored `Connect` assignment result can lead to `RefreshLink`. These are separate functions: recreate does not call `RefreshLink`.

Keep the existing typed `Result` model and explicitly switch on it. Do not redesign every binding around rejected promises merely to repair unchecked call sites.

`ComSession._disconnect` queues `accessApp`, `daoDb`, then `adoConn`, despite its opposite-order comment. It clears `session.currentDb` without release. That database is acquired through `OpenDatabase` at lines 170-171 and released during rollback at 181-186. Graceful shutdown also starts calls without awaiting their results. Establish ownership and aliases before selecting the close/release sequence; adding a nonexistent `session.handles.currentDb` is NOT a fix.

`releaseSyncAwait` returns a promise. Changing a no-op continuation while retaining `->ignore` does not establish an awaited dependency. Conversely, this fact alone does not locate or explain a native assertion. Do not repeat the unsupported claim that `setImmediate`, `nextTick`, or more sleep will drain all necessary work.

### What Is Not Proven

- The exact C++ cause and timing of exit 134 have not been established.
- A matching create response does not prove the table exists or has the requested metadata.
- Aggregate counts such as 787 passed / 12 failed do not identify which tests failed or why; they are not a green gate.
- Historical clean parity runs do not erase intervening crashes. The latest reported target state was 11 matched / 0 mismatched / 2 errored / 2 skipped, not completion.
- `main.mjs` does not control parity child shutdown. `parity/runRescript.ts` imports the facade directly and has its own disconnect/exit path.
- Direct invocation of `runRescript` DOES execute its setup array (`runRescript.ts:379-387`). Previous contrary explanations were wrong.

## Completion Scope

**Acceptance A: declared ReScript facade and adapter parity.** Cover every operation already included in the migration's facade/contracts and harness, for each intended backend. This includes closing `refresh_linked_table`, `recreate_linked_table`, the connected `getLinkedTables` empty-success stub, and `generate_sql`, not just retaining two skips.

**Acceptance B: full Python replacement.** Cover Python's actual registered tools, gating, transports, authentication, and other public behavior. Existing plans defer HTTP/auth/LLM and other exposure; the UI assessment is separate. This recovery plan must inventory those differences and produce ordered follow-on work, not silently expand implementation or label Acceptance A as full replacement.

`Server.res:319-391` registers 12 ReScript tools. The audit counted 143 Python decorator sites across 19 modules; this is NOT a verified runtime registration count. Case count is also not operation coverage. Phase 0 must resolve the actual inventory.

For each row record Python entrypoint and gate, ReScript facade/registration, backend, behavior, positive/negative/postcondition tests, status, evidence, and dependency. Status must distinguish implemented-and-verified, broken, stubbed, intentionally unsupported, deferred, and missing. For Acceptance B gaps, identify the next concrete work unit and its acceptance test. Do not write speculative feature implementations in this recovery change.

## Commands and Safety

Commands below are for a future executor. Run terminal calls with working directory `D:\code\python\ms-access-mcp-server`; do not change directory inside loops. Capture complete output and actual process exit codes, not selected lines containing `Compiled` or `PASS`.

```powershell
git status --short
git diff --numstat
git log --oneline -10
git diff --stat c8fe6a2..HEAD -- rescript-mcp/src rescript-mcp/parity rescript-mcp/test
pnpm -C rescript-mcp build
pnpm -C rescript-mcp lint:cases
pnpm -C rescript-mcp build:parity
pnpm -C rescript-mcp test
```

Build/compile/lint gates require exit 0. Test failures require names, assertions, and classification, not acceptance by unchanged totals. Use `rescript-mcp/package.json` as the actual runner contract; `rescript test` is not the test command. Proposed focused test files and harness filters below do not exist yet; verify the test runner's supported file selection before adding documented scripts.

If test-runner compiled files are missing, use the repository's documented `pnpm -C rescript-mcp clean:all` recovery, not `clean` alone. Capture any failure and diagnose it before reinstalling. Do not delete dependencies, prune global stores, alter global package configuration, or enable install scripts globally. If native rebuilding is genuinely needed, use the existing `.venv\Scripts\python.exe` through a process-local `PYTHON` variable and separately approved recovery steps.

Existing `parity:northwind:com:ddl` and `parity:northwind:ddl` scripts pin the fixture to the repository database. The current runner also fixes `PARITY_SOURCE_DB` to `db/postgres.accdb`. Therefore setting an environment variable alone does not provide complete isolation. Do not use these scripts for recovery acceptance until Phase 1 makes explicit isolated target AND source inputs effective.

Future isolated executions must set absolute paths for `ACCESS_TEST_DB`, `PARITY_SOURCE_DB`, and `ACCESS_MCP_ALLOWED_DIRS`, with `ACCESS_TEST_ASSUME_ACE=1` and `ACCESS_MCP_READONLY=false` only inside the disposable run. Use copied fixtures and a dedicated Windows test account or owned process tree. Never kill all MSACCESS processes on a developer desktop. Never probe mutations against the original northwind/postgres files. Record input hashes and detect accidental mutation; do not auto-delete tables introduced by earlier probes.

## Scope and Git Workflow

Only this plan and its index entry are changed during authoring. Future implementation may touch the adapter, `ComSession.res`, their interfaces, `Winax.res/.resi`, `TsBridge.res`, `winaxBinding.mts`, affected tests, `parity/run.ts`, `parity/runRescript.ts`, `scripts/parity_driver.py`, necessary package scripts, and evidence documentation. Boundary files are NOT presumed correct or prohibited from correction.

Python production behavior is the oracle, not a target to edit until the diff disappears. A demonstrated Python defect needs an explicit contract decision and separate work. No blanket adapter rewrite, recursive compatibility layer, new handle registry, wholesale async conversion, native-addon rewrite, timer workaround, or unrelated transport/UI migration is authorized by this plan.

Inspect dirty work before implementation. Preserve every pre-existing change. Ask the owner how to carry or isolate the 109-site sweep before modifying overlapping hunks; there is no authorization here to discard it. Treat `c8fe6a2` as a failed candidate, not a known-good base. Use separate evidence for committed and dirty candidates. Unrelated concurrent changes are not grounds for reverting them.

Use one reviewable work unit per phase. Commit only when explicitly authorized and after that unit's acceptance passes; stage intended files only. No pushes, PRs, amendments, or history rewrites are part of this plan.

## Execution Phases

### Phase 0: Preserve Evidence and Define the Inventory

1. Record HEAD, branch, dirty diff summary, toolchain versions, and retained results in a recovery ledger. Preserve the patch outside source control if the owner requests it; do not create a second committed copy of source in `plans/`.
2. Map the actual Python registration gates, ReScript registrations, facade methods, and all case directories. Produce `plans/044-inventory.md` during execution, including Acceptance A/B classifications and ordered missing-feature work.
3. Create `plans/044-evidence.md` with observed versus inferred statements. Mark earlier 040/042/043 completion claims unverified where gates failed; distinguish implementation commits from accepted fixes.
4. Obtain disposition for overlapping dirty work and establish an isolated execution context without mutating the originals.

**Verify:** every accepted operation has an inventory row; every retained failure has provenance; the original dirty patch is unchanged. No claimed baseline depends on a lucky run. **STOP:** uncertain ownership of changes or fixtures, missing source fixture, or unexplained environment corruption.

### Phase 1: Make Verification Truthful Before Native Reproduction

1. In `parity/run.ts`, independently record child status, signal, timeout/spawn error, stdout validity, logical result, and skip. Nonzero exit or timeout remains an error even with valid JSON. Retain logical equality separately for diagnosis, never as acceptance.
2. Add portable runner tests: identical JSON plus exit 134 must fail; timeout plus JSON must fail; malformed/missing output must fail; valid zero-exit paired results must pass; unavailable COM must not silently use ODBC. Inspect the Python driver's import/backend fallback and make backend identity explicit.
3. Persist ignored run-ID/case/backend artifacts containing paired envelopes, setup status, phase markers, and redacted stdout/stderr plus exit metadata. Preserve previous runs. Do not publish credentials, connection passwords, database contents, crash dumps, or machine-specific blobs in commits.
4. Add explicit isolated target/source fixture arguments and a documented exact-case selector. Copy both inputs per side as required, preserve path semantics for links, and verify originals' hashes. Remove the acceptance path's dependency on global MSACCESS kills. Keep process cleanup bounded and owned.
5. Expose source/compiled artifact provenance. Phase markers must distinguish setup, native operation, postcondition, disconnect, serialization, and process exit without polluting protocol stdout. Eliminate duplicate priming only after proving that the separate process does not provide required state.

**Verify:** new portable harness tests pass with exit 0; fake crashing children cannot produce a PASS; exact-case selection executes exactly the requested case and no others. **STOP:** fixture isolation or backend identity cannot be established. No live baseline runs before this gate.

### Phase 2: Add Failing Contract Tests Against Production Paths

1. Extend `test/WinaxBindingTest.res` or add proposed `test/ComHandleContractTest.res`. Use an existing injection seam or the smallest test seam needed. Test exactly-one envelope, proxy identity through `invokeAsObject/getItem -> set/get`, and `VComObject -> Append`. Include a callable fake proxy, an ordinary invalid object, and a nested-envelope fixture that exposes the current bug.
2. Extend `test/ComDdlTest.res` or add proposed `test/LinkedTableContractTest.res`. Inject `Error` from every setter, Append, Delete, RefreshLink, and metadata read. Assert failure propagation, no later mutation after failure, and cleanup. Use production adapter functions, not manually reconstructed algorithms.
3. Replace the selected literal-success simulations in `test/ComSessionTest.res` with production `connect/disconnect` calls through fake bindings. Assert acquired handles, rollback, release events, idempotency, aliases, and failure paths. Hold release promises unresolved and prove completion remains pending.
4. Repair logging-only COM test failures and assertion counts. Separate portable tests from explicit capability-gated live tests. Classify existing failures by identity; do not accept all twelve as environmental.

**Verify:** each new test fails on the intended current defect before the fix, not on missing imports or Access availability. Portable tests require no native COM. Record red output. **STOP:** test doubles bypass the production path or cannot detect a deliberately wrong handle/result/order.

### Phase 3: Correct Representation, Results, and Ownership

1. After `invokeAsObject` or `getItem`, use the returned `comObject` directly. The local name `tdefJson` does not change that type. Keep the one required wrap for a raw COM-valued `get` result. Audit all evidenced linked-table and relationship/field rewraps; do not mechanically delete every wrapper.
2. Keep the `VComObject` constructor and establish a checked native-argument contract. An invalid handle must produce a deliberate boundary error rather than silently become `JSON.Null`. Do not add recursive unwrapping or runtime-tag guessing. Update mirrored signatures only if a tested boundary correction requires it.
3. Switch on every relevant `Result` before proceeding. Match Python create/refresh/recreate/unlink and relationship behavior, including attributes and password stripping. Do not add guessed not-found text or a new recreate-existence rule based on earlier unpaired probes.
4. Re-evaluate the speculative index search after pointer identity is correct. Prefer the existing named DAO operation if the controlled probe verifies it; do not add an enumeration workaround to hide a failed append.
5. Document actual ownership: `accessApp`, `daoDb` (inspect whether DBEngine), separately opened `session.currentDb`, and `adoConn` from CurrentProject.Connection. Establish owned versus borrowed handles and aliases. Then chain required closes/releases in dependency-safe order. Include currentDb exactly once where owned; do not Close every proxy indiscriminately.
6. Return/await operation-local cleanup promises and session cleanup. Do not construct a release queue that starts before required work completes. Preserve the primary operation error while reporting cleanup failures. Evaluate the dirty sweep against these tests, not by renaming more release calls.

**Verify:** all Phase 2 red tests now pass; delayed cleanup blocks completion; properties and Append receive the original fake native proxy; fault injection cannot yield success. Build and focused portable tests exit 0. **STOP:** ownership is ambiguous or a change grows into native architecture; gather targeted evidence instead of guessing.

### Phase 4: Prove Native Behavior and Complete the Missing Operations

1. Use Phase 1's exact-case runner on fresh copied target/source fixtures. Compare Python and ReScript setup and main operations in equivalent conditions. Start with create plus independent DAO read-back, then refresh, recreate, unlink, and the affected relationship/field paths.
2. Assert postconditions: created name/source/connect metadata; refreshed link resolves and is queryable; recreated link points to the requested source and preserves the oracle's attributes; unlink removes the link; relationships/fields exist with expected endpoints. Verify after reopening independently when persistence is part of the contract. Use synthetic test credentials to verify password stripping without recording real secrets.
3. If a native assertion persists, stop that hypothesis immediately and retain the last phase, process metadata, and smallest reproducer. A crash is NOT progress or proof Append worked. After two failed hypotheses, obtain a new read-only specialist review of the evidence before another edit. Investigate native code only after envelope, Result, and ownership contracts have passed.
4. Implement the real `getLinkedTables` body. The current connected branch at `ComDataAdapter.res:2752-2759` returns `success: true, linkedTables: []`. Match Python DAO enumeration, fields, filters, and empty/error behavior. Use bounded native traversal with the now-tested handle lifetime; no blanket ban on named access and no speculative MSysObjects fallback.
5. Reproduce and close `generate_sql` under the same strict runner. Derive output, options, and side-effect constraints from the actual Python implementation and case. Verify generated SQL and original-fixture immutability; do not invent a helper/API based on the function name.
6. Unskip each case only after its positive, negative, and postcondition tests pass. A legitimately unsupported ODBC operation must return the oracle's unsupported contract; it is not implemented COM functionality.

**Verify:** targeted children exit 0, both sides meet postconditions, no timeout/crash/suppressed cleanup error occurs, and removed skips have retained evidence. **STOP:** any native crash, false success, setup failure, missing fixture, or source-fixture mutation. Do not proceed by changing volatility fields, success expectations, or skip reasons.

### Phase 5: Full Acceptance and Accurate Handoff

1. Execute every Acceptance A row across portable tests, ODBC and COM parity, and actual MCP registration/stdio smoke tests. Harness facade access alone does not prove a tool is exposed. Record intentionally unsupported outcomes separately from unavailable tests.
2. For the current 15 COM DDL cases, the completion target is 15 matched / 0 mismatched / 0 errored / 0 skipped. Historical ODBC 13 matched / 2 skipped is a starting observation, not a permanent exemption; verify those unsupported contracts or explicitly document their disposition.
3. Require three consecutive fresh-run passes with identical per-case statuses and zero child failures, not the best three from repeated attempts. Include all previously unstable cases and preserve every intervening result. A required capability unavailable in this environment means BLOCKED, not PASS.
4. Obtain independent code and evidence review. Check no Error-as-success, nested handles, ignored required cleanup, unsafe original-fixture access, or crash-as-pass remains in the affected scope.
5. Update the inventory, evidence ledger, findings, and plan statuses using actual commit/run identifiers. Keep historical failed attempts visible. Acceptance A may be marked complete only when its entire matrix passes; Acceptance B remains incomplete until its separately ordered public-feature gaps are delivered and verified.

**Verify:** an independent reviewer can reproduce commands from the ledger and identify the same passing cases, process outcomes, and postconditions. No outstanding in-scope stub or hidden skip remains. **STOP:** any acceptance item is supported only by totals, prose predictions, or unreviewed worker claims.

## Done Criteria

- [ ] Original user/agent work preserved; dirty candidate disposition recorded before overlapping edits.
- [ ] Complete Acceptance A/B inventory with named unsupported/deferred gaps and next work units.
- [ ] Strict harness rejects nonzero/signal/timeout even when output matches; isolated target and source fixtures verified.
- [ ] Production-path handle, Result, and cleanup tests demonstrated red then green.
- [ ] Linked-table and relationship operations have independent database postconditions, not success-envelope checks alone.
- [ ] `getLinkedTables` is not an empty-success stub; `generate_sql` and all required cases are verified without skips.
- [ ] All Acceptance A portable and live gates pass; current COM DDL is 15/0/0/0 in three consecutive fresh runs.
- [ ] No crashes, mismatches, unclassified failures, unsupported-completion claims, or acceptance-by-baseline-count remain.
- [ ] Independent reviewer accepts scope and evidence before any DONE status or authorized delivery commit.

## Maintenance and Limits

This is a correctness and verification audit focused on the migration blockers, not a full security, performance, UI, or native-addon audit. The exact C++ assertion cause remains open. Broader Python feature parity requires the Acceptance B inventory and separate delivery work.

Use current symbol definitions rather than assuming cited line numbers stay fixed. Reconcile historical plans as evidence, not immutable implementation instructions. The next execution unit is Phase 0 followed by portable Phase 1 harness tests, not another worker instructed to make the two live cases green by any means.
