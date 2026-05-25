# Tasks: COM Thread Cleanup

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~250 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | exception-ok |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Work Units

### Unit 1: Implement `_release_com_safe()` in ComDispatcher (~120 lines)

- [ ] 1.1 Add `import subprocess` at top of wincom.py
- [ ] 1.2 Create `_release_com_safe(self)` in `ComDispatcher` with ordered release + per-step logging + set-to-None after each
- [ ] 1.3 Add `Quit()` watchdog via `concurrent.futures.ThreadPoolExecutor` with 5s timeout
- [ ] 1.4 Add taskkill fallback after watchdog timeout, guarded by `sys.platform == 'win32'`
- [ ] 1.5 Replace `_cleanup_com()` body to delegate to `self._release_com_safe()`

Implementation:

```python
def _release_com_safe(self) -> None:
    """Release COM objects in strict order with watchdog + force-kill fallback.
    Each step is individually try/except-logged; always sets refs to None.
    """
    # Step 1: Close ADO connection
    if self._ado_conn is not None:
        try:
            self._ado_conn.Close()
        except Exception as e:
            print(f"Cleanup warning: _ado_conn.Close() failed: {e}", file=sys.stderr)
        self._ado_conn = None

    # Step 2: Close DAO database
    if self._current_db is not None:
        try:
            self._current_db.Close()
        except Exception as e:
            print(f"Cleanup warning: _current_db.Close() failed: {e}", file=sys.stderr)
        self._current_db = None

    # Step 3: CloseCurrentDatabase via Access
    app = self._access_app
    if app is not None:
        try:
            app.CloseCurrentDatabase()
        except Exception as e:
            print(f"Cleanup warning: CloseCurrentDatabase() failed: {e}", file=sys.stderr)

        # Step 4: Quit() with 5s watchdog
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(app.Quit).result(timeout=5.0)
        except concurrent.futures.TimeoutError:
            print("Cleanup warning: app.Quit() timed out after 5s", file=sys.stderr)
            self._force_kill_access()
        except Exception as e:
            print(f"Cleanup warning: app.Quit() failed: {e}", file=sys.stderr)
            self._force_kill_access()

    self._access_app = None

def _force_kill_access(self) -> None:
    """Force-kill MSACCESS.EXE via taskkill (Windows only)."""
    if sys.platform == 'win32':
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "MSACCESS.EXE"],
                capture_output=True, timeout=5.0,
            )
        except Exception as e:
            print(f"Cleanup warning: taskkill failed: {e}", file=sys.stderr)
    else:
        print("Cleanup warning: taskkill only supported on Windows", file=sys.stderr)
```

### Unit 2: Wire Cleanup Into All Entry Points (~80 lines)

- [ ] 2.1 In `_run()` finally: replace `self._cleanup_com()` → `self._release_com_safe()`
- [ ] 2.2 In `disconnect()`: replace `self._dispatcher._cleanup_com()` → call `_release_com_safe()` via dispatcher
- [ ] 2.3 In `close_access()`: replace inline cleanup → delegate to `_release_com_safe()`
- [ ] 2.4 In `connect()` error path: replace `self._dispatcher._cleanup_com()` → `self._dispatcher._release_com_safe()`
- [ ] 2.5 Extend `shutdown()` join timeout: `5.0` → `15.0` to accommodate the 5s watchdog + cleanup

Implementation:

```python
# _run() finally — replace:
#   self._cleanup_com()
# with:
#   self._release_com_safe()

# disconnect() — replace inner lambda:
#   def _do_disconnect() -> None:
#       self._dispatcher._cleanup_com()
# with:
#   def _do_disconnect() -> None:
#       self._dispatcher._release_com_safe()

# close_access() — replace inline Quit/set-None:
#   app.Quit()
#   self._dispatcher._access_app = None
#   self._dispatcher._current_db = None
# with:
#   self._dispatcher._release_com_safe()

# connect() error path — replace:
#   self._dispatcher._cleanup_com()
# with:
#   self._dispatcher._release_com_safe()

# shutdown() — change:
#   self._thread.join(timeout=5.0)
# to:
#   self._thread.join(timeout=15.0)
```

### Unit 3: Cleanup Logging Audit (~50 lines)

- [ ] 3.1 In `_cleanup_com()` delegate path: remove duplicate logging (already in `_release_com_safe()`)
- [ ] 3.2 In `disconnect()`: replace `except Exception: pass` → `except Exception as e: print(...)`
- [ ] 3.3 In `close_access()`: replace `except Exception: pass` → `except Exception as e: print(...)`

Implementation:

```python
# disconnect() — outer try/except:
#   try:
#       self._dispatcher.call(_do_disconnect)
#   except Exception:
#       pass
# replace with:
#   try:
#       self._dispatcher.call(_do_disconnect)
#   except Exception as e:
#       print(f"Cleanup warning: disconnect failed: {e}", file=sys.stderr)

# close_access() — outer try/except:
#   try:
#       self._dispatcher.call(_do)
#   except Exception:
#       pass
# replace with:
#   try:
#       self._dispatcher.call(_do)
#   except Exception as e:
#       print(f"Cleanup warning: close_access failed: {e}", file=sys.stderr)
```
