# Proposal: COM Thread Cleanup — Prevent Orphaned MSACCESS.EXE

## Intent

After `disconnect_access()` or server shutdown, MSACCESS.EXE processes remain running because COM objects are not released in the correct order and errors are silently swallowed. This leaks memory and holds database locks. Fix the cleanup chain so that every disconnect guarantees the Access process terminates.

## Scope

### In Scope
- Fix `_cleanup_com()` to release in correct order: ADO → DAO → Access Application
- Add explicit `.Close()` for `_current_db` (DAO) and `_ado_conn` (ADO)
- Add force-kill fallback (`taskkill /F`) when graceful `Quit()` times out
- Apply cleanup to both `disconnect()` and `shutdown()` paths
- Add cleanup on error paths in `connect()` and `_run()`
- Log (don't silence) cleanup errors
- Extend STA thread join timeout from 5s to 15s for graceful quit

### Out of Scope
- Cross-platform process management (Windows-only by COM requirement)
- ODBC adapter cleanup (separate concern, no orphaned process)

## Capabilities

### New Capabilities
None — spec-level contract already covers COM lifecycle, behavior needs to match.

### Modified Capabilities
- `com-thread-safety`: Strengthen "Clean disconnect" scenario to require no orphaned MSACCESS.EXE after disconnect.

## Approach

1. **New method `_release_com_safe()`** replaces `_cleanup_com()`:
   - Step 1: Close ADO connection via `_ado_conn.Close()` → set to None
   - Step 2: Close DAO database via `_current_db.Close()` → set to None
   - Step 3: Call `CloseCurrentDatabase()` on Access app
   - Step 4: Call `app.Quit()` with 5s watchdog (thread + join)
   - Step 5: If Quit fails/times out → `subprocess.run(["taskkill", "/F", "/IM", "MSACCESS.EXE"])`
   - Step 6: Set `_access_app = None`
   - All steps individually try/except-log, no bare `pass`

2. **In `_run()` finally block**: call `_release_com_safe()` instead of `_cleanup_com()`

3. **In `disconnect()`**: call `_release_com_safe()` synchronously, then `shutdown()`

4. **In `shutdown()`**: extend join to 15s; after join, check if process still alive and force-kill

5. **In `connect()` error path**: call `_release_com_safe()` instead of `_cleanup_com()`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ms_access_mcp/adapters/wincom.py` | Modified | `_cleanup_com()` → `_release_com_safe()`, `shutdown()`, `disconnect()`, `connect()` |
| `src/ms_access_mcp/services/connection.py` | None | No changes needed |
| `src/ms_access_mcp/mcp/server.py` | None | No changes needed |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Force-kill loses unsaved VBA changes | Low | `disconnect_access()` implies intentional close; user should `save_database()` first |
| `taskkill /F` is Windows-only | High | Guard with `sys.platform == 'win32'`; no-op on other platforms |
| Long-running VBA during Quit() | Low | 5s watchdog timeout then force-kill |

## Rollback Plan

Revert `wincom.py` to previous `_cleanup_com()` and `shutdown()` implementation. The old behavior (leaking processes) is the rollback state.

## Dependencies

None — all changes in `wincom.py`. No new packages.

## Success Criteria

- [ ] After `disconnect_access()`, `tasklist | findstr MSACCESS.EXE` returns empty
- [ ] After server shutdown, no orphaned MSACCESS.EXE process
- [ ] 10x connect → query → disconnect cycles without process leak
- [ ] Connect with invalid DB → cleanup runs, no orphaned process
- [ ] Tests pass: `pytest -xvs tests/`
