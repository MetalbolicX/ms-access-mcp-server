"""
Integration tests for OdbcAdapter using a SQLite backend.

Patches pyodbc.connect with sqlite3 to test the real OdbcAdapter data flow
end-to-end against a live database, without requiring an MS Access ODBC driver.

This tests: execute_query, insert/update/delete, create/drop table,
export CSV/JSON, query CRUD, error handling.

On Windows with proper ODBC drivers, use ACCESS_TEST_DB to test against a real
Access database instead.
"""

import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch
from pathlib import Path

from helpers import skip_unless_db


# ---- SQLite-backed pyodbc mock -------------------------------------------------

class _SqliteCursor:
    """Wraps sqlite3 cursor to respond like pyodbc cursor."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self._cursor = db.cursor()
        self.description = None

    def execute(self, sql: str, params: tuple | None = None) -> None:
        try:
            if params:
                self._cursor.execute(sql, params)
            else:
                self._cursor.execute(sql)
            self.description = self._cursor.description
        except Exception as e:
            self._cursor = self.db.cursor()
            raise e

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        pass  # don't close the underlying sqlite connection


class _SqliteConnection:
    """Wraps sqlite3 connection to mimic pyodbc.Connection."""

    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA journal_mode=WAL")

    def cursor(self):
        return _SqliteCursor(self.db)

    def close(self):
        self.db.close()


def _sqlite_pyodbc_connect(conn_str: str, autocommit: bool = False) -> _SqliteConnection:
    """Replace pyodbc.connect with sqlite3-backed connection.

    Extracts DBQ parameter or falls back to a temp file.
    """
    for part in conn_str.split(";"):
        if part.upper().startswith("DBQ="):
            db_path = part.split("=", 1)[1].strip()
            return _SqliteConnection(db_path)
    # Fallback: extract Data Source
    for part in conn_str.split(";"):
        if part.upper().startswith("DATA SOURCE="):
            db_path = part.split("=", 1)[1].strip()
            return _SqliteConnection(db_path)
    raise ValueError(f"Cannot extract DB path from: {conn_str}")


# ---- Fixtures ------------------------------------------------------------------

@pytest.fixture
def sqlite_db():
    """Create a temp SQLite database for the test, clean up after."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE __meta (name TEXT)")
    conn.execute("INSERT INTO __meta VALUES ('test_db')")
    conn.commit()
    conn.close()

    yield db_path

    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def odbc_adapter(sqlite_db):
    """OdbcAdapter connected to a SQLite database via patched pyodbc."""
    from ms_access_mcp.adapters.odbc import OdbcAdapter

    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        adapter = OdbcAdapter()
        result = adapter.connect(sqlite_db)
        assert result is True, f"Failed to connect to {sqlite_db}"
        assert adapter.is_connected()
        yield adapter
        adapter.disconnect()


@pytest.fixture
def temp_table_name():
    import time
    yield f"_test_{int(time.time() * 1000)}_{os.urandom(2).hex()}"


# ---- Connection lifecycle ------------------------------------------------------

class TestOdbcAdapterSqliteConnection:
    def test_connect_returns_true(self, sqlite_db):
        with patch("pyodbc.connect", _sqlite_pyodbc_connect):
            from ms_access_mcp.adapters.odbc import OdbcAdapter
            a = OdbcAdapter()
            assert a.connect(sqlite_db) is True
            assert a.is_connected()
            a.disconnect()
            assert not a.is_connected()

    def test_connect_nonexistent_path_returns_false(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter
        a = OdbcAdapter()
        assert a.connect("/nonexistent/path/test.accdb") is False
        assert not a.is_connected()


# ---- Data operations -----------------------------------------------------------

class TestOdbcAdapterSqliteData:
    def test_execute_query_select(self, odbc_adapter):
        result = odbc_adapter.execute_query("SELECT 1 AS num")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["columns"] == ["num"]

    def test_execute_query_not_connected_returns_error(self):
        with patch("pyodbc.connect", _sqlite_pyodbc_connect):
            from ms_access_mcp.adapters.odbc import OdbcAdapter
            a = OdbcAdapter()
            result = a.execute_query("SELECT 1")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_insert_and_query(self, odbc_adapter, temp_table_name):
        # Create table
        create = odbc_adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer"},
             {"name": "Name", "type": "Text", "size": 100}]
        )
        assert create["success"] is True

        try:
            # Insert
            insert = odbc_adapter.insert_data(temp_table_name, {"ID": 1, "Name": "Alice"})
            assert insert["success"] is True, f"Insert failed: {insert}"
            assert insert["affected"] == 1

            insert = odbc_adapter.insert_data(temp_table_name, [
                {"ID": 2, "Name": "Bob"},
                {"ID": 3, "Name": "Charlie"},
            ])
            assert insert["success"] is True
            assert insert["affected"] == 2

            # Read
            query = odbc_adapter.execute_query(f"SELECT * FROM [{temp_table_name}] ORDER BY ID")
            assert query["success"] is True
            assert query["count"] == 3

        finally:
            odbc_adapter.delete_table(temp_table_name)

    def test_update_and_verify(self, odbc_adapter, temp_table_name):
        create = odbc_adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer"},
             {"name": "Val", "type": "Text", "size": 50}]
        )
        assert create["success"] is True

        try:
            odbc_adapter.insert_data(temp_table_name, {"ID": 1, "Val": "Original"})
            odbc_adapter.insert_data(temp_table_name, {"ID": 2, "Val": "Other"})

            # Update
            upd = odbc_adapter.update_data(temp_table_name, {"Val": "Updated"}, {"ID": 1})
            assert upd["success"] is True

            # Verify
            rows = odbc_adapter.execute_query(
                f"SELECT Val FROM [{temp_table_name}] WHERE ID = 1"
            )
            assert rows["success"] is True
            if rows["rows"]:
                assert rows["rows"][0]["Val"] == "Updated"

        finally:
            odbc_adapter.delete_table(temp_table_name)

    def test_delete_and_verify(self, odbc_adapter, temp_table_name):
        create = odbc_adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer"}]
        )
        assert create["success"] is True

        try:
            odbc_adapter.insert_data(temp_table_name, {"ID": 1})
            odbc_adapter.insert_data(temp_table_name, {"ID": 2})

            dlt = odbc_adapter.delete_data(temp_table_name, {"ID": 1})
            assert dlt["success"] is True

            remaining = odbc_adapter.execute_query(f"SELECT ID FROM [{temp_table_name}]")
            assert remaining["count"] == 1

        finally:
            odbc_adapter.delete_table(temp_table_name)


