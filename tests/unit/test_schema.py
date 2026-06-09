"""Tests for mcp/schema.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock
# Import server first to resolve circular dependency
from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import schema as schema_module


class TestSchemaConnectionGuards:
    """Tests for tools that guard connection state."""

    @pytest.mark.parametrize("tool_func,args", [
        (schema_module.generate_sql, ("/tmp/out.sql",)),
        (schema_module.get_indexes, ("Customers",)),
    ])
    def test_schema_tools_return_error_when_not_connected(self, tool_func, args):
        """Schema tools should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestGetTables:
    """Tests for get_tables tool."""

    def _patch_connected_adapter(self, mock_adapter=None):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter or MagicMock()
        return patch.object(schema_module, '_pool', return_value=mock_conn)

    def test_get_tables_returns_table_list(self):
        """get_tables should return list of table dumps."""
        mock_table = MagicMock()
        mock_table.model_dump.return_value = {"name": "Customers", "fields": [], "record_count": 10}
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = [mock_table]
        with self._patch_connected_adapter(mock_adapter):
            result = schema_module.get_tables()
            assert result["success"] is True
            assert result["count"] == 1
            assert result["tables"][0]["name"] == "Customers"

    def test_get_tables_returns_empty_when_no_tables(self):
        """get_tables should return empty list when no tables found."""
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = []
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_tables()
            assert result["success"] is True
            assert result["count"] == 0


class TestGetTableSchema:
    """Tests for get_table_schema tool."""

    def test_get_table_schema_returns_table_when_found(self):
        """get_table_schema should return table dump when found."""
        mock_table = MagicMock()
        mock_table.name = "Customers"
        mock_table.model_dump.return_value = {"name": "Customers", "fields": []}
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = [mock_table]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_table_schema("Customers")
            assert result["success"] is True
            assert result["table"]["name"] == "Customers"

    def test_get_table_schema_returns_not_found_error(self):
        """get_table_schema should return error when table not found."""
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = []
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_table_schema("NonExistent")
            assert result["success"] is False
            assert "not found" in result["error"].lower()


class TestGetIndexes:
    """Tests for get_indexes tool."""

    def test_get_indexes_delegates_to_adapter(self):
        """get_indexes should delegate to adapter.get_indexes."""
        mock_idx = MagicMock()
        mock_idx.model_dump.return_value = {
            "name": "IX_Customers_Name",
            "columns": ["LastName", "FirstName"],
            "is_unique": False,
            "is_primary": False,
            "ignore_nulls": False,
        }
        mock_adapter = MagicMock()
        mock_adapter.get_indexes.return_value = [mock_idx]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_indexes("Customers")
            assert result["success"] is True
            assert result["count"] == 1
            assert result["indexes"][0]["name"] == "IX_Customers_Name"
            mock_adapter.get_indexes.assert_called_once_with("Customers")

    def test_get_indexes_returns_empty_list_when_no_indexes(self):
        """get_indexes should return empty list when no indexes found."""
        mock_adapter = MagicMock()
        mock_adapter.get_indexes.return_value = []
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_indexes("EmptyTable")
            assert result["success"] is True
            assert result["count"] == 0
            assert result["indexes"] == []

    def test_get_indexes_returns_no_adapter_error(self):
        """get_indexes should return error when no adapter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = None
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_indexes("Customers")
            assert result["success"] is False
            assert "No adapter" in result["error"]

    def test_get_indexes_returns_multiple_indexes(self):
        """get_indexes should return multiple index dumps."""
        mock_idx1 = MagicMock()
        mock_idx1.model_dump.return_value = {
            "name": "PK_Customers",
            "columns": ["ID"],
            "is_unique": True,
            "is_primary": True,
            "ignore_nulls": False,
        }
        mock_idx2 = MagicMock()
        mock_idx2.model_dump.return_value = {
            "name": "IX_Customers_Name",
            "columns": ["LastName", "FirstName"],
            "is_unique": False,
            "is_primary": False,
            "ignore_nulls": False,
        }
        mock_adapter = MagicMock()
        mock_adapter.get_indexes.return_value = [mock_idx1, mock_idx2]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_indexes("Customers")
            assert result["success"] is True
            assert result["count"] == 2
            assert result["indexes"][0]["is_primary"] is True
            assert result["indexes"][1]["name"] == "IX_Customers_Name"


class TestGetRelationships:
    """Tests for get_relationships tool."""

    def test_get_relationships_returns_relationship_list(self):
        """get_relationships should return list of relationship dumps."""
        mock_rel = MagicMock()
        mock_rel.model_dump.return_value = {"name": "FK_Orders_Customers", "table": "Orders"}
        mock_adapter = MagicMock()
        mock_adapter.get_relationships.return_value = [mock_rel]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_relationships()
            assert result["success"] is True
            assert result["count"] == 1
            assert result["relationships"][0]["name"] == "FK_Orders_Customers"


class TestGenerateSql:
    """Tests for generate_sql tool."""

    def test_generate_sql_delegates_to_adapter(self):
        """generate_sql should delegate to adapter.generate_sql."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.generate_sql.return_value = {"success": True, "file_path": "/tmp/out.sql"}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.generate_sql("/tmp/out.sql")
            assert result["success"] is True
            mock_conn.adapter.generate_sql.assert_called_once_with("/tmp/out.sql")

    def test_generate_sql_returns_no_adapter_error(self):
        """generate_sql should return error when no adapter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = None
        mock_conn.get_adapter.return_value = None
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.generate_sql("/tmp/out.sql")
            assert result["success"] is False
            assert "No adapter" in result["error"]


class TestGetErDiagram:
    """Tests for get_er_diagram tool."""

    def test_get_er_diagram_builds_nodes_and_edges(self):
        """get_er_diagram should return nodes and edges from schema."""
        mock_table = MagicMock()
        mock_table.name = "Customers"
        mock_table.fields = []
        mock_table.record_count = 5
        mock_rel = MagicMock()
        mock_rel.name = "FK_Orders_Customers"
        mock_rel.foreign_table = "Customers"
        mock_rel.table = "Orders"
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = [mock_table]
        mock_adapter.get_relationships.return_value = [mock_rel]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(schema_module, '_pool', return_value=mock_conn):
            result = schema_module.get_er_diagram()
            assert result["success"] is True
            assert result["node_count"] == 1
            assert result["edge_count"] == 1
            assert result["nodes"][0]["id"] == "Customers"
            assert result["edges"][0]["source"] == "Customers"
