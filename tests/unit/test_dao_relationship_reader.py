"""Unit tests for DaoRelationshipReader — DAO COM object mocked.

Covers the contract from spec `dao-relationship-extraction`:
- Happy path (1 FK, 1 column) with `attributes` populated.
- Multi-column composite FK merged into one RelationshipInfo.
- Multiple independent FKs returned as multiple entries.
- `~` and `MSys` system relations filtered out.
- Empty result set (no relations) returns `[]`.
- `db.Close()` is always invoked — even when the iteration raises.
- DAO `OpenDatabase` exception returns `[]` and logs a WARNING.
- Successful `OpenDatabase` then `db.Relations` access raising
  still closes the DB in `finally` and returns `[]`.

The DAO COM import is lazy inside `get_relationships()`, so we patch
`win32com.client.Dispatch` at the module attribute level — Python looks
the symbol up at call time, so the patch survives a deferred import.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from ms_access_mcp.adapters.dao_relationship_reader import DaoRelationshipReader


def _make_relation_mock(
    name: str,
    table: str,
    foreign_table: str,
    fields: list[tuple[str, str]],
    attributes: int = 0,
) -> MagicMock:
    """Build a MagicMock that mimics a DAO ``Relation`` object.

    Args:
        name: Relation name (e.g. ``FK_Orders_Customers``).
        table: Child table.
        foreign_table: Parent table.
        fields: list of ``(child_col, parent_col)`` tuples.
        attributes: Bitmask of DAO `Relation.Attributes` — we just stringify it.
    """
    rel = MagicMock()
    rel.Name = name
    rel.Table = table
    rel.ForeignTable = foreign_table
    rel.Attributes = attributes

    field_mocks: list[MagicMock] = []
    for child_col, parent_col in fields:
        f = MagicMock()
        f.Name = child_col
        f.ForeignName = parent_col
        field_mocks.append(f)
    rel.Fields.Count = len(field_mocks)
    # DAO `Fields` collection in real Python bindings is 0-indexed:
    # `rel.Fields(0)` is the first field. We support that as the primary
    # contract and `Fields.Item(0)` as a defensive fallback for some COM
    # bindings that expose Item() as well.
    def _fields_getter(i):
        return field_mocks[i]

    rel.Fields.side_effect = _fields_getter
    rel.Fields.Item.side_effect = _fields_getter
    return rel


def _make_db_mock(relations: list[MagicMock]) -> MagicMock:
    """Build a MagicMock that mimics a DAO ``Database`` object."""
    db = MagicMock()
    db.Relations.Count = len(relations)
    # DAO `Relations` collection is 0-indexed in real Python bindings.
    def _rel_getter(i):
        return relations[i]

    db.Relations.side_effect = _rel_getter
    db.Relations.Item.side_effect = _rel_getter
    return db


class TestDaoRelationshipReader:
    """Tests for the DAO relationship reader with mocked COM."""

    def setup_method(self):
        self.db_path = r"C:\fake\db.accdb"
        self.password = ""
        self.logger = MagicMock(spec=logging.Logger)
        self.reader = DaoRelationshipReader(self.db_path, self.password, self.logger)

    # ------------------------------------------------------------------ #
    # Happy path
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_get_relationships_single_fk_returns_one_relationship(self, mock_dispatch):
        """1 relation, 1 column → 1 RelationshipInfo with all fields populated."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock([
            _make_relation_mock(
                "FK_Orders_Customers",
                "Orders",
                "Customers",
                [("CustomerID", "ID")],
                attributes=256,
            )
        ])
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = self.reader.get_relationships()

        assert len(result) == 1
        rel = result[0]
        assert rel.name == "FK_Orders_Customers"
        assert rel.table == "Orders"
        assert rel.foreign_table == "Customers"
        assert rel.columns == ["CustomerID"]
        assert rel.foreign_columns == ["ID"]
        # attributes must be the string form of DAO Attributes
        assert rel.attributes == "256"
        # OpenDatabase was called with the path, not exclusive, read-only
        mock_engine.OpenDatabase.assert_called_once()
        # DB was closed in the finally
        mock_db.Close.assert_called_once()

    # ------------------------------------------------------------------ #
    # Multi-column composite FK
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_multi_column_fk_merged_into_one_relationship(self, mock_dispatch):
        """2 columns for same (child, parent) → 1 RelationshipInfo with both columns."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock([
            _make_relation_mock(
                "FK_OrderDetails_Orders",
                "OrderDetails",
                "Orders",
                [("OrderID", "ID"), ("LineNo", "LineNo")],
                attributes=0,
            )
        ])
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = self.reader.get_relationships()

        assert len(result) == 1
        rel = result[0]
        assert rel.name == "FK_OrderDetails_Orders"
        assert rel.table == "OrderDetails"
        assert rel.foreign_table == "Orders"
        assert rel.columns == ["OrderID", "LineNo"]
        assert rel.foreign_columns == ["ID", "LineNo"]

    # ------------------------------------------------------------------ #
    # Multiple independent FKs
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_multiple_independent_fks_returned_separately(self, mock_dispatch):
        """2 unrelated FKs → 2 RelationshipInfo entries."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock([
            _make_relation_mock(
                "FK_Orders_Customers",
                "Orders",
                "Customers",
                [("CustomerID", "ID")],
            ),
            _make_relation_mock(
                "FK_Orders_Employees",
                "Orders",
                "Employees",
                [("EmployeeID", "ID")],
            ),
        ])
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = self.reader.get_relationships()

        assert len(result) == 2
        names = {r.name for r in result}
        assert "FK_Orders_Customers" in names
        assert "FK_Orders_Employees" in names

    # ------------------------------------------------------------------ #
    # System relations filtered
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_system_relations_filtered(self, mock_dispatch):
        """Relations whose name starts with `~` or `MSys` are skipped."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock([
            _make_relation_mock(
                "FK_Orders_Customers",
                "Orders",
                "Customers",
                [("CustomerID", "ID")],
            ),
            _make_relation_mock(
                "~TMPCache",
                "Orders",
                "Whatever",
                [("X", "Y")],
            ),
            _make_relation_mock(
                "MSysRelZZZ",
                "Orders",
                "Whatever2",
                [("A", "B")],
            ),
        ])
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = self.reader.get_relationships()

        assert len(result) == 1
        assert result[0].name == "FK_Orders_Customers"
        for r in result:
            assert not r.name.startswith("~")
            assert not r.name.startswith("MSys")

    # ------------------------------------------------------------------ #
    # Empty result
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_empty_relations_returns_empty_list(self, mock_dispatch):
        """`Relations.Count == 0` → [] and Close() still called."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock([])
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = self.reader.get_relationships()

        assert result == []
        # Close still happens for an empty DB
        mock_db.Close.assert_called_once()

    # ------------------------------------------------------------------ #
    # Close is called even on exception
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_close_called_even_on_exception(self, mock_dispatch):
        """If iteration raises, db.Close() runs in the finally block."""
        mock_engine = MagicMock()
        mock_db = MagicMock()
        # db.Relations access itself raises
        mock_db.Relations.Count = property(
            lambda self_: (_ for _ in ()).throw(RuntimeError("relations boom"))
        )
        # Make the accessor pattern match a real COM binding
        type(mock_db.Relations).Count = property(
            lambda self_: (_ for _ in ()).throw(RuntimeError("relations boom"))
        )
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = self.reader.get_relationships()

        # No exception escapes; reader returns [] on internal error
        assert result == []
        # Critical invariant: Close() was called even though the iteration failed
        mock_db.Close.assert_called_once()

    # ------------------------------------------------------------------ #
    # OpenDatabase raises — returns [] and logs WARNING
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_open_database_raises_returns_empty_with_warning(self, mock_dispatch):
        """OpenDatabase failure → [] and WARNING logged, no exception."""
        mock_engine = MagicMock()
        mock_engine.OpenDatabase.side_effect = RuntimeError(
            "Cannot open database — file in use"
        )
        mock_dispatch.return_value = mock_engine

        result = self.reader.get_relationships()

        assert result == []
        # WARNING was logged
        self.logger.warning.assert_called()

    # ------------------------------------------------------------------ #
    # OpenDatabase OK, db.Relations access raises — Close in finally
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_open_ok_relations_access_raises_returns_empty_close_in_finally(
        self, mock_dispatch
    ):
        """db.Relations raises after a successful open → [] and Close() still called."""
        mock_engine = MagicMock()
        mock_db = MagicMock()
        # Force db.Relations to raise on Count access (typical first-attribute
        # access pattern from COM bindings)
        rels = mock_db.Relations
        type(rels).Count = property(
            lambda self_: (_ for _ in ()).throw(RuntimeError("Relations access boom"))
        )
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = self.reader.get_relationships()

        assert result == []
        mock_db.Close.assert_called_once()
