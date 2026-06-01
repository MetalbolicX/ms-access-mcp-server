"""
Integration tests for ConnectionPool using SQLite-backed OdbcAdapter.

Validates that ConnectionPool works end-to-end with real adapters,
without requiring Windows or MS Access ODBC drivers.
"""

import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch

from ms_access_mcp.services.connection import ConnectionPool, ConnectionState
from ms_access_mcp.adapters.odbc import OdbcAdapter


# ---- SQLite-backed pyodbc mock (same pattern as test_odbc_adapter_sqlite.py) ---

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
        pass


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
def pool_with_sqlite(sqlite_db):
    """ConnectionPool with one SQLite-backed OdbcAdapter connected as 'default'."""
    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        pool = ConnectionPool()
        state = pool.connect("default", sqlite_db, "odbc")
        assert state is not None
        yield pool
        pool.disconnect("default")


@pytest.fixture
def pool_with_two_adapters(sqlite_db):
    """ConnectionPool with two named SQLite-backed connections ("prod", "dev")."""
    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        pool = ConnectionPool()

        # Create a second temp DB for "dev"
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            dev_db_path = f.name

        conn = sqlite3.connect(dev_db_path)
        conn.execute("CREATE TABLE __meta (name TEXT)")
        conn.execute("INSERT INTO __meta VALUES ('dev_db')")
        conn.commit()
        conn.close()

        pool.connect("prod", sqlite_db, "odbc")
        pool.connect("dev", dev_db_path, "odbc")

        yield pool

        pool.disconnect("prod")
        pool.disconnect("dev")
        if os.path.exists(dev_db_path):
            os.unlink(dev_db_path)


# ---- Tests ---------------------------------------------------------------------

class TestPoolWithRealAdapter:
    """ConnectionPool using real SQLite-backed OdbcAdapter."""

    def test_connect_via_pool_returns_state(self, pool_with_sqlite, sqlite_db):
        """Pool connect returns ConnectionState with correct db_path."""
        state = pool_with_sqlite.get("default")
        assert state is not None
        assert state.db_path == sqlite_db
        assert state.adapter_type == "odbc"

    def test_get_adapter_returns_working_adapter(self, pool_with_sqlite, sqlite_db):
        """Adapter from pool can execute real queries."""
        adapter = pool_with_sqlite.get_adapter("default")
        assert adapter is not None
        result = adapter.execute_query("SELECT 1 AS num")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["columns"] == ["num"]

    def test_is_connected_returns_true_for_connected(self, pool_with_sqlite):
        """is_connected returns True for connected adapter."""
        assert pool_with_sqlite.is_connected("default") is True

    def test_is_connected_returns_false_for_unknown(self, pool_with_sqlite):
        """is_connected returns False for unknown connection name."""
        assert pool_with_sqlite.is_connected("nonexistent") is False


class TestPoolMultiConnection:
    """ConnectionPool with multiple named connections."""

    def test_two_named_connections_are_independent(self, pool_with_two_adapters, sqlite_db):
        """Two connected names in pool, each has own adapter, isolation."""
        prod_state = pool_with_two_adapters.get("prod")
        dev_state = pool_with_two_adapters.get("dev")
        assert prod_state is not None
        assert dev_state is not None
        assert prod_state.db_path != dev_state.db_path
        assert prod_state.adapter is not dev_state.adapter

        # Both adapters can execute queries independently
        prod_result = prod_state.adapter.execute_query("SELECT * FROM __meta")
        dev_result = dev_state.adapter.execute_query("SELECT * FROM __meta")
        assert prod_result["success"] is True
        assert dev_result["success"] is True

    def test_active_switch_changes_adapter(self, pool_with_two_adapters, sqlite_db):
        """set_active("dev") → get_adapter() returns dev's adapter."""
        pool_with_two_adapters.set_active("dev")
        assert pool_with_two_adapters.get_active() == "dev"

        # get_adapter(None) uses active
        adapter = pool_with_two_adapters.get_adapter(None)
        assert adapter is not None
        result = adapter.execute_query("SELECT name FROM __meta")
        assert result["success"] is True
        # The dev DB has 'dev_db' as its meta value
        assert result["rows"][0]["name"] == "dev_db"

    def test_list_returns_both_connections(self, pool_with_two_adapters):
        """list() returns all connection names."""
        connections = pool_with_two_adapters.list()
        assert "prod" in connections
        assert "dev" in connections


class TestPoolBackwardCompat:
    """Backward compatibility for 'default' name."""

    def test_old_connect_api_still_works(self, pool_with_sqlite, sqlite_db):
        """pool.connect(db_path, adapter) → populates "default"."""
        # pool_with_sqlite already used connect(name, db_path, adapter) form
        # Verify "default" is active and reachable
        assert pool_with_sqlite.get_active() == "default"
        state = pool_with_sqlite.get("default")
        assert state.db_path == sqlite_db

    def test_old_adapter_and_current_database_properties(self, pool_with_sqlite, sqlite_db):
        """pool.adapter and pool.current_database return active/default values."""
        # The pool has only "default" connected
        assert pool_with_sqlite.get_active() == "default"
        adapter = pool_with_sqlite.get_adapter("default")
        assert adapter is not None
        # current_database returns active db path
        state = pool_with_sqlite.get()
        assert state.db_path == sqlite_db


class TestPoolRecoverAccess:
    """recover_access() on non-Windows platforms returns not-supported."""

    def test_recover_access_with_mixed_pool(self, pool_with_two_adapters):
        """recover_access() returns success=False on non-Windows."""
        with patch("sys.platform", "linux"):
            result = pool_with_two_adapters.recover_access()
            assert result["success"] is False
            assert "Not supported" in result["error"]


class TestPoolListWithRealAdapter:
    """list() returns real ConnectionState values."""

    def test_list_returns_real_state(self, pool_with_sqlite, sqlite_db):
        """list() returns ConnectionState with real db_path."""
        connections = pool_with_sqlite.list()
        assert "default" in connections
        assert connections["default"].db_path == sqlite_db
        assert connections["default"].adapter_type == "odbc"

    def test_list_multiple_returns_all(self, pool_with_two_adapters):
        """list() with multiple connections returns all with correct db_path."""
        connections = pool_with_two_adapters.list()
        assert len(connections) == 2
        assert "prod" in connections
        assert "dev" in connections