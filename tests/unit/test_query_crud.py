"""Tests for query-crud capability — get_queries, create_query, set_query_sql, delete_query."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.models.database import QueryInfo


class TestWinComAdapterQueryCrud:
    """Task 2.7: TDD tests for WinComAdapter query-crud operations."""

    def test_get_queries_iterates_querydefs_and_returns_list(self):
        """WinComAdapter.get_queries should iterate QueryDefs, filter ~ prefixed, return QueryInfo list."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        # Mock is_connected to return True
        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        # Create mock QueryDefs
        mock_qdef1 = MagicMock()
        mock_qdef1.Name = "Q1"
        mock_qdef1.sql = "SELECT * FROM Table1"
        mock_qdef1.Type = 0

        mock_qdef2 = MagicMock()
        mock_qdef2.Name = "~SysQuery"
        mock_qdef2.sql = "SELECT * FROM MSysObjects"
        mock_qdef2.Type = 0

        mock_qdef3 = MagicMock()
        mock_qdef3.Name = "Q2"
        mock_qdef3.sql = "SELECT id FROM Table2"
        mock_qdef3.Type = 0

        mock_querydefs = [mock_qdef1, mock_qdef2, mock_qdef3]

        # Mock _current_db to return a db with QueryDefs
        mock_db = MagicMock()
        mock_db.QueryDefs = MagicMock()
        # Make QueryDefs(index) return the right query - DAO uses callable with int index
        mock_db.QueryDefs.Count = 3
        mock_db.QueryDefs.side_effect = lambda i: mock_querydefs[i]

        # Set _current_db on the dispatcher
        adapter._dispatcher._current_db = mock_db
        adapter._dispatcher._access_app = MagicMock()  # still exists but won't be used

        def call_side_effect(fn, *args, **kwargs):
            result = fn()
            return result

        adapter._dispatcher.call = call_side_effect

        result = adapter.get_queries()

        # Verify result is a list of QueryInfo objects (not including ~ prefixed)
        assert isinstance(result, list)
        # Should only return Q1 and Q2, not ~SysQuery
        assert len(result) == 2
        names = [q.name for q in result]
        assert "Q1" in names
        assert "Q2" in names
        assert "~SysQuery" not in names

    def test_create_query_calls_createquerydef(self):
        """WinComAdapter.create_query should call db.CreateQueryDef (auto-appends, no explicit Append needed)."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        # Mock the _current_db with CreateQueryDef
        mock_current_db = MagicMock()
        adapter._dispatcher._current_db = mock_current_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.create_query("NewQuery", "SELECT * FROM Customers")

        # Verify CreateQueryDef was called with name and sql
        # CreateQueryDef with non-empty name auto-appends — no explicit Append needed
        mock_current_db.CreateQueryDef.assert_called_once_with("NewQuery", "SELECT * FROM Customers")
        assert result == {"success": True}

    def test_create_query_returns_error_on_exception(self):
        """WinComAdapter.create_query should return error dict on exception."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_current_db = MagicMock()
        mock_current_db.CreateQueryDef.side_effect = Exception("Query already exists")
        adapter._dispatcher._current_db = mock_current_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.create_query("ExistingQuery", "SELECT * FROM Customers")

        assert result["success"] is False
        assert "error" in result

    def test_set_query_sql_updates_existing_querydef(self):
        """WinComAdapter.set_query_sql should find existing QueryDef and update its .sql property."""
        from unittest.mock import MagicMock

        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        # Create the mock QueryDef FIRST, before configuring QueryDefs
        mock_qdef = MagicMock()
        mock_qdef.Name = "Q1"
        mock_qdef.sql = "SELECT * FROM OldTable"

        # Create mock QueryDefs that returns mock_qdef when called by name
        mock_querydefs = MagicMock()
        # Make calling QueryDefs(name) return mock_qdef
        mock_querydefs.return_value = mock_qdef
        mock_querydefs.Delete = MagicMock()

        mock_current_db = MagicMock()
        mock_current_db.QueryDefs = mock_querydefs
        adapter._dispatcher._current_db = mock_current_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.set_query_sql("Q1", "SELECT * FROM NewTable")

        # Verify the query's sql property was updated
        assert mock_qdef.sql == "SELECT * FROM NewTable"
        assert result == {"success": True}

    def test_delete_query_removes_querydef(self):
        """WinComAdapter.delete_query should call QueryDefs.Delete to remove a query."""
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"

        adapter._dispatcher.is_connected = MagicMock(return_value=True)

        mock_querydefs = MagicMock()
        mock_querydefs.Delete = MagicMock()

        mock_current_db = MagicMock()
        mock_current_db.QueryDefs = mock_querydefs
        adapter._dispatcher._current_db = mock_current_db

        def call_side_effect(fn, *args, **kwargs):
            return fn()

        adapter._dispatcher.call = call_side_effect
        adapter._dispatcher._access_app = MagicMock()

        result = adapter.delete_query("Q1")

        mock_querydefs.Delete.assert_called_once_with("Q1")
        assert result == {"success": True}


