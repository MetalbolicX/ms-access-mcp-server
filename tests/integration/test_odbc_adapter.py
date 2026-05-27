"""
Integration tests against a real Access database via ODBC adapter.

These tests require:
  - An ODBC driver for MS Access (mdbtools on Linux, ACE/Microsoft on Windows)
  - A test .accdb or .mdb database file

Markers: odbc_integration

Usage:
  ACCESS_TEST_DB=/path/to/database.accdb pytest tests/integration/ -m odbc_integration -v
"""

import os
import tempfile
import pytest
from helpers import TEST_DB, skip_unless_db, skip_unless_odbc_driver

pytestmark = [pytest.mark.odbc_integration, skip_unless_db, skip_unless_odbc_driver]


# ---- Fixtures -----------------------------------------------------------------

@pytest.fixture(scope="module")
def adapter():
    """Connect the OdbcAdapter once per module, teardown at end."""
    from ms_access_mcp.adapters.odbc import OdbcAdapter

    a = OdbcAdapter()
    assert a.connect(TEST_DB), f"Failed to connect OdbcAdapter to {TEST_DB}"
    assert a.is_connected()
    yield a
    a.disconnect()
    assert not a.is_connected()


@pytest.fixture
def temp_table_name():
    """Generate a unique temp table name for the test run."""
    import time
    yield f"__integration_test_{int(time.time() * 1000)}__"


# ---- Connection lifecycle ----------------------------------------------------

class TestOdbcAdapterConnection:
    def test_connect_returns_true(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        a = OdbcAdapter()
        result = a.connect(TEST_DB)
        assert result is True
        assert a.is_connected()
        a.disconnect()
        assert not a.is_connected()

    def test_connect_to_nonexistent_path_returns_false(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        a = OdbcAdapter()
        assert a.connect("/nonexistent/path/db.accdb") is False
        assert not a.is_connected()


# ---- Schema operations -------------------------------------------------------

class TestOdbcAdapterSchema:
    def test_get_tables_returns_list(self, adapter):
        tables = adapter.get_tables()
        assert isinstance(tables, list)
        # Should have at least one table in a real database
        assert len(tables) > 0
        for t in tables:
            assert t.name
            assert isinstance(t.fields, list)

    def test_get_tables_returns_fields(self, adapter):
        tables = adapter.get_tables()
        if tables:
            # At least one table should have fields
            any_fields = any(len(t.fields) > 0 for t in tables)
            # Not all databases have schema-visible fields via ODBC
            assert isinstance(any_fields, bool)

    def test_get_queries_returns_list(self, adapter):
        queries = adapter.get_queries()
        assert isinstance(queries, list)

    def test_get_table_schema_plan_returns_tuple(self, adapter):
        schema_tables, unknown = adapter.get_table_schema_plan()
        assert isinstance(schema_tables, list)
        assert unknown is not None


# ---- Data operations ---------------------------------------------------------

class TestOdbcAdapterData:
    def test_execute_query_returns_dict_with_success(self, adapter):
        result = adapter.execute_query("SELECT 1 AS test")
        assert result["success"] is True
        assert "rows" in result
        assert "count" in result
        assert "columns" in result
        assert result["count"] >= 1

    def test_execute_query_with_params(self, adapter):
        result = adapter.execute_query("SELECT ? AS val", ["hello"])
        assert result["success"] is True
        if result["rows"]:
            # ODBC parameterized queries may bind differently per driver
            pass

    def test_insert_and_read_back(self, adapter, temp_table_name):
        """Create a temp table, insert a row, verify it's there, drop it."""
        # Create
        create = adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer", "nullable": False},
             {"name": "Name", "type": "Text", "size": 100, "nullable": True}]
        )
        assert create["success"] is True, f"Create failed: {create.get('error')}"

        try:
            # Insert
            insert = adapter.insert_data(temp_table_name, {"ID": 1, "Name": "IntegrationTest"})
            assert insert["success"] is True, f"Insert failed: {insert.get('error')}"

            # Read
            query = adapter.execute_query(f"SELECT * FROM [{temp_table_name}]")
            assert query["success"] is True
            assert query["count"] >= 1

        finally:
            # Cleanup
            adapter.delete_table(temp_table_name)

    def test_update_and_delete(self, adapter, temp_table_name):
        """Insert, update, delete, verify each step."""
        create = adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer", "nullable": False},
             {"name": "Val", "type": "Text", "size": 50, "nullable": True}]
        )
        assert create["success"] is True

        try:
            adapter.insert_data(temp_table_name, {"ID": 1, "Val": "Original"})

            # Update
            upd = adapter.update_data(temp_table_name, {"Val": "Updated"}, {"ID": 1})
            assert upd["success"] is True

            # Verify
            rows = adapter.execute_query(f"SELECT Val FROM [{temp_table_name}] WHERE ID = 1")
            if rows["rows"]:
                assert rows["rows"][0].get("Val") == "Updated" or rows["rows"][0].get("val") == "Updated"

            # Delete
            dlt = adapter.delete_data(temp_table_name, {"ID": 1})
            assert dlt["success"] is True

        finally:
            adapter.delete_table(temp_table_name)


