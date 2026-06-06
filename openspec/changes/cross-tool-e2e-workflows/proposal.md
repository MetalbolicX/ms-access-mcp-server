# Proposal: cross-tool-e2e-workflows

## Intent

Add cross-tool end-to-end workflow tests that chain multiple MCP tools together in realistic scenarios, validating the system as a whole across both internal (pool) and external (HTTP) boundaries.

## Scope

### In Scope
- Tier 1: Pool-level testing (SQLite backend, no HTTP, no WinCom)
- Tier 2: HTTP-level testing (TestClient, JSON-RPC, auth middleware)
- Full CRUD workflow (`create_table` -> `insert_data` -> `query_data` -> `get_table_schema` -> `disconnect`)
- Data export workflow (`get_tables` -> `export_data` -> verify file)
- Multi-table workflow (create, list, query multiple tables)
- Multi-connection isolation (verify no cross-contamination)
- Schema/ER diagram structure workflow (`get_table_schema` -> `get_relationships` -> `get_er_diagram`)
- HTTP transport JSON-RPC workflow (initialize, list, call tools)
- Enable `e2e` layer in `openspec/config.yaml` (`available: true`, `tool: pytest`)

### Out of Scope
- COM/VBA workflows (requires real Access, handled separately)
- Migration workflows (covered by `migration-sqlite-tests` change)
- Dev copy workflows (requires real Access)
- Error recovery / edge case testing (deferred to a follow-up)

## Capabilities

> This section is the CONTRACT between proposal and specs phases.
> The sdd-spec agent reads this to know exactly which spec files to create or update.
> Research `openspec/specs/` before filling this in.

### New Capabilities
- `e2e-workflows`: Cross-tool end-to-end testing requirements for pool and HTTP tiers.

### Modified Capabilities
- None

## Approach

Create a dedicated `tests/e2e/` directory mirroring the integration layer approach but focused on chained tool calls. We will leverage the existing `pool_with_sqlite` fixture and `call_mcp_tool` helper for Tier 1 tests to ensure they can run in any environment without real MS Access. For Tier 2, we will use FastAPI's `TestClient` to validate JSON-RPC over HTTP, reusing authentication context logic from existing HTTP tests. Finally, update `openspec/config.yaml` to enable the `e2e` layer with `pytest`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `tests/e2e/` | New | Directory for e2e tests |
| `tests/e2e/conftest.py` | New | Fixtures, reusing pool models |
| `tests/e2e/helpers.py` | New | Workflow helpers for chaining tools |
| `tests/e2e/test_workflows_pool.py` | New | Tier 1 (pool-level) tests |
| `tests/e2e/test_workflows_http.py` | New | Tier 2 (HTTP-level) tests |
| `openspec/config.yaml` | Modified | Set `e2e` layer to available |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Test flakiness due to shared state | Low | Use isolated SQLite test databases per fixture |
| Duplication with integration tests | Med | Focus strictly on chained cross-tool scenarios |

## Rollback Plan

Delete the `tests/e2e/` directory, revert `e2e` layer availability in `openspec/config.yaml`, and archive the change.

## Dependencies

- Existing SQLite-backed test pool from `tests/integration/conftest.py`
- HTTP client patterns from `tests/integration/test_http_transport.py`

## Success Criteria

- [ ] `tests/e2e/test_workflows_pool.py` executes all Tier 1 workflows successfully.
- [ ] `tests/e2e/test_workflows_http.py` executes the HTTP workflow successfully.
- [ ] `openspec/config.yaml` has `e2e` layer set to `available: true`.
- [ ] Tests can run on CI without requiring a real Access installation.