class TestOdbcAdapterQueryCrud:
    """Task 2.7: TDD tests for OdbcAdapter query-crud operations."""

    def test_get_queries_selects_from_information_schema_views(self):
        """OdbcAdapter.get_queries should SELECT from INFORMATION_SCHEMA.VIEWS."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("Q1", "SELECT * FROM Table1"),
            ("Q2", "SELECT id FROM Table2"),
        ]
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.get_queries()

        # Verify cursor.execute was called with INFORMATION_SCHEMA query
        call_args = mock_cursor.execute.call_args
        sql_query = call_args[0][0] if call_args[0] else call_args[1].get('sql', '')
        assert "INFORMATION_SCHEMA.VIEWS" in sql_query
        assert "TABLE_SCHEMA" in sql_query
        assert "dbo" in sql_query

        # Verify result
        assert isinstance(result, list)
        assert len(result) == 2

    def test_create_query_executes_create_view(self):
        """OdbcAdapter.create_query should execute CREATE VIEW sql."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.create_query("NewQuery", "SELECT * FROM Customers")

        # Verify CREATE VIEW was executed
        call_args = mock_cursor.execute.call_args
        sql_query = call_args[0][0] if call_args[0] else call_args[1].get('sql', '')
        assert "CREATE VIEW" in sql_query
        assert "[NewQuery]" in sql_query
        assert "SELECT * FROM Customers" in sql_query
        assert result == {"success": True}

    def test_create_query_returns_error_on_exception(self):
        """OdbcAdapter.create_query should return error dict on pyodbc exception."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("View already exists")
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.create_query("ExistingQuery", "SELECT * FROM Customers")

        assert result["success"] is False
        assert "error" in result

    def test_set_query_sql_drops_and_creates_view(self):
        """OdbcAdapter.set_query_sql should DROP VIEW then CREATE VIEW."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.set_query_sql("Q1", "SELECT * FROM NewTable")

        # Verify two calls: DROP VIEW and CREATE VIEW
        assert mock_cursor.execute.call_count == 2

        # First call should be DROP VIEW
        drop_call = mock_cursor.execute.call_args_list[0]
        drop_sql = drop_call[0][0] if drop_call[0] else drop_call[1].get('sql', '')
        assert "DROP VIEW" in drop_sql
        assert "[Q1]" in drop_sql

        # Second call should be CREATE VIEW
        create_call = mock_cursor.execute.call_args_list[1]
        create_sql = create_call[0][0] if create_call[0] else create_call[1].get('sql', '')
        assert "CREATE VIEW" in create_sql
        assert "[Q1]" in create_sql
        assert "SELECT * FROM NewTable" in create_sql

        assert result == {"success": True}

    def test_delete_query_executes_drop_view(self):
        """OdbcAdapter.delete_query should execute DROP VIEW sql."""
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()

        mock_cursor = MagicMock()
        adapter._conn.cursor.return_value = mock_cursor

        result = adapter.delete_query("Q1")

        # Verify DROP VIEW was executed
        call_args = mock_cursor.execute.call_args
        sql_query = call_args[0][0] if call_args[0] else call_args[1].get('sql', '')
        assert "DROP VIEW" in sql_query
        assert "[Q1]" in sql_query
        assert result == {"success": True}
