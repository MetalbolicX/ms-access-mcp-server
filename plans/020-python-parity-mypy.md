# Plan 020: Type-check the Python parity driver with mypy strict (test-infra upgrade)

> **Executor instructions**: This plan adds `mypy --strict` to the parity
> harness Python side and fixes any type errors it surfaces. Symmetric to
> plan 019 (JS side) and plan 015 (ReScript facade instance typing).
> Behavior is preserved: same JSON envelopes, same fixture contract, same
> per-case env. NO product behavior changes. When done, update this plan's
> status row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git status` must be clean (ignore `rescript-mcp/test/mjs_list.txt`,
> `tests/integration/fixtures/*.accdb`, `.atl/*`, `led.out`, `nul`).
> `git log -1 --oneline` on `main` must be `dc5fbdb` or later.
> If `main` is ahead with non-trivial changes, STOP and report.

## Status

- **Priority**: P2 (production-grade test infra; not blocking parity coverage)
- **Effort**: S
- **Risk**: MED — a botched typing pass can break the parity driver and
  flip `pnpm parity`. Add types in small commits, gate each commit with
  parity 17/17/0 and the ReScript test suite 678/0.
- **Depends on**: plan 019 (parity harness is now typed TS on the JS side);
  plan 016 (runner harness re-registered); plan 009 (UI assessment closed).
- **Category**: tests (verification infra upgrade)
- **Methodology**: NEITHER — behavior-preserving tooling upgrade; no new
  product behavior, no new contract. The existing parity harness is the
  behavioral gate for each commit.
- **Planned at**: branch cut from `main` @ `dc5fbdb`, 2026-08-28

## Why this matters

The parity driver is the Python half of the differential harness: every
mutating ReScript facade op is matched against `parity_driver.py`'s
JSON output. Plan 019 typed the JS side; the Python side is currently
untyped (`dict`, `Any`, no return-type annotations). A rename of
`OdbcAdapter.execute_query` to return a dataclass would silently pass
through `dict.get(...)` calls at runtime. Type-safe Python gives the same
drift-detection guarantee that mypy gives every other typed Python
project.

## Current state (verified 2026-08-28 on `main` @ `dc5fbdb`)

- `rescript-mcp/scripts/parity_driver.py` exists (~487 lines): the
  Python-side runner for the parity harness. Imports
  `ms_access_mcp.adapters.odbc.OdbcAdapter`.
- `rescript-mcp/scripts/inventory_fixture.py`: small helper from plan 016.
  Optional inclusion in the type-check surface (recommended: include; it
  shares the same environment assumptions).
- No `mypy.ini`, no `pyproject.toml` (for rescript-mcp), no `mypy`
  dependency installed yet.
- `.venv\Scripts\python.exe` is the validated interpreter; `uv` is not on
  PATH (per project AGENTS.md).
- ReScript suite baseline: 678 tests / 678 passed / 0 failed.
- Parity baseline: 17 cases / 17 matched / 0 mismatched / 0 errored.
- Plan 019 establishes the symmetric JS-side workflow and tooling layout.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install mypy | `.venv\Scripts\python.exe -m pip install mypy` | exit 0 |
| Type-check scripts | `.venv\Scripts\python.exe -m mypy --strict rescript-mcp/scripts/parity_driver.py rescript-mcp/scripts/inventory_fixture.py` | exit 0, no errors |
| ReScript build | `pnpm -C rescript-mcp build` | exit 0 |
| ReScript tests | `pnpm -C rescript-mcp test` | 678 / 678 / 0 |
| Parity | `cmd.exe /c "cd /d D:\code\python\ms-access-mcp-server\rescript-mcp && set ACCESS_TEST_ASSUME_ACE=1 && set ACCESS_TEST_DB=D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb && pnpm parity"` | 17 matched / 0 mismatched / 0 errored |

## Suggested executor toolkit

- **Targeted type fixes** over blanket `# type: ignore`. Use `# type:
  ignore[code]` with a one-line comment explaining why, only when a
  library's types are wrong or a legacy signature cannot change without
  product impact.
- **Dataclasses or TypedDict** for adapter envelopes if it cleans up
  annotations. Do NOT change `OdbcAdapter` public method signatures —
  that ripples into the MCP layer. Allowed: local wrappers that
  re-annotate the adapter's dict envelopes.
- **`cast()`** for the few cases where we genuinely know more about a
  return value than the type system can infer.
- **Run mypy early and often** during typing; running after every 20–30
  line change is cheaper than running at the end.

## Scope

**In scope**:
- `rescript-mcp/scripts/parity_driver.py` — full strict mypy pass.
- `rescript-mcp/scripts/inventory_fixture.py` — same.
- `rescript-mcp/mypy.ini` (new) — strict config with sane overrides
  (e.g., allow `import untyped` for adapter modules if necessary).
- `rescript-mcp/pyproject.toml` (new, optional) — `mypy` dependency
  pinned to a tested version.
- `rescript-mcp/package.json` — add `"parity:types"` pnpm script that
  invokes the documented mypy command. Optionally add it to the same
  hygiene script that runs before `pnpm parity`.
- `rescript-mcp/parity/README.md` — note mypy gate alongside the TS
  build.
- `rescript-mcp/parity/findings.md` — append a one-line note in change
  history: `parity driver typed with mypy strict; baseline re-verified`.
- `plans/README.md` — flip row 020 → DONE.

**Out of scope**:
- ReScript code (already typed by plan 015/019).
- `src/ms_access_mcp/` — Python source. The driver's imports use these
  modules, but typing changes to them risk breaking the MCP server or
  tests; the mypy config must tolerate untyped module imports (e.g.,
  `follow_imports = skip` for `src/ms_access_mcp/**`).
- Adapter signature changes.
- Plan 016 integration-runner changes (those are documented Access/ODBC
  limitations, not typing).

## Git workflow

- Branch: cut from `main` @ `dc5fbdb` (or later), named
  `rescript/020-parity-mypy`.
- Conventional commits, one per logical step. Do NOT rebase once landed.

## Steps

### Step 1: toolchain + config

- Add `rescript-mcp/mypy.ini` with strict mode plus documented overrides
  for untyped source (`src/ms_access_mcp`).
- Add `rescript-mcp/pyproject.toml` with `mypy` dev dependency.
- `.venv\Scripts\python.exe -m pip install mypy`.
- Verify: `.venv\Scripts\python.exe -m mypy --version`.

**Verify**: mypy is callable and reports its version.

### Step 2: parity_driver.py typing

- Annotate every function signature and return type.
- Replace `dict` parameters with `TypedDict` or dataclass envelopes where
  the schema is fixed.
- Annotate local helpers and the module-level `Any` import.
- Aim for zero errors with `--strict`.

**Verify**:
- `mypy --strict parity_driver.py` → exit 0.
- `pnpm -C rescript-mcp build` → exit 0.
- `pnpm -C rescript-mcp test` → 678 / 678 / 0.
- `pnpm -C rescript-mcp parity` → 17 matched / 0 mismatched / 0 errored.

### Step 3: inventory_fixture.py typing

- Same treatment as Step 2.

**Verify**: same gates as Step 2.

### Step 4: package.json + README

- Add `"parity:types": "python -m mypy --strict scripts/parity_driver.py scripts/inventory_fixture.py"` (using `.venv\Scripts\python.exe`).
  Note: package.json scripts on Windows can call `python` if the venv is
  active; alternatively use the absolute venv path. The repo's
  documented pattern is `.venv\Scripts\python.exe` per AGENTS.md.
- Update `rescript-mcp/parity/README.md` to mention the mypy gate.

**Verify**: `pnpm parity:types` from a clean checkout runs end-to-end.

### Step 5: findings + status

- Append one-line note to `rescript-mcp/parity/findings.md`.
- Update `plans/README.md` row 020 → DONE.

## Test plan

- `mypy --strict parity_driver.py inventory_fixture.py` exits 0.
- `pnpm -C rescript-mcp build` exits 0.
- `pnpm -C rescript-mcp test` 678 / 678 / 0.
- `pnpm -C rescript-mcp parity` reproduces 17 / 17 / 0.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `mypy --strict` exits 0 on the documented scripts.
- [ ] `rescript-mcp/mypy.ini` exists with strict mode.
- [ ] `rescript-mcp/pyproject.toml` declares mypy dev dependency.
- [ ] `pnpm parity:types` is runnable.
- [ ] ReScript suite and parity baseline unchanged at every commit.
- [ ] `plans/README.md` row 020 → DONE.

## STOP conditions

- `mypy --strict` surfaces > 20 errors at any step → STOP; the driver may
  have deeper typing gaps that need a small refactor before re-running.
  Record the errors in `rescript-mcp/parity/findings.md` and ask for a
  refactor exception.
- Any commit flips `pnpm parity` from 17 / 17 / 0 → STOP; revert and
  re-derive annotations.
- Adapting `OdbcAdapter` types would require changes in product code →
  STOP; keep types local to the driver instead.
- The pip install fails or `mypy --version` reports < 1.0 → STOP and
  report; mypy 1.x is required for `--strict` semantics that match
  plan 019's TS strictness.

## Maintenance notes

- If the parity harness grows new Python helpers, extend mypy coverage in
  the same commit that adds them.
- If `src/ms_access_mcp/` ever becomes typed, the
  `follow_imports = skip` override can be removed.
- Plan 020 is the Python-side symmetric counterpart to plan 019 (JS) and
  plan 015 (ReScript). Together these three plans ensure that all three
  implementations of the parity harness are type-checked at the strict
  level.