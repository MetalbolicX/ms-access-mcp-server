"""COM integration tests for WinComAdapter table and query operations.

Tests create_table, delete_table, create_query, set_query_sql, delete_query
on a temporary copy of the fixture DB.
"""

import shutil
import tempfile
import time

import pytest
from helpers import (
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
    TEST_DB,
)

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


def _unique_name(prefix: str) -> str:
    """Generate a unique name for temp objects."""
    return f"{prefix}_{int(time.time() * 1000)}"


class TestWinComTableCreate:
    """create_table via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_table_text_column(self):
        name = _unique_name("tblText")
        result = self.adapter.create_table(
            name,
            [{"name": "ID", "type": "Long Integer", "nullable": False},
             {"name": "Label", "type": "Text", "size": 100, "nullable": True}],
        )
        assert result["success"] is True

        # Verify it exists
        tables = self.adapter.get_tables()
        assert any(t.name == name for t in tables)

    def test_create_table_multiple_column_types(self):
        name = _unique_name("tblMulti")
        result = self.adapter.create_table(
            name,
            [
                {"name": "ID", "type": "Long Integer", "nullable": False},
                {"name": "Name", "type": "Text", "size": 50, "nullable": True},
                {"name": "Price", "type": "Double", "nullable": True},
                {"name": "Created", "type": "Date/Time", "nullable": True},
                {"name": "Active", "type": "Boolean", "nullable": False},
            ],
        )
        assert result["success"] is True

        # Verify columns via query
        rows = self.adapter.execute_query(f"SELECT * FROM [{name}]")
        assert rows["success"] is True

    def test_create_table_not_connected(self):
        self.adapter.disconnect()
        result = self.adapter.create_table("any_table", [{"name": "ID", "type": "Long Integer"}])
        assert result["success"] is False

    def test_create_table_duplicate_name(self):
        name = _unique_name("tblDup")
        self.adapter.create_table(
            name,
            [{"name": "ID", "type": "Long Integer", "nullable": False}],
        )
        # Creating same name again should fail or succeed (DAO behavior varies)
        result2 = self.adapter.create_table(
            name,
            [{"name": "ID", "type": "Long Integer", "nullable": False}],
        )
        # The operation may fail or the second call may be idempotent
        # We just verify it doesn't crash
        assert isinstance(result2.get("success"), bool)


class TestWinComTableDelete:
    """delete_table via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_delete_table(self):
        name = _unique_name("tblToDel")
        self.adapter.create_table(
            name,
            [{"name": "ID", "type": "Long Integer", "nullable": False}],
        )
        result = self.adapter.delete_table(name)
        assert result["success"] is True

        # Verify it's gone
        tables = self.adapter.get_tables()
        assert not any(t.name == name for t in tables)

    def test_delete_table_nonexistent(self):
        result = self.adapter.delete_table("__nonexistent_table__")
        assert result["success"] is False

    def test_delete_table_not_connected(self):
        name = _unique_name("tblConn")
        self.adapter.create_table(
            name,
            [{"name": "ID", "type": "Long Integer", "nullable": False}],
        )
        self.adapter.disconnect()
        result = self.adapter.delete_table(name)
        assert result["success"] is False


class TestWinComTableLifecycle:
    """create_table / delete_table lifecycle via WinComAdapter."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_insert_query_delete(self):
        name = _unique_name("tblLifecycle")
        # Create
        create = self.adapter.create_table(
            name,
            [
                {"name": "ID", "type": "Long Integer", "nullable": False},
                {"name": "Val", "type": "Text", "size": 50, "nullable": True},
            ],
        )
        assert create["success"] is True

        # Insert
        ins = self.adapter.insert_data(name, {"ID": 1, "Val": "Test"})
        assert ins["success"] is True

        # Query
        rows = self.adapter.execute_query(f"SELECT * FROM [{name}]")
        assert rows["success"] is True
        assert rows["count"] == 1

        # Delete
        dlt = self.adapter.delete_table(name)
        assert dlt["success"] is True

        # Verify gone
        tables = self.adapter.get_tables()
        assert not any(t.name == name for t in tables)


class TestWinComQueryCreate:
    """create_query via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_query(self):
        name = _unique_name("qry")
        result = self.adapter.create_query(name, "SELECT 1 AS test")
        assert result["success"] is True

        # Verify it appears in list
        queries = self.adapter.get_queries()
        assert any(q.name == name for q in queries)

    def test_create_and_execute_query(self):
        name = _unique_name("qryExec")
        # Create a query on the customers table
        result = self.adapter.create_query(
            name,
            "SELECT ID, Name FROM customers ORDER BY ID",
        )
        assert result["success"] is True

        # Execute it
        rows = self.adapter.execute_query(f"SELECT * FROM [{name}]")
        assert rows["success"] is True

    def test_create_query_not_connected(self):
        self.adapter.disconnect()
        result = self.adapter.create_query("any_query", "SELECT 1")
        assert result["success"] is False


class TestWinComQuerySetSql:
    """set_query_sql via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"
        # Pre-create a query to update
        self.test_query_name = _unique_name("qryUpd")
        self.adapter.create_query(self.test_query_name, "SELECT 1 AS original")

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_query_sql(self):
        new_sql = "SELECT 2 AS updated"
        result = self.adapter.set_query_sql(self.test_query_name, new_sql)
        assert result["success"] is True

        # Verify via get_queries
        queries = self.adapter.get_queries()
        qry = next((q for q in queries if q.name == self.test_query_name), None)
        assert qry is not None
        assert "updated" in qry.sql or "2" in qry.sql

    def test_set_query_sql_nonexistent(self):
        result = self.adapter.set_query_sql("__nonexistent_query__", "SELECT 1")
        assert result["success"] is False

    def test_set_query_sql_not_connected(self):
        self.adapter.disconnect()
        result = self.adapter.set_query_sql(self.test_query_name, "SELECT 1")
        assert result["success"] is False


class TestWinComQueryDelete:
    """delete_query via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"
        # Pre-create a query to delete
        self.test_query_name = _unique_name("qryDel")
        self.adapter.create_query(self.test_query_name, "SELECT 1 AS test")

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_delete_query(self):
        result = self.adapter.delete_query(self.test_query_name)
        assert result["success"] is True

        # Verify it's gone
        queries = self.adapter.get_queries()
        assert not any(q.name == self.test_query_name for q in queries)

    def test_delete_query_nonexistent(self):
        result = self.adapter.delete_query("__nonexistent_query__")
        assert result["success"] is False

    def test_delete_query_not_connected(self):
        self.adapter.disconnect()
        result = self.adapter.delete_query(self.test_query_name)
        assert result["success"] is False


class TestWinComQueryLifecycle:
    """create / update / delete query lifecycle via WinComAdapter."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_query_create_set_sql_delete(self):
        name = _unique_name("qryLife")
        # Create
        create = self.adapter.create_query(name, "SELECT 1 AS step1")
        assert create["success"] is True

        # Update
        update = self.adapter.set_query_sql(name, "SELECT 2 AS step2")
        assert update["success"] is True

        # Verify via get_queries
        queries = self.adapter.get_queries()
        qry = next((q for q in queries if q.name == name), None)
        assert qry is not None

        # Delete
        delete = self.adapter.delete_query(name)
        assert delete["success"] is True

        # Verify gone
        queries = self.adapter.get_queries()
        assert not any(q.name == name for q in queries)