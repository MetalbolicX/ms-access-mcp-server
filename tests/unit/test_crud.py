"""Tests for mcp/crud.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock
# Import server first to resolve circular dependency
from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import crud as crud_module


class TestCrudConnectionGuards:
    """Tests that CRUD tools check connection before executing."""

    @pytest.mark.parametrize("tool_func,args", [
        (crud_module.get_queries, ()),
        (crud_module.create_query, ("q1", "SELECT 1")),
        (crud_module.set_query_sql, ("q1", "SELECT 2")),
        (crud_module.delete_query, ("q1",)),
        (crud_module.create_table, ("T1", [{"name": "ID", "type": "Long Integer"}])),
        (crud_module.delete_table, ("T1",)),
        (crud_module.query_data, ("SELECT 1",)),
        (crud_module.insert_data, ("T1", {"ID": 1})),
        (crud_module.update_data, ("T1", {"Name": "Bob"}, {"ID": 1})),
        (crud_module.delete_data, ("T1", {"ID": 1})),
        (crud_module.create_index, ("T1", "IX_T1_Name", ["Name"])),
        (crud_module.drop_index, ("T1", "IX_T1_Name")),
    ])
    def test_crud_tools_return_error_when_not_connected(self, tool_func, args):
        """Each CRUD tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestQueryCrudTools:
    """Tests for query CRUD tools."""

    def test_get_queries_returns_query_list(self):
        """get_queries should return list of query dumps."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_q = MagicMock()
        mock_q.model_dump.return_value = {"name": "qryActive", "sql": "SELECT 1"}
        mock_conn.adapter.get_queries.return_value = [mock_q]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.get_queries()
            assert result["success"] is True
            assert result["count"] == 1
            assert result["queries"][0]["name"] == "qryActive"

    def test_create_query_delegates_to_adapter(self):
        """create_query should delegate to adapter.create_query."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_query.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.create_query("q1", "SELECT 1")
            assert result["success"] is True
            mock_conn.adapter.create_query.assert_called_once_with("q1", "SELECT 1")

    def test_set_query_sql_delegates_to_adapter(self):
        """set_query_sql should delegate to adapter.set_query_sql."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.set_query_sql.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.set_query_sql("q1", "SELECT 2")
            assert result["success"] is True
            mock_conn.adapter.set_query_sql.assert_called_once_with("q1", "SELECT 2")

    def test_delete_query_delegates_to_adapter(self):
        """delete_query should delegate to adapter.delete_query."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.delete_query.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.delete_query("q1", confirm=True)
            assert result["success"] is True
            mock_conn.adapter.delete_query.assert_called_once_with("q1")


class TestTableCrudTools:
    """Tests for table CRUD tools."""

    def test_create_table_delegates_to_adapter(self):
        """create_table should delegate to adapter.create_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        cols = [{"name": "ID", "type": "Long Integer"}]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.create_table("T1", cols)
            assert result["success"] is True
            mock_conn.adapter.create_table.assert_called_once_with("T1", cols)

    def test_delete_table_delegates_to_adapter(self):
        """delete_table should delegate to adapter.delete_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.delete_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.delete_table("T1", confirm=True)
            assert result["success"] is True
            mock_conn.adapter.delete_table.assert_called_once_with("T1")


