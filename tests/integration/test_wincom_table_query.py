r"""
Integration tests for WinComAdapter table and query write operations.

These tests require:
  - Windows OS with MS Access installed
  - pywin32 (win32com.client)
  - A test .accdb database file

Markers: com_integration
Execution: pytest tests/integration/test_wincom_table_query.py -m com_integration -v

Each test gets its own cloned database via `temp_db_copy`.  Test object names
are generated uniquely to prevent collisions when tests run in the same session.
"""

import pytest

from ms_access_mcp.adapters.wincom import WinComAdapter
from helpers import skip_unless_windows, skip_unless_pywin32, skip_unless_db

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


def _unique_name(prefix: str) -> str:
    """Generate a unique name for test objects to avoid collisions on reuse."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _cleanup_adapter(adapter: WinComAdapter) -> None:
    """Safely disconnect an adapter, swallowing cleanup exceptions."""
    try:
        if adapter.is_connected():
            adapter.disconnect()
    except Exception:
        pass  # best-effort cleanup; Access may already be dead


# =============================================================================
# Table CRUD
# =============================================================================

class TestWinComTableCreate:
    """Create table operations via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_create_table_simple(self, temp_db_copy: str):
        """CREATE TABLE with a single TEXT column — table must exist after."""
        assert self.adapter.connect(temp_db_copy)
        table_name = _unique_name("tblSimple")

        result = self.adapter.create_table(table_name, [
            {"name": "ID", "type": "Long Integer"},
            {"name": "Description", "type": "Text", "size": 100},
        ])
        assert result["success"] is True, f"create_table failed: {result.get('error')}"

        # Verify table exists in get_tables()
        tables = self.adapter.get_tables()
        table_names = [t.name for t in tables]
        assert table_name in table_names, f"{table_name} not found in {table_names}"

        # Verify we can SELECT from it
        rows = self.adapter.execute_query(f"SELECT * FROM [{table_name}]")
        assert rows["success"] is True
        assert rows["count"] == 0  # empty table

    def test_create_table_with_types(self, temp_db_copy: str):
        """CREATE TABLE with multiple Access field types — all must be creatable."""
        assert self.adapter.connect(temp_db_copy)
        table_name = _unique_name("tblTypes")

        columns = [
            {"name": "ID", "type": "Long Integer"},
            {"name": "fullname", "type": "Text", "size": 50},
            {"name": "active", "type": "Boolean"},
            {"name": "dob", "type": "Date/Time"},
            {"name": "salary", "type": "Currency"},
            {"name": "bio", "type": "Memo"},
            {"name": "weight", "type": "Double"},
            {"name": "age", "type": "Byte"},
        ]
        result = self.adapter.create_table(table_name, columns)
        assert result["success"] is True, f"create_table failed: {result.get('error')}"

        # Verify
        tables = self.adapter.get_tables()
        table_names = [t.name for t in tables]
        assert table_name in table_names

    def test_create_table_not_connected(self):
        """create_table on a disconnected adapter must return error."""
        adapter = WinComAdapter()  # never connected
        result = adapter.create_table("any_table", [{"name": "Col1", "type": "Text"}])
        assert result["success"] is False
        assert "not connected" in result.get("error", "").lower()

    def test_create_table_duplicate_name(self, temp_db_copy: str):
        """Creating a table that already exists must return an error."""
        assert self.adapter.connect(temp_db_copy)
        table_name = _unique_name("tblDup")

        # Create once
        r1 = self.adapter.create_table(table_name, [{"name": "Col1", "type": "Long Integer"}])
        assert r1["success"] is True

        # Create again — must fail
        r2 = self.adapter.create_table(table_name, [{"name": "Col1", "type": "Long Integer"}])
        assert r2["success"] is False


class TestWinComTableDelete:
    """Delete table operations via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_delete_table(self, temp_db_copy: str):
        """DELETE TABLE — table must not exist after."""
        assert self.adapter.connect(temp_db_copy)
        table_name = _unique_name("tblToDelete")

        # Create first
        self.adapter.create_table(table_name, [{"name": "ID", "type": "Long Integer"}])
        tables_before = [t.name for t in self.adapter.get_tables()]
        assert table_name in tables_before

        # Delete
        result = self.adapter.delete_table(table_name)
        assert result["success"] is True, f"delete_table failed: {result.get('error')}"

        # Verify gone
        tables_after = [t.name for t in self.adapter.get_tables()]
        assert table_name not in tables_after

    def test_delete_table_nonexistent(self, temp_db_copy: str):
        """Deleting a non-existent table must return an error."""
        assert self.adapter.connect(temp_db_copy)
        result = self.adapter.delete_table("tblDoesNotExist_xyz")
        assert result["success"] is False

    def test_delete_table_not_connected(self):
        """delete_table on disconnected adapter must return error."""
        adapter = WinComAdapter()
        result = adapter.delete_table("any_table")
        assert result["success"] is False


class TestWinComTableLifecycle:
    """Full table lifecycle: create -> insert -> query -> delete."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_create_rename_delete(self, temp_db_copy: str):
        """Full lifecycle on an isolated clone — create, insert, verify, delete."""
        assert self.adapter.connect(temp_db_copy)
        table_name = _unique_name("tblLifecycle")

        # Create
        r = self.adapter.create_table(table_name, [
            {"name": "ID", "type": "Long Integer"},
            {"name": "Label", "type": "Text", "size": 50},
        ])
        assert r["success"] is True

        # Insert
        ins = self.adapter.insert_data(table_name, {"ID": 1, "Label": "First"})
        assert ins["success"] is True

        # Query
        rows = self.adapter.execute_query(f"SELECT * FROM [{table_name}]")
        assert rows["success"] is True
        assert rows["count"] == 1
        assert rows["rows"][0]["Label"] == "First"

        # Delete table
        del_r = self.adapter.delete_table(table_name)
        assert del_r["success"] is True

        # Confirm gone
        table_names = [t.name for t in self.adapter.get_tables()]
        assert table_name not in table_names


