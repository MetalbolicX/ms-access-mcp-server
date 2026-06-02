# Proposal: Bootstrap MCP Server

## Intent

Bootstrap a Model Context Protocol (MCP) server for Microsoft Access. Provide a robust foundation using Python (FastAPI/pywin32) for the backend and Vue 3 for a minimal monitoring dashboard. Provide capabilities beyond existing solutions like migrations, schema upload, and version-controlled exports.

## Scope

### In Scope
- Setup Python project structure with Typer CLI and FastAPI MCP backend
- Implement `wincom` adapter for basic COM operations
- Setup Vue 3 frontend with Element Plus and Vue Flow
- Define the 33 core tools via MCP API
- Implement schema reading via pyodbc or ADO
- Establish export-to-text formatting for version control

### Out of Scope
- Full implementations of all 33 tools (start with skeleton and basic connectivity)
- Cross-OS deployment scripts (WSL bridge is a fast-follow)
- Complex migration engine execution (start with schema extraction)

## Capabilities

### New Capabilities
- `access-mcp`: The core server runtime and protocol handler.
- `schema-explorer`: Reads tables, queries, relationships.
- `data-access`: Basic SQL querying and export.
- `com-automation`: Manage Access instance lifecycle and VBA manipulation.
- `versioning-engine`: Text-based serialization of Access binaries.
- `web-dashboard`: Minimal Vue 3 UI for monitoring.

### Modified Capabilities
None.

## Approach

Create an adapter-based Python application (`src/ms_access_mcp`) that abstracts COM and ODBC interactions. Expose tools via the official MCP Python SDK. For the UI, scaffold a Vue 3 Vite app in `frontend/`. Use `pywin32` for Windows COM automation and `pyodbc` for fast data reads. 

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/` | New | Python backend |
| `frontend/` | New | Vue 3 frontend |
| `tests/` | New | pytest suite |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| COM interaction deadlocks | High | Wrap COM calls in safe blocks, ensure `Quit` is called on error |
| Python bitness mismatch | Med | Document strict requirement for matching Office bitness |
| Access file locks | Med | Auto-detect `.laccdb` and handle gracefully |

## Rollback Plan
Delete initialized directories and revert to empty repo.

## Dependencies
- Microsoft Access installed
- Python 3.11+
- Node.js (for frontend build)

## Success Criteria
- [ ] Server responds to MCP initialize requests
- [ ] Backend dependencies install cleanly
- [ ] Vue 3 app builds and runs
- [ ] CLI runs without errors