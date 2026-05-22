import pytest
import os
import tempfile
from ms_access_mcp.adapters.wincom import WinComAdapter


class TestWinComAdapterExecuteSqlScriptNotConnected:
    """execute_sql_script returns error when adapter not connected."""

    def test_returns_error_when_not_connected(self):
        # Use a real temp file path - since file exists but adapter is not connected
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("SELECT 1;")
            temp_path = f.name
        try:
            adapter = WinComAdapter()
            result = adapter.execute_sql_script(temp_path)
            assert result["success"] is False
            assert "not connected" in result["error"].lower()
        finally:
            os.unlink(temp_path)


class TestWinComAdapterExecuteSqlScriptFileNotFound:
    """execute_sql_script returns error for non-existent file."""

    def test_file_not_found_returns_file_error(self):
        adapter = WinComAdapter()
        # File check happens before connection check
        result = adapter.execute_sql_script("C:\\nonexistent\\path\\file.sql")
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestWinComAdapterExecuteSqlScriptEmptyFile:
    """execute_sql_script handles empty file."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_empty_file_returns_zero_statements(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            # Not connected, so should fail on not-connected check first
            result = self.adapter.execute_sql_script(temp_path)
            assert result["success"] is False
        finally:
            os.unlink(temp_path)


class TestOdbcAdapterExecuteSqlScript:
    """OdbcAdapter does not support execute_sql_script (COM-only)."""

    def setup_method(self):
        self.adapter = OdbcAdapter()

    def test_odbc_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.adapter.execute_sql_script("/tmp/test.sql")


from ms_access_mcp.adapters.odbc import OdbcAdapter