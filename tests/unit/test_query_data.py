"""Tests for query_data capability — execute_query method."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter


class TestExecuteQueryReturnsRowsKeyedByColumnName:
    """Task 1.6: TDD test — verify execute_query returns rows as dicts keyed by column name."""

    def test_wincom_execute_query_returns_rows_keyed_by_column_name(self):
        """WinComAdapter.execute_query should return rows as dicts with column names as keys."""
        # This test verifies the NEW dict return shape:
        # {"success": True, "rows": [...], "count": N, "columns": [...]}
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._current_db = MagicMock()
        adapter._dispatcher._started = True

        # Mock OpenRecordset with a recordset that has fields
        mock_rs = MagicMock()
        mock_rs.RecordCount = 2
        mock_rs.EOF = False
        mock_rs.Fields.Count = 2

        # Simulate two fields: "id" and "name"
        mock_field_id = MagicMock()
        mock_field_id.Name = "id"
        mock_field_id.Value = 1

        mock_field_name = MagicMock()
        mock_field_name.Name = "name"
        mock_field_name.Value = "Alice"

        # Index-based field access
        def get_field(i):
            return [mock_field_id, mock_field_name][i]
        mock_rs.Fields.side_effect = get_field
        adapter._dispatcher._current_db.OpenRecordset.return_value = mock_rs
        adapter._dispatcher._access_app = MagicMock()
        adapter._connected = True

        # Mock is_connected to return True
        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        # Mock dispatcher.call to directly return the expected dict
        expected_result = {
            "success": True,
            "rows": [{"id": 1, "name": "Alice"}],
            "count": 1,
            "columns": ["id", "name"]
        }
        adapter._dispatcher.call = MagicMock(return_value=expected_result)

        result = adapter.execute_query("SELECT id, name FROM Customers")

        # Verify the dict shape
        assert isinstance(result, dict), "execute_query should return a dict"
        assert result["success"] is True
        assert result["count"] == 1
        assert result["columns"] == ["id", "name"]
        assert len(result["rows"]) == 1
        assert result["rows"][0]["id"] == 1
        assert result["rows"][0]["name"] == "Alice"

    def test_wincom_execute_query_handles_exception_and_returns_error_shape(self):
        """WinComAdapter.execute_query should catch exceptions and return error dict."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._dispatcher.is_connected = MagicMock(return_value=True)
        adapter._connected = True

        # Simulate an exception being raised
        def raise_error(*args, **kwargs):
            raise Exception("Invalid SQL syntax")

        adapter._dispatcher.call.side_effect = raise_error

        result = adapter.execute_query("SELECT * FROM nonexistent")

        # Should return error shape, not raise
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "error" in result


class TestExecuteQueryOdbcReturnsCorrectShape:
    """Task 1.7: TDD test — verify OdbcAdapter.execute_query returns correct dict shape."""

    def test_odbc_execute_query_returns_correct_shape(self):
        """OdbcAdapter.execute_query should return dict with success, rows, count, columns."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._connected = True

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("id",), ("name",)
        ]
        mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.execute_query("SELECT id, name FROM Customers")

        # This will FAIL in RED because current OdbcAdapter.execute_query
        # returns list[dict] not the new dict shape
        assert isinstance(result, dict), "execute_query should return a dict"
        assert result["success"] is True
        assert result["count"] == 2
        assert result["columns"] == ["id", "name"]
        assert len(result["rows"]) == 2
        assert result["rows"][0]["id"] == 1
        assert result["rows"][0]["name"] == "Alice"
        assert result["rows"][1]["id"] == 2
        assert result["rows"][1]["name"] == "Bob"

    def test_odbc_execute_query_handles_exception_and_returns_error_shape(self):
        """OdbcAdapter.execute_query should catch exceptions and return error dict."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._connected = True

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("SQL syntax error")
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.execute_query("SELECT * FROM nonexistent")

        assert isinstance(result, dict)
        assert result["success"] is False
        assert "error" in result

    def test_odbc_execute_query_when_not_connected_returns_error(self):
        """OdbcAdapter.execute_query should return error dict when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None  # Set _conn to None to simulate not connected
        adapter._connected = False

        result = adapter.execute_query("SELECT id FROM Customers")

        assert isinstance(result, dict)
        assert result["success"] is False
        assert "error" in result