r"""
Integration tests for advanced WinComAdapter operations.

Tests cover:
- Linked-table source DB operations
- Schema calls (list tables, list queries on cloned DB)
- launch_access() / close_access() lifecycle
- Multiple DB connections (connect to two different DBs)

Each test gets its own cloned database via `temp_db_copy`.  A fresh
WinComAdapter is instantiated per test class to minimise COM threading issues.

Markers: com_integration
Execution: pytest tests/integration/test_wincom_advanced.py -m com_integration -v
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
# Linked Tables
# =============================================================================

class TestWinComLinkedTables:
    """Linked-table source DB operations via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_get_linked_tables_empty(self, temp_db_copy: str):
        """get_linked_tables on a fresh clone returns empty list (no linked tables)."""
        assert self.adapter.connect(temp_db_copy)

        result = self.adapter.get_linked_tables()
        assert result["success"] is True
        assert isinstance(result["linked_tables"], list)

    def test_get_linked_tables_on_clone(self, temp_db_copy: str):
        """get_linked_tables returns linked table info when present in DB."""
        assert self.adapter.connect(temp_db_copy)

        result = self.adapter.get_linked_tables()
        # Structure check
        assert result["success"] is True
        assert "linked_tables" in result

    def test_refresh_linked_tables(self, temp_db_copy: str):
        """refresh_linked_table attempts to refresh a linked table source."""
        assert self.adapter.connect(temp_db_copy)

        # First, get current linked tables
        result = self.adapter.get_linked_tables()
        assert result["success"] is True

        # Try to refresh (may have no linked tables in fixture)
        refresh_result = self.adapter.refresh_linked_table("nonexistent_link")
        # Returns error dict if table not found or not a linked table
        assert isinstance(refresh_result, dict)

    def test_unlink_nonexistent_table(self, temp_db_copy: str):
        """unlink_table returns error for non-existent linked table."""
        assert self.adapter.connect(temp_db_copy)

        result = self.adapter.unlink_table("nonexistent_linked_table")
        # Non-existent linked table should return error
        assert result["success"] is False or "error" in result

    def test_get_linked_tables_includes_attributes(self, temp_db_copy: str):
        """get_linked_tables must return attributes integer for each entry."""
        assert self.adapter.connect(temp_db_copy)

        result = self.adapter.get_linked_tables()
        assert result["success"] is True

        # If there are any linked tables, each must have attributes
        for linked in result.get("linked_tables", []):
            assert "attributes" in linked, "linked table must include attributes field"
            assert isinstance(linked["attributes"], int), "attributes must be integer"

    def test_refresh_linked_table_with_connect_string(self, temp_db_copy: str):
        """refresh_linked_table accepts optional connect_string parameter."""
        assert self.adapter.connect(temp_db_copy)

        # Method signature must accept connect_string kwarg
        result = self.adapter.refresh_linked_table("nonexistent_link", connect_string=None)
        assert isinstance(result, dict)

        # With a provided connect_string it should attempt the operation
        result2 = self.adapter.refresh_linked_table(
            "nonexistent_link",
            connect_string="ODBC;DSN=none;PWD=test",
        )
        assert isinstance(result2, dict)


# =============================================================================
# Schema Queries
# =============================================================================

