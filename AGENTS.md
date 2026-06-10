# AGENTS.md — MS Access MCP Server

## Commands

```bash
uv sync                     # install all deps (no extras)
uv sync --extra windows     # with pywin32 (Windows-only COM)
uv sync --extra dev         # with pytest, ruff, pyright

uv run pytest                        # all tests
uv run pytest tests/unit/            # unit tests only
uv run pytest tests/integration/ -k "not com_integration"  # CI-safe subset
uv run ruff check .                  # lint (line-length 100, double-quotes)
uv run ruff format .                 # format
uv run pyright                       # type check (basic mode)

uv run ms-access-mcp serve           # HTTP (default), requires ACCESS_MCP_API_KEY
uv run ms-access-mcp serve --transport stdio  # stdio, no auth needed
uv run python -m ms_access_mcp.mcp.server      # same as stdio
```

## Architecture

- **Entrypoints**: `src/ms_access_mcp/cli/main.py` (Typer CLI), `src/ms_access_mcp/mcp/server.py` (FastMCP server)
- **Tool modules** in `src/ms_access_mcp/mcp/` — each file registers tools via `@mcp.tool()` starting at `server.py:106` (`from . import connection, schema, ...`)
- **Adapters**: `OdbcAdapter` (cross-platform, data-only) and `WinComAdapter` (Windows-only, full COM/VBA). Split into segregated interfaces: `IDataAdapter`, `ISchemaAdapter`, `IUiAdapter` in `adapters/interfaces.py`
- **Service container**: `mcp/container.py` — singleton via `get_container()`. Tool modules access it via lazy `_pool()` helpers to avoid circular imports
- **Legacy compat**: `server.py` has `__getattr__` fallback resolving `connection_service` → container's `connection_pool`, etc.
- **Auth**: `ApiKeyMiddleware` validates Bearer token on every hook. Only active in HTTP mode. `ServerConfig()` raises `ValueError` when `ACCESS_MCP_API_KEY` is missing — catch this in tests.
- **PathGuard**: validates file paths against `ACCESS_MCP_ALLOWED_DIRS`. Lazily initialized via `_get_path_guard()`. Rejects UNC paths and traversal.
- **COM dispatcher** (`adapters/com_dispatcher.py`): single STA thread serializes all COM calls to avoid apartment-affinity errors

## Key Gotchas

- **No API key? Use stdio.** HTTP mode requires `ACCESS_MCP_API_KEY` (min 32 chars, min 3.0 entropy). Stdio mode works without it.
- **Tool modules must be imported in `server.py`** for `@mcp.tool()` registration. Adding a new tool module = add import line near `server.py:106`.
- **Integration tests skip on non-Windows** unless you mock pyodbc. Use SQLite-backed fixtures from `tests/integration/conftest.py` (`_sqlite_pyodbc_connect`, `pool_with_sqlite`, `pool_with_two_adapters`).
- **Integration test db**: set `ACCESS_TEST_DB` env var or place a `.accdb` at `tests/integration/fixtures/test_db.accdb`
- **CI guard** (`test_no_provider_sdk_in_core.py`): core must never import `openai`, `anthropic`, etc. Provider SDKs only in `adapters/llm_*.py`.
- **Reset container** between tests: call `from ms_access_mcp.mcp.container import _reset_container; _reset_container()` then re-init globals (`_path_guard`, `_auth_middleware`).
- **E2E HTTP tests**: Starlette `TestClient` with monkeypatched env. Reset server module globals before each fixture.
- **LLM tools** (`ai_tools.py`): guarded by `LlmConfig.enabled` (default `False`). Returning `{"disabled": True}` dict, not raising errors.
- **Formatting**: ruff line-length 100, double quotes, space indent. pyright strict with basic mode.

## Env Vars

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `ACCESS_MCP_API_KEY` | for HTTP | — | min 32 chars, high entropy |
| `ACCESS_MCP_HOST` | no | `127.0.0.1` | |
| `ACCESS_MCP_PORT` | no | `8000` | |
| `ACCESS_MCP_ALLOWED_DIRS` | no | user home | semicolon-sep |
| `ACCESS_MCP_ALLOW_REMOTE` | no | — | ack `0.0.0.0` risk |
| `ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE` | no | false | |
| `ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS` | no | false | Windows only |
