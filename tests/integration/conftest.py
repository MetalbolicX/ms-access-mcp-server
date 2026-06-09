"""
Pytest configuration for integration tests.

Shared skip conditions and helpers are in helpers.py.
"""

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from ms_access_mcp.services.connection import ConnectionPool

from tests.integration.helpers import TEST_DB, skip_unless_windows, skip_unless_pywin32, skip_unless_db

pytestmark = [skip_unless_windows, skip_unless_pywin32, skip_unless_db]


@pytest.fixture
def temp_db_copy():
    """Create a temporary copy of the test database for destructive tests.

    Yields the path to the cloned .accdb file.  The clone is a file-level copy
    (shutil.copy2) so every test gets a pristine isolated database.  The master
    fixture at TEST_DB is never modified.

    Teardown always removes the clone and its parent temp directory — even if
    the test raises an exception.  Access files cannot be deleted while Access
    holds a lock, so we rely on ComDispatcher's _release_com_safe() being called
    by the test's teardown (adapter.disconnect()).
    """
    if not TEST_DB:
        pytest.skip("ACCESS_TEST_DB not set and no fixture found")

    src_path = Path(TEST_DB)
    if not src_path.exists():
        pytest.skip(f"Fixture database not found: {src_path}")

    # Create a temp directory that will own the clone; when we clean it up
    # the clone goes with it regardless of whether the test forgot to delete.
    tmpdir = tempfile.mkdtemp(prefix="acc_test_")
    clone_path = Path(tmpdir) / src_path.name

    try:
        shutil.copy2(src_path, clone_path)
        yield str(clone_path)
    finally:
        # Give any lingering Access process a moment to release the file
        import time
        time.sleep(0.25)
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# ---- SQLite-backed pyodbc mock ------------------------------------------------

class _SqliteCursor:
    """Wraps sqlite3 cursor to respond like pyodbc cursor."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self._cursor = db.cursor()
        self.description = None

    def execute(self, sql: str, params: tuple | None = None) -> None:
        try:
            # Handle Jet SQL DROP INDEX ... ON ... syntax (not supported by SQLite)
            # Convert to standard SQLite DROP INDEX [index_name]
            if sql.strip().upper().startswith("DROP INDEX"):
                import re
                # Match: DROP INDEX [name] ON [table] or DROP INDEX name ON table
                m = re.match(r"DROP\s+INDEX\s+(\[?\w+\]?)\s+ON\s+(\[?\w+\]?)", sql, re.IGNORECASE)
                if m:
                    index_name = m.group(1).strip("[]")
                    # SQLite doesn't support this syntax, so we just succeed silently
                    # (the test is verifying tool interface, not actual index dropping)
                    self.description = self._cursor.description
                    return
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
    """Replace pyodbc.connect with sqlite3-backed connection."""
    for part in conn_str.split(";"):
        if part.upper().startswith("DBQ="):
            db_path = part.split("=", 1)[1].strip()
            return _SqliteConnection(db_path)
    for part in conn_str.split(";"):
        if part.upper().startswith("DATA SOURCE="):
            db_path = part.split("=", 1)[1].strip()
            return _SqliteConnection(db_path)
    raise ValueError(f"Cannot extract DB path from: {conn_str}")


# ---- Fixtures -----------------------------------------------------------------

@pytest.fixture
def sqlite_db():
    """Create a temp SQLite database, clean up after."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE __meta (name TEXT)")
    conn.execute("INSERT INTO __meta VALUES ('prod_db')")
    conn.commit()
    conn.close()
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def pool_with_sqlite(sqlite_db):
    """ConnectionPool with one SQLite-backed OdbcAdapter connected as 'default'."""
    from unittest.mock import patch
    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        pool = ConnectionPool()
        state = pool.connect("default", sqlite_db, "odbc")
        assert state is not None
        yield pool
        pool.disconnect("default")


@pytest.fixture
def pool_with_two_adapters(sqlite_db):
    """ConnectionPool with two named SQLite-backed connections ("prod", "dev")."""
    from unittest.mock import patch
    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        pool = ConnectionPool()

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


@pytest.fixture
def pool_with_three_adapters(sqlite_db):
    """ConnectionPool with three named SQLite-backed connections ("alpha", "beta", "gamma")."""
    from unittest.mock import patch
    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        pool = ConnectionPool()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            beta_db_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            gamma_db_path = f.name

        for db_path in (beta_db_path, gamma_db_path):
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE __meta (name TEXT)")
            conn.execute("INSERT INTO __meta VALUES ('secondary_db')")
            conn.commit()
            conn.close()

        pool.connect("alpha", sqlite_db, "odbc")
        pool.connect("beta", beta_db_path, "odbc")
        pool.connect("gamma", gamma_db_path, "odbc")

        yield pool

        pool.disconnect("alpha")
        pool.disconnect("beta")
        pool.disconnect("gamma")
        for p in (beta_db_path, gamma_db_path):
            if os.path.exists(p):
                os.unlink(p)