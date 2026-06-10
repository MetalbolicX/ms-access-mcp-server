# Session Termination Error Analysis

## Problem Description

When users terminate or close a session in opencode, an error is displayed indicating an issue with bun.js. However, this error is **misleading** — bun.js is not the root cause. The actual problem originates from the Python MCP server's lack of proper signal handling and graceful shutdown mechanisms.

## Error Manifestation

The error typically appears when:
- A user closes the opencode session
- The MCP server process is terminated
- Any unhandled exception occurs during process shutdown

The error message incorrectly attributes the problem to bun.js, leading developers to investigate the wrong component.

## Root Cause Analysis

### The Real Culprit: Missing Graceful Shutdown

The Python MCP server (`ms-access-mcp-server`) manages Microsoft Access databases through COM automation. When using the `WinComAdapter`, the server:

1. Spawns a **daemon thread** (`ComDispatcher-STA`) for COM operations
2. Maintains a **queue of pending calls** between the main thread and the STA thread
3. Holds references to **COM objects** (`_access_app`, `_current_db`, `_ado_conn`)

When opencode terminates the session, it sends termination signals to the Python process. Without proper handling:

```
opencode session closed
    ↓
SIGTERM/SIGINT sent to Python process
    ↓
Process terminates IMMEDIATELY (no cleanup)
    ↓
ComDispatcher daemon thread killed abruptly
    ↓
Pending futures never resolved → InvalidStateError
    ↓
COM objects not released → MS Access instances orphaned
    ↓
Error propagates to opencode (reported as bun.js error)
```

### Key Issues Identified

#### 1. No Signal Handlers

The server module (`server.py`) had no signal handlers registered:

```python
# BEFORE: No signal handling
if __name__ == "__main__":
    mcp.run(transport="stdio")
```

When opencode sends `SIGTERM` or `SIGINT`, the process dies without cleanup.

#### 2. Pending Futures Not Cancelled

The `ComDispatcher.call()` method creates `concurrent.futures.Future` objects:

```python
def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    future: concurrent.futures.Future[Any] = concurrent.futures.Future()
    self._call_queue.put((fn, args, kwargs, future))
    return future.result(timeout=self.DISPATCH_TIMEOUT)
```

When the thread is killed while calls are pending, attempting to set results on cancelled futures raises `InvalidStateError`.

#### 3. COM Objects Not Released

The `_release_com_safe()` method exists but is only called when the dispatcher shuts down gracefully. Without proper shutdown, COM objects remain in memory and MS Access instances continue running.

#### 4. No atexit Handler

Python's `atexit` module provides a way to register cleanup functions. Without registration, even normal process exit skips cleanup.

## The Solution

### 1. Signal Handlers in server.py

```python
import signal
import atexit
import logging

_logger = logging.getLogger(__name__)

def _graceful_shutdown() -> None:
    """Clean up all resources on process exit."""
    try:
        container = get_container()
        for name in list(container.connection_pool.list().keys()):
            try:
                container.connection_pool.disconnect(name)
            except Exception as e:
                _logger.debug(f"Error disconnecting '{name}' during shutdown: {e}")
    except Exception as e:
        _logger.debug(f"Error during graceful shutdown: {e}")

def _handle_signal(signum: int, frame: Any) -> None:
    """Signal handler for graceful shutdown on SIGTERM/SIGINT."""
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    _logger.info(f"Received {sig_name}, initiating graceful shutdown...")
    _graceful_shutdown()
    raise SystemExit(0)

# Register signal handlers and atexit cleanup
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, _handle_signal)
if hasattr(signal, 'SIGINT'):
    signal.signal(signal.SIGINT, _handle_signal)
atexit.register(_graceful_shutdown)
```

###2. Flush Pending Futures in ComDispatcher

```python
def shutdown(self) -> None:
    """Signal the dispatcher thread to stop and clean up COM objects."""
    self._stopping = True
    # Flush pending futures with CancelledError before shutting down
    self._flush_pending_futures()
    # ... rest of shutdown logic

def _flush_pending_futures(self) -> None:
    """Cancel all pending futures in the queue to prevent hanging calls."""
    cancelled = 0
    while True:
        try:
            fn, args, kwargs, future = self._call_queue.get_nowait()
            if fn is not None:
                try:
                    future.cancel()
                    cancelled += 1
                except Exception:
                    pass
        except queue.Empty:
            break
    if cancelled > 0:
        logger.debug(f"Flushed {cancelled} pending futures during shutdown")
```

### 3. Handle InvalidStateError

```python
try:
    result = fn(*args, **kwargs)
    future.set_result(result)
except Exception as e:
    try:
        future.set_exception(e)
    except concurrent.futures.InvalidStateError:
        # Future was cancelled — discard exception
        pass
```

## Files Modified

### `src/ms_access_mcp/mcp/server.py`

- Added `signal`, `atexit`, and `logging` imports
- Added `_graceful_shutdown()` function
- Added `_handle_signal()` function
- Registered signal handlers for SIGTERM and SIGINT
- Registered atexit handler

### `src/ms_access_mcp/adapters/com_dispatcher.py`

- Added `_flush_pending_futures()` method
- Modified `shutdown()` to call `_flush_pending_futures()`
- Added `InvalidStateError` handling in `_run()` loop

## How It Works Now

```
opencode session closed
    ↓
SIGTERM/SIGINT sent to Python process
    ↓
_handle_signal() catches the signal
    ↓
_graceful_shutdown() is called
    ↓
All connections disconnected (releases COM objects)
    ↓
ComDispatcher.shutdown() called
    ↓
_pending futures cancelled
    ↓
COM cleanup (_release_com_safe) runs
    ↓
Process exits cleanly with code 0
```

## Testing the Fix

### Manual Test

1. Start the MCP server:
   ```powershell
   python -m ms_access_mcp.mcp.server
   ```

2. Connect to a database using opencode

3. Close the opencode session

4. Verify:
   - No error displayed in opencode
   - No orphaned MSACCESS.EXE processes
   - Clean exit in server logs

### Automated Test

```python
import subprocess
import signal
import time

def test_graceful_shutdown():
    # Start server
    proc = subprocess.Popen(
        ["python", "-m", "ms_access_mcp.mcp.server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(2)  # Wait for startup
    
    # Send SIGTERM
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=10)
    
    # Verify clean exit
    assert proc.returncode == 0, "Server should exit cleanly"
```

## Additional Notes

### Why bun.js Gets Blamed

opencode is built on bun.js (a JavaScript runtime). When the Python server process terminates abnormally, the error propagates through the MCP protocol and gets attributed to the JavaScript layer. This is a red herring — the actual issue is in Python's cleanup logic.

### Daemon Threads and Shutdown

Python daemon threads are terminated when the main process exits. This is intentional for non-critical threads, but the `ComDispatcher` thread holds critical resources (COM objects) that must be explicitly released. Making it a daemon thread without proper cleanup causes resource leaks.

### COM Thread Affinity

COM objects have thread affinity — they must be created and used on the same thread. The `ComDispatcher` solves this by running all COM operations on a dedicated STA (Single-Threaded Apartment) thread. When this thread is killed without cleanup, the COM objects become orphaned references.

## References

- [Python atexit module](https://docs.python.org/3/library/atexit.html)
- [Python signal module](https://docs.python.org/3/library/signal.html)
- [concurrent.futures documentation](https://docs.python.org/3/library/concurrent.futures.html)
- [pywin32 COM documentation](https://github.com/mhammond/pywin32)
