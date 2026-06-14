# Design: COM Thread Affinity

## Technical Approach

Introduce a `ComDispatcher` class that owns a dedicated STA thread and holds all COM objects. `WinComAdapter` becomes a thin proxy — each method wraps its work through `dispatcher.call(fn, *args)`. This ensures all COM operations execute on the same thread regardless of which async worker fielded the request.

## Architecture Decisions

### Decision: COM object ownership — dispatcher vs adapter

**Choice**: `ComDispatcher` owns the `Access.Application`, `_current_db`, `_ado_conn` COM objects. `WinComAdapter` holds no COM references directly.

**Alternatives considered**:
- Adapter owns COM objects, dispatcher ensures thread-safe access — adds complexity managing cross-thread COM object access
- Single global dispatcher (module-level) — simpler but harder to test and couples all adapters to one Access instance

**Rationale**: Centralizing COM ownership in the dispatcher is the classic COM apartment pattern. The adapter is a pure proxy — testable by injecting a mock dispatcher.

### Decision: Dispatcher lifecycle — per-adapter vs shared

**Choice**: Each `WinComAdapter` instance gets its own `ComDispatcher`.

**Alternatives considered**:
- Global singleton dispatcher shared across all adapters — would require connection-to-dispatcher mapping
- Session-scoped dispatcher — premature optimization

**Rationale**: `connect_access(use_com=True)` creates a new adapter per connection. The natural mapping is one dispatcher per adapter instance. When `disconnect()` is called, the dispatcher shuts down cleanly.

### Decision: Call serialization — queue with Future result

**Choice**: `threading.Queue` + `concurrent.futures.Future` for each call.

**Alternatives considered**:
- `multiprocessing.Queue` — overkill for in-process thread dispatch
- `asyncio.Queue` — would require bridging sync COM calls into async, complex
- `queue.Queue` with callback — loses return value pattern

**Rationale**: Python stdlib `concurrent.futures.Future` is the canonical way to get a result from a concurrent call. Paired with `queue.Queue` for the message-passing, this is the simplest reliable pattern.

### Decision: Timeout

**Choice**: 30-second timeout on `Future.result()`; after timeout, set a flag and let the dispatcher thread continue.

**Alternatives considered**:
- No timeout — risk of indefinite deadlock if Access hangs
- Kill the dispatcher thread — undefined behavior with COM

**Rationale**: If a COM call hangs (e.g., modal dialog from Access), the caller gets `TimeoutError`. The dispatcher continues processing other requests. A subsequent `disconnect()` can trigger cleanup.

## Data Flow

```
MCP Request (any thread)
        │
        ▼
WinComAdapter.method() ──dispatcher.call(fn, args)──┐
        ▲                                           │
        │                                           ▼
        │                              ┌─────────────────────┐
        │                              │  ComDispatcher      │
        │                              │  ┌───────────────┐  │
        │                              │  │ STA Thread    │  │
        │                              │  │ pythoncom.Co  │  │
        │                              │  │ Initialize()  │  │
        │                              │  │               │  │
        │                              │  │ Access.App    │  │
        │                              │  │ .Dispatch()   │  │
        │                              │  │               │  │
        │                              │  │ while True:   │  │
        │                              │  │   fn,*a,**k = │  │
        │                              │  │       queue.get│  │
        │                              │  │   result = fn │  │
        │                              │  │   future.put()│  │
        │                              └─────────────────────┘
        │                                           │
        └──────────── future.result() ←─────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ms_access_mcp/adapters/wincom.py` | Modify | Add `ComDispatcher` class; refactor all ~40 COM methods to route through dispatcher |
| `src/ms_access_mcp/adapters/base.py` | None | No changes |
| `tests/unit/test_concrete_adapters.py` | Modify | Add instantiation test for dispatcher-aware adapter |
| `tests/unit/test_execute_sql_script.py` | Modify | Mock dispatcher in tests |

## Interfaces / Contracts

### ComDispatcher

```python
class ComDispatcher:
    def __init__(self) -> None:
        """Create dispatcher and start STA thread."""

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        """Execute fn(*args, **kwargs) on STA thread. Returns result.
        Raises TimeoutError if >30s. Raises Exception if fn raises."""

    def set_db_path(self, db_path: str) -> None:
        """Called by adapter's connect() — tells dispatcher which DB to open."""

    def is_connected(self) -> bool:
        """Check if dispatcher has an active Access.Application connection."""

    def shutdown(self) -> None:
        """Close Access, stop thread, clean up COM."""
```

### WinComAdapter changes

```python
class WinComAdapter:
    def __init__(self) -> None:
        self._dispatcher = ComDispatcher()  # owned

    # All COM-touching methods:
    def get_tables(self) -> list[TableInfo]:
        def _do():
            # same logic as current method, but with self._dispatcher._access_app
            ...
        return self._dispatcher.call(_do)
```

### Platform guard

```python
import sys

class WinComAdapter:
    def __init__(self) -> None:
        if sys.platform != 'win32':
            raise RuntimeError("WinComAdapter requires Windows (COM automation)")
        self._dispatcher: Optional[ComDispatcher] = None
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit (Linux) | `ComDispatcher` call/reraise logic, timeout, platform guard | Mock threading components; `unittest.mock.patch` queue and thread |
| Unit (Linux) | `WinComAdapter` method dispatch routing | Inject mock dispatcher; verify `dispatcher.call` is invoked per method |
| Unit (Linux) | `is_connected`, `connect`, `disconnect` | Mock dispatcher; verify sequence of dispatcher calls |
| Integration (Windows) | Connect → multiple ops → disconnect, 3x | `powershell.exe` MCP protocol test |

## Migration / Rollback

No data migration needed. Feature is pure runtime behavior change. Rollback via `git checkout`.

## Open Questions

- [ ] Should `ComDispatcher` be a module-level singleton to allow sharing across adapters? (Not needed now — each `connect_access` creates a new adapter anyway)
- [ ] Should the dispatcher thread be named for debugging purposes? (Nice to have — deferred)