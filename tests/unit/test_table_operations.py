"""Tests for table operations capability — create_table, delete_table."""

import pytest
from unittest.mock import MagicMock
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter


class TestWinComAdapterTableOperations:
    """TDD tests for WinComAdapter create_table and delete_table operations."""

    def test_create_table_calls_createtabledef_and_append(self):
        """WinComAdapter.create_table should call CreateTableDef, CreateField for each col, and append to TableDefs."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_tdef = MagicMock()
        mock_fld = MagicMock()
        mock_tdef.CreateField.return_value = mock_fld
        mock_tdef.Fields = MagicMock()
        mock_tdef.Fields.Append = MagicMock()

        mock_db = MagicMock()
        mock_db.CreateTableDef.return_value = mock_tdef
        mock_db.TableDefs = MagicMock()
        mock_db.TableDefs.Append = MagicMock()

        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        columns = [
            {"name": "ID", "type": "Long Integer"},
            {"name": "Name", "type": "Text", "size": 50},
        ]
        result = adapter.create_table("Customers", columns)

        assert result["success"] is True
        mock_db.CreateTableDef.assert_called_once_with("Customers")
        assert mock_tdef.CreateField.call_count == 2
        mock_tdef.Fields.Append.assert_called()
        mock_db.TableDefs.Append.assert_called_once_with(mock_tdef)

    def test_create_table_sets_required_field_based_on_nullable(self):
        """WinComAdapter.create_table should set Required=True when nullable=False."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_tdef = MagicMock()
        mock_fld = MagicMock()
        mock_tdef.CreateField.return_value = mock_fld
        mock_tdef.Fields = MagicMock()
        mock_tdef.Fields.Append = MagicMock()

        mock_db = MagicMock()
        mock_db.CreateTableDef.return_value = mock_tdef
        mock_db.TableDefs = MagicMock()
        mock_db.TableDefs.Append = MagicMock()

        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        columns = [
            {"name": "ID", "type": "Long Integer", "nullable": False},
        ]
        result = adapter.create_table("Customers", columns)

        assert result["success"] is True
        # nullable=False -> Required = not False = True
        assert mock_fld.Required is True

    def test_delete_table_calls_tabledefs_delete(self):
        """WinComAdapter.delete_table should call TableDefs.Delete to remove a table."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_tdefs = MagicMock()
        mock_tdefs.Delete = MagicMock()

        mock_db = MagicMock()
        mock_db.TableDefs = mock_tdefs

        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.delete_table("Customers")

        assert result["success"] is True
        mock_tdefs.Delete.assert_called_once_with("Customers")

    def test_create_table_returns_error_when_not_connected(self):
        """WinComAdapter.create_table should return error when not connected."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = False
        adapter._db_path = None

        result = adapter.create_table("Customers", [{"name": "ID", "type": "Long Integer"}])

        assert result["success"] is False
        assert "error" in result

    def test_delete_table_returns_error_when_not_connected(self):
        """WinComAdapter.delete_table should return error when not connected."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = False
        adapter._db_path = None

        result = adapter.delete_table("Customers")

        assert result["success"] is False
        assert "error" in result

    def test_create_table_type_mapping_text(self):
        """WinComAdapter.create_table should map type 'Text' to DAO dbText (10)."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        captured_types = []

        mock_tdef = MagicMock()
        mock_fld = MagicMock()
        mock_fld.Required = False

        def create_field_side_effect(name, field_type, size):
            captured_types.append(field_type)
            return mock_fld

        mock_tdef.CreateField.side_effect = create_field_side_effect
        mock_tdef.Fields = MagicMock()
        mock_tdef.Fields.Append = MagicMock()

        mock_db = MagicMock()
        mock_db.CreateTableDef.return_value = mock_tdef
        mock_db.TableDefs = MagicMock()
        mock_db.TableDefs.Append = MagicMock()

        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        columns = [{"name": "Name", "type": "Text", "size": 100}]
        adapter.create_table("Customers", columns)

        # dbText = 10
        assert 10 in captured_types

    def test_create_table_type_mapping_long_integer(self):
        """WinComAdapter.create_table should map type 'Long Integer' to DAO dbLong (4)."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        captured_types = []

        mock_tdef = MagicMock()
        mock_fld = MagicMock()

        def create_field_side_effect(name, field_type, size):
            captured_types.append(field_type)
            return mock_fld

        mock_tdef.CreateField.side_effect = create_field_side_effect
        mock_tdef.Fields = MagicMock()
        mock_tdef.Fields.Append = MagicMock()

        mock_db = MagicMock()
        mock_db.CreateTableDef.return_value = mock_tdef
        mock_db.TableDefs = MagicMock()
        mock_db.TableDefs.Append = MagicMock()

        adapter._dispatcher._current_db = mock_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        columns = [{"name": "ID", "type": "Long Integer"}]
        adapter.create_table("Customers", columns)

        # dbLong = 4
        assert 4 in captured_types


class TestOdbcAdapterTableOperations:
    """TDD tests for OdbcAdapter create_table and delete_table operations."""

    def test_create_table_executes_create_table_ddl(self):
        """OdbcAdapter.create_table should generate and execute CREATE TABLE DDL."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        columns = [
            {"name": "ID", "type": "Long Integer"},
            {"name": "Name", "type": "Text", "size": 50},
        ]
        result = adapter.create_table("Customers", columns)

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "CREATE TABLE" in sql
        assert "[Customers]" in sql
        assert "[ID]" in sql
        assert "[Name]" in sql

    def test_create_table_generates_text_type_with_size(self):
        """OdbcAdapter.create_table should generate VARCHAR(size) for Text type."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        columns = [{"name": "Name", "type": "Text", "size": 100}]
        adapter.create_table("Customers", columns)

        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "VARCHAR(100)" in sql

    def test_create_table_generates_not_null_when_nullable_false(self):
        """OdbcAdapter.create_table should generate NOT NULL when nullable=False."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        columns = [{"name": "ID", "type": "Long Integer", "nullable": False}]
        adapter.create_table("Customers", columns)

        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "NOT NULL" in sql

    def test_delete_table_executes_drop_table(self):
        """OdbcAdapter.delete_table should execute DROP TABLE sql."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.delete_table("Customers")

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "DROP TABLE" in sql
        assert "[Customers]" in sql

    def test_create_table_returns_error_when_not_connected(self):
        """OdbcAdapter.create_table should return error when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.create_table("Customers", [{"name": "ID", "type": "Long Integer"}])

        assert result["success"] is False
        assert "error" in result

    def test_delete_table_returns_error_when_not_connected(self):
        """OdbcAdapter.delete_table should return error when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.delete_table("Customers")

        assert result["success"] is False
        assert "error" in result

    def test_create_table_type_mapping_memo(self):
        """OdbcAdapter.create_table should map type 'Memo' to TEXT (no size)."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        columns = [{"name": "Notes", "type": "Memo"}]
        adapter.create_table("Customers", columns)

        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "TEXT" in sql.upper()

    def test_create_table_type_mapping_boolean(self):
        """OdbcAdapter.create_table should map type 'Boolean' to BIT."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        columns = [{"name": "IsActive", "type": "Boolean"}]
        adapter.create_table("Customers", columns)

        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "BIT" in sql.upper()