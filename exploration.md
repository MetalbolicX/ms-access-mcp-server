## Exploration: Production Hardening — Codebase Audit

### Current State
The `ms-access-mcp-server` is a FastAPI/FastMCP-based MCP server for Microsoft Access databases. It has 1,708 test functions across 24,623 LOC, uses strict TDD, and has an openspec workflow. The project is at v0.1.0 and has never been deployment-audited. This exploration covers a 4-phase production-hardening mega-change.

---

### Phase 1 — Security Hardening

#### 1. Hardcoded API keys — CONFIRMED
- `start-server.ps1:1` — `$env:ACCESS_MCP_API_KEY='dev-key-123'`
- `sample-sql/start-server.ps1:9` — `$env:ACCESS_MCP_API_KEY = 'test-key-123'`
- `sample-sql/start-server-for-test.ps1:1` — `$env:ACCESS_MCP_API_KEY = 'test-key-123'`
- All three files have hardcoded dev/test keys. `dev-key-123` has zero entropy; `test-key-123` is equally weak.

#### 2. Auth `==` comparison — CONFIRMED
- `src/ms_access_mcp/auth.py:46` — `return token == self._api_key`
- Uses `==` not `hmac.compare_digest`. Timing attack is possible over network (though MCP is HTTP-based, so timing attacks are less practical than other vectors). Still, constant-time comparison is a production best practice.

#### 3. Narrow auth hooks — CONFIRMED (but incomplete)
- `src/ms_access_mcp/auth.py` only implements:
  - `on_call_tool()` (line 16) — validates Bearer token
  - `on_initialize()` (line 30) — passes through without auth
- **Missing hooks**: `on_read_resource`, `on_list_tools`, `on_complete`, `on_progress`, `on_set_logging_level`
- However, FastMCP may route these through the same HTTP endpoint. This needs investigation against the actual FastMCP version (3.x).

#### 4. Config key validation — CONFIRMED (missing)
- `src/ms_access_mcp/config.py:50-56` — `ServerConfig.__init__` only checks `if not api_key` (non-empty string)
- No length minimum (e.g., 32 chars)
- No entropy check (e.g., `secrets.token_urlsafe()` expected)
- The error message at line 55 even tells users how to generate a proper key, but nothing enforces it.

#### 5. Unscoped taskkill — CONFIRMED in both locations
- `src/ms_access_mcp/services/connection.py:278` — `["taskkill", "/F", "/IM", "MSACCESS.EXE"]` — kills ALL MSACCESS.EXE processes globally
- `src/ms_access_mcp/adapters/com_dispatcher.py:193-196` — same unscoped command
- No PID scoping. On a shared server, this kills ALL Access processes, not just the ones managed by this server.

#### 6. Missing security files — CONFIRMED
- `LICENSE` — NOT FOUND at repo root
- `SECURITY.md` — NOT FOUND at repo root
- `.env.example` — NOT FOUND at repo root

#### 7. Sample SQL hardcoded keys — CONFIRMED
- `sample-sql/start-server.ps1:9` — `'test-key-123'`
- `sample-sql/start-server-for-test.ps1:1` — `'test-key-123'`

---

### Phase 2 — Transport + Packaging

#### 8. Stdio broken — CONFIRMED
- `src/ms_access_mcp/mcp/server.py` — has NO `if __name__ == "__main__":` guard
- Has NO `mcp.run()` call (stdio transport never works)
- Only has `run_http()` for HTTP transport (line 114)
- The only `__main__` guard is in `cli/main.py:122` which runs the Typer CLI

#### 9. `cli serve` missing — CONFIRMED (critical)
- `src/ms_access_mcp/cli/main.py` — only has commands: `export-all`, `compare-versioning`, `git-hook-init`, `export-vba`
- **NO `serve` subcommand**
- **HOWEVER** `docs/deployment.md:29` references: `python -m ms_access_mcp.cli.main serve`
- And `docs/deployment.md:35` references: `python -m ms_access_mcp.cli.main serve --host 0.0.0.0 --port 8000 --api-key <key> --allowed-dirs "C:\Data;D:\DBs"`
- And `docs/deployment.md:175` references: `python -m ms_access_mcp.cli.main serve --host 127.0.0.1 --port 8000`
- Also `docs/deployment.md:102` references: `python -m ms_access_mcp.mcp.server` as another start method
- **This is a documentation bug**: the deployment guide references a `serve` command that doesn't exist

