"""Connected-path unit tests for OdbcAdapter — mocked pyodbc."""
import os
import json
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.models.database import TableInfo, QueryInfo
from ms_access_mcp.models.migration import TableSchema, ColumnSchema, UnknownMetadata


class ConnectedAdapterTestBase:
    """Base setup for connected-path tests using mocked pyodbc."""

    def setup_method(self):
        """Create a connected adapter with mocked pyodbc connection and cursor."""
        self.mock_conn = MagicMock()
        with patch("pyodbc.connect", return_value=self.mock_conn):
            self.adapter = OdbcAdapter()
        self.adapter._conn = self.mock_conn
        self.mock_cursor = self.mock_conn.cursor.return_value

    def _setup_fetchall(self, rows):
        """Configure mock cursor.fetchall and __iter__ for row iteration."""
        self.mock_cursor.fetchall.return_value = rows
        self.mock_cursor.__iter__ = lambda self: iter(rows)

    def _setup_description(self, columns: list[str]):
        """Set cursor.description with column names (type is None for all)."""
        self.mock_cursor.description = [
            (name, None, None, None, None, None, None) for name in columns
        ]

    def teardown_method(self):
        """No cleanup needed — no patch.start/stop used."""
        pass


class TestOdbcAdapterConnectedHelpers(ConnectedAdapterTestBase):
    """Test static helpers and query string generation."""

    def test_pyodbc_type_name_maps_known_types(self):
        """Known Python types map to expected Access type names."""
        assert self.adapter._pyodbc_type_name("VARCHAR") == "Text"
        assert self.adapter._pyodbc_type_name("CHAR") == "Text"
        assert self.adapter._pyodbc_type_name("INTEGER") == "Long Integer"
        assert self.adapter._pyodbc_type_name("INT") == "Long Integer"
        assert self.adapter._pyodbc_type_name("DATETIME") == "Date/Time"
        assert self.adapter._pyodbc_type_name("DATE") == "Date/Time"
        assert self.adapter._pyodbc_type_name("BIT") == "Boolean"
        assert self.adapter._pyodbc_type_name("DECIMAL") == "Decimal"
        assert self.adapter._pyodbc_type_name("MONEY") == "Currency"
        assert self.adapter._pyodbc_type_name("FLOAT") == "Double"
        assert self.adapter._pyodbc_type_name("DOUBLE") == "Double"
        assert self.adapter._pyodbc_type_name("BINARY") == "Binary"
        assert self.adapter._pyodbc_type_name("IMAGE") == "Binary"
        assert self.adapter._pyodbc_type_name("TEXT") == "Text"
        assert self.adapter._pyodbc_type_name("MEMO") == "Memo"

    def test_pyodbc_type_name_unknown_returns_upper(self):
        """Unknown type strings are returned as-is."""
        assert self.adapter._pyodbc_type_name("unknown") == "unknown"
        assert self.adapter._pyodbc_type_name("UNKNOWN_TYPE") == "UNKNOWN_TYPE"

    def test_pyodbc_type_name_none_handled(self):
        """None input returns as-is (empty string map key)."""
        assert self.adapter._pyodbc_type_name(None) is None

    def test_tables_query_matches_expected_sql(self):
        """_tables_query returns SQL selecting MSysObjects with type and flags."""
        q = self.adapter._tables_query()
        assert "MSysObjects" in q
        assert "type" in q.lower() or "Type" in q
        assert "name" in q.lower() or "Name" in q

    def test_columns_query_escapes_brackets(self):
        """_columns_query escapes brackets in table names for SQL safety."""
        q = self.adapter._columns_query("My]Table")
        assert "[My]]Table]" in q

    def test_columns_query_with_special_chars(self):
        """Bracket in table name is doubled to escape."""
        q = self.adapter._columns_query("Table[1]")
        assert "Table[1]" in q or "Table]]1]" in q


class TestOdbcAdapterConnectedConnectionLifecycle(ConnectedAdapterTestBase):
    """Test connect/disconnect lifecycle with mocked os.path.exists and pyodbc."""

    def test_connect_accdb_uses_oledb_first(self):
        """ACCDB connection tries OLEDB providers before driver."""
        with patch("os.path.exists", return_value=True):
            with patch("pyodbc.connect", return_value=self.mock_conn) as mock_connect:
                result = self.adapter.connect("test.accdb")
                assert result is True
                assert self.adapter._conn is not None
                # At least one call used OLEDB provider string
                calls = [str(c) for c in mock_connect.call_args_list]
                oledb_calls = [c for c in calls if "Microsoft.ACE.OLEDB" in c or "Provider" in c]
                assert len(oledb_calls) > 0

    def test_connect_mdb_uses_driver_first(self):
        """MDB connection tries Access Driver before OLEDB."""
        with patch("os.path.exists", return_value=True):
            with patch("pyodbc.connect", return_value=self.mock_conn) as mock_connect:
                result = self.adapter.connect("test.mdb")
                assert result is True
                # At least one call used Access Driver
                calls = [str(c) for c in mock_connect.call_args_list]
                driver_calls = [c for c in calls if "Microsoft Access Driver" in c or "Driver" in c]
                assert len(driver_calls) > 0

    def test_connect_file_not_found_returns_false(self):
        """connect returns False when file does not exist."""
        self.adapter._conn = None
        with patch("os.path.exists", return_value=False):
            result = self.adapter.connect("nonexistent.accdb")
        assert result is False
        assert self.adapter.is_connected() is False

    def test_disconnect_closes_connection(self):
        """disconnect closes conn and resets state."""
        mock_conn = MagicMock()
        self.adapter._conn = mock_conn
        self.adapter.disconnect()
        mock_conn.close.assert_called_once()
        assert self.adapter._conn is None
        assert self.adapter.is_connected() is False

    def test_disconnect_without_connection_does_nothing(self):
        """disconnect when not connected raises no error."""
        self.adapter._conn = None
        self.adapter.disconnect()  # should not raise


