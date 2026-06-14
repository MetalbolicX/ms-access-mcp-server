"""
Integration test for OdbcAdapter.get_relationships() against a real .accdb.

Creates a temporary database with tables + a foreign-key relationship via
COM automation, then reads the relationships back via ODBC's MSysRelationships
query to verify the new OdbcSchemaReader path works end-to-end.

Note: the dedicated DAO integration test
``tests/integration/test_dao_relationship_reader_real.py`` covers the real
FK extraction against the project's ``db/postgres.accdb`` (the 4 known FKs
with their `attributes` populated, and the concurrent-ODBC-after-DAO
invariant).  This test stays focused on the OdbcSchemaReader fallback
path — it creates a temp .accdb with a single FK and asserts the
ODBC ``MSysRelationships`` query returns it.

Markers: com_integration

Execution:
    pytest tests/integration/test_odbc_relationships_real.py -m com_integration -v
"""

from __future__ import annotations

import os
import tempfile

import pytest
from helpers import skip_unless_pywin32, skip_unless_windows

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
]


@pytest.fixture(scope="module")
def accdb_with_relationship():
    """Create a temporary .accdb with one FK, clean up after."""
    if os.name != "nt":
        pytest.skip("Windows required to create .accdb via COM")
    try:
        import win32com.client
    except ImportError:
        pytest.skip("pywin32 required to create .accdb via COM")

    fd, db_path = tempfile.mkstemp(suffix=".accdb")
    os.close(fd)

    access = win32com.client.Dispatch("Access.Application")
    try:
        access.Visible = False
        access.NewCurrentDatabase(db_path)
        dao = access.CurrentDb()

        # --- TableA: parent ---
        tbl_a = dao.CreateTableDef("TableA")
        tbl_a.Fields.Append(tbl_a.CreateField("ID", 4))  # dbLong
        dao.TableDefs.Append(tbl_a)

        # --- TableB: child with FK to TableA ---
        tbl_b = dao.CreateTableDef("TableB")
        tbl_b.Fields.Append(tbl_b.CreateField("ID", 4))  # dbLong
        tbl_b.Fields.Append(tbl_b.CreateField("AID", 4))  # FK to TableA.ID
        dao.TableDefs.Append(tbl_b)

        # Refresh so Relation creation sees the table defs
        dao.TableDefs.Refresh()

        # --- Create the relationship ---
        rel = dao.CreateRelation("FK_TableB_TableA")
        rel.Table = "TableB"
        rel.ForeignTable = "TableA"
        field = rel.CreateField("AID")
        field.ForeignName = "ID"
        rel.Fields.Append(field)
        dao.Relations.Append(rel)

        dao.Close()
    finally:
        access.Quit()

    yield db_path

    if os.path.exists(db_path):
        os.unlink(db_path)


def test_odbc_get_relationships_returns_fk(accdb_with_relationship):
    """ODBC can read the FK defined via COM in a real .accdb."""
    from ms_access_mcp.adapters.odbc import OdbcAdapter

    adapter = OdbcAdapter()
    try:
        connected = adapter.connect(accdb_with_relationship)
        assert connected, "OdbcAdapter should connect to the temp .accdb"

        rels = adapter.get_relationships()
        assert isinstance(rels, list), "get_relationships must return a list"

        # We expect at least one relationship (FK_TableB_TableA)
        assert len(rels) >= 1, (
            f"Expected at least 1 relationship, got {len(rels)}. "
            "The ODBC MSysRelationships query may not be returning results. "
            "Check that MSysRelationships is accessible via the ODBC driver."
        )

        # Verify the FK details
        names = {r.name for r in rels}
        assert "FK_TableB_TableA" in names, (
            f"Expected FK_TableB_TableA in {names}. "
            f"All relationships: {[(r.name, r.table, r.foreign_table) for r in rels]}"
        )

        # Find the actual relationship object
        fk = next(r for r in rels if r.name == "FK_TableB_TableA")
        assert fk.table == "TableB", f"Expected table=TableB, got {fk.table}"
        assert fk.foreign_table == "TableA", (
            f"Expected foreign_table=TableA, got {fk.foreign_table}"
        )
        assert fk.columns == ["AID"], f"Expected columns=['AID'], got {fk.columns}"
        assert fk.foreign_columns == ["ID"], (
            f"Expected foreign_columns=['ID'], got {fk.foreign_columns}"
        )

        # Attributes are empty via ODBC (DAO Attributes not exposed)
        assert fk.attributes == "", f"Expected attributes='', got {fk.attributes!r}"

    finally:
        adapter.disconnect()
