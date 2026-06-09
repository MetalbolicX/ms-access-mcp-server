"""
E2E workflow tests for pool-level operations using SQLite-backed adapters.

These tests chain multiple MCP tools to validate complete workflows:
- CRUD cycle (create_table → insert_data → query_data → get_table_schema → disconnect)
- Data export (CSV + JSON)
- Multi-table operations
- Multi-connection isolation
- Schema and ER diagram

All tests use __e2e_test_ prefix for created objects.
Cleanup: explicit try/finally blocks (not autouse fixtures).
"""

import json
import os
import sqlite3
from pathlib import Path

import pytest

from tests.e2e.conftest import e2e_pool, e2e_two_adapters, temp_export_dir, call_mcp_tool
from tests.e2e.helpers import assert_file_exists, assert_file_not_empty, assert_workflow_result


# ============================================================================
# Helper
# ============================================================================

def _columns_for_product_table() -> list[dict]:
    """Standard column definition for product table in CRUD tests."""
    return [
        {"name": "id", "type": "Long Integer"},
        {"name": "name", "type": "Text", "size": 100},
        {"name": "price", "type": "Currency"},
    ]


# ============================================================================
# TestCrudCycle
# ============================================================================

class TestCrudCycle:
    """Complete CRUD cycle via pool — spec scenario 'Complete CRUD cycle via pool'."""

    def test_crud_cycle_create_insert_query(self, e2e_pool):
        """create_table → insert_data → query_data → get_table_schema → disconnect."""
        TABLE = "__e2e_test_products"
        pool = e2e_pool

        try:
            # Step 1: create_table
            create_result = call_mcp_tool(
                "create_table",
                TABLE,
                _columns_for_product_table(),
                connection_service=pool,
            )
            assert create_result["success"] is True, f"create_table failed: {create_result}"

            # Step 2: insert two rows
            insert_result = call_mcp_tool(
                "insert_data",
                TABLE,
                [{"id": 1, "name": "Widget", "price": 9.99}, {"id": 2, "name": "Gadget", "price": 19.99}],
                connection_service=pool,
            )
            assert insert_result["success"] is True, f"insert_data failed: {insert_result}"

            # Step 3: query_data — verify 2 rows returned
            query_result = call_mcp_tool(
                "query_data",
                f"SELECT id, name, price FROM {TABLE} ORDER BY id",
                connection_service=pool,
            )
            assert query_result["success"] is True, f"query_data failed: {query_result}"
            rows = query_result.get("rows", [])
            assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
            assert rows[0]["id"] == 1
            assert rows[0]["name"] == "Widget"
            assert rows[1]["id"] == 2
            assert rows[1]["name"] == "Gadget"

            # Step 4: get_table_schema — verify 3 columns
            schema_result = call_mcp_tool(
                "get_table_schema",
                TABLE,
                connection_service=pool,
            )
            assert schema_result["success"] is True, f"get_table_schema failed: {schema_result}"
            table = schema_result.get("table", {})
            fields = table.get("fields", [])
            assert len(fields) == 3, f"Expected 3 columns, got {len(fields)}"
            field_names = {f["name"] for f in fields}
            assert field_names >= {"id", "name", "price"}, f"Missing expected columns: {field_names}"

            # Step 5: disconnect — pool still usable for other tests
            pool.disconnect("default")
            assert not pool.is_connected("default"), "Should be disconnected after disconnect() call"

        finally:
            # Cleanup: drop table if still connected
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass
                pool.disconnect("default")


# ============================================================================
# TestDataExport
# ============================================================================