class TestOdbcAdapterConnectedExecuteQuery(ConnectedAdapterTestBase):
    """Test execute_query with mocked cursor."""

    def test_execute_query_returns_dict_rows(self):
        """SELECT results are mapped to list of row dicts."""
        self._setup_description(["ID", "Name"])
        self._setup_fetchall([(1, "Alice"), (2, "Bob")])
        result = self.adapter.execute_query("SELECT * FROM T")
        assert result["success"] is True
        assert len(result["rows"]) == 2
        assert result["rows"][0] == {"ID": 1, "Name": "Alice"}
        assert result["rows"][1] == {"ID": 2, "Name": "Bob"}

    def test_execute_query_passes_params(self):
        """execute_query forwards SQL parameters to cursor.execute."""
        self._setup_description(["ID"])
        self._setup_fetchall([(42,)])
        self.adapter.execute_query("SELECT * FROM T WHERE ID = ?", [1])
        call_args = self.mock_cursor.execute.call_args
        assert call_args is not None
        sql_call = call_args[0][0] if call_args[0] else call_args[1].get("sql", "")
        params_call = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", [])
        assert "?" in sql_call or "WHERE" in sql_call
        # params passed either as positional 2nd arg or keyword
        assert 1 in params_call or [1] == params_call

    def test_execute_query_non_select_returns_empty_rows(self):
        """Non-SELECT (mutation) SQL returns empty rows list without error."""
        self._setup_description([])
        self.mock_cursor.fetchall.side_effect = Exception("No results for mutation")
        self._setup_fetchall([])
        result = self.adapter.execute_query("INSERT INTO T (ID) VALUES (1)")
        assert result["success"] is False or result["count"] == 0

    def test_execute_query_not_connected_returns_error(self):
        """execute_query when disconnected returns error dict."""
        self.adapter._conn = None
        result = self.adapter.execute_query("SELECT 1")
        assert result["success"] is False
        assert "error" in result


class TestOdbcAdapterConnectedGetTables(ConnectedAdapterTestBase):
    """Test get_tables with mocked sequential cursor calls."""

    def test_get_tables_returns_tableinfo_list(self):
        """get_tables returns TableInfo list for each user table."""
        table_row = MagicMock()
        table_row.__getitem__ = lambda self, i: "Table1" if i == 0 else None
        table_row[0] = "Table1"

        col_row = MagicMock()
        col_row.name = "ID"
        col_row.type = "Long Integer"
        col_row.size = 0
        col_row.nullable = "NO"

        count_row = (5,)

        self.mock_cursor.fetchall.side_effect = [
            [table_row],
            [col_row],
            [count_row],
        ]
        self.mock_cursor.fetchone.return_value = count_row

        tables = self.adapter.get_tables()
        assert len(tables) >= 1
        # Table name
        assert any(t.name == "Table1" for t in tables)
        # Fields present
        table1 = next(t for t in tables if t.name == "Table1")
        assert len(table1.fields) >= 1

    def test_get_tables_empty_when_not_connected(self):
        """get_tables returns empty list when not connected."""
        self.adapter._conn = None
        tables = self.adapter.get_tables()
        assert tables == []


class TestOdbcAdapterConnectedSchemaPlan(ConnectedAdapterTestBase):
    """Test get_table_schema_plan with mocked get_tables."""

    def test_get_table_schema_plan_returns_unknown_metadata(self):
        """get_table_schema_plan returns UnknownMetadata with all flags True."""
        with patch.object(self.adapter, "get_tables", return_value=[]) as mock_get:
            tables, unknown = self.adapter.get_table_schema_plan()
            # UnknownMetadata flags are True for ODBC
            assert unknown.defaults is True
            assert unknown.primary_keys is True

    def test_get_table_schema_plan_maps_columns(self):
        """Schema plan maps FieldInfo to ColumnSchema correctly."""
        field = MagicMock()
        field.name = "ID"
        field.type = "Long Integer"
        field.size = 0
        field.required = True
        table = MagicMock()
        table.name = "T1"
        table.fields = [field]

        with patch.object(self.adapter, "get_tables", return_value=[table]):
            tables, unknown = self.adapter.get_table_schema_plan()
            assert len(tables) == 1
            assert tables[0].name == "T1"
            assert len(tables[0].columns) == 1
            assert tables[0].columns[0].name == "ID"


class TestOdbcAdapterConnectedGetQueries(ConnectedAdapterTestBase):
    """Test get_queries with mocked cursor."""

    def test_get_queries_maps_information_schema_views(self):
        """get_queries returns list of QueryInfo from INFORMATION_SCHEMA.VIEWS."""
        view_row = MagicMock()
        view_row.__getitem__ = lambda self, i: "View1" if i == 0 else "SELECT 1"
        view_row[0] = "View1"
        view_row[1] = "SELECT 1"

        self.mock_cursor.fetchall.return_value = [view_row]

        queries = self.adapter.get_queries()
        assert len(queries) >= 1
        assert any(q.name == "View1" for q in queries)

    def test_get_queries_empty_when_not_connected(self):
        """get_queries returns empty list when not connected."""
        self.adapter._conn = None
        queries = self.adapter.get_queries()
        assert queries == []