# Design: Bootstrap MCP Server

## Technical Approach

Use an adapter pattern to separate the core business logic from the specific database drivers (pywin32 for COM, pyodbc for data-only). The FastMCP framework handles the MCP protocol serialization, schema generation, validation, and server lifecycle. It routes incoming JSON-RPC calls to the appropriate adapter method based on decorators (`@mcp.tool()`). FastMCP allows us to compose multiple server modules (e.g., schema, vba, data) into a single cohesive MCP instance.

## Architecture Decisions

### Decision: Python backend for COM automation
**Choice**: Use `pywin32` on a Windows host
**Alternatives considered**: Node.js `winax`, C#/.NET interop
**Rationale**: Python offers the best ecosystem for data manipulation (pandas, pyodbc) and is requested by the user.

### Decision: Frontend Framework
**Choice**: Vue 3 + Element Plus
**Alternatives considered**: React + Ant Design, Elm
**Rationale**: Vue provides excellent reactivity and simple templating. The user explicitly chose Vue to avoid runtime errors (with TS) without the overhead of building UI elements from scratch.

### Decision: Web standard HTTP client
**Choice**: Native `fetch`
**Alternatives considered**: Axios
**Rationale**: User explicitly demanded "No axios, use fetch" to follow modern web standards.

## Data Flow

    [MCP Client] ── JSON-RPC ──→ [FastMCP Server]
                                        │
                                        ▼
                                [Tool Router]
                               /             \
                             COM             ODBC
                           Adapter          Adapter
                            /                  \
                    [pywin32]               [pyodbc]
                        │                      │
                        ▼                      ▼
                  [MS Access Instance] ─── [.accdb file]

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Create | Python dependencies and Typer entry points |
| `src/ms_access_mcp/main.py` | Create | FastAPI entry point and MCP tool registration |
| `src/ms_access_mcp/adapters/wincom.py` | Create | COM automation implementation |
| `src/ms_access_mcp/adapters/odbc.py` | Create | Data access implementation |
| `frontend/package.json` | Create | Vue 3 dependencies |
| `frontend/src/App.vue` | Create | Main dashboard layout |

## Interfaces / Contracts

```python
class AccessAdapter(Protocol):
    def connect(self, db_path: str) -> bool: ...
    def get_tables(self) -> list[str]: ...
    def execute_query(self, sql: str) -> list[dict]: ...
    # ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Adapters | Mock COM objects and pyodbc connections |
| Integration | End-to-end tools | Create a dummy `.accdb` file and run real queries against it via the MCP JSON-RPC handler |

## Migration / Rollout
No migration required. This is a greenfield bootstrap.

## Open Questions
None.