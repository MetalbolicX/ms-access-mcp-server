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


class TestOdbcAdapterAlterTable:
    """TDD tests for OdbcAdapter alter_table operations."""

    def test_alter_table_add_column_generates_alter_table_add_column_sql(self):
        """OdbcAdapter.alter_table with add_column should generate ALTER TABLE ADD COLUMN SQL."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        operations = [
            {"action": "add_column", "params": {"name": "Email", "type": "Text", "size": 100, "nullable": True}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ALTER TABLE" in sql
        assert "[Customers]" in sql
        assert "ADD COLUMN" in sql
        assert "[Email]" in sql
        assert "VARCHAR(100)" in sql
        assert "NULL" in sql

    def test_alter_table_drop_column_generates_alter_table_drop_column_sql(self):
        """OdbcAdapter.alter_table with drop_column should generate ALTER TABLE DROP COLUMN SQL."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        operations = [
            {"action": "drop_column", "params": {"name": "OldCol"}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ALTER TABLE" in sql
        assert "[Customers]" in sql
        assert "DROP COLUMN" in sql
        assert "[OldCol]" in sql

    def test_alter_table_modify_column_generates_alter_table_alter_column_sql(self):
        """OdbcAdapter.alter_table with modify_column should generate ALTER TABLE ALTER COLUMN SQL."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        operations = [
            {"action": "modify_column", "params": {"name": "ID", "type": "Long Integer", "nullable": False}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ALTER TABLE" in sql
        assert "[Customers]" in sql
        assert "ALTER COLUMN" in sql
        assert "[ID]" in sql
        assert "NOT NULL" in sql

    def test_alter_table_rename_table_raises_not_implemented_error(self):
        """OdbcAdapter.alter_table with rename_table should raise NotImplementedError."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        operations = [
            {"action": "rename_table", "params": {"new_name": "NewCustomers"}},
        ]
        with pytest.raises(NotImplementedError):
            adapter.alter_table("Customers", operations)

    def test_alter_table_rename_column_raises_not_implemented_error(self):
        """OdbcAdapter.alter_table with rename_column should raise NotImplementedError."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        operations = [
            {"action": "rename_column", "params": {"name": "OldName", "new_name": "NewName"}},
        ]
        with pytest.raises(NotImplementedError):
            adapter.alter_table("Customers", operations)

    def test_alter_table_invalid_action_returns_error(self):
        """OdbcAdapter.alter_table with invalid action should return error in per-op result."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        operations = [
            {"action": "invalid_action", "params": {}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is False
        assert len(result["operations"]) == 1
        assert result["operations"][0]["success"] is False
        assert "error" in result["operations"][0]

    def test_alter_table_not_connected_returns_error(self):
        """OdbcAdapter.alter_table should return error when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        operations = [
            {"action": "add_column", "params": {"name": "Email", "type": "Text", "size": 50, "nullable": True}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is False
        assert "error" in result

    def test_alter_table_multiple_operations_executes_all(self):
        """OdbcAdapter.alter_table with multiple operations should execute each."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        operations = [
            {"action": "add_column", "params": {"name": "Email", "type": "Text", "size": 100, "nullable": True}},
            {"action": "add_column", "params": {"name": "Phone", "type": "Text", "size": 20, "nullable": True}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        assert mock_cursor.execute.call_count == 2


class TestWinComAdapterAlterTable:
    """TDD tests for WinComAdapter alter_table operations."""

    def _make_adapter(self):
        """Create a WinComAdapter with mocked dispatcher."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"
        adapter._dispatcher.is_connected = MagicMock(return_value=True)
        return adapter

    def test_alter_table_add_column_executes_alter_table_add_column_ddl(self):
        """WinComAdapter.alter_table with add_column should execute ALTER TABLE ADD COLUMN DDL."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        operations = [
            {"action": "add_column", "params": {"name": "Email", "type": "Text", "size": 100, "nullable": True}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        assert len(result["operations"]) == 1
        assert result["operations"][0]["action"] == "add_column"
        assert result["operations"][0]["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "ALTER TABLE" in sql
        assert "[Customers]" in sql
        assert "ADD COLUMN" in sql
        assert "[Email]" in sql
        assert "VARCHAR(100)" in sql
        assert "NULL" in sql
        # Verify DAO_DB_FAIL_ON_ERROR flag (128) is passed
        assert call_args[0][1] == 128

    def test_alter_table_drop_column_executes_alter_table_drop_column_ddl(self):
        """WinComAdapter.alter_table with drop_column should execute ALTER TABLE DROP COLUMN DDL."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        operations = [
            {"action": "drop_column", "params": {"name": "OldCol"}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        assert len(result["operations"]) == 1
        assert result["operations"][0]["action"] == "drop_column"
        assert result["operations"][0]["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "ALTER TABLE" in sql
        assert "[Customers]" in sql
        assert "DROP COLUMN" in sql
        assert "[OldCol]" in sql
        assert call_args[0][1] == 128

    def test_alter_table_modify_column_executes_alter_table_alter_column_ddl(self):
        """WinComAdapter.alter_table with modify_column should execute ALTER TABLE ALTER COLUMN DDL."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        operations = [
            {"action": "modify_column", "params": {"name": "ID", "type": "Long Integer", "nullable": False}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        assert len(result["operations"]) == 1
        assert result["operations"][0]["action"] == "modify_column"
        assert result["operations"][0]["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "ALTER TABLE" in sql
        assert "[Customers]" in sql
        assert "ALTER COLUMN" in sql
        assert "[ID]" in sql
        assert "NOT NULL" in sql
        assert call_args[0][1] == 128

    def test_alter_table_rename_table_sets_tabledef_name(self):
        """WinComAdapter.alter_table with rename_table should set TableDef.Name via DAO."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_tdef = MagicMock()
        mock_db = MagicMock()
        # TableDefs is callable - configure it to return mock_tdef
        mock_db.TableDefs.return_value = mock_tdef

        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        operations = [
            {"action": "rename_table", "params": {"new_name": "NewCustomers"}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        assert len(result["operations"]) == 1
        assert result["operations"][0]["action"] == "rename_table"
        assert result["operations"][0]["success"] is True
        mock_db.TableDefs.assert_called_with("Customers")
        assert mock_tdef.Name == "NewCustomers"

    def test_alter_table_rename_column_sets_field_name(self):
        """WinComAdapter.alter_table with rename_column should set Field.Name via DAO."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_field = MagicMock()
        mock_tdef = MagicMock()
        mock_tdef.Fields.return_value = mock_field

        mock_db = MagicMock()
        mock_db.TableDefs.return_value = mock_tdef

        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        operations = [
            {"action": "rename_column", "params": {"name": "OldName", "new_name": "NewName"}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        assert len(result["operations"]) == 1
        assert result["operations"][0]["action"] == "rename_column"
        assert result["operations"][0]["success"] is True
        mock_tdef.Fields.assert_called_with("OldName")
        assert mock_field.Name == "NewName"

    def test_alter_table_invalid_action_returns_error(self):
        """WinComAdapter.alter_table with invalid action should return error in per-op result."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        operations = [
            {"action": "invalid_action", "params": {}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is False
        assert len(result["operations"]) == 1
        assert result["operations"][0]["success"] is False
        assert "error" in result["operations"][0]

    def test_alter_table_not_connected_returns_error(self):
        """WinComAdapter.alter_table should return error when not connected."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = False
        adapter._db_path = None

        operations = [
            {"action": "add_column", "params": {"name": "Email", "type": "Text", "size": 50, "nullable": True}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is False
        assert "error" in result

    def test_alter_table_multiple_operations_executes_all(self):
        """WinComAdapter.alter_table with multiple operations should execute each."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        operations = [
            {"action": "add_column", "params": {"name": "Email", "type": "Text", "size": 100, "nullable": True}},
            {"action": "add_column", "params": {"name": "Phone", "type": "Text", "size": 20, "nullable": True}},
        ]
        result = adapter.alter_table("Customers", operations)

        assert result["success"] is True
        assert mock_db.Execute.call_count == 2


class TestWinComAdapterIndexOperations:
    """TDD tests for WinComAdapter create_index and drop_index DDL."""

    def _make_adapter(self):
        """Create a WinComAdapter with mocked dispatcher."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"
        adapter._dispatcher.is_connected = MagicMock(return_value=True)
        return adapter

    def test_create_index_executes_create_index_ddl(self):
        """WinComAdapter.create_index should execute CREATE INDEX DDL via db.Execute."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.create_index("Customers", "IX_Name", ["Name"])

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "CREATE INDEX" in sql
        assert "[IX_Name]" in sql
        assert "[Customers]" in sql
        assert "[Name]" in sql
        # Verify DAO_DB_FAIL_ON_ERROR flag (128) is passed
        assert call_args[0][1] == 128

    def test_create_index_with_unique_executes_unique_index_ddl(self):
        """WinComAdapter.create_index with unique=True should include UNIQUE keyword."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.create_index("Customers", "IX_Name_Unique", ["Name"], unique=True)

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "CREATE UNIQUE INDEX" in sql
        assert "[IX_Name_Unique]" in sql

    def test_create_index_with_ignore_nulls_executes_with_ignore_null_ddl(self):
        """WinComAdapter.create_index with ignore_nulls=True should include WITH IGNORE NULL."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.create_index("Customers", "IX_Name", ["Name"], ignore_nulls=True)

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "WITH IGNORE NULL" in sql

    def test_create_index_composite_columns(self):
        """WinComAdapter.create_index with multiple columns should generate composite index DDL."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.create_index("Customers", "IX_Name_City", ["LastName", "City"])

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "[LastName]" in sql
        assert "[City]" in sql

    def test_drop_index_executes_drop_index_ddl(self):
        """WinComAdapter.drop_index should execute DROP INDEX DDL via db.Execute."""
        from unittest.mock import PropertyMock
        adapter = self._make_adapter()

        mock_db = MagicMock()
        type(adapter._dispatcher).current_db = PropertyMock(return_value=mock_db)

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.drop_index("Customers", "IX_Name")

        assert result["success"] is True
        mock_db.Execute.assert_called_once()
        call_args = mock_db.Execute.call_args
        sql = call_args[0][0]
        assert "DROP INDEX" in sql
        assert "[IX_Name]" in sql
        assert "[Customers]" in sql
        # Verify DAO_DB_FAIL_ON_ERROR flag (128) is passed
        assert call_args[0][1] == 128

    def test_create_index_returns_error_when_not_connected(self):
        """WinComAdapter.create_index should return error when not connected."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = False
        adapter._db_path = None

        result = adapter.create_index("Customers", "IX_Name", ["Name"])

        assert result["success"] is False
        assert "error" in result

    def test_drop_index_returns_error_when_not_connected(self):
        """WinComAdapter.drop_index should return error when not connected."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = False
        adapter._db_path = None

        result = adapter.drop_index("Customers", "IX_Name")

        assert result["success"] is False
        assert "error" in result


class TestOdbcAdapterIndexOperations:
    """TDD tests for OdbcAdapter create_index and drop_index DDL."""

    def test_create_index_executes_create_index_ddl(self):
        """OdbcAdapter.create_index should generate and execute CREATE INDEX DDL."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.create_index("Customers", "IX_Name", ["Name"])

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "CREATE INDEX" in sql
        assert "[IX_Name]" in sql
        assert "[Customers]" in sql
        assert "[Name]" in sql
        mock_cursor.close.assert_called_once()

    def test_create_index_with_unique_executes_unique_index_ddl(self):
        """OdbcAdapter.create_index with unique=True should include UNIQUE keyword."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.create_index("Customers", "IX_Name_Unique", ["Name"], unique=True)

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "CREATE UNIQUE INDEX" in sql

    def test_create_index_with_ignore_nulls_executes_with_ignore_null_ddl(self):
        """OdbcAdapter.create_index with ignore_nulls=True should include WITH IGNORE NULL."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.create_index("Customers", "IX_Name", ["Name"], ignore_nulls=True)

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "WITH IGNORE NULL" in sql

    def test_create_index_composite_columns(self):
        """OdbcAdapter.create_index with multiple columns should generate composite index DDL."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.create_index("Customers", "IX_Name_City", ["LastName", "City"])

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "[LastName]" in sql
        assert "[City]" in sql

    def test_drop_index_executes_drop_index_ddl(self):
        """OdbcAdapter.drop_index should execute DROP INDEX sql."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.drop_index("Customers", "IX_Name")

        assert result["success"] is True
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "DROP INDEX" in sql
        assert "[IX_Name]" in sql
        assert "[Customers]" in sql
        mock_cursor.close.assert_called_once()

    def test_create_index_returns_error_when_not_connected(self):
        """OdbcAdapter.create_index should return error when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.create_index("Customers", "IX_Name", ["Name"])

        assert result["success"] is False
        assert "error" in result

    def test_drop_index_returns_error_when_not_connected(self):
        """OdbcAdapter.drop_index should return error when not connected."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.drop_index("Customers", "IX_Name")

        assert result["success"] is False
        assert "error" in result