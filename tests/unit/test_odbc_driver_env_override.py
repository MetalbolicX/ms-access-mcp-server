"""Unit tests for OdbcAdapter ACCESS_MCP_ODBC_DRIVER env var override."""
import os
import tempfile
from unittest.mock import patch, MagicMock

from ms_access_mcp.adapters.odbc import OdbcAdapter


class TestOdbcDriverEnvOverride:
    """Test ACCESS_MCP_ODBC_DRIVER env var handling in OdbcAdapter."""

    DEFAULT_DRIVER = "{Microsoft Access Driver (*.mdb, *.accdb)}"

    def test_env_var_read_when_present(self, monkeypatch):
        """OdbcAdapter reads ACCESS_MCP_ODBC_DRIVER when set."""
        monkeypatch.setenv("ACCESS_MCP_ODBC_DRIVER", "MDBTOOLS")
        with patch("pyodbc.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            adapter = OdbcAdapter()
            # The driver name should be stored in the adapter
            assert adapter._driver_name == "MDBTOOLS"

    def test_env_var_falls_back_to_default_when_unset(self, monkeypatch):
        """OdbcAdapter falls back to default driver when env var is not set."""
        monkeypatch.delenv("ACCESS_MCP_ODBC_DRIVER", raising=False)
        with patch("pyodbc.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            adapter = OdbcAdapter()
            assert adapter._driver_name == self.DEFAULT_DRIVER

    def test_connection_string_contains_driver_from_env(self, monkeypatch):
        """Connection string uses driver name from ACCESS_MCP_ODBC_DRIVER."""
        monkeypatch.setenv("ACCESS_MCP_ODBC_DRIVER", "MDBTOOLS")
        with patch("pyodbc.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            adapter = OdbcAdapter()
            with tempfile.NamedTemporaryFile(suffix=".mdb", delete=False) as f:
                db_path = f.name
            try:
                adapter.connect(db_path)
                # Check that pyodbc.connect was called with a connection string containing MDBTOOLS
                call_args = mock_connect.call_args
                conn_str = call_args[0][0]
                assert "Driver=MDBTOOLS" in conn_str
            finally:
                os.unlink(db_path)

    def test_connection_string_contains_default_driver_when_env_unset(self, monkeypatch):
        """Connection string uses default driver when ACCESS_MCP_ODBC_DRIVER is unset."""
        monkeypatch.delenv("ACCESS_MCP_ODBC_DRIVER", raising=False)
        with patch("pyodbc.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            adapter = OdbcAdapter()
            with tempfile.NamedTemporaryFile(suffix=".mdb", delete=False) as f:
                db_path = f.name
            try:
                adapter.connect(db_path)
                call_args = mock_connect.call_args
                conn_str = call_args[0][0]
                assert f"Driver={self.DEFAULT_DRIVER}" in conn_str
            finally:
                os.unlink(db_path)

    def test_empty_string_env_var_falls_back_to_default(self, monkeypatch):
        """ACCESS_MCP_ODBC_DRIVER with empty string falls back to default."""
        monkeypatch.setenv("ACCESS_MCP_ODBC_DRIVER", "")
        with patch("pyodbc.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            adapter = OdbcAdapter()
            assert adapter._driver_name == self.DEFAULT_DRIVER

    def test_whitespace_only_env_var_falls_back_to_default(self, monkeypatch):
        """ACCESS_MCP_ODBC_DRIVER with whitespace-only string falls back to default."""
        monkeypatch.setenv("ACCESS_MCP_ODBC_DRIVER", "   ")
        with patch("pyodbc.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            adapter = OdbcAdapter()
            assert adapter._driver_name == self.DEFAULT_DRIVER

    def test_env_var_with_whitespace_is_stripped(self, monkeypatch):
        """ACCESS_MCP_ODBC_DRIVER with surrounding whitespace is stripped."""
        monkeypatch.setenv("ACCESS_MCP_ODBC_DRIVER", "  MDBTOOLS  ")
        with patch("pyodbc.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            adapter = OdbcAdapter()
            assert adapter._driver_name == "MDBTOOLS"
