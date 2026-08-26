# Plan 004: COM layer via winax — VBA, forms, macros, versioning (SDD)

> **Executor instructions**: This plan is executed through the repo's SDD
> workflow (openspec), NOT as a direct coding task. Drive an SDD change
> through propose → spec → design → tasks → apply → verify → archive; apply
> follows strict TDD where unit-testable. Use the SDD skills
> (sdd-propose … sdd-archive) if available, else follow `openspec/`
> conventions manually. When done, update this plan's status row in
> `plans/README.md`.
>
> **Prerequisite check (run BEFORE proposing)**: winax has NO prebuilt
> binaries — `pnpm -C rescript-mcp install` will invoke node-gyp and needs
> Visual Studio Build Tools (C++ workload) + Python available. Verify with
> `pnpm -C rescript-mcp add winax` in a throwaway state or check VS Build
> Tools presence first. If the native build cannot run, STOP — everything
> else in this plan is blocked on it.
>
> **Drift check (run first)**:
> `git diff --stat 0b69c82..HEAD -- src/ms_access_mcp/adapters/wincom.py src/ms_access_mcp/adapters/com_dispatcher.py src/ms_access_mcp/adapters/dao.py src/ms_access_mcp/adapters/vba_operations.py src/ms_access_mcp/adapters/ui_operations.py src/ms_access_mcp/adapters/trusted_locations.py src/ms_access_mcp/adapters/versioning_io.py openspec/specs/com-automation openspec/specs/com-thread-safety openspec/specs/win-com openspec/specs/versioning-engine`
> Material changes → reconcile; on mismatch, STOP.

## Status

- **Priority**: P2
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: plans/002-foundation-types-tdd.md, plans/003-odbc-core-sdd.md
- **Category**: migration
- **Methodology**: SDD. Highest-risk phase: the winax FFI surface is
  undocumented territory for this stack, COM threading semantics change
  fundamentally from Python (STA dispatcher thread → single-threaded Node),
  and trusted-location registry access needs a design decision. An
  explore-first SDD change is mandatory; unit tests alone cannot drive FFI
  design against a native COM library. Apply-stage logic that IS pure
  (marshaling, result shaping) is strict TDD.
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

Everything ODBC cannot do lives here: VBA module read/write/compile/execute,
forms and reports (create/open/properties/controls), macros, database
properties, compact/repair, copy/backup/restore, and versioning
export/import. Python implements this in `adapters/wincom.py` (~1800 LOC)
plus helpers, all serialized through an STA dispatcher thread
(`com_dispatcher.py`). The user decision (recorded): use the **winax**
native module (node-activex) for in-process COM IDispatch — true 1:1 with
pywin32. This is the phase that makes the migration a full replacement
rather than a data-only subset.

## Current state

- Python oracle files (see drift check for the full list): the big ones are
  `wincom.py` (WinComAdapter), `com_dispatcher.py` (STA thread),
  `vba_operations.py`, `ui_operations.py`, `trusted_locations.py`,
  `versioning_io.py`.
- Existing openspec specs to build on: `openspec/specs/com-automation`,
  `openspec/specs/com-thread-safety`, `openspec/specs/win-com`,
  `openspec/specs/versioning-engine`.
- Adapter conventions established by plan 003:
  `rescript-mcp/src/Adapters/Interfaces.res` module types, `Errors.t`
  mapping, Promise-based API.

### Interface surface to port (interfaces.py)

`IVbaAdapter`: get_modules, module_exists, create_module, delete_module,
rename_module, get_vba_code, set_vba_code, add_vba_procedure, compile_vba,
save_database, vba_list_procedures, vba_get_procedure, vba_replace_procedure,
export_module_to_text, get_vba_module, save_vba_module, execute_vba,
get_vba_references, add_vba_reference

`IFormAdapter`: get_forms, form_exists, create_form, rename_form,
delete_form, open_form, close_form, get/set_form_property(ies),
get/set_form_section_property(ies), get_reports, report_exists,
create_report, rename_report, delete_report, get/set_report_property(ies),
get/set_report_section_property(ies), export_form_to_text,
import_form_from_text, export_report_to_text, import_report_from_text,
get_form_controls, export_form_to_html, get/set_control_property