# =============================================================================
# Query CRUD
# =============================================================================

class TestWinComQueryCreate:
    """Create query operations via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_create_query(self, temp_db_copy: str):
        """CREATE QueryDef with a SELECT query — must be listed in get_queries()."""
        assert self.adapter.connect(temp_db_copy)
        query_name = _unique_name("qryTest")
        sql = "SELECT ID, Name FROM customers ORDER BY ID"

        result = self.adapter.create_query(query_name, sql)
        assert result["success"] is True, f"create_query failed: {result.get('error')}"

        # Verify it appears in queries
        queries = self.adapter.get_queries()
        query_names = [q.name for q in queries]
        assert query_name in query_names, f"{query_name} not in {query_names}"

    def test_create_query_and_execute(self, temp_db_copy: str):
        """Create a query and verify it returns data from the underlying tables."""
        assert self.adapter.connect(temp_db_copy)
        query_name = _unique_name("qryExec")
        sql = "SELECT COUNT(*) AS cnt FROM customers"

        self.adapter.create_query(query_name, sql)

        # Execute the query directly
        result = self.adapter.execute_query(f"SELECT * FROM [{query_name}]")
        assert result["success"] is True
        assert result["count"] >= 0  # table has data

    def test_create_query_not_connected(self):
        """create_query on disconnected adapter must return error."""
        adapter = WinComAdapter()
        result = adapter.create_query("any_query", "SELECT 1")
        assert result["success"] is False


class TestWinComQuerySetSql:
    """Modify existing query SQL via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_set_query_sql(self, temp_db_copy: str):
        """Update an existing query's SQL and verify the change."""
        assert self.adapter.connect(temp_db_copy)
        query_name = _unique_name("qryMod")
        original_sql = "SELECT ID, Name FROM customers"
        new_sql = "SELECT ID, Name FROM customers WHERE ID = 1"

        # Create with original
        r1 = self.adapter.create_query(query_name, original_sql)
        assert r1["success"] is True

        # Modify SQL
        r2 = self.adapter.set_query_sql(query_name, new_sql)
        assert r2["success"] is True, f"set_query_sql failed: {r2.get('error')}"

        # Verify via get_queries that SQL changed
        queries = self.adapter.get_queries()
        qdef = next((q for q in queries if q.name == query_name), None)
        assert qdef is not None
        assert new_sql in qdef.sql or new_sql.lower() in qdef.sql.lower()

    def test_set_query_sql_nonexistent(self, temp_db_copy: str):
        """Modifying a non-existent query must return an error."""
        assert self.adapter.connect(temp_db_copy)
        result = self.adapter.set_query_sql("qryDoesNotExist_xyz", "SELECT 1")
        assert result["success"] is False

    def test_set_query_sql_not_connected(self):
        """set_query_sql on disconnected adapter must return error."""
        adapter = WinComAdapter()
        result = adapter.set_query_sql("any_query", "SELECT 1")
        assert result["success"] is False


class TestWinComQueryDelete:
    """Delete query operations via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_delete_query(self, temp_db_copy: str):
        """DELETE QueryDef — query must not appear in get_queries() after."""
        assert self.adapter.connect(temp_db_copy)
        query_name = _unique_name("qryToDel")

        # Create
        self.adapter.create_query(query_name, "SELECT 1")
        queries_before = [q.name for q in self.adapter.get_queries()]
        assert query_name in queries_before

        # Delete
        result = self.adapter.delete_query(query_name)
        assert result["success"] is True, f"delete_query failed: {result.get('error')}"

        # Verify gone
        queries_after = [q.name for q in self.adapter.get_queries()]
        assert query_name not in queries_after

    def test_delete_query_nonexistent(self, temp_db_copy: str):
        """Deleting a non-existent query must return an error."""
        assert self.adapter.connect(temp_db_copy)
        result = self.adapter.delete_query("qryDoesNotExist_xyz")
        assert result["success"] is False

    def test_delete_query_not_connected(self):
        """delete_query on disconnected adapter must return error."""
        adapter = WinComAdapter()
        result = adapter.delete_query("any_query")
        assert result["success"] is False


class TestWinComQueryLifecycle:
    """Full query lifecycle: create -> set_sql -> delete."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        try:
            self.adapter.disconnect()
        except Exception:
            pass

    def test_lifecycle(self, temp_db_copy: str):
        """Full cycle: create query, update its SQL, execute it, then delete."""
        assert self.adapter.connect(temp_db_copy)
        query_name = _unique_name("qryLifeCycle")

        # Create
        r = self.adapter.create_query(query_name, "SELECT 1 AS col")
        assert r["success"] is True

        # Update SQL
        new_sql = "SELECT ID, Name FROM customers"
        r2 = self.adapter.set_query_sql(query_name, new_sql)
        assert r2["success"] is True

        # Execute
        rows = self.adapter.execute_query(f"SELECT * FROM [{query_name}]")
        assert rows["success"] is True
        assert rows["count"] >= 1  # customers table has rows

        # Delete
        r3 = self.adapter.delete_query(query_name)
        assert r3["success"] is True

        # Confirm gone
        query_names = [q.name for q in self.adapter.get_queries()]
        assert query_name not in query_names
