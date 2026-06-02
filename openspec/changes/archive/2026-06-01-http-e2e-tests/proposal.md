# Proposal: HTTP End-to-End Tests

## Intent

Add comprehensive end-to-end testing for the HTTP transport mode of the MS Access MCP Server. This will verify server startup, authentication, path guarding, tool lifecycle, error handling, and different transport modes (http, streamable-http, sse), while fixing a critical bug preventing API key middleware registration.

## Scope

### In Scope
- Fix the missing middleware registration in `_init_http_config()`
- Server startup and config initialization tests
- Authentication tests (valid, invalid, missing API key, initialize bypass)
- PathGuard integration tests (allowed dirs, traversal, UNC rejection)
- Tool lifecycle over HTTP (diagnose_environment)
- Error handling tests (unknown tool, malformed JSON, wrong method)
- Test client using `Starlette TestClient` (via `httpx`)
- Dedicated HTTP protocol test helpers

### Out of Scope
- Full E2E testing of MS Access COM automation over HTTP (covered by `diagnose_environment` smoke test to avoid flakiness)
- Direct socket/TCP level testing (handled by Starlette)
- Non-HTTP transport testing (STDIO is tested separately)

## Capabilities

> This section is the CONTRACT between proposal and specs phases.
> The sdd-spec agent reads this to know exactly which spec files to create or update.

### New Capabilities
- `http-e2e-tests`: End-to-End testing for the HTTP transport including Server startup, Auth, PathGuard, Tool lifecycle, Error handling, and Transports.

### Modified Capabilities
- `server`: `_init_http_config` will register the `ApiKeyMiddleware` to actually enforce HTTP authentication.

## Approach

We will use a hybrid approach relying on `Starlette TestClient` (which uses `httpx`) for 90% of the tests, avoiding full server binding overhead for most cases. We'll also include 1-2 full server startup tests using an actual bound port. A new test suite `tests/e2e/test_http.py` will be created with appropriate fixtures. The `server.py` file will be patched to properly register `_auth_middleware` using FastMCP's middleware registration mechanisms.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ms_access_mcp/mcp/server.py` | Modified | Add middleware registration to `_init_http_config` |
| `tests/e2e/test_http.py` | New | Add HTTP end-to-end test suite |
| `tests/e2e/conftest.py` | New | Add HTTP test fixtures and environment overrides |
| `pyproject.toml` | Modified | Add `httpx` to `dev` dependencies |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Authentication still fails after middleware registration | Low | The E2E tests for missing/invalid keys will immediately surface if middleware isn't active. |
| Test flakiness due to port binding | Medium | Use `Starlette TestClient` for most tests; only bind to port 0 (OS assigned) for the true startup test. |
| Missing dependency `httpx` | Low | Explicitly add `httpx` to `pyproject.toml` dev dependencies. |

## Rollback Plan

Revert `_init_http_config()` to its previous state, remove `httpx` from `pyproject.toml`, and delete the `tests/e2e` HTTP test files.

## Dependencies

- `httpx` (must be added to `dev` dependencies in `pyproject.toml`)

## Success Criteria

- [ ] `_init_http_config()` correctly registers `ApiKeyMiddleware`.
- [ ] Authentication tests pass (valid, invalid, missing, initialize bypass).
- [ ] PathGuard integration tests pass over HTTP.
- [ ] Tool lifecycle tests pass over HTTP (`diagnose_environment`).
- [ ] Error handling tests pass over HTTP.
- [ ] Tests run successfully via `pytest`.