`IMacroAdapter`: get_macros, macro_exists, create_macro, rename_macro,
delete_macro, run_macro, get_macro_properties, export_macro_to_text

`IControlAdapter`: add_control, remove_control, set/get_control_property(ies),
get_control_event_procedures, set_control_event_procedure,
add/remove_report_control, get_report_controls,
get/set_report_control_property(ies), get_controls, set_control_source

`IDatabasePropertiesAdapter`: get_database_properties, set_database_property

`IVersioningAdapter`: export_all_versioning, import_all_versioning,
compare_versioning, export_schema_ddl, export_query_to_text,
import_query_from_text, compact_repair, copy_database, export_database,
import_database, create_backup, restore_backup

(Signature details: authoritative in `src/ms_access_mcp/adapters/interfaces.py`.)

### winax facts (verified)

- npm package `winax` 3.6.x, repo https://github.com/durs/node-activex —
  Windows COM bindings (ActiveX/OLE/IDispatch), installs via node-gyp
  rebuild (NO prebuilds), MIT.
- Its README/examples define the exact API for creating COM objects — the
  SDD explore stage MUST read it and pin the binding surface before
  spec'ing anything else.
- Target COM object: `Access.Application` (same as Python's
  `win32com.client.Dispatch("Access.Application")`).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install with native build | `pnpm -C rescript-mcp install` | exit 0 (node-gyp builds winax) |
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit tests | `pnpm -C rescript-mcp test` | all pass |
| COM integration tests | `pnpm -C rescript-mcp test:com` | pass on Windows w/ MS Access; skip elsewhere |

## Suggested executor toolkit

- SDD skills (sdd-explore first — this phase needs exploration before
  proposal), then sdd-propose → sdd-spec → sdd-design → sdd-tasks →
  sdd-apply → sdd-verify → sdd-archive.
- node-activex README + tests: https://github.com/durs/node-activex
- Python COM behavior oracle: `wincom.py` + openspec specs listed above.

## Scope

**In scope**:
- `openspec/changes/rescript-com-core/**` (SDD artifacts)
- `rescript-mcp/src/Bindings/Winax.res` (FFI layer ONLY)
- `rescript-mcp/src/Adapters/WinComAdapter.res`
- `rescript-mcp/src/Adapters/VbaOperations.res`, `UiOperations.res`,
  `TrustedLocations.res`, `VersioningIo.res` (ports of the Python helpers)
- `rescript-mcp/package.json` (+`winax` dep, +`test:com` script)
- `rescript-mcp/test/**` unit + `rescript-mcp/test/com-integration/**`

**Out of scope**:
- ODBC data/schema operations (plan 003), pooling (plan 005), facade
  (plan 006), MCP (plan 008).
- DAO adapter (`adapters/dao.py`) — only port if the SDD spec finds
  WinComAdapter cannot cover a data/schema operation ODBC misses; record
  the decision either way.
- HTTP transport/auth/telemetry.

## Git workflow

- Branch: `rescript/004-com-core`.
- Conventional commits, e.g. `feat(rescript): bind winax Access.Application`.

## Steps (SDD stages with gates)

### Stage 0: Explore (gate: binding surface memo)

Spike (timeboxed, discardable): from node-activex README + a scratch script,
determine and memo: how to instantiate `Access.Application`, read/write
properties, call methods with args, handle COM errors, and whether method
calls are synchronous. Verify MS Access (or its runtime) is installed.

### Stage 1: Propose

SDD change `rescript-com-core`. Intent: full COM capability parity via
winax. Record the threading model decision: Node's single main thread
replaces Python's STA dispatcher thread — every winax call is naturally
serialized; `com_dispatcher.py` has NO ReScript counterpart (document this
in the design doc).

### Stage 2: Spec (gate: behavioral spec with scenarios)

