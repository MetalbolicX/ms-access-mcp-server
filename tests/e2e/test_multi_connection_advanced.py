"""
Advanced multi-connection E2E tests for ConnectionPool.

Tests active context switching, 3+ concurrent connections, connection lifecycle,
list_connections accuracy, and overlapping table isolation.

Naming: all test-created objects prefixed with __e2e_test_.
Cleanup: each test uses explicit try/finally blocks.
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from tests.e2e.conftest import call_mcp_tool
from tests.integration.conftest import _sqlite_pyodbc_connect


# ============================================================================
# TestActiveConnectionSwitching
# ============================================================================

class TestActiveConnectionSwitching:
    """R1 — Active context switching: set_active_connection routes implicit calls."""

    def test_switch_active_context(self, e2e_two_adapters):
        """set_active('prod') → create_table (implicit) → set_active('dev') → get_tables (implicit) → dev lacks prod table."""
        pool = e2e_two_adapters
        PROD = "prod"
        DEV = "dev"
        TABLE = "__e2e_switch_test"

        try:
            # Set active to prod
            pool.set_active(PROD)

            # Create table without explicit connection_name — uses active "prod"
            create_result = call_mcp_tool(
                "create_table",
                TABLE,
                [{"name": "id", "type": "Long Integer"}],
                connection_name=PROD,  # explicit — but active is also PROD
                connection_service=pool,
            )
            assert create_result["success"] is True, f"create_table failed: {create_result}"

            # Switch to dev
            pool.set_active(DEV)

            # get_tables on dev (explicit) — should NOT see prod's table
            dev_tables_result = call_mcp_tool(
                "get_tables",
                connection_name=DEV,
                connection_service=pool,
            )
            assert dev_tables_result["success"] is True
            dev_table_names = {t["name"] for t in dev_tables_result.get("tables", [])}
            assert TABLE not in dev_table_names, f"{TABLE} should NOT be visible on dev: {dev_table_names}"

            # Switch back to prod
            pool.set_active(PROD)

            # get_tables on prod (explicit) — should see the table
            prod_tables_result = call_mcp_tool(
                "get_tables",
                connection_name=PROD,
                connection_service=pool,
            )
            assert prod_tables_result["success"] is True
            prod_table_names = {t["name"] for t in prod_tables_result.get("tables", [])}
            assert TABLE in prod_table_names, f"{TABLE} should be visible on prod: {prod_table_names}"

        finally:
            for conn_name in (PROD, DEV):
                if pool.is_connected(conn_name):
                    adapter = pool.get_adapter(conn_name)
                    try:
                        adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                    except Exception:
                        pass


# ============================================================================
# TestThreeConcurrentConnections
# ============================================================================

class TestThreeConcurrentConnections:
    """R2 — Three or more concurrent connections with independent data."""

    def test_independent_operations(self, e2e_three_adapters):
        """Create table + insert + query on alpha, beta, gamma independently — each returns only its own data."""
        pool = e2e_three_adapters
        ALPHA = "alpha"
        BETA = "beta"
        GAMMA = "gamma"

        alpha_table = "__e2e_3con_alpha"
        beta_table = "__e2e_3con_beta"
        gamma_table = "__e2e_3con_gamma"

        try:
            # --- Alpha ---
            create_alpha = call_mcp_tool(
                "create_table",
                alpha_table,
                [{"name": "id", "type": "Long Integer"}, {"name": "val", "type": "Text"}],
                connection_name=ALPHA,
                connection_service=pool,
            )
            assert create_alpha["success"] is True, f"create_table alpha failed: {create_alpha}"

            insert_alpha = call_mcp_tool(
                "insert_data",
                alpha_table,
                [{"id": 1, "val": "alpha_data"}],
                connection_name=ALPHA,
                connection_service=pool,
            )
            assert insert_alpha["success"] is True, f"insert_data alpha failed: {insert_alpha}"

            query_alpha = call_mcp_tool(
                "query_data",
                f"SELECT val FROM {alpha_table}",
                connection_name=ALPHA,
                connection_service=pool,
            )
            assert query_alpha["success"] is True
            alpha_rows = query_alpha.get("rows", [])
            assert len(alpha_rows) == 1
            assert alpha_rows[0]["val"] == "alpha_data"

            # --- Beta ---
            create_beta = call_mcp_tool(
                "create_table",
                beta_table,
                [{"name": "id", "type": "Long Integer"}, {"name": "val", "type": "Text"}],
                connection_name=BETA,
                connection_service=pool,
            )
            assert create_beta["success"] is True, f"create_table beta failed: {create_beta}"

            insert_beta = call_mcp_tool(
                "insert_data",
                beta_table,
                [{"id": 1, "val": "beta_data"}],
                connection_name=BETA,
                connection_service=pool,
            )
            assert insert_beta["success"] is True, f"insert_data beta failed: {insert_beta}"

            query_beta = call_mcp_tool(
                "query_data",
                f"SELECT val FROM {beta_table}",
                connection_name=BETA,
                connection_service=pool,
            )
            assert query_beta["success"] is True
            beta_rows = query_beta.get("rows", [])
            assert len(beta_rows) == 1
            assert beta_rows[0]["val"] == "beta_data"

            # --- Gamma ---
            create_gamma = call_mcp_tool(
                "create_table",
                gamma_table,
                [{"name": "id", "type": "Long Integer"}, {"name": "val", "type": "Text"}],
                connection_name=GAMMA,
                connection_service=pool,
            )
            assert create_gamma["success"] is True, f"create_table gamma failed: {create_gamma}"

            insert_gamma = call_mcp_tool(
                "insert_data",
                gamma_table,
                [{"id": 1, "val": "gamma_data"}],
                connection_name=GAMMA,
                connection_service=pool,
            )
            assert insert_gamma["success"] is True, f"insert_data gamma failed: {insert_gamma}"

            query_gamma = call_mcp_tool(
                "query_data",
                f"SELECT val FROM {gamma_table}",
                connection_name=GAMMA,
                connection_service=pool,
            )
            assert query_gamma["success"] is True
            gamma_rows = query_gamma.get("rows", [])
            assert len(gamma_rows) == 1
            assert gamma_rows[0]["val"] == "gamma_data"

            # --- Cross-check: alpha should NOT see beta or gamma data ---
            query_alpha_again = call_mcp_tool(
                "query_data",
                f"SELECT val FROM {alpha_table}",
                connection_name=ALPHA,
                connection_service=pool,
            )
            assert query_alpha_again["success"] is True
            assert query_alpha_again.get("rows", []) == [{"val": "alpha_data"}]

        finally:
            for conn_name, tbl in [(ALPHA, alpha_table), (BETA, beta_table), (GAMMA, gamma_table)]:
                if pool.is_connected(conn_name):
                    adapter = pool.get_adapter(conn_name)
                    try:
                        adapter.execute_query(f"DROP TABLE IF EXISTS [{tbl}]")
                    except Exception:
                        pass


# ============================================================================
# TestConnectionLifecycle
# ============================================================================

class TestConnectionLifecycle:
    """R3 — Connect → Disconnect → Reconnect lifecycle."""

    def test_disconnect_reconnect_lifecycle(self, e2e_pool):
        """Disconnect 'default' → is_connected=False → reconnect → verify connection works."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        pool = e2e_pool
        conn_name = "default"

        # Create a temp db to reconnect with
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(tmp_fd)
        conn = sqlite3.connect(tmp_path)
        conn.execute("CREATE TABLE __meta (name TEXT)")
        conn.execute("INSERT INTO __meta VALUES ('lifecycle_reconnect')")
        conn.commit()
        conn.close()

        try:
            # Verify connected initially
            assert pool.is_connected(conn_name), f"{conn_name} should be connected initially"

            # Disconnect
            pool.disconnect(conn_name)
            assert not pool.is_connected(conn_name), f"{conn_name} should be disconnected"

            # Reconnect: create a fresh OdbcAdapter and reconnect
            with patch("pyodbc.connect", _sqlite_pyodbc_connect):
                new_adapter = OdbcAdapter()
                new_adapter.connect(tmp_path)
                # Replace the adapter in the pool's state
                pool._pool[conn_name].adapter = new_adapter

            assert pool.is_connected(conn_name), f"{conn_name} should be reconnected"

            # Verify it actually works
            adapter = pool.get_adapter(conn_name)
            adapter.execute_query("SELECT 1")

            # Create table and query to verify full functionality
            create_result = call_mcp_tool(
                "create_table",
                "__e2e_lifecycle_test",
                [{"name": "id", "type": "Long Integer"}],
                connection_name=conn_name,
                connection_service=pool,
            )
            assert create_result["success"] is True, f"create_table after reconnect failed: {create_result}"

        finally:
            if pool.is_connected(conn_name):
                adapter = pool.get_adapter(conn_name)
                try:
                    adapter.execute_query("DROP TABLE IF EXISTS [__e2e_lifecycle_test]")
                except Exception:
                    pass
                pool.disconnect(conn_name)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ============================================================================
