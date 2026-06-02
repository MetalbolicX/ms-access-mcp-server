# Tasks: Bootstrap MCP Server

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~600-800 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Backend Core) → PR 2 (Frontend) → PR 3 (Integration/Docs) |
| Delivery strategy | exception-ok |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Python MCP Backend | PR 1 | Base framework, models, wincom adapter, typer CLI |
| 2 | Vue 3 Frontend | PR 2 | Scaffolding, dashboard UI |
| 3 | Integration & Docs | PR 3 | Final wiring, README, examples |

## Phase 1: Foundation (Backend Skeleton)

- [x] 1.1 Create `pyproject.toml` with dependencies: `fastmcp`, `typer`, `pywin32`, `pyodbc`, `pydantic`.
- [x] 1.2 Setup `src/ms_access_mcp/models/` for database and vba entities.
- [x] 1.3 Create abstract `AccessAdapter` in `src/ms_access_mcp/adapters/base.py`.
- [x] 1.4 Implement `WinComAdapter` stub in `wincom.py`.
- [x] 1.5 Implement `OdbcAdapter` stub in `odbc.py`.

## Phase 2: Core MCP Implementation

- [x] 2.1 Implement `connection.py` service.
- [x] 2.2 Implement `schema.py` service (tables, columns, relations).
- [x] 2.3 Implement `com_automation.py` service (launch, VBA injection).
- [x] 2.4 Setup MCP JSON-RPC server entry point in `src/ms_access_mcp/mcp/server.py`.
- [x] 2.5 Map the 33 tools to the MCP server.

## Phase 3: Frontend Scaffolding

- [x] 3.1 Initialize Vue 3 Vite app in `frontend/`.
- [x] 3.2 Install `element-plus`, `vue-router`, `@tanstack/vue-query`, `@vue-flow/core`.
- [x] 3.3 Setup modern CSS nesting and layout variables.
- [x] 3.4 Create main dashboard views (Dashboard, SchemaExplorer, JobMonitor).

## Phase 4: CLI and Testing

- [x] 4.1 Implement `Typer` commands mapping to core services.
- [x] 4.2 Write unit tests for `WinComAdapter` (mocked) and `OdbcAdapter`.
- [x] 4.3 Write tests for schema extraction output formats.

## Phase 5: Cleanup & Verification

- [x] 5.1 Run `ruff check` and `ruff format` on backend.
- [x] 5.2 Validate type checks with `pyright`.
- [x] 5.3 Write README.md with setup instructions and architectural overview.