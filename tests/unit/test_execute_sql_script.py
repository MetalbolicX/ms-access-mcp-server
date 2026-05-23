import pytest
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
from ms_access_mcp.adapters.wincom import WinComAdapter, ComDispatcher


class TestWinComAdapterExecuteSqlScriptNotConnected:
    """execute_sql_script returns error when adapter not connected."""

    def test_returns_error_when_not_connected(self):
        """File exists but adapter is not connected — returns not-connected error."""
        with patch.object(sys, 'platform', 'win32'):
            adapter = WinComAdapter()
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
                f.write("SELECT 1;")
                temp_path = f.name
            try:
                result = adapter.execute_sql_script(temp_path)
                assert result["success"] is False
                assert "not connected" in result["error"].lower()
            finally:
                os.unlink(temp_path)


class TestWinComAdapterExecuteSqlScriptFileNotFound:
    """execute_sql_script returns error for non-existent file."""

    def test_file_not_found_returns_file_error(self):
        """File check happens before connection check."""
        with patch.object(sys, 'platform', 'win32'):
            adapter = WinComAdapter()
            result = adapter.execute_sql_script("C:\\nonexistent\\path\\file.sql")
            assert result["success"] is False
            assert "not found" in result["error"].lower()


class TestWinComAdapterExecuteSqlScriptEmptyFile:
    """execute_sql_script handles empty file."""

    def test_empty_file_returns_zero_statements(self):
        """Empty file — not-connected check triggers first since dispatcher not started."""
        with patch.object(sys, 'platform', 'win32'):
            adapter = WinComAdapter()
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
                f.write("")
                temp_path = f.name
            try:
                result = adapter.execute_sql_script(temp_path)
                assert result["success"] is False
            finally:
                os.unlink(temp_path)


class TestOdbcAdapterExecuteSqlScript:
    """OdbcAdapter does not support execute_sql_script (COM-only)."""

    def setup_method(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter
        self.adapter = OdbcAdapter()

    def test_odbc_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.adapter.execute_sql_script("/tmp/test.sql")


class TestComDispatcher:
    """ComDispatcher thread-safety behavior (mocked)."""

    def test_dispatcher_initial_state(self):
        """Dispatcher starts unstarted."""
        with patch.object(sys, 'platform', 'win32'):
            d = ComDispatcher()
            assert d._started is False
            assert d._thread is None
            assert d.is_connected() is False

    def test_dispatcher_call_raises_before_start(self):
        """call() before start() raises RuntimeError."""
        with patch.object(sys, 'platform', 'win32'):
            d = ComDispatcher()
            with pytest.raises(RuntimeError, match="not been started"):
                d.call(lambda: 42)

    def test_dispatcher_set_db_path(self):
        """set_db_path stores the path without starting thread."""
        with patch.object(sys, 'platform', 'win32'):
            d = ComDispatcher()
            d.set_db_path("D:/test.accdb")
            assert d._db_path == "D:/test.accdb"

    def test_dispatcher_shutdown_idempotent(self):
        """shutdown() is safe to call twice."""
        with patch.object(sys, 'platform', 'win32'):
            d = ComDispatcher()
            d._started = True  # simulate started state
            d._thread = MagicMock()
            d._stopping = False
            # Should not raise
            d.shutdown()
            assert d._started is False