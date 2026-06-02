# Design: COM Thread Cleanup — Prevent Orphaned MSACCESS.EXE

## Technical Approach

Introduce `_release_com_safe()` in `ComDispatcher` that follows a strict ordered release chain with per-step error logging and a `ThreadPoolExecutor`-backed watchdog for `Quit()`. If the watchdog times out, fall back to `taskkill /F /IM MSACCESS.EXE`. Wire the new method into `_cleanup_com()`, `disconnect()`, `close_access()`, `connect()` error path, and `_run()` finally.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Watchdog | `concurrent.futures.ThreadPoolExecutor` with 5s timeout | `threading.Timer`, `signal.alarm` | Already imported; timeout semantics match requirement exactly; `signal.alarm` unavailable on Windows threads |
| Release order | ADO → DAO → CloseCurrentDatabase → Quit → taskkill | Reverse or arbitrary | COM hierarchy: ADO depends on DAO workspace, DAO depends on Access app. Releasing child first prevents dangling references |
| taskkill | `subprocess.run(["taskkill","/F","/IM","MSACCESS.EXE"])` | `os.kill()`, ctypes | Simplest reliable way to terminate by image name on Windows |
| Platform guard | `sys.platform == 'win32'` conditional | Always-run, config flag | COM is Windows-only; match existing `_ensure_windows()` pattern |

## Data Flow

```
disconnect() / shutdown() / _run() finally / connect() error
    │
    ▼
  _release_com_safe()                 ← single cleanup entry point
    │
    ├─ 1. _ado_conn.Close()           try/except → log → set None
    ├─ 2. _current_db.Close()         try/except → log → set None
    ├─ 3. app.CloseCurrentDatabase()  try/except → log
    ├─ 4. Quit() watchdog             ThreadPoolExecutor.submit().result(5s)
    │      └─ timeout/error → taskkill /F /IM MSACCESS.EXE
    └─ 5. _access_app = None
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ms_access_mcp/adapters/wincom.py` | Modify | Add `_release_com_safe()`, update `_cleanup_com()`, `shutdown()`, `disconnect()`, `close_access()`, `connect()` error path |

## Interfaces / Contracts

```python
def _release_com_safe(self) -> None:
    """Release COM objects in strict order with watchdog + force-kill fallback.
    Safe to call multiple times; each step is individually try/except-logged.
    Must run on the STA thread.
    """
```

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | `_release_com_safe()` release order | Mock COM objects, assert Close() call sequence |
| Unit | Watchdog timeout | Mock `app.Quit` to block >5s, verify taskkill called |
| Unit | Platform guard | Mock `sys.platform`, no taskkill on non-Windows |
| Integration | Full disconnect cycle | Real COM: `tasklist` before/after on Windows |

## Migration / Rollback

No migration required. Rollback: revert `wincom.py` changes — previous behavior (leaking processes) is the fallback.