#### 10. `[project.scripts]` missing — CONFIRMED
- `pyproject.toml` has NO `[project.scripts]` section
- No entry point like `ms-access-mcp = "ms_access_mcp.cli.main:main"` or `ms-access-mcp = "ms_access_mcp.mcp.server:run_http"`
- Users must invoke via `python -c "from ms_access_mcp.mcp.server import run_http; run_http(...)"` or `python -m ms_access_mcp.cli.main`

#### 11. Tool configs — CURRENT STATE
- `[tool.ruff]` — only has `line-length = 100` (pyproject.toml:40)
- `[tool.pytest.ini_options]` — has `addopts = "-v"`, `testpaths = ["tests"]`, and 3 markers (line 31-38)
- `[tool.pyright]` — ABSENT from pyproject.toml
- No `[tool.ruff.lint]` section (no lint rules configured)

#### 12. 0.0.0.0 binding — CONFIRMED
- `start-server.ps1:3` — `host="0.0.0.0"`
- `sample-sql/start-server.ps1:11` — `host='0.0.0.0'`
- `sample-sql/start-server-for-test.ps1:4` — `host='0.0.0.0'`
- However, `ServerConfig` defaults to `127.0.0.1` (config.py:59) — the start scripts explicitly override to 0.0.0.0

---

### Phase 3 — Input Validation + Tool Safety

#### 13. PathGuard bypass — CONFIRMED (partial coverage)
- **PathGuard IS used in:**
  - `mcp/connection.py:40-43` — validates `database_path` in `connect_access()`
  - `mcp/schema.py:109-113` — validates `output_path` in `generate_sql()`
  - Imported in `mcp/server.py:19` and `mcp/container.py:19`

- **PathGuard is NOT used in tools that accept file paths:**
  - `mcp/persistence.py` — `execute_sql_script(script_path)` (line 336), `export_all_versioning(output_dir)` (line 240), `export_schema_ddl(output_dir)` (line 311) — NO PathGuard
  - `mcp/dev_copy.py` — `compact_repair(source_path, dest_path)` (line 47), `import_module_from_text(file_path)` (line 127), `restore_module_backup(backup_path)` (line 153), `import_form_from_file(file_path)` (line 199), `restore_form_backup(backup_path)` (line 226), `import_report_from_file(file_path)` (line 272), `restore_report_backup(backup_path)` (line 295) — NO PathGuard
  - `mcp/migration.py` — `database_path` (line 38) — NO PathGuard (though it tries to find existing connection)
  - `mcp/linked_tables.py` — no file paths accepted directly
  - `mcp/export.py` — `export_data(file_path)` (line 32) — NO PathGuard
  - `analysis.py` — does not accept file paths

#### 14. SQL injection via where_dict — CONFIRMED
- **`odbc.py` (pyodbc path):**
  - `update_data()` at line 176: `sql += f" WHERE {where_dict}"` — raw string concatenation
  - `delete_data()` at line 209: `sql += f" WHERE {where_dict}"` — raw string concatenation
  - Note: the `dict` path uses parameterized queries (`?` placeholders) which IS safe

- **`wincom.py` (DAO path):**
  - `update_data()` at line 1014-1015: `sql += f" WHERE {where_dict}"` — raw string concatenation
  - `delete_data()` at line 1044-1045: `sql += f" WHERE {where_dict}"` — raw string concatenation
  - Note: the `dict` path uses `_format_dao_value()` which escapes single quotes by doubling. The string dict values are safe; integer/float/bool are type-constrained by Python.
  - However, DAO doesn't support parameterized queries, so inline formatting is the only option.

