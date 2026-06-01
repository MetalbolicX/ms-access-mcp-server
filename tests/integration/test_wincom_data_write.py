"""COM integration tests for WinComAdapter data write operations.

Tests insert_data, update_data, delete_data on a temporary copy of the fixture DB.
"""

import shutil
import tempfile

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


class TestWinComDataInsert:
    """insert_data via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_insert_single_row(self):
        result = self.adapter.insert_data("customers", {"ID": 100, "Name": "Test Corp"})
        assert result["success"] is True
        assert result["affected"] == 1

        # Verify via query
        rows = self.adapter.execute_query("SELECT * FROM customers WHERE ID = 100")
        assert rows["success"] is True
        assert rows["count"] == 1
        assert rows["rows"][0]["Name"] == "Test Corp"

    def test_insert_multiple_rows(self):
        rows_data = [
            {"ID": 200, "Name": "Alpha"},
            {"ID": 201, "Name": "Beta"},
            {"ID": 202, "Name": "Gamma"},
        ]
        result = self.adapter.insert_data("customers", rows_data)
        assert result["success"] is True
        assert result["affected"] == 3

    def test_insert_not_connected_returns_error(self):
        self.adapter.disconnect()
        result = self.adapter.insert_data("customers", {"ID": 1, "Name": "X"})
        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_insert_into_nonexistent_table(self):
        result = self.adapter.insert_data("nonexistent", {"ID": 1})
        assert result["success"] is False


class TestWinComDataUpdate:
    """update_data via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"
        # Ensure at least one row
        self.adapter.insert_data("customers", {"ID": 1, "Name": "Original"})

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_update_by_dict_where(self):
        result = self.adapter.update_data("customers", {"Name": "Updated"}, {"ID": 1})
        assert result["success"] is True

        row = self.adapter.execute_query("SELECT Name FROM customers WHERE ID = 1")
        assert row["rows"][0]["Name"] == "Updated"

    def test_update_not_connected(self):
        self.adapter.disconnect()
        result = self.adapter.update_data("customers", {"Name": "X"}, {"ID": 1})
        assert result["success"] is False

    def test_update_nonexistent_table(self):
        result = self.adapter.update_data("nonexistent", {"Name": "X"}, {"ID": 1})
        assert result["success"] is False


class TestWinComDataDelete:
    """delete_data via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"
        self.adapter.insert_data("customers", {"ID": 1, "Name": "ToDelete"})

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_delete_by_dict_where(self):
        result = self.adapter.delete_data("customers", {"ID": 1})
        assert result["success"] is True

        row = self.adapter.execute_query("SELECT * FROM customers WHERE ID = 1")
        assert row["count"] == 0

    def test_delete_not_connected(self):
        self.adapter.disconnect()
        result = self.adapter.delete_data("customers", {"ID": 1})
        assert result["success"] is False