class TestDataExport:
    """Data export to CSV and JSON — spec scenarios 'Export data (CSV)' and 'Export data (JSON)'."""

    def test_export_csv(self, e2e_pool, temp_export_dir):
        """create_table → insert_data → export_data(format=csv) → verify file."""
        TABLE = "__e2e_test_export_csv"
        pool = e2e_pool
        csv_path = os.path.join(temp_export_dir, "export_test.csv")

        try:
            # Setup
            create_result = call_mcp_tool(
                "create_table",
                TABLE,
                [
                    {"name": "id", "type": "Long Integer"},
                    {"name": "name", "type": "Text", "size": 50},
                ],
                connection_service=pool,
            )
            assert create_result["success"] is True

            call_mcp_tool(
                "insert_data",
                TABLE,
                [
                    {"id": 1, "name": "Alpha"},
                    {"id": 2, "name": "Beta"},
                    {"id": 3, "name": "Gamma"},
                ],
                connection_service=pool,
            )

            # Export
            export_result = call_mcp_tool(
                "export_data",
                f"SELECT id, name FROM {TABLE} ORDER BY id",
                csv_path,
                format="csv",
                connection_service=pool,
            )
            assert export_result["success"] is True, f"CSV export failed: {export_result}"
            assert export_result.get("rows_exported", 0) == 3

            # Verify
            assert_file_exists(csv_path)
            content = Path(csv_path).read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            assert len(lines) == 4, f"Expected 4 lines (header + 3 data), got {len(lines)}: {content!r}"
            assert "id,name" in lines[0], f"Expected CSV header, got: {lines[0]}"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass

    def test_export_json(self, e2e_pool, temp_export_dir):
        """create_table → insert_data → export_data(format=json) → verify file parses."""
        TABLE = "__e2e_test_export_json"
        pool = e2e_pool
        json_path = os.path.join(temp_export_dir, "export_test.json")

        try:
            # Setup
            create_result = call_mcp_tool(
                "create_table",
                TABLE,
                [
                    {"name": "id", "type": "Long Integer"},
                    {"name": "value", "type": "Double"},
                ],
                connection_service=pool,
            )
            assert create_result["success"] is True

            call_mcp_tool(
                "insert_data",
                TABLE,
                [{"id": 10, "value": 1.5}, {"id": 20, "value": 2.5}],
                connection_service=pool,
            )

            # Export
            export_result = call_mcp_tool(
                "export_data",
                f"SELECT id, value FROM {TABLE} ORDER BY id",
                json_path,
                format="json",
                pretty=True,
                connection_service=pool,
            )
            assert export_result["success"] is True, f"JSON export failed: {export_result}"
            assert export_result.get("rows_exported", 0) == 2

            # Verify
            assert_file_exists(json_path)
            data = json.loads(Path(json_path).read_text(encoding="utf-8"))
            assert isinstance(data, list), f"Expected JSON list, got {type(data)}"
            assert len(data) == 2, f"Expected 2 records, got {len(data)}"
            assert data[0]["id"] == 10
            assert data[0]["value"] == 1.5

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass


# ============================================================================
# TestMultiTableWorkflow
# ============================================================================

class TestMultiTableWorkflow:
    """Multi-table workflow — create 2 tables, get_tables, delete one, verify."""

    def test_multi_table_workflow(self, e2e_pool):
        """create __e2e_test_a + __e2e_test_b → get_tables → delete __e2e_test_a → re-check."""
        pool = e2e_pool
        TABLE_A = "__e2e_test_a"
        TABLE_B = "__e2e_test_b"

        try:
            # Create both tables
            for tbl in (TABLE_A, TABLE_B):
                result = call_mcp_tool(
                    "create_table",
                    tbl,
                    [{"name": "id", "type": "Long Integer"}],
                    connection_service=pool,
                )
                assert result["success"] is True, f"create_table {tbl} failed: {result}"

            # Verify both appear in get_tables
            tables_result = call_mcp_tool("get_tables", connection_service=pool)
            assert tables_result["success"] is True
            table_names = {t["name"] for t in tables_result.get("tables", [])}
            assert TABLE_A in table_names, f"{TABLE_A} not in tables: {table_names}"
            assert TABLE_B in table_names, f"{TABLE_B} not in tables: {table_names}"

            # Delete TABLE_A
            delete_result = call_mcp_tool("delete_table", TABLE_A, connection_service=pool)
            assert delete_result["success"] is True, f"delete_table failed: {delete_result}"

            # Verify only TABLE_B remains
            tables_after = call_mcp_tool("get_tables", connection_service=pool)
            assert tables_after["success"] is True
            remaining = {t["name"] for t in tables_after.get("tables", [])}
            assert TABLE_A not in remaining, f"{TABLE_A} should be deleted: {remaining}"
            assert TABLE_B in remaining, f"{TABLE_B} should still exist: {remaining}"

        finally:
            for tbl in (TABLE_A, TABLE_B):
                if pool.is_connected("default"):
                    adapter = pool.get_adapter("default")
                    try:
                        adapter.execute_query(f"DROP TABLE IF EXISTS [{tbl}]")
                    except Exception:
                        pass