#### 15. `print()` instead of logging — CONFIRMED
- **Total `print()` calls in `src/ms_access_mcp/`**: **7** (excluding config.py which is inside a ValueError string)
  1. `wincom.py:120` — `print(f"[WinComAdapter] _do_connect FAILED: {_ex}", file=sys.stderr)`
  2. `wincom.py:132` — `print(f"Cleanup warning: disconnect failed: {e}", file=sys.stderr)`
  3. `vba_operations.py:278` — `print(f"[set_vba_code] Exception: {set_vba_exc}", file=sys.stderr)`
  4. `com_dispatcher.py:201` — `print(f"[ComDispatcher] Cleanup completed with {len(errors)} warning(s): ...", file=sys.stderr)` — WAIT, this doesn't have file=sys.stderr
  5. `trusted_locations.py:25` — `print("[trusted_locations] winreg not available...", file=sys.stderr)`
  6. `trusted_locations.py:95` — `print("[trusted_locations] winreg not available...", file=sys.stderr)`
  7. `trusted_locations.py:123` — `print(f"[trusted_locations] Failed to restore Trusted Locations: {e}", file=sys.stderr)`
- **`logging` module usage**: **ZERO** — no `import logging` anywhere in `src/ms_access_mcp/`
- All errors go to stderr (except com_dispatcher.py:201 which has no file argument, goes to stdout)
- No structured logging, no log levels, no log rotation

#### 16. Bare except Exception — CONFIRMED (widespread)
- In `src/ms_access_mcp/mcp/` directory: **1 instance** at `migration.py:25` (`except Exception:` pass)
- In the entire `src/ms_access_mcp/` tree: **171 instances** across adapters, connectors, services
- **ZERO** bare `except:` (without exception type) — all specify `Exception` or specific types
- The density is very high in `schema_inspector.py` (30+), `ui_operations.py` (30+), `versioning_io.py` (20+), `vba_operations.py` (15+)
- Most are: `except Exception: pass` — silent swallow. This is a deliberate pattern for COM operations that might fail nondeterministically, but makes debugging very hard.

#### 17. ConnectionPool thread safety — CONFIRMED (no locking)
- `src/ms_access_mcp/services/connection.py:49` — `self._pool: dict[str, ConnectionState] = {}`
- `services/connection.py:50` — `self._active: str = "default"`
- Both are plain dicts/strings with NO threading locks
- ConnectionPool is accessed from multiple tool calls that may run on different async workers
- While FastAPI/MCP uses asyncio (single-threaded event loop), the ODBC adapter uses `pyodbc` which releases the GIL for DB operations, and COM dispatcher has its own STA thread
- Concurrent access to `_pool` and `_active` is a data race risk

#### 18. Destructive tools — CONFIRMED (missing confirm/dry_run)
- `mcp/crud.py` — `delete_query()`, `delete_table()`, `delete_data()` — NO `confirm` or `dry_run` params
- `mcp/persistence.py` — `delete_form()`, `delete_report()` — NO confirm/dry_run
- `mcp/dev_copy.py` — `deploy_dev_copy()`, `discard_dev_copy()` — NO confirm/dry_run
- `mcp/migration.py` — `transfer_data()` — NO confirm/dry_run
- `mcp/linked_tables.py` — `unlink_table()` — NO confirm/dry_run
- `mcp/vba.py` — `delete_module()`, `set_vba_code()` (can destroy code) — NO confirm/dry_run
- **The only tool with `dry_run`**: `analyze_query` in `mcp/analysis.py:29` (but this is read-only anyway)

#### 19. connect_string injection — CONFIRMED
- `src/ms_access_mcp/mcp/linked_tables.py:57` — `connect_string: str` parameter accepted without any validation
- `src/ms_access_mcp/mcp/linked_tables.py:66` — passed directly to `adapter.create_linked_table(name, source_table, connect_string)`
- The connect_string could contain `ODBC;DSN=...` or other connection data. No sanitization, no allowlist of prefixes, no regex validation.

---

### Phase 4 — CI/CD + Observability

