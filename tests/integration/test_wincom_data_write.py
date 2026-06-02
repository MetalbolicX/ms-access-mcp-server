r"""
Integration tests for WinComAdapter data write operations (insert / update / delete).

These tests require:
  - Windows OS with MS Access installed
  - pywin32 (win32com.client)
  - A test .accdb database file (customers table with ID, Name columns)

Markers: com_integration
Execution: pytest tests/integration/test_wincom_data_write.py -m com_integration -v

Each test gets its own cloned database via `temp_db_copy` so the master fixture
is never modified.  A fresh WinComAdapter is instantiated per test class to
minimise COM threading issues.
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
    """Safely disconnect an adapter.

    Tries to call disconnect() but catches all exceptions (including COM
    teardown crashes like 0x80010108 RPC_E_CALL_CANCELED) so the test
    process never crashes in teardown.
    """
    try:
        adapter.disconnect()
    except Exception:
        pass


class TestWinComDataInsert:
    """Insert operations via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_insert_customer(self, temp_db_copy: str):
        """Insert a new customer row and verify it is readable via SELECT."""
        assert self.adapter.connect(temp_db_copy), f"Failed to connect to {temp_db_copy}"

        result = self.adapter.insert_data("customers", {"ID": 999, "Name": "TestInsert"})
        assert result["success"] is True, f"Insert failed: {result.get('error')}"
        assert result.get("affected", 0) == 1

        # Verify the row is present
        rows = self.adapter.execute_query("SELECT * FROM customers WHERE ID = 999")
        assert rows["success"] is True
        assert rows["count"] == 1
        assert rows["rows"][0]["Name"] == "TestInsert"

    def test_insert_order(self, temp_db_copy: str):
        """Insert an order with FK reference to an existing customer."""
        assert self.adapter.connect(temp_db_copy)

        result = self.adapter.insert_data("orders", {"ID": 999, "CustomerID": 1, "Total": 250.00})
        assert result["success"] is True, f"Insert order failed: {result.get('error')}"

        rows = self.adapter.execute_query("SELECT * FROM orders WHERE ID = 999")
        assert rows["success"] is True
        assert rows["count"] == 1
        assert rows["rows"][0]["CustomerID"] == 1

    def test_insert_type_test_row(self, temp_db_copy: str):
        """Insert a row into type_test with all column types."""
        assert self.adapter.connect(temp_db_copy)

        from datetime import datetime
        row = {
            "ID": 999,
            "name": "FullTypeRow",
            "active": True,
            "created": datetime(2024, 6, 15, 12, 0, 0),
            "price": 199.99,
            "notes": "Testing all types",
            "guid": "{550e8400-e29b-41d4-a716-446655440000}",
            "rating": 4.5,
            "level": 3,
        }
        result = self.adapter.insert_data("type_test", row)
        assert result["success"] is True, f"Insert type_test failed: {result.get('error')}"

        # Verify
        rows = self.adapter.execute_query("SELECT * FROM type_test WHERE ID = 999")
        assert rows["success"] is True
        assert rows["rows"][0]["name"] == "FullTypeRow"


class TestWinComDataUpdate:
    """Update operations via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_update_customer_name(self, temp_db_copy: str):
        """Update an existing customer's Name and verify the change via SELECT."""
        assert self.adapter.connect(temp_db_copy)

        # Pre-condition: customer 1 exists
        rows = self.adapter.execute_query("SELECT Name FROM customers WHERE ID = 1")
        assert rows["count"] >= 1, "Precondition: customer 1 must exist"

        result = self.adapter.update_data("customers", {"Name": "AliceUpdated"}, {"ID": 1})
        assert result["success"] is True, f"Update failed: {result.get('error')}"

        # Verify
        rows = self.adapter.execute_query("SELECT Name FROM customers WHERE ID = 1")
        assert rows["success"] is True
        assert rows["rows"][0]["Name"] == "AliceUpdated"

    def test_update_order_total(self, temp_db_copy: str):
        """Update an order's Total and verify via SELECT."""
        assert self.adapter.connect(temp_db_copy)

        # Pre-condition: order 1 exists
        rows = self.adapter.execute_query("SELECT Total FROM orders WHERE ID = 1")
        assert rows["count"] >= 1, "Precondition: order 1 must exist"

        result = self.adapter.update_data("orders", {"Total": 999.99}, {"ID": 1})
        assert result["success"] is True, f"Update total failed: {result.get('error')}"

        rows = self.adapter.execute_query("SELECT Total FROM orders WHERE ID = 1")
        assert rows["success"] is True
        assert rows["rows"][0]["Total"] == 999.99


class TestWinComDataDelete:
    """Delete operations via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_delete_customer(self, temp_db_copy: str):
        """Delete an existing customer and verify it is gone."""
        assert self.adapter.connect(temp_db_copy)

        # Insert a row we can safely delete
        self.adapter.insert_data("customers", {"ID": 888, "Name": "ToDelete"})
        rows = self.adapter.execute_query("SELECT ID FROM customers WHERE ID = 888")
        assert rows["count"] == 1, "Precondition: row must exist before delete"

        result = self.adapter.delete_data("customers", {"ID": 888})
        assert result["success"] is True, f"Delete failed: {result.get('error')}"

        rows = self.adapter.execute_query("SELECT ID FROM customers WHERE ID = 888")
        assert rows["count"] == 0, "Row should be gone after delete"

    def test_delete_all_orders(self, temp_db_copy: str):
        """Delete all orders for a specific customer using dict-where."""
        assert self.adapter.connect(temp_db_copy)

        # Pre-condition: customer 1 has at least one order
        rows = self.adapter.execute_query("SELECT COUNT(*) AS cnt FROM orders WHERE CustomerID = 1")
        pre_count = rows["rows"][0]["cnt"]
        assert pre_count >= 1, "Precondition: customer 1 must have at least one order"

        result = self.adapter.delete_data("orders", {"CustomerID": 1})
        assert result["success"] is True, f"Delete all orders failed: {result.get('error')}"

        rows = self.adapter.execute_query("SELECT COUNT(*) AS cnt FROM orders WHERE CustomerID = 1")
        assert rows["rows"][0]["cnt"] == 0, "All orders for customer 1 should be deleted"

    def test_delete_restores_on_clone(self, temp_db_copy: str, request):
        """Verify the master fixture is unaffected by deletes on the clone.

        We delete customer 3 on the clone and confirm the master still has it.
        """
        # First connect to the MASTER (not clone) and confirm customer 3 exists
        from helpers import TEST_DB
        master_adapter = WinComAdapter()
        assert master_adapter.connect(TEST_DB)
        master_before = master_adapter.execute_query("SELECT ID FROM customers WHERE ID = 3")
        assert master_before["count"] == 1, "Precondition: customer 3 must exist in master"
        master_adapter.disconnect()

        # Now delete on the clone
        assert self.adapter.connect(temp_db_copy)
        result = self.adapter.delete_data("customers", {"ID": 3})
        assert result["success"] is True
        self.adapter.disconnect()

        # Reconnect to master — customer 3 must still be there
        master_adapter2 = WinComAdapter()
        master_adapter2.connect(TEST_DB)
        master_after = master_adapter2.execute_query("SELECT ID FROM customers WHERE ID = 3")
        assert master_after["count"] == 1, "Master fixture should be unaffected by clone delete"
        master_adapter2.disconnect()