# ============================================================================
# TestMultiConnectionIsolation
# ============================================================================

class TestMultiConnectionIsolation:
    """Multi-connection isolation — prod and dev are isolated, disconnect prod doesn't affect dev."""

    def test_prod_dev_isolation(self, e2e_two_adapters):
        """Create table on prod (invisible to dev) → disconnect prod → dev still works."""
        pool = e2e_two_adapters
        PROD_TABLE = "__e2e_test_secret"
        DEV_TABLE = "__e2e_test_visible"
        PROD = "prod"
        DEV = "dev"

        try:
            # Create table on prod only
            create_prod = call_mcp_tool(
                "create_table",
                PROD_TABLE,
                [{"name": "id", "type": "Long Integer"}],
                connection_name=PROD,
                connection_service=pool,
            )
            assert create_prod["success"] is True, f"create_table on prod failed: {create_prod}"

            # Verify prod table is visible when querying through prod
            prod_tables = call_mcp_tool("get_tables", connection_name=PROD, connection_service=pool)
            assert prod_tables["success"] is True
            prod_table_names = {t["name"] for t in prod_tables.get("tables", [])}
            assert PROD_TABLE in prod_table_names, f"{PROD_TABLE} not visible on prod: {prod_table_names}"

            # Verify prod table is NOT visible from dev (isolation)
            dev_tables = call_mcp_tool("get_tables", connection_name=DEV, connection_service=pool)
            assert dev_tables["success"] is True
            dev_table_names = {t["name"] for t in dev_tables.get("tables", [])}
            assert PROD_TABLE not in dev_table_names, \
                f"prod table {PROD_TABLE} should not be visible on dev: {dev_table_names}"

            # Create dev-specific table
            create_dev = call_mcp_tool(
                "create_table",
                DEV_TABLE,
                [{"name": "id", "type": "Long Integer"}],
                connection_name=DEV,
                connection_service=pool,
            )
            assert create_dev["success"] is True

            # Disconnect prod
            pool.disconnect(PROD)
            assert not pool.is_connected(PROD), "prod should be disconnected"

            # Dev is still usable after prod disconnect
            dev_after = call_mcp_tool("get_tables", connection_name=DEV, connection_service=pool)
            assert dev_after["success"] is True, f"dev should still work after prod disconnect: {dev_after}"
            dev_remaining = {t["name"] for t in dev_after.get("tables", [])}
            assert DEV_TABLE in dev_remaining, f"{DEV_TABLE} should still be visible on dev: {dev_remaining}"

        finally:
            for conn in (PROD, DEV):
                if pool.is_connected(conn):
                    adapter = pool.get_adapter(conn)
                    try:
                        for tbl in (PROD_TABLE, DEV_TABLE):
                            adapter.execute_query(f"DROP TABLE IF EXISTS [{tbl}]")
                    except Exception:
                        pass
                    pool.disconnect(conn)


# ============================================================================
# TestSchemaErDiagram
# ============================================================================