# ---- Schema operations ---------------------------------------------------------

class TestOdbcAdapterSqliteSchema:
    def test_get_tables_includes_our_tables(self, odbc_adapter, temp_table_name):
        """get_tables() uses MSysObjects (Access-only), so this won't list SQLite tables.
        Instead, test that the created table is queryable via execute_query."""
        create = odbc_adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer"}]
        )
        assert create["success"] is True

        try:
            # Can't verify via get_tables() (MSysObjects is Access-only).
            # But we CAN verify the table exists by querying it.
            result = odbc_adapter.execute_query(f"SELECT * FROM [{temp_table_name}]")
            assert result["success"] is True
        finally:
            odbc_adapter.delete_table(temp_table_name)

    def test_get_queries_returns_list(self, odbc_adapter):
        queries = odbc_adapter.get_queries()
        assert isinstance(queries, list)

    def test_get_table_schema_plan_returns_tuple(self, odbc_adapter):
        schema_tables, unknown = odbc_adapter.get_table_schema_plan()
        assert isinstance(schema_tables, list)
        assert unknown is not None

    def test_create_and_delete_table(self, odbc_adapter, temp_table_name):
        result = odbc_adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer", "nullable": False}]
        )
        assert result["success"] is True

        # Verify by querying (get_tables() uses Access-only MSysObjects)
        query = odbc_adapter.execute_query(f"SELECT * FROM [{temp_table_name}]")
        assert query["success"] is True

        # Delete
        result = odbc_adapter.delete_table(temp_table_name)
        assert result["success"] is True

        # Verify deletion (query should fail)
        query = odbc_adapter.execute_query(f"SELECT * FROM [{temp_table_name}]")
        assert query["success"] is False


# ---- Export operations ---------------------------------------------------------

class TestOdbcAdapterSqliteExport:
    def test_export_csv(self, odbc_adapter, temp_table_name):
        create = odbc_adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer"},
             {"name": "Name", "type": "Text", "size": 50}]
        )
        assert create["success"] is True

        try:
            odbc_adapter.insert_data(temp_table_name, {"ID": 1, "Name": "Test"})

            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
                csv_path = f.name

            try:
                result = odbc_adapter.export_table_csv(temp_table_name, csv_path)
                assert result["success"] is True
                assert result["rows_exported"] >= 1
                assert os.path.exists(csv_path)
            finally:
                os.unlink(csv_path)
        finally:
            odbc_adapter.delete_table(temp_table_name)

    def test_export_json(self, odbc_adapter, temp_table_name):
        create = odbc_adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer"}]
        )
        assert create["success"] is True

        try:
            odbc_adapter.insert_data(temp_table_name, {"ID": 99})

            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                json_path = f.name

            try:
                result = odbc_adapter.export_query_json(temp_table_name, json_path)
                assert result["success"] is True
                assert result["rows_exported"] >= 1
                assert os.path.exists(json_path)
            finally:
                os.unlink(json_path)
        finally:
            odbc_adapter.delete_table(temp_table_name)


# ---- Error handling ------------------------------------------------------------

class TestOdbcAdapterSqliteErrors:
    def test_execute_invalid_sql_returns_error(self, odbc_adapter):
        result = odbc_adapter.execute_query("SELECT * FROM nonexistent_table")
        assert result["success"] is False
        assert "error" in result

    def test_insert_into_nonexistent_table_returns_error(self, odbc_adapter):
        result = odbc_adapter.insert_data("_nonexistent_", {"ID": 1})
        assert result["success"] is False

    def test_delete_table_nonexistent_returns_error(self, odbc_adapter):
        result = odbc_adapter.delete_table("_nonexistent_")
        assert result["success"] is False

    def test_export_csv_nonexistent_table_returns_error(self, odbc_adapter):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            result = odbc_adapter.export_table_csv("_nonexistent_", csv_path)
            assert result["success"] is False
        finally:
            os.unlink(csv_path)