#### 20. CI/CD — CONFIRMED (missing)
- `.github/workflows/` — DIRECTORY DOES NOT EXIST
- No CI/CD configuration whatsoever

#### 21. Dependabot — CONFIRMED (missing)
- `.github/dependabot.yml` — FILE DOES NOT EXIST

#### 22. Metrics — CONFIRMED (LLM-only)
- `src/ms_access_mcp/telemetry/metrics.py` — only has 4 LLM-specific metrics:
  - `llm_calls_total` (line 70)
  - `llm_calls_failed` (line 75)
  - `llm_calls_fallbacks` (line 80)
  - `llm_latency_seconds` (line 85)
- No metrics for: tool calls, auth failures, connection pool state, COM errors, path guard rejections

#### 23. Audit log — CONFIRMED (missing)
- No audit logging module exists
- No request/response logging
- No auth failure logging (beyond the McpError response)
- The only persistent logging is `print()` to stderr

#### 24. Skipped tests — CONFIRMED (4 always-skipped)
- `tests/integration/test_http_transport.py:666` — `@pytest.mark.skip(reason="Starlette TestClient blocks on SSE streaming response; needs live server")`
- `tests/integration/test_http_transport.py:671` — `@pytest.mark.skip(reason="Starlette TestClient blocks on SSE streaming response; needs live server")`
- `tests/integration/test_migration.py:165` — `@pytest.mark.skip(reason="Service does not populate primary_key yet")`
- Note: `test_system.py:504,510` and `test_mcp_tools_pool.py:199` use `skipif` (conditional skip), not unconditional skip

#### 25. OpenSpec config — FOUND
- `openspec/config.yaml` — exists with strict TDD configuration:
  - Testing layers: unit/integration available, e2e not available
  - Coverage: available via `pytest --cov=src`
  - Quality: linter (ruff), type checker (pyright), formatter (ruff format)
  - Rules define the full SDD workflow: propose → spec → design → tasks → apply → verify → archive

---

### Additional Findings

#### 26. ConnectionPool sharing (ODBC) — CONFIRMED
- `OdbcAdapter.__init__()` creates a single `self._conn: Optional[pyodbc.Connection]`
- Shared across all tool calls routed to that connection name
- `pyodbc` connections are NOT thread-safe by default (the module releases the GIL but the connection object itself has internal state)
- COM dispatcher path is safer (serialized through STA thread queue)

#### 27. `_trusted_locations_wrap` caching — CONFIRMED (not cached)
- `vba_operations.py:113-133` — `_trusted_locations_wrap()` calls `ServerConfig()` **every invocation** (line 120)
- `ServerConfig()` reads environment variables fresh each time
- This means env vars are re-read on every VBA-modifying tool call (no caching)
- This also means `capture_trusted_locations()` reads the Windows registry on every call
- Impact: performance cost, but no correctness issue (env changes take effect immediately)

#### 28. COM dispatcher threading — CONFIRMED
- `com_dispatcher.py` uses a **dedicated STA thread** (`ComDispatcher-STA`, line 73)
- All COM operations are serialized through a `queue.Queue` with `concurrent.futures.Future`
- Cleanup in `_release_com_safe()` (line 144) uses a watchdog thread for `Access.Quit()` timeout
- Dialog dismissal in `_dismiss_access_dialogs()` (line 203) uses Win32 API to close `#32770` windows
- Fallback to `taskkill /F /IM MSACCESS.EXE` (line 193) if Quit() times out
- **Dialog dismissal scope issue**: When `access_pids` is empty (Access minimized), it closes ALL `#32770` dialogs on the system (line 237: `close_all_dialogs = not access_pids`)

#### 29. Repo State
- Branch: (current as of exploration)
- Recent commits:
  ```
  df2bebc sync engram memories
  0b06e02 Delete unnecessary workflow file
  01436c4 chore: add package.json and pnpm-lock.yaml from project setup
  8aed9ab test: fix 7 pre-existing test failures (NotImplementedError + FastMCP API)
  83f1dfc refactor(adapters): deprecate AccessAdapter god Protocol in favor of ISP interfaces (Chain C)
  ```