class TestSchemaErDiagram:
    """Schema and ER diagram workflow — get_table_schema, get_relationships, get_er_diagram."""

    def test_schema_er_diagram_structure(self, e2e_pool):
        """get_table_schema(__meta) → get_relationships → get_er_diagram return expected structures."""
        pool = e2e_pool

        # __meta table is created by sqlite_db fixture
        # Step 1: get_table_schema for __meta
        schema_result = call_mcp_tool(
            "get_table_schema",
            "__meta",
            connection_service=pool,
        )
        assert schema_result["success"] is True, f"get_table_schema failed: {schema_result}"
        table = schema_result.get("table", {})
        assert "name" in table, "table schema should include 'name' field"
        assert "fields" in table, "table schema should include 'fields' key"
        assert len(table["fields"]) >= 1, f"__meta should have at least 1 field, got {len(table['fields'])}"

        # Step 2: get_relationships
        rel_result = call_mcp_tool(
            "get_relationships",
            connection_service=pool,
        )
        assert rel_result["success"] is True, f"get_relationships failed: {rel_result}"
        assert "relationships" in rel_result, "relationships result should have 'relationships' key"
        assert isinstance(rel_result["relationships"], list), "relationships should be a list"

        # Step 3: get_er_diagram
        er_result = call_mcp_tool(
            "get_er_diagram",
            connection_service=pool,
        )
        assert er_result["success"] is True, f"get_er_diagram failed: {er_result}"
        assert "nodes" in er_result, "ER diagram should include 'nodes' key"
        assert "edges" in er_result, "ER diagram should include 'edges' key"
        assert isinstance(er_result["nodes"], list), "nodes should be a list"
        assert isinstance(er_result["edges"], list), "edges should be a list"
        assert "node_count" in er_result
        assert "edge_count" in er_result

        # __meta should appear as a node
        node_ids = {n["id"] for n in er_result["nodes"]}
        assert "__meta" in node_ids, f"__meta should appear as node, got nodes: {node_ids}"


# ============================================================================
# TestIndexSmoke
# ============================================================================