MUST pin, with scenarios:
1. Winax binding surface (from Stage 0 memo): object creation, property
   get/set, method invocation, error capture → `Errors.t`.
2. Per-operation scenarios for every method in the interface surface above,
   matching Python input/output dict shapes (explore `wincom.py` for each).
3. VBA execution semantics: `execute_vba(function_name, *args)` arg
   marshaling (string/int/bool at minimum, matching Python) and return
   value unmarshaling.
4. `compact_repair(action, source_path, dest_path, keep_original)` exact
   behavior incl. temp-file handling.
5. Trusted locations: registry read/write design decision (winax
   `WScript.Shell`? PowerShell child process? spec must choose and record
   — `trusted_locations.py` is the oracle).
6. COM error taxonomy: COMException → Errors.t mapping, including
   "Access is busy" / modal-dialog hangs — record a timeout policy if
   Python has one.
7. Database open/close lifecycle: when `Access.Application` is created vs
   reused, `OpenCurrentDatabase`/`CloseCurrentDatabase` semantics,
   `Visible=False`, `AutomationSecurity` settings — mirror `wincom.py`.

### Stage 3: Design

`Bindings/Winax.res` is the ONLY module importing `winax`. Adapter module
implements the plan-003 `Interfaces.res` module types. Marshaling layer
(ReScript values ↔ COM variants) as its own module for unit-testability.

### Stage 4: Tasks

Sized for TDD cycles; marshaling/result-shaping tasks are unit-TDD'able
with fakes; FFI-correctness tasks are integration-verified.

### Stage 5: Apply (strict TDD where unit-testable)

- Unit (fake winax binding): marshaling both directions, result dict
  shaping, error mapping, arg-name/property-name string building.
- Integration (`test:com`, Windows + MS Access installed, gated like
  Python's `com_integration` marker): create db fixture via
  `create_access_database` equivalent, VBA module round-trip, compile,
  execute_vba echo function, form create/get_properties/export_to_text,
  macro create/run, compact_repair round-trip, backup/restore.

### Stage 6: Verify

- `pnpm -C rescript-mcp test` green (unit).
- On Windows with MS Access: `pnpm -C rescript-mcp test:com` green;
  elsewhere skips cleanly, exit 0.
- Manual smoke: a scratch script opens the `ACCESS_TEST_DB` fixture via
  COM, runs `execute_vba("Now")` (or a trivial function), closes.

### Stage 7: Archive

Sync artifacts; update `plans/README.md`.

## Test plan

- Unit: marshaling cases (string, int, float, bool, null, array, nested),
  error mapping cases, each operation's dict shaping (happy + error).
- Integration: the lifecycle + capability cases in Stage 5, each mirroring
  a Python `com_integration` test where one exists.
- Structural pattern: `test/ConfigTest.res` for unit; Python
  `tests/integration/` for COM cases.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] SDD change archived
- [ ] `pnpm -C rescript-mcp build` exits 0 (winax installed)
- [ ] `pnpm -C rescript-mcp test` exits 0
- [ ] `Bindings/Winax.res` is the only file importing `winax`
- [ ] On Windows+Access: `test:com` passes; elsewhere skips with exit 0
- [ ] VBA round-trip proven: create module → set code → compile → execute
- [ ] `plans/README.md` status row updated

## STOP conditions

- winax native build fails (missing VS Build Tools/Python) — report the
  node-gyp log; do NOT vendor binaries or switch COM strategies.
- Stage 0 spike cannot create `Access.Application` (missing Access
  runtime) — report; the phase is blocked, not the whole migration (003
  and 005 proceed).
- Any COM operation's Python behavior is undeterminable from `wincom.py`.
- A COM call hangs > 60s in integration tests — report; do not add
  arbitrary timeouts without spec'ing the policy.

## Maintenance notes

- COM object lifecycle bugs surface as zombie `MSACCESS.EXE` processes —
  integration tests must kill/verify process cleanup; note this in the
  design doc's risks section.
- If winax proves unmaintainable later, the fallback is a PowerShell
  bridge — the `Bindings/Winax.res` isolation is what makes that swappable.
