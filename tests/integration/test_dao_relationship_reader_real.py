"""Integration test: real `db/postgres.accdb` relationships via DAO.

Connects to the live project database and verifies the OdbcAdapter picks
the DAO reader on Windows, returns the 4 known FKs with the correct
tables, columns, and non-empty ``attributes``, and proves the DAO open
does NOT lock the file (a concurrent ODBC read still succeeds).

Slice 7 of dao-first-linked-tables-properties replaces the standalone
``DaoRelationshipReader`` class with
``DaoAdapter.read_relationships_short_lived``. This test exercises the
new path against the live project database and proves the open/close
behavior (concurrent ODBC read after DAO open) is unchanged.

This is the "real .accdb" counterpart of the SQLite-backed
``test_mcp_schema.py::test_get_er_diagram_via_sqlite`` test.

Markers: ``com_integration`` (requires Windows + pywin32 + the live DB).

Execution:
    pytest tests/integration/test_dao_relationship_reader_real.py \\
        -m com_integration -v
"""
from __future__ import annotations

from pathlib import Path

import pytest
from helpers import skip_unless_pywin32, skip_unless_windows

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
]


# Known FKs in db/postgres.accdb (verified via DAO on Windows).
# Each tuple: (relation_name, child_table, parent_table, child_col, parent_col)
EXPECTED_FKS: list[tuple[str, str, str, str, str]] = [
    ("Rel_1186CF53_FF2E_405A", "orders", "order_items", "order_id", "order_item_order_id"),
    ("Rel_A7C1AB0A_38B9_4C5B", "products", "order_items", "product_id", "order_item_product_id"),
    ("Rel_A96FAB3D_35CE_4022", "customers", "orders", "customer_id", "order_customer_id"),
    ("Rel_B46CE34B_E74B_4E07", "categories", "products", "category_id", "product_category_id"),
]


def _project_db() -> str:
    """Resolve the live project database path."""
    return str(Path(__file__).resolve().parents[2] / "db" / "postgres.accdb")


@pytest.fixture(scope="module")
def accdb_path() -> str:
    """The live ``db/postgres.accdb`` path. Skips if not present."""
    path = _project_db()
    if not Path(path).exists():
        pytest.skip(f"Live database not found at {path}")
    return path


class TestDaoRelationshipReaderReal:
    """End-to-end DAO reader against the live Access database."""

    def test_odbc_adapter_returns_all_four_known_fks(self, accdb_path: str):
        """OdbcAdapter.get_relationships() returns the 4 known FKs via DAO."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter()
        try:
            connected = adapter.connect(accdb_path)
            assert connected, "OdbcAdapter should connect to db/postgres.accdb"

            rels = adapter.get_relationships()
            assert isinstance(rels, list), f"Expected list, got {type(rels)}"
            assert len(rels) == 4, (
                f"Expected 4 FKs, got {len(rels)}: "
                f"{[(r.name, r.table, r.foreign_table) for r in rels]}"
            )

            # Index by name for ordered assertion
            by_name = {r.name: r for r in rels}
            for name, child, parent, child_col, parent_col in EXPECTED_FKS:
                assert name in by_name, (
                    f"Missing FK {name!r}. Got: {sorted(by_name)}"
                )
                rel = by_name[name]
                assert rel.table == child, (
                    f"{name}: expected table={child!r}, got {rel.table!r}"
                )
                assert rel.foreign_table == parent, (
                    f"{name}: expected foreign_table={parent!r}, got {rel.foreign_table!r}"
                )
                assert rel.columns == [child_col], (
                    f"{name}: expected columns=[{child_col!r}], got {rel.columns!r}"
                )
                assert rel.foreign_columns == [parent_col], (
                    f"{name}: expected foreign_columns=[{parent_col!r}], "
                    f"got {rel.foreign_columns!r}"
                )
        finally:
            adapter.disconnect()

    def test_attributes_populated_by_dao_source(self, accdb_path: str):
        """DAO source populates `attributes` (not empty)."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter()
        try:
            connected = adapter.connect(accdb_path)
            assert connected

            rels = adapter.get_relationships()
            assert len(rels) == 4

            # attributes is a stringified DAO bitmask — must be non-empty
            for r in rels:
                assert r.attributes != "", (
                    f"FK {r.name!r} has empty attributes — DAO source should "
                    "populate it; got ODBC fallback instead"
                )
                # All known FKs in this DB have Attributes=4352 (cascade update/delete)
                assert r.attributes == "4352", (
                    f"FK {r.name!r}: expected attributes='4352', got {r.attributes!r}"
                )
        finally:
            adapter.disconnect()

    def test_concurrent_odbc_read_succeeds_after_dao(self, accdb_path: str):
        """After DAO has read relationships, a separate ODBC read still works.

        Proves the DAO ``OpenDatabase(..., Exclusive=False, ReadOnly=True)``
        does NOT lock the file. If it did, this SELECT would fail with
        a file-lock error from the Access ODBC driver.
        """
        import pyodbc

        from ms_access_mcp.adapters.dao import DaoAdapter
        from ms_access_mcp.logging import get_logger

        # 1) DaoAdapter.read_relationships_short_lived extracts FKs
        #    (slice 7 of dao-first-linked-tables-properties: the
        #    standalone DaoRelationshipReader class is gone; the
        #    same contract lives on DaoAdapter as a static method.)
        dao_rels = DaoAdapter.read_relationships_short_lived(
            accdb_path, "", get_logger(__name__)
        )
        assert len(dao_rels) == 4, f"Expected 4 DAO FKs, got {len(dao_rels)}"

        # 2) A separate pyodbc connection reads the same file
        conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={accdb_path};"
        conn = None
        try:
            conn = pyodbc.connect(conn_str, autocommit=True)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            row = cursor.fetchone()
            assert row is not None, "Expected a COUNT(*) result from orders"
            assert row[0] >= 0, f"Expected non-negative count, got {row[0]!r}"
            cursor.close()
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
