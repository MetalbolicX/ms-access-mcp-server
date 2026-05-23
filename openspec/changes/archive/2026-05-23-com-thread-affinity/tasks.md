# Tasks: COM Thread Affinity

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~350 (mostly mechanical wrapping in wincom.py) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | ComDispatcher class + WinComAdapter refactor | PR 1 | All changes in one commit since they are tightly coupled |

## Phase 1: Foundation (Dispatcher Class)

- [x] 1.1 In `src/ms_access_mcp/adapters/wincom.py`, add `sys.platform` guard in `WinComAdapter.__init__`.
- [x] 1.2 In `wincom.py`, implement `ComDispatcher` class with `threading.Queue`, `concurrent.futures.Future`, and `threading.Thread(daemon=True)`.
- [x] 1.3 In `ComDispatcher._run()`, implement the `while True` loop that executes callables and sets `future.put_result()` or `set_exception()`.
- [x] 1.4 In `ComDispatcher.call()`, implement the 30-second timeout logic `future.result(timeout=30)`.

## Phase 2: Adapter Refactoring (Mechanical)

- [x] 2.1 Modify `WinComAdapter.__init__` to instantiate `self._dispatcher = ComDispatcher()`.
- [x] 2.2 Refactor `WinComAdapter.connect()` to initialize COM via the dispatcher and keep DB path state in dispatcher.
- [x] 2.3 Refactor `WinComAdapter.is_connected()` and `disconnect()` to delegate to dispatcher.
- [x] 2.4 Refactor `get_tables`, `execute_query`, and `get_relationships` to wrap their existing logic in a nested `def _do():` and return `self._dispatcher.call(_do)`.
- [x] 2.5 Refactor all Form operations (get_forms, form_exists, etc.) to use the `_do()` delegate pattern.
- [x] 2.6 Refactor all Report and Macro operations to use the `_do()` delegate pattern.
- [x] 2.7 Refactor all VBA/Module operations to use the `_do()` delegate pattern.
- [x] 2.8 Refactor `execute_sql_script` and versioning exports to use the `_do()` delegate pattern.

## Phase 3: Testing

- [x] 3.1 In `tests/unit/test_concrete_adapters.py`, update tests to mock the `ComDispatcher` thread start.
- [x] 3.2 In `tests/unit/test_execute_sql_script.py`, update tests to use a mocked `ComDispatcher` that executes `_do()` immediately on the same thread for testing.
- [x] 3.3 Create a PowerShell test script (`test-com-thread.ps1`) that initializes a session, calls `connect_access`, `get_tables`, and `execute_sql_script` sequentially, asserting no "Not connected" errors occur.