# Proposal: COM Thread Affinity

## Intent

`WinComAdapter` creates COM objects (`Access.Application`) on whatever thread uvicorn dispatches a request to. COM objects have apartment affinity — they're bound to the thread that created them. When a subsequent request lands on a different thread, the adapter reports `is_connected() = False` even though the objects exist. This causes intermittent "Not connected to database" errors across MCP sessions.

**Goal**: Ensure ALL COM operations execute on a single dedicated STA thread, eliminating thread-affinity failures.

## Scope

### In Scope
- Create `ComDispatcher` class — a dedicated STA thread that owns all COM objects
- Wrap `WinComAdapter` to delegate COM calls through `ComDispatcher` via `concurrent.futures.Future`
- Ensure all adapter methods (connect, disconnect, get_tables, execute_sql_script, etc.) go through the dispatcher
- Add proper cleanup of the dispatcher thread on adapter disconnect
- Unit tests with mocked dispatcher (no COM required)

### Out of Scope
- Rewriting `OdbcAdapter` (no COM involvement)
- Changing the MCP server's async/concurrent architecture
- Performance optimization beyond correctness

## Capabilities

### New Capabilities
- `com-thread-safety`: `WinComAdapter` operations are guaranteed to run on a single STA thread, regardless of which async worker handles the request

### Modified Capabilities
- `access-mcp` (tool execution): `connect_access` and all schema/com automation tools gain reliability — no more intermittent disconnections from thread switches

## Approach

1. Create `ComDispatcher` class in `adapters/wincom.py`:
   - Owns a daemon STA thread that initializes `pythoncom.CoInitialize()`
   - Holds the `Access.Application` COM object
   - Accepts callables via a `threading.Queue`, executes them on the STA thread, returns result via `Future`
2. Modify `WinComAdapter.__init__` to accept an optional `ComDispatcher` instance
3. Refactor `WinComAdapter.connect()` to create/access a shared dispatcher
4. Wrap all ~40 COM-touching methods to use `dispatcher.call(method, *args)` pattern
5. On `disconnect()`, signal the dispatcher to close Access and shut down cleanly

**Pattern**:
```python
class ComDispatcher:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def call(self, fn, *args, **kwargs):
        future = concurrent.futures.Future()
        self._queue.put((fn, args, kwargs, future))
        return future.result(timeout=30)

    def _run(self):
        pythoncom.CoInitialize()
        self._app = win32com.client.Dispatch("Access.Application")
        while True:
            fn, args, kwargs, future = self._queue.get()
            try:
                future.put_result(fn(*args, **kwargs))
            except Exception as e:
                future.set_exception(e)
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ms_access_mcp/adapters/wincom.py` | Modified | Add `ComDispatcher`; refactor all COM methods to use it |
| `src/ms_access_mcp/services/connection.py` | None | No changes — adapter interface unchanged |
| `src/ms_access_mcp/services/schema.py` | None | No changes — adapter interface unchanged |
| `src/ms_access_mcp/mcp/server.py` | None | No changes — adapter creation unchanged |
| `tests/unit/test_execute_sql_script.py` | Modified | Add dispatcher-mock tests |
| `tests/unit/test_concrete_adapters.py` | Modified | Update to handle dispatcher injection |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Deadlock if COM call blocks indefinitely | Low | `Future.result(timeout=30)` ensures caller doesn't wait forever |
| ~40 methods need wrapping (mechanical) | High | Systematic find/replace with ast_grep pattern |
| Dispatcher startup failure on non-Windows | Medium | Guard with `if sys.platform != 'win32'`; OdbcAdapter unaffected |

## Rollback Plan

1. Revert `adapters/wincom.py` to previous version via `git checkout HEAD~1 -- src/ms_access_mcp/adapters/wincom.py`
2. Re-run integration test — if "Not connected" errors return, the fix is confirmed needed
3. No schema or data migration needed — only runtime behavior

## Dependencies

- `pywin32` (already required) — provides `win32com.client` and `pythoncom`
- `concurrent.futures` (stdlib) — for `Future` return pattern

## Success Criteria

- [ ] `pytest` passes on Linux (unit tests, no COM)
- [ ] `powershell.exe` MCP test: connect → execute_sql_script → disconnect → repeat 3x with NO "Not connected" errors
- [ ] All `WinComAdapter` methods pass through `ComDispatcher.call()`
- [ ] Adapter correctly cleans up Access.exe on `disconnect()`