class TestIndexCrudTools:
    """Tests for index CRUD tools."""

    def test_create_index_delegates_to_adapter(self):
        """create_index should delegate to adapter.create_index."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_index.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.create_index("T1", "IX_T1_Name", ["Name"])
            assert result["success"] is True
            mock_conn.adapter.create_index.assert_called_once_with(
                "T1", "IX_T1_Name", ["Name"], False, False
            )

    def test_create_index_with_unique_flag(self):
        """create_index with unique=True should pass unique flag to adapter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_index.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.create_index("T1", "IX_T1_Name", ["Name"], unique=True)
            assert result["success"] is True
            mock_conn.adapter.create_index.assert_called_once_with(
                "T1", "IX_T1_Name", ["Name"], True, False
            )

    def test_create_index_with_ignore_null(self):
        """create_index with ignore_null=True should pass flag to adapter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_index.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.create_index("T1", "IX_T1_Name", ["Name"], ignore_null=True)
            assert result["success"] is True
            mock_conn.adapter.create_index.assert_called_once_with(
                "T1", "IX_T1_Name", ["Name"], False, True
            )

    def test_create_index_composite_columns(self):
        """create_index with multiple columns should pass all to adapter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_index.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.create_index("T1", "IX_T1_Name", ["LastName", "FirstName"])
            assert result["success"] is True
            mock_conn.adapter.create_index.assert_called_once_with(
                "T1", "IX_T1_Name", ["LastName", "FirstName"], False, False
            )

    def test_create_index_returns_error_on_exception(self):
        """create_index should return error when adapter raises exception."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_index.side_effect = Exception("DAO error")
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.create_index("T1", "IX_T1_Name", ["Name"])
            assert result["success"] is False
            assert "DAO error" in result["error"]

    def test_drop_index_delegates_to_adapter(self):
        """drop_index should delegate to adapter.drop_index when confirm=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.drop_index.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.drop_index("T1", "IX_T1_Name", confirm=True)
            assert result["success"] is True
            mock_conn.adapter.drop_index.assert_called_once_with("T1", "IX_T1_Name")

    def test_drop_index_rejected_without_confirm(self):
        """drop_index must require confirm=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.drop_index("T1", "IX_T1_Name")
            assert result["success"] is False
            assert "confirm=True" in result["error"]

    def test_drop_index_dry_run_returns_preview(self):
        """drop_index with dry_run=True returns preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.drop_index("T1", "IX_T1_Name", confirm=True, dry_run=True)
            assert result.get("dry_run") is True
            mock_conn.adapter.drop_index.assert_not_called()

    def test_drop_index_returns_error_on_exception(self):
        """drop_index should return error when adapter raises exception."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.drop_index.side_effect = Exception("DAO error")
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.drop_index("T1", "IX_T1_Name", confirm=True)
            assert result["success"] is False
            assert "DAO error" in result["error"]


class TestDataCrudTools:
    """Tests for data CRUD tools."""

    def test_query_data_delegates_to_adapter(self):
        """query_data should delegate to adapter.execute_query."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.execute_query.return_value = {"success": True, "rows": [{"ID": 1}]}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.query_data("SELECT * FROM T1")
            assert result["success"] is True
            mock_conn.adapter.execute_query.assert_called_once_with("SELECT * FROM T1", None)

    def test_insert_data_delegates_to_adapter(self):
        """insert_data should delegate to adapter.insert_data."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.insert_data.return_value = {"success": True, "rows_inserted": 1}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.insert_data("T1", {"ID": 1})
            assert result["success"] is True
            mock_conn.adapter.insert_data.assert_called_once()

    def test_update_data_delegates_to_adapter(self):
        """update_data should delegate to adapter.update_data."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.update_data.return_value = {"success": True, "rows_updated": 1}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.update_data("T1", {"Name": "Bob"}, {"ID": 1})
            assert result["success"] is True
            mock_conn.adapter.update_data.assert_called_once()

    def test_update_data_mass_update_requires_confirm(self):
        """update_data with where_dict=None (mass update) must require confirm=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.update_data("T1", {"Name": "Bob"}, where_dict=None)
            assert result["success"] is False
            assert "confirm=True" in result["error"]
            mock_conn.adapter.update_data.assert_not_called()

    def test_update_data_mass_update_with_confirm_executes(self):
        """update_data with where_dict=None and confirm=True executes mass update."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.update_data.return_value = {"success": True, "rows_updated": 5}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.update_data("T1", {"Name": "Bob"}, where_dict=None, confirm=True)
            assert result["success"] is True
            mock_conn.adapter.update_data.assert_called_once()

    def test_update_data_mass_update_dry_run_returns_preview(self):
        """update_data with where_dict=None and dry_run=True returns preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.update_data("T1", {"Name": "Bob"}, where_dict=None, confirm=True, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "update_data"
            assert result["table_name"] == "T1"
            mock_conn.adapter.update_data.assert_not_called()

    def test_update_data_targeted_update_proceeds_without_confirm(self):
        """update_data with where_dict dict (targeted update) proceeds without confirm."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.update_data.return_value = {"success": True, "rows_updated": 1}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.update_data("T1", {"Name": "Bob"}, where_dict={"ID": 1})
            assert result["success"] is True
            mock_conn.adapter.update_data.assert_called_once()

    def test_delete_data_delegates_to_adapter(self):
        """delete_data should delegate to adapter.delete_data."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.delete_data.return_value = {"success": True, "rows_deleted": 1}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.delete_data("T1", {"ID": 1}, confirm=True)
            assert result["success"] is True
            mock_conn.adapter.delete_data.assert_called_once_with("T1", {"ID": 1})


class TestDestructiveToolGuards:
    """Tests for confirm=True / dry_run=True guards on destructive tools."""

    @pytest.mark.parametrize("tool_func,args", [
        (crud_module.delete_data, ("T1", {"ID": 1})),
        (crud_module.delete_table, ("T1",)),
        (crud_module.delete_query, ("q1",)),
        (crud_module.drop_index, ("T1", "IX_T1_Name")),
    ])
    def test_destructive_tool_rejected_without_confirm(self, tool_func, args):
        """Destructive tool must raise ValueError when confirm=False (default)."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.delete_data.return_value = {"success": True}
        mock_conn.adapter.delete_table.return_value = {"success": True}
        mock_conn.adapter.delete_query.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "confirm=True" in result["error"]

    @pytest.mark.parametrize("tool_func,args", [
        (crud_module.delete_data, ("T1", {"ID": 1})),
        (crud_module.delete_table, ("T1",)),
        (crud_module.delete_query, ("q1",)),
        (crud_module.drop_index, ("T1", "IX_T1_Name")),
    ])
    def test_destructive_tool_executes_with_confirm_true(self, tool_func, args):
        """Destructive tool executes when confirm=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.delete_data.return_value = {"success": True, "rows_deleted": 1}
        mock_conn.adapter.delete_table.return_value = {"success": True}
        mock_conn.adapter.delete_query.return_value = {"success": True}
        mock_conn.adapter.drop_index.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = tool_func(*args, confirm=True)
            assert result["success"] is True

    @pytest.mark.parametrize("tool_func,args", [
        (crud_module.delete_data, ("T1", {"ID": 1})),
        (crud_module.delete_table, ("T1",)),
        (crud_module.delete_query, ("q1",)),
        (crud_module.drop_index, ("T1", "IX_T1_Name")),
    ])
    def test_destructive_tool_dry_run_returns_preview(self, tool_func, args):
        """Destructive tool with dry_run=True returns preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = tool_func(*args, confirm=True, dry_run=True)
            assert result.get("dry_run") is True
            # No actual adapter call should be made
            mock_conn.adapter.delete_data.assert_not_called()
            mock_conn.adapter.delete_table.assert_not_called()
            mock_conn.adapter.delete_query.assert_not_called()
            mock_conn.adapter.drop_index.assert_not_called()


