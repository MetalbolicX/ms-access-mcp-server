"""Tests for execute_raw_sql MCP tool."""
from unittest.mock import MagicMock, patch

# isort: off
from ms_access_mcp.mcp import server  # noqa: F401  - import server first to avoid circular import
from ms_access_mcp.mcp import raw_sql as raw_sql_module

# isort: on


class TestToolExecuteRawSql:
    def test_success(self):
        mock_adapter = MagicMock()
        mock_adapter.execute_raw_sql.return_value = 5
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(raw_sql_module, "_pool", return_value=mock_conn):
            result = raw_sql_module.execute_raw_sql(
                "DELETE FROM Customers WHERE ID = 1",
                confirm=True,
            )
            assert result["success"] is True
            assert result["rows_affected"] == 5
            mock_adapter.execute_raw_sql.assert_called_once_with(
                "DELETE FROM Customers WHERE ID = 1",
            )

    def test_not_connected(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False

        with patch.object(raw_sql_module, "_pool", return_value=mock_conn):
            result = raw_sql_module.execute_raw_sql(
                "DELETE FROM Customers", confirm=True,
            )
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_dry_run_returns_preview(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True

        with patch.object(raw_sql_module, "_pool", return_value=mock_conn):
            result = raw_sql_module.execute_raw_sql(
                "DELETE FROM Customers", confirm=True, dry_run=True,
            )
            assert result["dry_run"] is True
            assert result["action"] == "execute_raw_sql"
            assert result["sql"] == "DELETE FROM Customers"

    def test_confirm_false_returns_error(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True

        with patch.object(raw_sql_module, "_pool", return_value=mock_conn):
            result = raw_sql_module.execute_raw_sql(
                "DELETE FROM Customers", confirm=False,
            )
            assert result["success"] is False
            assert "confirm=True" in result["error"]
            assert result["sql"] == "DELETE FROM Customers"

    def test_adapter_exception_returns_error_dict(self):
        mock_adapter = MagicMock()
        mock_adapter.execute_raw_sql.side_effect = Exception("syntax error")
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(raw_sql_module, "_pool", return_value=mock_conn):
            result = raw_sql_module.execute_raw_sql(
                "INVALID SQL", confirm=True,
            )
            assert result["success"] is False
            assert "syntax error" in result["error"]

    def test_no_adapter_returns_error(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = None

        with patch.object(raw_sql_module, "_pool", return_value=mock_conn):
            result = raw_sql_module.execute_raw_sql(
                "SELECT 1", confirm=True,
            )
            assert result["success"] is False
            assert "No adapter" in result["error"]
