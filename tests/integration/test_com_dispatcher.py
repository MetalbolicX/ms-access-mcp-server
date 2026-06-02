r"""
Integration tests for ComDispatcher lifecycle.

Tests cover:
- Start dispatcher → verify running
- Call a method → verify result
- Shutdown dispatcher → verify stopped
- Restart after shutdown → verify clean restart
- Error propagation through dispatcher

Uses the WinComAdapter's internal ComDispatcher to exercise real STA thread
management. Each test gets its own fresh adapter so dispatcher state is isolated.

Markers: com_integration
Execution: pytest tests/integration/test_com_dispatcher.py -m com_integration -v
"""

import pytest

from ms_access_mcp.adapters.wincom import WinComAdapter, ComDispatcher
from helpers import skip_unless_windows, skip_unless_pywin32, skip_unless_db

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


def _cleanup_adapter(adapter: WinComAdapter) -> None:
    """Safely disconnect an adapter, swallowing cleanup exceptions."""
    try:
        if adapter.is_connected():
            adapter.disconnect()
    except Exception:
        pass


class TestComDispatcherLifecycle:
    """ComDispatcher start/call/shutdown/restart lifecycle."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_start_sets_running_flag(self, temp_db_copy: str):
        """start() sets _started=True and spawns the STA thread."""
        assert self.adapter.connect(temp_db_copy)

        # After connect, dispatcher should be started
        assert self.adapter._dispatcher._started is True
        assert self.adapter._dispatcher._thread is not None
        assert self.adapter._dispatcher._thread.is_alive() is True

    def test_dispatcher_accepts_calls(self, temp_db_copy: str):
        """Dispatcher call() executes a function and returns the result."""
        assert self.adapter.connect(temp_db_copy)

        def dummy_fn():
            return 42

        result = self.adapter._dispatcher.call(dummy_fn)
        assert result == 42

    def test_shutdown_clears_running_flag(self, temp_db_copy: str):
        """shutdown() sets _started=False and stops the thread."""
        assert self.adapter.connect(temp_db_copy)
        assert self.adapter._dispatcher._started is True

        self.adapter.disconnect()

        # After disconnect (which calls shutdown), dispatcher should be stopped
        assert self.adapter._dispatcher._started is False

    def test_restart_after_shutdown(self, temp_db_copy: str):
        """start() after shutdown() relaunches a clean STA thread."""
        # Connect first time
        assert self.adapter.connect(temp_db_copy)
        first_thread = self.adapter._dispatcher._thread
        assert first_thread is not None

        # Disconnect (shutdown)
        self.adapter.disconnect()

        # Reconnect — dispatcher should restart cleanly
        assert self.adapter.connect(temp_db_copy)
        assert self.adapter._dispatcher._started is True
        assert self.adapter._dispatcher._thread is not None
        # New thread may be different from old one (expected)
        assert self.adapter._dispatcher._thread.is_alive() is True

    def test_multiple_calls_through_same_dispatcher(self, temp_db_copy: str):
        """Multiple sequential calls through the dispatcher all succeed."""
        assert self.adapter.connect(temp_db_copy)

        def add(a, b):
            return a + b

        r1 = self.adapter._dispatcher.call(add, 1, 2)
        r2 = self.adapter._dispatcher.call(add, 10, 20)
        r3 = self.adapter._dispatcher.call(add, 100, 200)

        assert r1 == 3
        assert r2 == 30
        assert r3 == 300

    def test_dispatcher_thread_is_sta(self, temp_db_copy: str):
        """Verify the dispatcher thread runs in STA mode (apartment state)."""
        import pythoncom

        assert self.adapter.connect(temp_db_copy)

        def check_apartment():
            return pythoncom.GetCurrentThreadApartment()

        apt = self.adapter._dispatcher.call(check_apartment)
        # STA = 2
        assert apt == 2, f"Expected STA apartment (2), got {apt}"


class TestComDispatcherErrorHandling:
    """Error propagation through the dispatcher."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_exception_propagates_from_dispatcher(self, temp_db_copy: str):
        """Exceptions raised inside _do() propagate through call()."""
        assert self.adapter.connect(temp_db_copy)

        def raise_error():
            raise ValueError("test error from dispatcher")

        with pytest.raises(ValueError, match="test error from dispatcher"):
            self.adapter._dispatcher.call(raise_error)

    def test_call_before_start_raises(self):
        """Calling call() before start() raises RuntimeError."""
        dispatcher = ComDispatcher()  # never started

        with pytest.raises(RuntimeError, match="not been started"):
            dispatcher.call(lambda: 42)

    def test_dispatcher_retains_state_after_error(self, temp_db_copy: str):
        """Dispatcher remains usable after an exception in a previous call."""
        assert self.adapter.connect(temp_db_copy)

        def failing():
            raise RuntimeError("expected failure")

        # First call fails
        with pytest.raises(RuntimeError):
            self.adapter._dispatcher.call(failing)

        # Second call should still work
        def succeed():
            return "ok"

        result = self.adapter._dispatcher.call(succeed)
        assert result == "ok"

    def test_dispatcher_shutdown_idempotent(self, temp_db_copy: str):
        """shutdown() can be called multiple times without error."""
        assert self.adapter.connect(temp_db_copy)

        # First shutdown
        self.adapter.disconnect()

        # Second shutdown should not raise
        self.adapter._dispatcher.shutdown()  # should not raise

        assert self.adapter._dispatcher._started is False