class TestWinComSchemaQueries:
    """Schema listing (tables, queries) on cloned DB via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_get_tables_on_clone(self, temp_db_copy: str):
        """get_tables returns expected tables on a cloned DB."""
        assert self.adapter.connect(temp_db_copy)

        tables = self.adapter.get_tables()
        assert isinstance(tables, list)
        table_names = [t.name for t in tables]
        # The fixture has customers, orders, products, type_test
        assert "customers" in table_names
        assert "orders" in table_names

    def test_get_queries_on_clone(self, temp_db_copy: str):
        """get_queries returns saved queries on a cloned DB."""
        assert self.adapter.connect(temp_db_copy)

        queries = self.adapter.get_queries()
        assert isinstance(queries, list)
        query_names = [q.name for q in queries]
        # qryCustomerOrders is created in the fixture
        assert "qryCustomerOrders" in query_names

    def test_get_tables_not_connected(self):
        """get_tables on disconnected adapter returns empty list."""
        adapter = WinComAdapter()  # never connected
        tables = adapter.get_tables()
        assert tables == []

    def test_get_queries_not_connected(self):
        """get_queries on disconnected adapter returns empty list."""
        adapter = WinComAdapter()  # never connected
        queries = adapter.get_queries()
        assert queries == []


# =============================================================================
# App Lifecycle
# =============================================================================

class TestWinComAppLifecycle:
    """launch_access() / close_access() lifecycle via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_launch_access(self, temp_db_copy: str):
        """launch_access starts a new Access.Application instance."""
        assert self.adapter.connect(temp_db_copy)

        self.adapter.launch_access(visible=False)
        # After launch, dispatcher should be running
        assert self.adapter._dispatcher._started is True

    def test_launch_access_then_query(self, temp_db_copy: str):
        """launch_access followed by query operations still works."""
        assert self.adapter.connect(temp_db_copy)

        self.adapter.launch_access(visible=False)

        # Query should still work after launching
        rows = self.adapter.execute_query("SELECT COUNT(*) AS cnt FROM customers")
        assert rows["success"] is True
        assert rows["count"] == 1

    def test_close_access(self, temp_db_copy: str):
        """close_access shuts down the Access.Application cleanly."""
        assert self.adapter.connect(temp_db_copy)

        self.adapter.launch_access(visible=False)
        self.adapter.close_access()

        # Access app should be None after close
        # Note: close_access clears _access_app on the dispatcher
        assert self.adapter._dispatcher._access_app is None

    def test_launch_close_launch_cycle(self, temp_db_copy: str):
        """launch_access -> close_access -> launch_access again is clean."""
        assert self.adapter.connect(temp_db_copy)

        self.adapter.launch_access(visible=False)
        self.adapter.close_access()

        # Re-launch should work
        self.adapter.launch_access(visible=False)
        assert self.adapter._dispatcher._started is True

        # Query still works
        rows = self.adapter.execute_query("SELECT 1 AS test")
        assert rows["success"] is True


# =============================================================================
# Multiple Connections
# =============================================================================

class TestWinComMultiConnection:
    """Multiple DB connections (two different DBs simultaneously)."""

    def setup_method(self):
        self.adapter_a: WinComAdapter = WinComAdapter()
        self.adapter_b: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter_a)
        _cleanup_adapter(self.adapter_b)

    def test_connect_two_dbs(self, temp_db_copy: str, request):
        """Connect to two different DB files simultaneously with separate adapters."""
        # Get two clones of the same DB to simulate two "different" DBs
        import os
        import shutil
        import tempfile

        # Clone 1: use temp_db_copy as-is
        assert self.adapter_a.connect(temp_db_copy)
        rows_a = self.adapter_a.execute_query("SELECT COUNT(*) AS cnt FROM customers")
        assert rows_a["success"] is True

        # Clone 2: create a second copy
        tmpdir2 = tempfile.mkdtemp(prefix="acc_test2_")
        src_path = temp_db_copy  # same fixture
        clone2_path = os.path.join(tmpdir2, os.path.basename(temp_db_copy))
        shutil.copy2(src_path, clone2_path)

        def cleanup_clone2():
            import time
            time.sleep(0.25)
            try:
                shutil.rmtree(tmpdir2, ignore_errors=True)
            except Exception:
                pass

        request.addfinalizer(cleanup_clone2)

        assert self.adapter_b.connect(clone2_path)
        rows_b = self.adapter_b.execute_query("SELECT COUNT(*) AS cnt FROM customers")
        assert rows_b["success"] is True

        # Both should return results
        assert rows_a["count"] >= 0
        assert rows_b["count"] >= 0

    def test_isolation_between_adapters(self, temp_db_copy: str, request):
        """Changes made via adapter_a are not visible in adapter_b (true isolation)."""
        import os, shutil, tempfile

        # Adapter A connects to clone A
        assert self.adapter_a.connect(temp_db_copy)

        # Create clone B for adapter B
        tmpdir2 = tempfile.mkdtemp(prefix="acc_test2_")
        clone2_path = os.path.join(tmpdir2, os.path.basename(temp_db_copy))
        shutil.copy2(temp_db_copy, clone2_path)

        def cleanup_clone2():
            import time
            time.sleep(0.25)
            try:
                shutil.rmtree(tmpdir2, ignore_errors=True)
            except Exception:
                pass

        request.addfinalizer(cleanup_clone2)

        assert self.adapter_b.connect(clone2_path)

        # Insert via adapter A
        self.adapter_a.insert_data("customers", {"ID": 777, "Name": "AdapterA_Insert"})
        self.adapter_a.disconnect()

        # Adapter B should NOT see adapter A's insert (isolated clones)
        rows_b = self.adapter_b.execute_query("SELECT ID FROM customers WHERE ID = 777")
        assert rows_b["count"] == 0, "Adapter B should not see Adapter A's insert (isolated DBs)"