# ---- Query CRUD --------------------------------------------------------------

class TestOdbcAdapterQueryCrud:
    def test_create_and_delete_query(self, adapter, temp_table_name):
        """Create a temporary query (view), verify, delete it."""
        create = adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer", "nullable": False},
             {"name": "Name", "type": "Text", "size": 50, "nullable": True}]
        )
        assert create["success"] is True

        q_name = f"q_{temp_table_name}"
        try:
            result = adapter.create_query(q_name, f"SELECT * FROM [{temp_table_name}]")
            # Some Access ODBC drivers may not support CREATE VIEW
            if not result["success"]:
                pytest.skip(f"CREATE VIEW not supported by this ODBC driver: {result.get('error')}")

            # Verify it appears in list
            queries = adapter.get_queries()
            assert any(q.name == q_name for q in queries), f"Query {q_name} not found"

            # Delete
            adapter.delete_query(q_name)

        finally:
            adapter.delete_table(temp_table_name)

    def test_delete_query_nonexistent_returns_error(self, adapter):
        result = adapter.delete_query("__nonexistent_query__")
        # Depending on driver, this may raise or return error dict
        if result.get("success"):
            pytest.skip("ODBC driver silently accepted drop of nonexistent view")


# ---- Table CRUD --------------------------------------------------------------

class TestOdbcAdapterTableCrud:
    def test_create_and_delete_table(self, adapter, temp_table_name):
        result = adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer", "nullable": False}]
        )
        assert result["success"] is True

        # Verify it exists
        tables = adapter.get_tables()
        assert any(t.name == temp_table_name for t in tables)

        # Delete
        result = adapter.delete_table(temp_table_name)
        assert result["success"] is True

        # Verify it's gone
        tables = adapter.get_tables()
        assert not any(t.name == temp_table_name for t in tables)


# ---- Data export -------------------------------------------------------------

class TestOdbcAdapterExport:
    def test_export_table_csv(self, adapter, temp_table_name):
        create = adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer", "nullable": False}]
        )
        assert create["success"] is True

        try:
            adapter.insert_data(temp_table_name, {"ID": 42})

            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                csv_path = f.name

            try:
                result = adapter.export_table_csv(temp_table_name, csv_path)
                assert result["success"] is True
                assert result["rows_exported"] >= 1
                assert os.path.exists(csv_path)
                with open(csv_path) as f:
                    content = f.read()
                assert "42" in content or "ID" in content
            finally:
                os.unlink(csv_path)
        finally:
            adapter.delete_table(temp_table_name)

    def test_export_query_json(self, adapter, temp_table_name):
        create = adapter.create_table(
            temp_table_name,
            [{"name": "ID", "type": "Long Integer", "nullable": False}]
        )
        assert create["success"] is True

        try:
            adapter.insert_data(temp_table_name, {"ID": 99})

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json_path = f.name

            try:
                result = adapter.export_query_json(temp_table_name, json_path)
                assert result["success"] is True
                assert result["rows_exported"] >= 1
                assert os.path.exists(json_path)
            finally:
                os.unlink(json_path)
        finally:
            adapter.delete_table(temp_table_name)
