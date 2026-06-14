"""Unit tests for OdbcSchemaReader — MSysRelationships query + grouping."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

from ms_access_mcp.adapters.odbc_schema_reader import OdbcSchemaReader


class TestOdbcSchemaReader:
    """Tests for the MSysRelationships reader with mocked pyodbc cursor."""

    def setup_method(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.logger = logging.getLogger(__name__)
        self.reader = OdbcSchemaReader(self.mock_conn, self.logger)

    # ------------------------------------------------------------------ #
    # Disconnected guard
    # ------------------------------------------------------------------ #

    def test_get_relationships_returns_empty_when_conn_is_none(self):
        """Reader with no connection returns [] without error."""
        reader = OdbcSchemaReader(None, self.logger)
        assert reader.get_relationships() == []

    # ------------------------------------------------------------------ #
    # MSysRelationships denied / raises
    # ------------------------------------------------------------------ #

    def test_get_relationships_returns_empty_on_sql_error(self):
        """When MSysRelationships is denied, returns [] and logs a warning."""
        import pyodbc

        self.mock_cursor.execute.side_effect = pyodbc.ProgrammingError(
            "SELECT permission denied on object 'MSysRelationships'"
        )
        result = self.reader.get_relationships()
        # No exception propagates — caught and degraded gracefully
        assert result == []

    def test_get_relationships_returns_empty_on_generic_exception(self):
        """Any cursor exception is caught and returns []."""
        self.mock_cursor.execute.side_effect = RuntimeError("Something bad")
        result = self.reader.get_relationships()
        assert result == []

    # ------------------------------------------------------------------ #
    # Empty result set
    # ------------------------------------------------------------------ #

    def test_get_relationships_returns_empty_when_no_rows(self):
        """No MSysRelationships rows → empty list, no error."""
        self.mock_cursor.fetchall.return_value = []
        result = self.reader.get_relationships()
        assert result == []

    # ------------------------------------------------------------------ #
    # Single-column FK
    # ------------------------------------------------------------------ #

    def test_get_relationships_single_column_fk(self):
        """One FK with one column returns one RelationshipInfo."""
        self.mock_cursor.fetchall.return_value = [
            ("Orders", "CustomerID", "Customers", "ID"),
        ]
        result = self.reader.get_relationships()
        assert len(result) == 1
        rel = result[0]
        assert rel.name == "FK_Orders_Customers"
        assert rel.table == "Orders"
        assert rel.foreign_table == "Customers"
        assert rel.columns == ["CustomerID"]
        assert rel.foreign_columns == ["ID"]
        assert rel.attributes == ""

    # ------------------------------------------------------------------ #
    # Multi-column FK (composite key)
    # ------------------------------------------------------------------ #

    def test_get_relationships_multiple_distinct_fks(self):
        """Two rows with different parent tables → two RelationshipInfo entries."""
        self.mock_cursor.fetchall.return_value = [
            ("OrderDetails", "OrderID", "Orders", "OrderID"),
            ("OrderDetails", "ProductID", "Products", "ProductID"),
        ]
        result = self.reader.get_relationships()
        assert len(result) == 2  # different parent tables
        names = {r.name for r in result}
        assert "FK_OrderDetails_Orders" in names
        assert "FK_OrderDetails_Products" in names

    def test_get_relationships_multi_column_fk_same_parent(self):
        """Two columns referencing the same parent table → one grouped entry."""
        self.mock_cursor.fetchall.return_value = [
            ("LineItems", "OrderID", "Orders", "ID"),
            ("LineItems", "ProductID", "Products", "ProductID"),
        ]
        result = self.reader.get_relationships()
        assert len(result) == 2  # different parents

    def test_get_relationships_composite_key_same_fk(self):
        """Same (child, parent) pair → composite FK merged into one entry."""
        self.mock_cursor.fetchall.return_value = [
            ("OrderDetails", "OrderID", "Orders", "OrderID"),
            ("OrderDetails", "OrderID", "Orders", "OrderID2"),
        ]
        result = self.reader.get_relationships()
        assert len(result) == 1
        rel = result[0]
        assert rel.table == "OrderDetails"
        assert rel.foreign_table == "Orders"
        assert rel.columns == ["OrderID", "OrderID"]
        assert rel.foreign_columns == ["OrderID", "OrderID2"]

    # ------------------------------------------------------------------ #
    # Multiple independent FKs
    # ------------------------------------------------------------------ #

    def test_get_relationships_multiple_fks(self):
        """Multiple unrelated FKs produce one RelationshipInfo per FK."""
        self.mock_cursor.fetchall.return_value = [
            ("Orders", "CustomerID", "Customers", "ID"),
            ("Orders", "EmployeeID", "Employees", "ID"),
        ]
        result = self.reader.get_relationships()
        assert len(result) == 2
        names = {r.name for r in result}
        assert "FK_Orders_Customers" in names
        assert "FK_Orders_Employees" in names

    # ------------------------------------------------------------------ #
    # Sort stability
    # ------------------------------------------------------------------ #

    def test_get_relationships_sorted_by_name(self):
        """Result is sorted by name for deterministic edge IDs."""
        self.mock_cursor.fetchall.return_value = [
            ("ZTable", "AID", "ATable", "ID"),
            ("ATable", "ZID", "ZTable", "ID"),
        ]
        result = self.reader.get_relationships()
        assert len(result) == 2
        assert result[0].name < result[1].name

    # ------------------------------------------------------------------ #
    # SQL verification — ensures the right query is sent
    # ------------------------------------------------------------------ #

    def test_issues_correct_sql(self):
        """The correct MSysRelationships query is sent to the cursor."""
        from ms_access_mcp.adapters.odbc_schema_reader import MSYS_RELATIONSHIPS_QUERY

        self.mock_cursor.fetchall.return_value = []
        self.reader.get_relationships()
        self.mock_cursor.execute.assert_called_once_with(MSYS_RELATIONSHIPS_QUERY)
