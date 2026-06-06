# Design: cross-tool-e2e-workflows

## Technical Approach

We will create a new `tests/e2e` test suite mimicking real-world chained interactions with the MCP toolset. The tests will validate the system at two levels: Tier 1 (using the `ConnectionPool` directly with an SQLite backend) and Tier 2 (using an HTTP JSON-RPC via `TestClient`). E2E-specific fixtures will wrap existing integration fixtures to enforce isolation, and explicit `try/finally` blocks will handle cleanup. The `openspec/config.yaml` will be updated to formally enable the `e2e` layer.

## Architecture Decisions

### Decision: Fixture Design and Reuse
**Choice**: Create thin e2e-specific fixtures (`e2e_pool`, `e2e_two_adapters`, `e2e_http_client`) in `tests/e2e/conftest.py` that import and delegate to existing `tests/integration/conftest.py` fixtures.
**Alternatives considered**: Duplicate setup logic in `tests/e2e/conftest.py`, or exclusively use integration fixtures directly.
**Rationale**: Thin wrappers maintain DRY principles while allowing E2E tests to have distinct setup/teardown boundaries (like injecting temporary directories or configuring specific HTTP client states) without bleeding into integration test state.

### Decision: Temporary Directory for Exports
**Choice**: Use a dedicated `temp_export_dir` fixture yielding `tempfile.TemporaryDirectory()`.
**Alternatives considered**: Manual setup/teardown in each export test.
**Rationale**: A fixture ensures consistent, fail-safe cleanup of the OS filesystem for all data export tests.

### Decision: HTTP Client Initialization
**Choice**: Reset server globals (`_config`, `_path_guard`, `_auth_middleware`) to `None` and monkeypatch the API key environment variable in the `e2e_http_client` fixture before instantiating `server_module.mcp.http_app(json_response=True, stateless_http=True)` wrapped in a `TestClient`.
**Alternatives considered**: Use an existing app instance or do not reset globals.
**Rationale**: FastAPI/MCP module state often persists between tests if globals aren't reset. Resetting ensures a pristine configuration for the HTTP pipeline and authentication middleware in E2E validation.

### Decision: E2E Test Object Naming Convention
**Choice**: All E2E test-created tables/objects must use the `__e2e_test_` prefix.
**Alternatives considered**: Use generic names like `test_table`.
**Rationale**: Clearly identifies objects created by the E2E suite and simplifies broad cleanup actions if a test is abruptly aborted.

### Decision: Cleanup Strategy
**Choice**: Use explicit `try/finally` blocks within each test function to drop created tables.
**Alternatives considered**: Use `autouse=True` teardown fixtures to automatically wipe the database.
**Rationale**: Autouse fixtures can lead to fragile tests and mask the exact point of failure. Explicit `finally` blocks guarantee cleanup while keeping the setup-execute-teardown flow visible inside the test.

## Data Flow

### Tier 1 Flow (Pool Level)
    Test Function ──(call_mcp_tool)──→ Tool Handler ──→ ConnectionPool ──→ SQLite Adapter ──→ Temp DB
         │                                                                                  │
         └─────────────(assert success & structure)─────────────────────────────────────────┘

### Tier 2 Flow (HTTP JSON-RPC Level)
    Test Function ──(TestClient.post)──→ HTTP App ──→ JSON-RPC Router ──→ Tool Handler ──→ Pool
         │                                                                                  │
         └─────────────(assert JSON-RPC response)───────────────────────────────────────────┘

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `tests/e2e/conftest.py` | Create | E2E test fixtures (`e2e_pool`, `e2e_http_client`, `temp_export_dir`) leveraging integration fixtures. |
| `tests/e2e/helpers.py` | Create | E2E-specific helper wrappers (e.g. `execute_e2e_tool`) if necessary, or re-export integration helpers. |
| `tests/e2e/test_workflows_pool.py` | Create | Tier 1 workflow tests: CRUD, Export, Multi-table, Multi-connection, Schema/ER. |
| `tests/e2e/test_workflows_http.py` | Create | Tier 2 workflow tests: HTTP transport initialization and tool execution. |
| `openspec/config.yaml` | Modify | Update `testing.layers.e2e` to `{ available: true, tool: pytest }`. |

## Interfaces / Contracts

**Fixture Contract (`tests/e2e/conftest.py`)**:
```python
@pytest.fixture
def e2e_pool(pool_with_sqlite):
    """Provides a pristine pool connection and ensures it is active."""
    yield pool_with_sqlite

@pytest.fixture
def e2e_http_client(valid_env, monkeypatch):
    """Resets global config and returns a TestClient for HTTP E2E tests."""
    import src.ms_access_mcp.mcp.server as server_module
    server_module._config = None
    server_module._path_guard = None
    server_module._auth_middleware = None
    
    app = server_module.mcp.http_app(json_response=True, stateless_http=True)
    with TestClient(app) as client:
        yield client
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | N/A | Handled by existing suites. |
| Integration | N/A | Handled by existing suites. |
| E2E | Workflow Chains | Execute chained MCP tool sequences mimicking a user session (create -> insert -> query -> export). Ensure state is carried forward accurately and isolate connections securely. |

## Migration / Rollout

No migration required. The tests will automatically run on CI assuming `pytest` is configured to run `tests/e2e`.

## Open Questions

- None