class TestAlterTableTool:
    """Tests for alter_table MCP tool."""

    def test_alter_table_not_connected_returns_error(self):
        """alter_table should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.alter_table("T1", [{"action": "add_column", "params": {"name": "C1", "type": "Text", "size": 50, "nullable": True}}])
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_alter_table_delegates_to_adapter(self):
        """alter_table should delegate to adapter.alter_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.alter_table.return_value = {"success": True, "operations": []}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        ops = [{"action": "add_column", "params": {"name": "C1", "type": "Text", "size": 50, "nullable": True}}]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.alter_table("T1", ops)
            assert result["success"] is True
            mock_conn.adapter.alter_table.assert_called_once_with("T1", ops)

    def test_alter_table_drop_column_requires_confirm(self):
        """alter_table with drop_column action must require confirm=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        ops = [{"action": "drop_column", "params": {"name": "C1"}}]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.alter_table("T1", ops)
            assert result["success"] is False
            assert "confirm=True" in result["error"]

    def test_alter_table_drop_column_executes_with_confirm(self):
        """alter_table with drop_column executes when confirm=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.alter_table.return_value = {"success": True, "operations": [{"action": "drop_column", "success": True}]}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        ops = [{"action": "drop_column", "params": {"name": "C1"}}]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.alter_table("T1", ops, confirm=True)
            assert result["success"] is True
            mock_conn.adapter.alter_table.assert_called_once()

    def test_alter_table_dry_run_returns_preview(self):
        """alter_table with dry_run=True returns preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        ops = [
            {"action": "add_column", "params": {"name": "C1", "type": "Text", "size": 50, "nullable": True}},
            {"action": "drop_column", "params": {"name": "C2"}},
        ]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.alter_table("T1", ops, confirm=True, dry_run=True)
            assert result.get("dry_run") is True
            assert result["table_name"] == "T1"
            assert result["operations"] == ops
            mock_conn.adapter.alter_table.assert_not_called()

    def test_alter_table_invalid_operation_returns_error(self):
        """alter_table with invalid action returns error."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.alter_table.return_value = {"success": False, "operations": [{"action": "bad", "success": False, "error": "Unknown action"}]}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        ops = [{"action": "invalid_action", "params": {}}]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.alter_table("T1", ops)
            # The adapter should return error for invalid action
            assert result["success"] is False

    def test_alter_table_multiple_operations_delegates_all(self):
        """alter_table with multiple operations delegates all to adapter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.alter_table.return_value = {"success": True, "operations": [{"action": "add_column", "success": True}, {"action": "modify_column", "success": True}]}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        ops = [
            {"action": "add_column", "params": {"name": "C1", "type": "Text", "size": 50, "nullable": True}},
            {"action": "modify_column", "params": {"name": "C2", "type": "Long Integer", "nullable": False}},
        ]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.alter_table("T1", ops)
            assert result["success"] is True
            mock_conn.adapter.alter_table.assert_called_once_with("T1", ops)

    def test_alter_table_rename_not_implemented_by_odbc_returns_error(self):
        """alter_table with rename_table on ODBC adapter returns clear error."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.alter_table.side_effect = NotImplementedError("ODBC does not support rename operations")
        mock_conn.get_adapter.return_value = mock_conn.adapter
        ops = [{"action": "rename_table", "params": {"new_name": "NewT1"}}]
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.alter_table("T1", ops, confirm=True)
            assert result["success"] is False
            assert "ODBC does not support rename" in result["error"]