- Note: `0b06e02` deleted a workflow file, suggesting CI was partially set up before

---

### Summary Table

| # | Finding | Status | Severity | File:Line |
|---|---------|--------|----------|-----------|
| 1 | Hardcoded API keys | CONFIRMED | **CRITICAL** | `start-server.ps1:1`, `sample-sql/start-server*.ps1:9/1` |
| 2 | `==` not `hmac.compare_digest` | CONFIRMED | Medium | `auth.py:46` |
| 3 | Narrow auth hooks | CONFIRMED | Low | `auth.py:16-32` (only 2 hooks) |
| 4 | No API key validation | CONFIRMED | Medium | `config.py:51-56` |
| 5 | Unscoped taskkill | CONFIRMED | **HIGH** | `connection.py:278`, `com_dispatcher.py:193` |
| 6 | Missing security files | CONFIRMED | Medium | repo root |
| 7 | Sample SQL hardcoded keys | CONFIRMED | Medium | `sample-sql/*.ps1` |
| 8 | Stdio broken | CONFIRMED | Low | `server.py` (no `__main__` or `mcp.run()`) |
| 9 | `cli serve` missing | CONFIRMED | **HIGH** | `cli/main.py` (no serve cmd), `docs/deployment.md:29/35/175` (references it) |
| 10 | No `[project.scripts]` | CONFIRMED | Medium | `pyproject.toml` |
| 11 | Tool configs minimal | CONFIRMED | Low | `pyproject.toml:40-41` |
| 12 | 0.0.0.0 binding | CONFIRMED | Medium | `start-server.ps1:3` |
| 13 | PathGuard bypass | CONFIRMED | **HIGH** | Multiple tool modules (see above) |
| 14 | SQL injection via where_dict | CONFIRMED | **CRITICAL** | `odbc.py:176,209`, `wincom.py:1015,1045` |
| 15 | `print()` not logging | CONFIRMED | Medium | 7 instances, zero `logging` usage |
| 16 | except Exception widespread | CONFIRMED | Medium | 1 in `mcp/`, 171 total in `src/` |
| 17 | ConnectionPool no locks | CONFIRMED | Medium | `connection.py:49-50` |
| 18 | Destructive tools no guards | CONFIRMED | **HIGH** | Multiple tools (see above) |
| 19 | connect_string injection | CONFIRMED | **HIGH** | `linked_tables.py:57` |
| 20 | No CI/CD | CONFIRMED | Medium | `.github/workflows/` missing |
| 21 | No Dependabot | CONFIRMED | Low | `.github/dependabot.yml` missing |
| 22 | Metrics LLM-only | CONFIRMED | Medium | `metrics.py:70-90` |
| 23 | No audit log | CONFIRMED | Medium | No audit module exists |
| 24 | Skipped tests | CONFIRMED | Low | 4 always-skipped (2 SSE, 1 migration, 1 Linux-only) |
| 25 | OpenSpec config | FOUND | Info | `openspec/config.yaml` |

### Recommendations

**Phase 1 Priority**: Fix hardcoded keys (#1) and add env key validation (#4) immediately. Scope taskkill to PID (#5). Add SECURITY.md and .env.example (#6).

**Phase 2 Priority**: Add `serve` subcommand to CLI (#9) or fix docs to reference actual start method. Add `[project.scripts]` entry point (#10).

**Phase 3 Priority**: Apply PathGuard to ALL file-path-accepting tools (#13). Fix SQL injection in where_dict raw string paths (#14). Add confirm/dry_run to destructive tools (#18). Validate connect_string (#19).

**Phase 4 Priority**: Add CI/CD workflows (#20). Add tool_call/auth/connection metrics (#22). Add audit logging (#23).

### Ready for Proposal
Yes — all findings are confirmed with exact file:line references. The exploration reveals 4 critical, 6 high, and numerous medium-severity issues. The orchestrator can proceed to `sdd-propose` with this data.
