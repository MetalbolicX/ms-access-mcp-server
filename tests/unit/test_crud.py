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
            result = crud_module.delete_query("q1")
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
            result = crud_module.delete_table("T1")
            assert result["success"] is True
            mock_conn.adapter.delete_table.assert_called_once_with("T1")


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

    def test_delete_data_delegates_to_adapter(self):
        """delete_data should delegate to adapter.delete_data."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.delete_data.return_value = {"success": True, "rows_deleted": 1}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(crud_module, '_pool', return_value=mock_conn):
            result = crud_module.delete_data("T1", {"ID": 1})
            assert result["success"] is True
            mock_conn.adapter.delete_data.assert_called_once()
