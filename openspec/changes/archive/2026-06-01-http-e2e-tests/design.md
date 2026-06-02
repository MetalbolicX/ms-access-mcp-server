# Design: HTTP End-to-End Tests

## Technical Approach

We will implement a hybrid testing strategy for the HTTP transport. For 90% of the tests, we will use Starlette's `TestClient` directly against the FastMCP internal Starlette app. This simulates HTTP requests (JSON-RPC) without the overhead and flakiness of binding to a real network port. For the remaining 10%, we will test actual port-bound startup using `subprocess` to guarantee the `run_http()` method operates correctly end-to-end. We will use the `diagnose_environment` tool for functional tests since it doesn't require an active MS Access COM automation session, ensuring tests can run anywhere. 

A critical bug fix in `server.py` will be applied to properly register the authentication middleware using FastMCP's integration hooks.

## Architecture Decisions

### Decision: FastMCP Middleware Registration Fix

**Choice**: Add `mcp.add_middleware(_auth_middleware)` inside `server._init_http_config()`.
**Alternatives considered**: Adding it globally in the module scope instead of lazily in `_init_http_config`.
**Rationale**: Adding it globally would incorrectly enforce HTTP authentication on Standard Input/Output (STDIO) transport. Scoping the middleware registration to `_init_http_config` ensures it only activates when `run_http` is invoked.

### Decision: Test Client Approach

**Choice**: Use Starlette `TestClient` mapped to FastMCP's ASGI app for in-memory HTTP integration testing.
**Alternatives considered**: Running a real local server for all tests using `pytest-xprocess` or `subprocess`.
**Rationale**: Real network bindings introduce test flakiness, cross-test port conflicts, and slower test execution. `TestClient` offers the exact same HTTP layer execution without TCP overhead.

### Decision: Environment Variable Isolation

**Choice**: Use pytest's `monkeypatch` fixture to isolate `ACCESS_MCP_API_KEY` and `ACCESS_MCP_ALLOWED_DIRS` on a per-test/per-group basis.
**Alternatives considered**: Modifying `os.environ` directly and resetting it in teardown.
**Rationale**: `monkeypatch` is idiomatic pytest, thread-safe for the test run, and guarantees cleanup even if a test panics.

### Decision: Module-Level State Reset

**Choice**: We will manually reset `server._config`, `server._path_guard`, and `server._auth_middleware` to `None` in a pytest fixture before and after each test.
**Alternatives considered**: Relying on process isolation.
**Rationale**: Because `TestClient` runs in the same process, the lazy-initialization global variables in `server.py` will persist across tests and break configuration changes (like testing missing vs valid API keys).

## Data Flow

```text
    Test (pytest) ──[ monkeypatch env ]──→ server.py (globals)
         │                                       │
         ├──[ HTTP POST /mcp/message ]──→ TestClient (Starlette)
         │                                       │
         └──←[ JSON-RPC Response ]──────── ApiKeyMiddleware
                                                 │
                                           FastMCP Tool Route
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ms_access_mcp/mcp/server.py` | Modify | Add `mcp.add_middleware(_auth_middleware)` inside `_init_http_config`. |
| `tests/integration/test_http_transport.py` | Create | New test suite for HTTP auth, tool execution, and lifecycle. |
| `pyproject.toml` | Modify | Add `httpx` to `dev` dependencies to enable `TestClient`. |

## Interfaces / Contracts

```python
# Helper to formulate JSON-RPC over HTTP
def mcp_request(client, method: str, params: dict, auth_token: str | None = None) -> httpx.Response:
    """Helper to format JSON-RPC 2.0 requests over HTTP POST."""
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    # Send to the appropriate endpoint FastMCP exposes for HTTP POST
    return client.post("/messages", json=payload, headers=headers)
```

*Note: The exact FastMCP endpoint varies depending on whether SSE (`/messages`) or direct HTTP transport is being used. The test helper will inspect FastMCP's routes to determine the correct path.*

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Integration | Auth Middleware Registration | Ensure `mcp.add_middleware` handles the HTTP Auth correctly. |
| Integration | Token Validation | Assert 200 for valid tokens, 401/403 for missing/invalid tokens. |
| Integration | Tool Bypass & Handshake | Validate MCP initialization lifecycle bypasses token requirement if needed. |
| Integration | PathGuard Validation | Execute `diagnose_environment` with valid and invalid paths. Expect JSON-RPC errors for traversal/UNC paths. |
| E2E | Server Startup | Use `subprocess.Popen("ms-access-mcp serve ...")`. Verify standard output signals "running" and `exit(0)`. |
| E2E | Startup Failure | Attempt startup without `ACCESS_MCP_API_KEY` set. Expect immediate crash/exit code 1. |

## Migration / Rollout

No migration required. The fix will immediately secure the HTTP endpoints.

## Open Questions

- [ ] FastMCP internal ASGI app attribute: Does FastMCP expose `.app`, `.get_starlette_app()`, or similar for `TestClient`? *Will be inspected during implementation.*
- [ ] Direct HTTP vs SSE routes: FastMCP relies heavily on SSE. Does it support a single stateless HTTP POST endpoint for standard testing? *Will adapt test helper route dynamically.*