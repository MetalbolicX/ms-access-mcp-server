"""SchemaInspector unit tests — index inspection (PR 1 Task 2.1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ms_access_mcp.adapters.schema_inspector import SchemaInspector
from ms_access_mcp.models.database import IndexInfo


# =============================================================================
# Mock DAO objects for index testing
# =============================================================================


class MockDaoField:
    """Mock DAO Field object."""
    def __init__(self, name: str):
        self.Name = name


class MockDaoFields:
    """Mock DAO Fields collection."""
    def __init__(self, fields: list[MockDaoField]):
        self._fields = fields

    def __iter__(self):
        return iter(self._fields)


class MockDaoIndex:
    """Mock DAO Index object."""
    def __init__(self, name: str, field_names: list[str], primary: bool = False,
                 unique: bool = False, ignore_nulls: bool = False):
        self.Name = name
        self._fields = MockDaoFields([MockDaoField(fn) for fn in field_names])
        self.Primary = primary
        self.Unique = unique
        self.IgnoreNulls = ignore_nulls

    @property
    def Fields(self):
        return self._fields


class MockDaoIndexes:
    """Mock DAO Indexes collection with Count and __call__ support."""
    def __init__(self, indexes: list[MockDaoIndex] | None = None):
        self._indexes = list(indexes or [])

    def __call__(self, key: int | str):
        """Support indexes(index) lookup."""
        if isinstance(key, int):
            return self._indexes[key]
        raise TypeError(f"MockDaoIndexes does not support string key: {key}")

    def __iter__(self):
        return iter(self._indexes)

    @property
    def Count(self) -> int:
        return len(self._indexes)


class MockDaoTableDef:
    """Mock DAO TableDef with index support."""
    def __init__(self, name: str, indexes: list[MockDaoIndex] | None = None):
        self.Name = name
        self._indexes = MockDaoIndexes(indexes or [])

    @property
    def Indexes(self) -> MockDaoIndexes:
        return self._indexes


class MockDaoTableDefs:
    """Mock DAO TableDefs collection — callable for name lookup."""
    def __init__(self, table_defs: dict[str, MockDaoTableDef] | None = None):
        self._tables = table_defs or {}

    def __call__(self, key: int | str) -> MockDaoTableDef:
        """Support TableDefs(table_name) and TableDefs(index) lookup."""
        if isinstance(key, str):
            return self._tables[key]
        elif isinstance(key, int):
            names = list(self._tables.keys())
            return self._tables[names[key]]
        raise TypeError(f"Invalid key type: {type(key)}")

    def __iter__(self):
        return iter(self._tables.values())

    @property
    def Count(self) -> int:
        return len(self._tables)


class MockDaoDatabase:
    """Mock DAO Database — provides TableDefs as a callable collection."""
    def __init__(self, table_defs: dict[str, MockDaoTableDef] | None = None):
        self._table_defs = MockDaoTableDefs(table_defs)

    @property
    def TableDefs(self) -> MockDaoTableDefs:
        return self._table_defs


# =============================================================================
# Test cases
# =============================================================================


class TestSchemaInspectorGetIndexes:
    """Test SchemaInspector.get_indexes() — returns ALL indexes (PR 1 Task 2.1)."""

    def _make_inspector(self, table_defs: dict[str, MockDaoTableDef] | None = None) -> SchemaInspector:
        """Create a SchemaInspector with a mock dispatcher that returns table_defs."""
        mock_dispatcher = MagicMock()
        mock_db = MockDaoDatabase(table_defs)
        mock_dispatcher.is_connected.return_value = True
        mock_dispatcher.call.side_effect = lambda fn: fn()
        mock_dispatcher.current_db = mock_db
        return SchemaInspector(mock_dispatcher)

    # ------------------------------------------------------------------ #
    # Not-connected behavior
    # ------------------------------------------------------------------ #

    def test_get_indexes_not_connected_returns_empty(self):
        """get_indexes must return [] when dispatcher is not connected."""
        mock_dispatcher = MagicMock()
        mock_dispatcher.is_connected.return_value = False
        inspector = SchemaInspector(mock_dispatcher)
        result = inspector.get_indexes("any_table")
        assert result == []

    # ------------------------------------------------------------------ #
    # Single primary index
    # ------------------------------------------------------------------ #

    def test_get_indexes_returns_primary_index(self):
        """get_indexes must return IndexInfo for a primary index."""
        pk_index = MockDaoIndex(
            name="PK_Customers",
            field_names=["CustomerID"],
            primary=True,
            unique=True,
        )
        tdef = MockDaoTableDef("Customers", indexes=[pk_index])
        inspector = self._make_inspector({"Customers": tdef})

        result = inspector.get_indexes("Customers")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].name == "PK_Customers"
        assert result[0].columns == ["CustomerID"]
        assert result[0].is_primary is True
        assert result[0].is_unique is True

    # ------------------------------------------------------------------ #
    # Primary + secondary indexes (the key requirement)
    # ------------------------------------------------------------------ #

    def test_get_indexes_returns_both_primary_and_secondary(self):
        """get_indexes must return ALL indexes — not just primary ones.

        This is the core behavioral change from _get_table_indexes (which
        filtered on Primary=True). get_indexes returns every index on the table.
        """
        pk_index = MockDaoIndex(
            name="PK_Orders",
            field_names=["OrderID"],
            primary=True,
            unique=True,
        )
        ix_date = MockDaoIndex(
            name="IX_OrderDate",
            field_names=["OrderDate"],
            primary=False,
            unique=False,
        )
        ix_cust = MockDaoIndex(
            name="IX_CustomerID",
            field_names=["CustomerID"],
            primary=False,
            unique=False,
        )
        tdef = MockDaoTableDef("Orders", indexes=[pk_index, ix_date, ix_cust])
        inspector = self._make_inspector({"Orders": tdef})

        result = inspector.get_indexes("Orders")
        assert len(result) == 3

        names = {idx.name for idx in result}
        assert "PK_Orders" in names
        assert "IX_OrderDate" in names
        assert "IX_CustomerID" in names

        pk = next(idx for idx in result if idx.name == "PK_Orders")
        assert pk.is_primary is True
        assert pk.is_unique is True

        sec = next(idx for idx in result if idx.name == "IX_OrderDate")
        assert sec.is_primary is False
        assert sec.is_unique is False

    # ------------------------------------------------------------------ #
    # Composite (multi-column) index
    # ------------------------------------------------------------------ #

    def test_get_indexes_composite_index(self):
        """get_indexes must return all column names for a composite index."""
        ix_composite = MockDaoIndex(
            name="IX_OrderItems",
            field_names=["OrderID", "ItemID"],
            primary=False,
            unique=True,
        )
        tdef = MockDaoTableDef("OrderItems", indexes=[ix_composite])
        inspector = self._make_inspector({"OrderItems": tdef})

        result = inspector.get_indexes("OrderItems")
        assert len(result) == 1
        idx = result[0]
        assert idx.name == "IX_OrderItems"
        assert "OrderID" in idx.columns
        assert "ItemID" in idx.columns
        assert len(idx.columns) == 2

    # ------------------------------------------------------------------ #
    # IgnoreNulls flag
    # ------------------------------------------------------------------ #

    def test_get_indexes_ignore_nulls_true(self):
        """get_indexes must set ignore_nulls=True when DAO Index.IgnoreNulls is True."""
        ix_ignore = MockDaoIndex(
            name="IX_Name",
            field_names=["LastName"],
            primary=False,
            unique=False,
            ignore_nulls=True,
        )
        tdef = MockDaoTableDef("Contacts", indexes=[ix_ignore])
        inspector = self._make_inspector({"Contacts": tdef})

        result = inspector.get_indexes("Contacts")
        assert len(result) == 1
        assert result[0].ignore_nulls is True

    # ------------------------------------------------------------------ #
    # Empty result — no indexes
    # ------------------------------------------------------------------ #

    def test_get_indexes_no_indexes_returns_empty(self):
        """get_indexes must return [] when the table has no indexes."""
        tdef = MockDaoTableDef("EmptyTable", indexes=[])
        inspector = self._make_inspector({"EmptyTable": tdef})

        result = inspector.get_indexes("EmptyTable")
        assert result == []
        assert isinstance(result, list)

    # ------------------------------------------------------------------ #
    # Non-existent table
    # ------------------------------------------------------------------ #

    def test_get_indexes_nonexistent_table_returns_empty(self):
        """get_indexes must return [] when the table does not exist."""
        inspector = self._make_inspector({})
        result = inspector.get_indexes("NonExistent")
        assert result == []

    # ------------------------------------------------------------------ #
    # Unique non-primary index
    # ------------------------------------------------------------------ #

    def test_get_indexes_unique_non_primary(self):
        """get_indexes must set is_unique=True for a unique non-primary index."""
        ix_unique = MockDaoIndex(
            name="UQ_Email",
            field_names=["Email"],
            primary=False,
            unique=True,
        )
        tdef = MockDaoTableDef("Users", indexes=[ix_unique])
        inspector = self._make_inspector({"Users": tdef})

        result = inspector.get_indexes("Users")
        assert len(result) == 1
        idx = result[0]
        assert idx.is_unique is True
        assert idx.is_primary is False

    # ------------------------------------------------------------------ #
    # Multiple secondary indexes (no primary key)
    # ------------------------------------------------------------------ #

    def test_get_indexes_secondary_only_no_primary(self):
        """get_indexes must return secondary indexes even when there is no primary."""
        ix1 = MockDaoIndex(name="IX_ColA", field_names=["ColA"], primary=False, unique=False)
        ix2 = MockDaoIndex(name="IX_ColB", field_names=["ColB"], primary=False, unique=False)
        tdef = MockDaoTableDef("NoPK", indexes=[ix1, ix2])
        inspector = self._make_inspector({"NoPK": tdef})

        result = inspector.get_indexes("NoPK")
        assert len(result) == 2
        names = {idx.name for idx in result}
        assert "IX_ColA" in names
        assert "IX_ColB" in names
        # None should be marked primary
        assert all(not idx.is_primary for idx in result)


class TestSchemaInspectorLoggingMigration:
    """Bare-except logging migration for schema_inspector.py (PR 1 Task 1.4).

    RED: Verify logger.warning is called when COM property access fails in
    top-level collection iteration methods (get_tables, get_queries, get_relationships).
    """

    def test_get_tables_logs_warning_on_collection_failure(self):
        """get_tables() must call logger.warning when the TableDefs collection access fails."""
        mock_dispatcher = MagicMock()
        mock_dispatcher.is_connected.return_value = True

        # Simulate a failure when accessing TableDefs
        mock_db = MagicMock()
        mock_db.TableDefs.side_effect = RuntimeError("DAO TableDefs unavailable")
        mock_dispatcher.current_db = mock_db
        mock_dispatcher.call.side_effect = lambda fn: fn()

        with patch("ms_access_mcp.adapters.schema_inspector.logger") as mock_logger:
            from ms_access_mcp.adapters.schema_inspector import SchemaInspector
            inspector = SchemaInspector(mock_dispatcher)
            result = inspector.get_tables()

            # Should return empty and log warning
            assert result == []
            mock_logger.warning.assert_called()
            # Verify the warning mentions the method name
            warning_args = mock_logger.warning.call_args[0]
            assert "get_tables" in warning_args[0]

    def test_get_queries_logs_warning_on_collection_failure(self):
        """get_queries() must call logger.warning when the QueryDefs collection access fails."""
        mock_dispatcher = MagicMock()
        mock_dispatcher.is_connected.return_value = True

        mock_db = MagicMock()
        mock_db.QueryDefs.side_effect = RuntimeError("DAO QueryDefs unavailable")
        mock_dispatcher.current_db = mock_db
        mock_dispatcher.call.side_effect = lambda fn: fn()

        with patch("ms_access_mcp.adapters.schema_inspector.logger") as mock_logger:
            from ms_access_mcp.adapters.schema_inspector import SchemaInspector
            inspector = SchemaInspector(mock_dispatcher)
            result = inspector.get_queries()

            assert result == []
            mock_logger.warning.assert_called()
            warning_args = mock_logger.warning.call_args[0]
            assert "get_queries" in warning_args[0]

    def test_get_relationships_logs_warning_on_collection_failure(self):
        """get_relationships() must call logger.warning when the Relations collection access fails."""
        mock_dispatcher = MagicMock()
        mock_dispatcher.is_connected.return_value = True

        mock_db = MagicMock()
        mock_db.Relations.side_effect = RuntimeError("DAO Relations unavailable")
        mock_dispatcher.current_db = mock_db
        mock_dispatcher.call.side_effect = lambda fn: fn()

        with patch("ms_access_mcp.adapters.schema_inspector.logger") as mock_logger:
            from ms_access_mcp.adapters.schema_inspector import SchemaInspector
            inspector = SchemaInspector(mock_dispatcher)
            result = inspector.get_relationships()

            assert result == []
            mock_logger.warning.assert_called()
            warning_args = mock_logger.warning.call_args[0]
            assert "get_relationships" in warning_args[0]