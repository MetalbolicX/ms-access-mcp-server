# Tasks: HTTP End-to-End Tests

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 380-430 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 auth fix+harness -> PR2 path guard+tool lifecycle -> PR3 errors+transports |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Fix broken HTTP auth and build test harness | PR 1 | `server.py`, `pyproject.toml`, base test file; keep CI green |
| 2 | Cover PathGuard and `diagnose_environment` over HTTP | PR 2 | Additive tests only; depends on PR 1 |
| 3 | Cover protocol errors and transport variants | PR 3 | Additive tests only; depends on PR 2 |

## Phase 1: Foundation / Auth (PR 1)

- [x] 1.1 `src/ms_access_mcp/mcp/server.py`: add `mcp.add_middleware(_auth_middleware)` in `_init_http_config()`. Verify HTTP `tools/call` requests hit `ApiKeyMiddleware`.
- [x] 1.2 `pyproject.toml`: add `httpx` to `project.optional-dependencies.dev`. Verify `TestClient` imports in pytest env.
- [x] 1.3 `tests/integration/test_http_transport.py`: create fixtures for env monkeypatch, temp `.accdb`, state reset via `cleanup_all()`/globals, app factory from `server._init_http_config()` + `server.mcp.http_app()`, and `mcp_request(...)`. Verify each class gets a fresh app.
- [x] 1.4 RED in `tests/integration/test_http_transport.py`: add auth cases for `initialize` bypass plus missing, invalid, and valid Bearer tokens on `tools/call`. Verify failures reproduce before the fix.
- [x] 1.5 GREEN in `tests/integration/test_http_transport.py`: make auth/startup cases pass, including missing `ACCESS_MCP_API_KEY`, allowed-dir load, and `_init_http_config()` idempotent reset behavior. Verify `pytest tests/integration/test_http_transport.py -k "auth or startup or initialize"`.

## Phase 2: Path Guard / Tool Lifecycle (PR 2)

- [x] 2.1 RED in `tests/integration/test_http_transport.py`: add `diagnose_environment` cases for allowed temp `.accdb`, `..` traversal, and UNC-style paths under `ACCESS_MCP_ALLOWED_DIRS`. Verify JSON-RPC error expectations fail first.
- [x] 2.2 GREEN in `tests/integration/test_http_transport.py`: make PathGuard cases pass through the HTTP helper and fresh server state. Verify allowed paths return success and blocked paths return validation errors.
- [x] 2.3 `tests/integration/test_http_transport.py`: add tool lifecycle coverage for authenticated `diagnose_environment` over HTTP. Verify parsed JSON-RPC result shape and tool payload.

## Phase 3: Error Handling / Transport Modes (PR 3)

- [x] 3.1 `tests/integration/test_http_transport.py`: add error cases for unknown tool, malformed JSON body, and wrong HTTP method. Verify HTTP status plus MCP error envelope.
- [x] 3.2 `tests/integration/test_http_transport.py`: parametrize transport coverage for `http`, `streamable-http`, and `sse`, including dynamic route selection in `mcp_request(...)`. Verify each mode resolves a working endpoint.
- [x] 3.3 `tests/integration/test_http_transport.py`: add one subprocess smoke test for `run_http()` success and one failure case without `ACCESS_MCP_API_KEY`. Verify clean startup/exit behavior.

## Phase 4: Verification / Cleanup

- [x] 4.1 Run `pytest tests/integration/test_http_transport.py` and the per-PR focused selectors; verify no global state leaks between classes or transport parametrizations.
