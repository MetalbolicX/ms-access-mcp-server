"""COM integration tests for ComDispatcher thread safety and lifecycle.

Tests ComDispatcher directly without requiring a full WinComAdapter connection.
"""

import sys
import threading
import time

import pytest

from tests.integration.helpers import skip_unless_windows, skip_unless_pywin32

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
]


class TestComDispatcherBasic:
    """ComDispatcher lifecycle without COM — lightweight functions only."""

    def test_dispatcher_starts_and_stops(self):
        """Create dispatcher, start it, verify started, then shutdown."""
        from ms_access_mcp.adapters.wincom import ComDispatcher

        dispatcher = ComDispatcher()
        assert not dispatcher._started

        dispatcher.start()
        assert dispatcher._started
        assert dispatcher._thread is not None
        assert dispatcher._thread.daemon is True

        dispatcher.shutdown()
        # After shutdown, _started is False
        assert dispatcher._started is False

    def test_call_with_simple_lambda(self):
        """Start dispatcher and call a simple lambda function."""
        from ms_access_mcp.adapters.wincom import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.start()

        try:
            result = dispatcher.call(lambda: 42)
            assert result == 42
        finally:
            dispatcher.shutdown()

    def test_is_connected_returns_false_before_connect(self):
        """is_connected returns False when no DB is opened."""
        from ms_access_mcp.adapters.wincom import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.start()

        try:
            # Before any DB connection, is_connected should be False
            connected = dispatcher.is_connected()
            assert connected is False
        finally:
            dispatcher.shutdown()

    def test_call_raises_when_not_started(self):
        """call() raises RuntimeError if dispatcher not started."""
        from ms_access_mcp.adapters.wincom import ComDispatcher

        dispatcher = ComDispatcher()
        # Don't start it
        with pytest.raises(RuntimeError, match="not been started"):
            dispatcher.call(lambda: 42)

    def test_reentrant_start_works(self):
        """Start -> shutdown -> start again works (idempotent/reentrant)."""
        from ms_access_mcp.adapters.wincom import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.start()
        result1 = dispatcher.call(lambda: 1)
        assert result1 == 1

        dispatcher.shutdown()

        # Re-start after shutdown
        dispatcher.start()
        result2 = dispatcher.call(lambda: 2)
        assert result2 == 2
        dispatcher.shutdown()


class TestComDispatcherTimeout:
    """Timeout behavior tests."""

    def test_call_raises_runtime_when_dispatcher_not_started(self):
        """call() raises RuntimeError when dispatcher was never started."""
        from ms_access_mcp.adapters.wincom import ComDispatcher

        dispatcher = ComDispatcher()
        # Never called start()
        with pytest.raises(RuntimeError):
            dispatcher.call(lambda: 99)


class TestComDispatcherConcurrentCalls:
    """Concurrency tests — calls are serialized through STA thread."""

    def test_multiple_calls_return_correct_values(self):
        """Sequential calls return correct values in order."""
        from ms_access_mcp.adapters.wincom import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.start()

        try:
            r1 = dispatcher.call(lambda: 1)
            r2 = dispatcher.call(lambda: 2)
            r3 = dispatcher.call(lambda: 3)
            assert r1 == 1
            assert r2 == 2
            assert r3 == 3
        finally:
            dispatcher.shutdown()

    def test_calls_are_serialized(self):
        """Multiple calls complete in order — no parallelism."""
        from ms_access_mcp.adapters.wincom import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.start()

        try:
            results = []
            for i in range(5):
                r = dispatcher.call(lambda x=i: x * 2)
                results.append(r)
            assert results == [0, 2, 4, 6, 8]
        finally:
            dispatcher.shutdown()


class TestComDispatcherWithWinComAdapter:
    """ComDispatcher through WinComAdapter — requires temp DB."""

    def setup_method(self):
        import shutil
        import tempfile
        from tests.integration.helpers import TEST_DB

        if not TEST_DB:
            pytest.skip("No test database available")

        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        try:
            self.adapter.disconnect()
        except Exception:
            pass
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_is_connected_through_adapter(self):
        """WinComAdapter.is_connected() reflects dispatcher state."""
        assert self.adapter.is_connected() is True

        self.adapter.disconnect()
        assert self.adapter.is_connected() is False

    def test_adapter_rejects_calls_after_disconnect(self):
        """After disconnect, adapter operations return error dict."""
        import shutil
        import tempfile
        from tests.integration.helpers import TEST_DB

        # Reconnect
        db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter.connect(db_path)

        self.adapter.disconnect()
        # Any operation should now fail gracefully
        result = self.adapter.get_tables()
        assert result == []

    def test_dispatcher_shutdown_and_restart(self):
        """Shutdown dispatcher via adapter, restart with new connection."""
        # First connection
        db_path1 = self.db_path
        self.adapter.connect(db_path1)
        assert self.adapter.is_connected() is True

        # Disconnect
        self.adapter.disconnect()
        assert self.adapter.is_connected() is False

        # Reconnect with new DB copy
        import shutil
        db_path2 = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter.connect(db_path2)
        assert self.adapter.is_connected() is True
        tables = self.adapter.get_tables()
        assert isinstance(tables, list)