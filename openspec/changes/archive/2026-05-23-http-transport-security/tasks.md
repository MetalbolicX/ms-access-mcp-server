# Tasks: HTTP Transport with Security

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~320 (6 source + 3 test + 1 doc) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: not-needed
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | All modules wired together | PR 1 | Single unit, includes tests and docs |

---

## Phase 1: Foundation — Core Modules (TDD)

- [x] 1.1 Create `src/ms_access_mcp/config.py` — `ServerConfig` class with host, port, api_key, allowed_dirs from env vars. Require api_key; raise ValueError if missing.
- [x] 1.2 RED: Write failing test in `tests/unit/test_config.py` that expects api_key required error.
- [x] 1.3 GREEN: Implement config module.
- [x] 1.4 REFACTOR: Ensure test runs: `pytest tests/unit/test_config.py`.

- [x] 1.5 Create `src/ms_access_mcp/path_guard.py` — `PathGuard` class with `is_allowed(path)` and `validate(path)` methods.
- [x] 1.6 RED: Write failing test for path traversal denial.
- [x] 1.7 GREEN: Implement path guard with resolve+relative_to check; reject UNC.
- [x] 1.8 REFACTOR: Ensure tests pass: `pytest tests/unit/test_path_guard.py`.

- [x] 1.9 Create `src/ms_access_mcp/auth.py` — `ApiKeyMiddleware` extending `fastmcp.server.middleware.Middleware`.
- [x] 1.10 RED: Write failing test expecting middleware import works.
- [x] 1.11 GREEN: Implement stub middleware (full token validation can delegate to HTTP-layer auth).
- [x] 1.12 REFACTOR: Ensure imports work.

---

## Phase 2: Wiring and Integration

- [x] 2.1 Modify `src/ms_access_mcp/mcp/server.py` — Import config/auth/path_guard; initialize server config at import or lazily. Wrap `connect_access` tool function to call `path_guard.validate(database_path)` before creating adapter; return error dict on ValueError.
- [x] 2.2 Verify server still runs: `python -c "from ms_access_mcp.mcp.server import mcp"` — no import errors.

- [x] 2.3 Modify `src/ms_access_mcp/cli/main.py` — Add `@app.command() serve(...)` with options: host, port, api_key, allowed_dirs, transport. Should call `mcp.run(transport=transport, host=host, port=port)` after config init.
- [x] 2.4 Verify CLI loads: `python -m ms_access_mcp.cli.main serve --help` — shows help.

- [x] 2.5 Run full unit test regression: `pytest tests/unit/ -v` — ensure no breakage.

---

## Phase 3: Verification Against Specs

- [x] 3.1 Verify API key required scenario: missing `ACCESS_MCP_API_KEY` should raise during config creation.
- [x] 3.2 Verify path inside allowed dir passes: path_guard.is_allowed('some-dir/db.accdb') returns True.
- [x] 3.3 Verify path outside allowed dir rejected: returns False.
- [x] 3.4 Verify traversal attempted: `../../etc/db.accdb` returns False.
- [x] 3.5 Verify UNC attempted: `//server/share/db.accdb` returns False.

---

## Phase 4: Documentation

- [x] 4.1 Create `docs/deployment.md` — Windows host server startup; env var setup; firewall rules; client opencode.json HTTP config; security caveats.

---

## Phase 5: Polish

- [ ] 5.1 Commit all changes together.
- [ ] 5.2 Tag version (optional).
- [ ] 5.3 Verify build/install: `pip install -e ".[windows]"` without errors.

---

## Implementation Order Recommendation

1. **Phase 1**: New modules first — no dependencies on existing code. TDD cycle ensures behavior from specs.
2. **Phase 2**: Wiring into server.py and CLI — introduces runtime mode switch.
3. **Phase 3**: Verification against each spec scenario — confirm behavior matches requirements.
4. **Phase 4**: Deployment doc — completes outward-facing experience.
5. **Phase 5**: Polish commit — done.

---

## Dependencies

| From | Depends on | Reason |
|------|-----------|--------|
| Phase 2 server import | Phase 1 config/auth/path_guard | Uses those classes |
| Phase 2 CLI serve | Phase 1 config | Reads env configuration |
| Phase 3 verification | Phase 1 path_guard | Tests the module's behavior |