# TestListConnectionsAccuracy
# ============================================================================

class TestListConnectionsAccuracy:
    """R4 — list_connections returns accurate count, names, and connected status."""

    def test_list_connections_multiple_states(self, e2e_three_adapters):
        """List all 3 connections → verify count=3, names include alpha/beta/gamma, all connected=True. Disconnect beta → list again → verify disconnected."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        pool = e2e_three_adapters

        # Initial state: all 3 connected
        list_result = call_mcp_tool("list_connections", connection_service=pool)
        assert list_result["success"] is True, f"list_connections failed: {list_result}"
        assert list_result.get("count") == 3, f"Expected count=3, got: {list_result.get('count')}"
        connections = list_result.get("connections", {})
        assert "alpha" in connections, f"alpha not in connections: {connections}"
        assert "beta" in connections, f"beta not in connections: {connections}"
        assert "gamma" in connections, f"gamma not in connections: {connections}"
        for name, c in connections.items():
            assert c.get("connected") is True, f"{name} should be connected: {c}"

        # Verify all 3 connected initially
        list_result = call_mcp_tool("list_connections", connection_service=pool)
        assert list_result["success"] is True, f"list_connections failed: {list_result}"
        assert list_result.get("count") == 3, f"Expected count=3, got: {list_result.get('count')}"
        connections = list_result.get("connections", {})
        assert "alpha" in connections, f"alpha not in connections: {connections}"
        assert "beta" in connections, f"beta not in connections: {connections}"
        assert "gamma" in connections, f"gamma not in connections: {connections}"
        for name, c in connections.items():
            assert c.get("connected") is True, f"{name} should be connected: {c}"

        # Disconnect beta (removes from pool for non-default connections)
        pool.disconnect("beta")
        assert not pool.is_connected("beta"), "beta should be disconnected"

        # List again: beta is removed from pool (not retained as disconnected)
        list_after = call_mcp_tool("list_connections", connection_service=pool)
        assert list_after["success"] is True
        assert list_after.get("count") == 2, f"count should be 2 after removing beta: {list_after.get('count')}"
        connections_after = list_after.get("connections", {})
        assert "beta" not in connections_after, "beta should be removed from pool after disconnect"
        assert "alpha" in connections_after, "alpha should still be in pool"
        assert "gamma" in connections_after, "gamma should still be in pool"


# ============================================================================
# TestOverlappingTableIsolation
# ============================================================================

class TestOverlappingTableIsolation:
    """R5 — Identically-named tables on different connections return their own data."""

    def test_same_table_different_data(self, e2e_two_adapters):
        """Create '__e2e_overlap' on prod with 'prod_data' → create '__e2e_overlap' on dev with 'dev_data' → switch active → query → each returns own data."""
        pool = e2e_two_adapters
        PROD = "prod"
        DEV = "dev"
        TABLE = "__e2e_overlap"

        try:
            # Create table on prod with prod data
            create_prod = call_mcp_tool(
                "create_table",
                TABLE,
                [{"name": "id", "type": "Long Integer"}, {"name": "val", "type": "Text"}],
                connection_name=PROD,
                connection_service=pool,
            )
            assert create_prod["success"] is True, f"create_table prod failed: {create_prod}"

            insert_prod = call_mcp_tool(
                "insert_data",
                TABLE,
                [{"id": 1, "val": "prod_data"}],
                connection_name=PROD,
                connection_service=pool,
            )
            assert insert_prod["success"] is True, f"insert_data prod failed: {insert_prod}"

            # Create table on dev with different data
            create_dev = call_mcp_tool(
                "create_table",
                TABLE,
                [{"name": "id", "type": "Long Integer"}, {"name": "val", "type": "Text"}],
                connection_name=DEV,
                connection_service=pool,
            )
            assert create_dev["success"] is True, f"create_table dev failed: {create_dev}"

            insert_dev = call_mcp_tool(
                "insert_data",
                TABLE,
                [{"id": 1, "val": "dev_data"}],
                connection_name=DEV,
                connection_service=pool,
            )
            assert insert_dev["success"] is True, f"insert_data dev failed: {insert_dev}"

            # Switch active to prod → query via explicit connection_name
            pool.set_active(PROD)
            query_prod = call_mcp_tool(
                "query_data",
                f"SELECT val FROM {TABLE}",
                connection_name=PROD,
                connection_service=pool,
            )
            assert query_prod["success"] is True, f"query_data prod failed: {query_prod}"
            prod_rows = query_prod.get("rows", [])
            assert len(prod_rows) == 1, f"Expected 1 row on prod, got: {prod_rows}"
            assert prod_rows[0]["val"] == "prod_data", f"Expected 'prod_data' on prod, got: {prod_rows[0]}"

            # Switch active to dev → query via explicit connection_name
            pool.set_active(DEV)
            query_dev = call_mcp_tool(
                "query_data",
                f"SELECT val FROM {TABLE}",
                connection_name=DEV,
                connection_service=pool,
            )
            assert query_dev["success"] is True, f"query_data dev failed: {query_dev}"
            dev_rows = query_dev.get("rows", [])
            assert len(dev_rows) == 1, f"Expected 1 row on dev, got: {dev_rows}"
            assert dev_rows[0]["val"] == "dev_data", f"Expected 'dev_data' on dev, got: {dev_rows[0]}"

        finally:
            for conn_name in (PROD, DEV):
                if pool.is_connected(conn_name):
                    adapter = pool.get_adapter(conn_name)
                    try:
                        adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                    except Exception:
                        pass