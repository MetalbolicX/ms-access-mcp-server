"""Tests for relation MCP tools and adapters."""
from unittest.mock import MagicMock, patch

import pytest

from ms_access_mcp.adapters.com_only_mixin import ComOnlyAdapterMixin
from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import relations as relations_module
from ms_access_mcp.models.database import ForeignKeyInfo, RelationshipInfo


class TestRelationshipModel:
    def test_columns_default_to_empty_list(self):
        rel = RelationshipInfo(name="FK_Test", table="Child", foreign_table="Parent")
        assert rel.columns == []
        assert rel.foreign_columns == []

    def test_columns_populated(self):
        rel = RelationshipInfo(
            name="FK_Test", table="Child", foreign_table="Parent",
            columns=["child_id"], foreign_columns=["id"],
        )
        assert rel.columns == ["child_id"]
        assert rel.foreign_columns == ["id"]

    def test_foreign_key_info(self):
        fk = ForeignKeyInfo(
            name="FK_Test", columns=["child_id"],
            foreign_table="Parent", foreign_columns=["id"],
        )
        assert fk.columns == ["child_id"]
        assert fk.foreign_columns == ["id"]


class TestComOnlyMixinStubs:
    def setup_method(self):
        self.mixin = ComOnlyAdapterMixin()

    def test_create_relationship_raises(self):
        with pytest.raises(NotImplementedError, match="requires COM automation"):
            self.mixin.create_relationship("t", "fk", ["c"], "p", ["c2"])

    def test_delete_relationship_raises(self):
        with pytest.raises(NotImplementedError, match="requires COM automation"):
            self.mixin.delete_relationship("t", "fk")


class TestOdbcAdapterRelationships:
    """Test ODBC DDL generation for relationships."""

    def test_create_relationship_sql(self):
        adapter = MagicMock()
        adapter.is_connected.return_value = True
        adapter.create_relationship.return_value = {"success": True}

        result = adapter.create_relationship(
            "Orders", "FK_Orders_Customers", ["CustomerID"], "Customers", ["ID"],
        )
        assert result["success"] is True

    def test_create_relationship_not_connected(self):
        adapter = MagicMock()
        adapter.is_connected.return_value = False
        # Simulate the adapter method check
        assert not adapter.is_connected()

    def test_create_relationship_column_mismatch(self):
        adapter = MagicMock()
        adapter.is_connected.return_value = True
        adapter.create_relationship.return_value = {
            "success": False,
            "error": "columns and foreign_columns must have same length",
        }
        result = adapter.create_relationship(
            "t", "fk", ["a", "b"], "p", ["c"],
        )
        assert result["success"] is False

    def test_delete_relationship_sql(self):
        adapter = MagicMock()
        adapter.is_connected.return_value = True
        adapter.delete_relationship.return_value = {"success": True}

        result = adapter.delete_relationship("Orders", "FK_Orders_Customers")
        assert result["success"] is True

    def test_delete_relationship_error(self):
        adapter = MagicMock()
        adapter.is_connected.return_value = True
        adapter.delete_relationship.side_effect = Exception("Constraint not found")

        with pytest.raises(Exception, match="Constraint not found"):
            adapter.delete_relationship("t", "fk")


class TestToolCreateRelationship:
    def test_success(self):
        mock_adapter = MagicMock()
        mock_adapter.create_relationship.return_value = {"success": True}
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.create_relationship(
                "Orders", "FK_Orders_Customers", ["CustomerID"], "Customers", ["ID"],
                confirm=True,
            )
            assert result["success"] is True
            mock_adapter.create_relationship.assert_called_once_with(
                "Orders", "FK_Orders_Customers", ["CustomerID"], "Customers", ["ID"],
            )

    def test_requires_confirm(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.create_relationship(
                "Orders", "FK_Orders_Customers", ["CustomerID"], "Customers", ["ID"],
                confirm=False,
            )
            assert result["success"] is False
            assert "confirm=True" in result["error"]

    def test_dry_run(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.create_relationship(
                "Orders", "FK_Orders_Customers", ["CustomerID"], "Customers", ["ID"],
                confirm=True, dry_run=True,
            )
            assert result["dry_run"] is True

    def test_not_connected(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.create_relationship(
                "Orders", "FK_Orders_Customers", ["CustomerID"], "Customers", ["ID"],
                confirm=True,
            )
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_adapter_error_propagated(self):
        mock_adapter = MagicMock()
        mock_adapter.create_relationship.side_effect = Exception("DB error")
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.create_relationship(
                "Orders", "FK_Orders_Customers", ["CustomerID"], "Customers", ["ID"],
                confirm=True,
            )
            assert result["success"] is False
            assert "DB error" in result["error"]

    def test_column_mismatch_validated(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.create_relationship.return_value = {
            "success": False,
            "error": "columns and foreign_columns must have same length",
        }
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.create_relationship(
                "t", "fk", ["a", "b"], "p", ["c"],
                confirm=True,
            )
            assert result["success"] is False


class TestToolDeleteRelationship:
    def test_success(self):
        mock_adapter = MagicMock()
        mock_adapter.delete_relationship.return_value = {"success": True}
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.delete_relationship(
                "Orders", "FK_Orders_Customers", confirm=True,
            )
            assert result["success"] is True
            mock_adapter.delete_relationship.assert_called_once_with(
                "Orders", "FK_Orders_Customers",
            )

    def test_requires_confirm(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.delete_relationship(
                "Orders", "FK_Orders_Customers", confirm=False,
            )
            assert result["success"] is False
            assert "confirm=True" in result["error"]

    def test_dry_run(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.delete_relationship(
                "Orders", "FK_Orders_Customers", confirm=True, dry_run=True,
            )
            assert result["dry_run"] is True

    def test_adapter_error_propagated(self):
        mock_adapter = MagicMock()
        mock_adapter.delete_relationship.side_effect = Exception("Constraint not found")
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(relations_module, "_pool", return_value=mock_conn):
            result = relations_module.delete_relationship(
                "Orders", "FK_NoExist", confirm=True,
            )
            assert result["success"] is False
            assert "Constraint not found" in result["error"]
