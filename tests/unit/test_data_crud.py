"""Tests for data-crud capability — insert_data, update_data, delete_data."""

import pytest
from unittest.mock import MagicMock
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter


class TestWinComAdapterDataCrud:
    """TDD tests for WinComAdapter data-crud operations."""

    def test_insert_data_single_row(self):
        """WinComAdapter.insert_data should build and execute INSERT INTO [table] (cols) VALUES (?, ?, ...)."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_db = MagicMock()
        mock_db.Execute = MagicMock(return_value=None)
        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.insert_data("Customers", {"Name": "Alice", "Email": "alice@example.com"})

        assert result["success"] is True
        assert "affected" in result
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO [Customers]" in sql
        assert "[Name]" in sql
        assert "[Email]" in sql
        assert call_args[0][1] == 128

    def test_insert_data_multiple_rows(self):
        """WinComAdapter.insert_data should insert multiple rows when data is a list of dicts."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_db = MagicMock()
        mock_db.Execute = MagicMock(return_value=None)
        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.insert_data("Customers", [
            {"Name": "Alice", "Email": "alice@example.com"},
            {"Name": "Bob", "Email": "bob@example.com"},
        ])

        assert result["success"] is True
        assert result["affected"] == 2
        assert mock_db.Execute.call_count == 2

    def test_update_data_with_where_dict(self):
        """WinComAdapter.update_data should build UPDATE [table] SET col = ? ... WHERE col = ? with dict where."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_db = MagicMock()
        mock_db.Execute = MagicMock(return_value=None)
        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.update_data("Customers", {"Name": "Alice Updated"}, {"ID": 1})

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "UPDATE [Customers] SET" in sql
        assert "[Name]" in sql
        assert "[ID]" in sql
        assert call_args[0][1] == 128

    def test_update_data_with_where_string(self):
        """WinComAdapter.update_data should use raw string WHERE clause when where_dict is a string."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_db = MagicMock()
        mock_db.Execute = MagicMock(return_value=None)
        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.update_data("Customers", {"Name": "Alice Updated"}, "ID = 1 AND Status = 'Active'")

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "UPDATE [Customers] SET" in sql
        assert "[Name]" in sql
        assert "ID = 1 AND Status = 'Active'" in sql

    def test_update_data_no_where(self):
        """WinComAdapter.update_data should have no WHERE clause when where_dict is None."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_db = MagicMock()
        mock_db.Execute = MagicMock(return_value=None)
        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.update_data("Customers", {"Name": "All Updated"})

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "UPDATE [Customers] SET" in sql
        assert "WHERE" not in sql

    def test_delete_data_with_where_dict(self):
        """WinComAdapter.delete_data should build DELETE FROM [table] WHERE col = ? AND col = ? with dict."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_db = MagicMock()
        mock_db.Execute = MagicMock(return_value=None)
        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.delete_data("Customers", {"ID": 1, "Status": "Inactive"})

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "DELETE FROM [Customers]" in sql
        assert "[ID]" in sql
        assert "[Status]" in sql
        assert "WHERE" in sql
        assert call_args[0][1] == 128

    def test_delete_data_with_where_string(self):
        """WinComAdapter.delete_data should use raw string WHERE clause when where_dict is a string."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_db = MagicMock()
        mock_db.Execute = MagicMock(return_value=None)
        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.delete_data("Customers", "ID = 1 OR Status = 'Spam'")

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "DELETE FROM [Customers]" in sql
        assert "ID = 1 OR Status = 'Spam'" in sql

    def test_delete_data_no_where(self):
        """WinComAdapter.delete_data should delete all rows when where_dict is None."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_db = MagicMock()
        mock_db.Execute = MagicMock(return_value=None)
        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.delete_data("Customers")

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "DELETE FROM [Customers]" in sql
        assert "WHERE" not in sql

    def test_insert_data_returns_error_when_not_connected(self):
        """WinComAdapter.insert_data should return error when not connected."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = False
        adapter._db_path = None

        result = adapter.insert_data("Customers", {"Name": "Alice"})

        assert result["success"] is False
        assert "error" in result


class TestOdbcAdapterDataCrud:
    """TDD tests for OdbcAdapter data-crud operations."""

    def test_insert_data_single_row(self):
        """OdbcAdapter.insert_data should build INSERT INTO [table] (cols) VALUES (?, ?, ...) parameterized."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.insert_data("Customers", {"Name": "Alice", "Email": "alice@example.com"})

        assert result["success"] is True
        assert result["affected"] == 1
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO [Customers]" in sql
        assert "[Name]" in sql
        assert "[Email]" in sql
        params = call_args[0][1]
        assert "Alice" in params
        assert "alice@example.com" in params

    def test_insert_data_multiple_rows(self):
        """OdbcAdapter.insert_data should insert multiple rows when data is a list of dicts."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.insert_data("Customers", [
            {"Name": "Alice", "Email": "alice@example.com"},
            {"Name": "Bob", "Email": "bob@example.com"},
        ])

        assert result["success"] is True
        assert result["affected"] == 2
        assert mock_cursor.execute.call_count == 2

    def test_update_data_with_where(self):
        """OdbcAdapter.update_data should build UPDATE [table] SET col = ? ... WHERE col = ? parameterized."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.update_data("Customers", {"Name": "Alice Updated"}, {"ID": 1})

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "UPDATE [Customers] SET" in sql
        assert "[Name]" in sql
        assert "[ID]" in sql
        params = call_args[0][1]
        assert "Alice Updated" in params
        assert 1 in params

    def test_update_data_no_where(self):
        """OdbcAdapter.update_data should have no WHERE clause when where_dict is None."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 10
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.update_data("Customers", {"Status": "Inactive"})

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "UPDATE [Customers] SET" in sql
        assert "WHERE" not in sql

    def test_delete_data_with_where(self):
        """OdbcAdapter.delete_data should build DELETE FROM [table] WHERE col = ? parameterized."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.delete_data("Customers", {"ID": 1, "Status": "Spam"})

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "DELETE FROM [Customers]" in sql
        assert "[ID]" in sql
        assert "[Status]" in sql
        params = call_args[0][1]
        assert 1 in params
        assert "Spam" in params

    def test_delete_data_no_where(self):
        """OdbcAdapter.delete_data should delete all rows when where_dict is None."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.delete_data("Customers")

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "DELETE FROM [Customers]" in sql
        assert "WHERE" not in sql

    def test_insert_data_returns_error_when_not_connected(self):
        """OdbcAdapter.insert_data should return error when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.insert_data("Customers", {"Name": "Alice"})

        assert result["success"] is False
        assert "error" in result

    def test_update_data_returns_error_when_not_connected(self):
        """OdbcAdapter.update_data should return error when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.update_data("Customers", {"Name": "Alice"})

        assert result["success"] is False
        assert "error" in result

    def test_delete_data_returns_error_when_not_connected(self):
        """OdbcAdapter.delete_data should return error when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.delete_data("Customers")

        assert result["success"] is False
        assert "error" in result