class TestIndexSmoke:
    """E2E smoke tests for index CRUD tools via SQLite-backed ODBC pool.

    These tests verify the ODBC contract: get_indexes returns an empty list
    because ODBC cannot enumerate DAO indexes. The tests assert:
    - create_index succeeds (DDL executes)
    - get_indexes returns empty list (ODBC limitation by contract)
    - drop_index succeeds (DDL executes)
    - No errors propagate unexpectedly
    """

    def test_create_index_via_odbc_succeeds(self, e2e_pool):
        """create_index via ODBC pool returns success even though get_indexes stays empty."""
        pool = e2e_pool
        TABLE = "__e2e_test_idx_tbl"
        INDEX = "__e2e_test_idx"

        try:
            # Create table first
            create_tbl = call_mcp_tool(
                "create_table",
                TABLE,
                [{"name": "id", "type": "Long Integer"}, {"name": "name", "type": "Text", "size": 100}],
                connection_service=pool,
            )
            assert create_tbl["success"] is True, f"create_table failed: {create_tbl}"

            # Create index — should succeed (DDL executes)
            create_idx = call_mcp_tool(
                "create_index",
                TABLE,
                INDEX,
                ["name"],
                connection_service=pool,
            )
            assert create_idx["success"] is True, f"create_index failed: {create_idx}"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP INDEX [{INDEX}] ON [{TABLE}]")
                except Exception:
                    pass
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass

    def test_get_indexes_returns_empty_via_odbc(self, e2e_pool):
        """get_indexes via ODBC pool returns empty list — ODBC DAO limitation contract."""
        pool = e2e_pool
        TABLE = "__e2e_test_idx_empty"

        try:
            # Create table
            create_tbl = call_mcp_tool(
                "create_table",
                TABLE,
                [{"name": "id", "type": "Long Integer"}],
                connection_service=pool,
            )
            assert create_tbl["success"] is True

            # get_indexes on a table with no user-created indexes returns empty
            # (ODBC cannot enumerate DAO indexes — this is the contract)
            indexes_result = call_mcp_tool(
                "get_indexes",
                TABLE,
                connection_service=pool,
            )
            assert indexes_result["success"] is True, f"get_indexes failed: {indexes_result}"
            assert indexes_result.get("count", -1) == 0, \
                f"ODBC get_indexes should return 0, got: {indexes_result.get('count')}"
            assert indexes_result.get("indexes", []) == [], \
                f"ODBC get_indexes should return empty list, got: {indexes_result.get('indexes')}"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass

    def test_drop_index_via_odbc_succeeds(self, e2e_pool):
        """drop_index via ODBC pool returns success after create_index."""
        pool = e2e_pool
        TABLE = "__e2e_test_drop_idx"
        INDEX = "__e2e_test_drop_idx"

        try:
            # Create table and index
            call_mcp_tool(
                "create_table",
                TABLE,
                [{"name": "id", "type": "Long Integer"}],
                connection_service=pool,
            )
            call_mcp_tool(
                "create_index",
                TABLE,
                INDEX,
                ["id"],
                connection_service=pool,
            )

            # Drop index with confirm=True — should succeed
            drop_result = call_mcp_tool(
                "drop_index",
                TABLE,
                INDEX,
                confirm=True,
                connection_service=pool,
            )
            assert drop_result["success"] is True, f"drop_index failed: {drop_result}"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass

    def test_drop_index_requires_confirm_via_odbc(self, e2e_pool):
        """drop_index without confirm=True is rejected via ODBC pool."""
        pool = e2e_pool
        TABLE = "__e2e_test_noconfirm"
        INDEX = "__e2e_test_noconfirm"

        try:
            call_mcp_tool(
                "create_table",
                TABLE,
                [{"name": "id", "type": "Long Integer"}],
                connection_service=pool,
            )
            call_mcp_tool(
                "create_index",
                TABLE,
                INDEX,
                ["id"],
                connection_service=pool,
            )

            # Without confirm=True — should be rejected
            drop_result = call_mcp_tool(
                "drop_index",
                TABLE,
                INDEX,
                connection_service=pool,
            )
            assert drop_result["success"] is False, \
                "drop_index should reject without confirm=True"
            assert "confirm" in drop_result.get("error", "").lower()

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass

    def test_index_lifecycle_odbc_empty_by_contract(self, e2e_pool):
        """Full index lifecycle via ODBC: create_index → get_indexes(empty) → drop_index.

        This test proves the ODBC contract: get_indexes stays empty even after
        create_index because ODBC cannot enumerate DAO indexes.
        """
        pool = e2e_pool
        TABLE = "__e2e_test_lifecycle"
        INDEX = "__e2e_test_lifecycle_ix"

        try:
            # Step 1: create_table
            create_tbl = call_mcp_tool(
                "create_table",
                TABLE,
                [{"name": "id", "type": "Long Integer"}, {"name": "value", "type": "Double"}],
                connection_service=pool,
            )
            assert create_tbl["success"] is True, f"create_table failed: {create_tbl}"

            # Step 2: create_index — DDL executes successfully
            create_idx = call_mcp_tool(
                "create_index",
                TABLE,
                INDEX,
                ["value"],
                connection_service=pool,
            )
            assert create_idx["success"] is True, f"create_index failed: {create_idx}"

            # Step 3: get_indexes — ODBC contract: returns empty list
            indexes_result = call_mcp_tool(
                "get_indexes",
                TABLE,
                connection_service=pool,
            )
            assert indexes_result["success"] is True, f"get_indexes failed: {indexes_result}"
            assert indexes_result.get("count", -1) == 0, \
                f"ODBC contract: get_indexes should return 0, got: {indexes_result.get('count')}"
            assert indexes_result.get("indexes", []) == [], \
                f"ODBC contract: get_indexes should return [], got: {indexes_result.get('indexes')}"

            # Step 4: drop_index — DDL executes successfully
            drop_result = call_mcp_tool(
                "drop_index",
                TABLE,
                INDEX,
                confirm=True,
                connection_service=pool,
            )
            assert drop_result["success"] is True, f"drop_index failed: {drop_result}"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass