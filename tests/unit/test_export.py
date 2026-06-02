"""Tests for mcp/export.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


class TestExportToolsConnectionGuards:
    """Tests that export tools check connection state."""

    @pytest.mark.parametrize("tool_func,args", [
        (server.export_table_csv, ("Customers", "/tmp/out.csv")),
        (server.export_query_json, ("qryActive", "/tmp/out.json")),
    ])
    def test_export_tools_return_error_when_not_connected(self, tool_func, args):
        """Each export tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(tool_func.__globals__, connection_service=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestCompareVersioningTool:
    """Tests for compare_versioning tool."""

    def test_compare_versioning_delegates_to_schema_service(self):
        """compare_versioning should delegate to schema_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.compare_versioning.return_value = {"success": True, "new": [], "missing": [], "changed": [], "unchanged": []}
        with patch.dict(server.compare_versioning.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.compare_versioning("/tmp/compare")
            mock_schema.compare_versioning.assert_called_once_with("/tmp/compare")
            assert result["success"] is True

    def test_compare_versioning_returns_error_when_not_connected(self):
        """compare_versioning should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.compare_versioning.__globals__, connection_service=mock_conn):
            result = server.compare_versioning("/tmp/compare")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestExportTableCsv:
    """Tests for export_table_csv tool."""

    def test_export_table_csv_delegates_to_adapter(self):
        """export_table_csv should delegate to adapter.export_table_csv."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.export_table_csv.return_value = {"success": True, "file_path": "/tmp/out.csv"}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.export_table_csv.__globals__, connection_service=mock_conn):
            result = server.export_table_csv("Customers", "/tmp/out.csv")
            assert result["success"] is True
            assert result["file_path"] == "/tmp/out.csv"
            mock_conn.adapter.export_table_csv.assert_called_once()

    def test_export_table_csv_returns_error_on_failure(self):
        """export_table_csv should return error on adapter failure."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.export_table_csv.return_value = {"success": False, "error": "File not found"}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.export_table_csv.__globals__, connection_service=mock_conn):
            result = server.export_table_csv("NonExistent", "/tmp/nonexistent.csv")
            assert result["success"] is False
            assert "File not found" in result["error"]


class TestExportQueryJson:
    """Tests for export_query_json tool."""

    def test_export_query_json_delegates_to_adapter(self):
        """export_query_json should delegate to adapter.export_query_json."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.export_query_json.return_value = {"success": True, "file_path": "/tmp/out.json"}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.export_query_json.__globals__, connection_service=mock_conn):
            result = server.export_query_json("qryActive", "/tmp/out.json")
            assert result["success"] is True
            assert result["file_path"] == "/tmp/out.json"
            mock_conn.adapter.export_query_json.assert_called_once()

    def test_export_query_json_returns_error_on_failure(self):
        """export_query_json should return error on adapter failure."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.export_query_json.return_value = {"success": False, "error": "Query not found"}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.export_query_json.__globals__, connection_service=mock_conn):
            result = server.export_query_json("NonExistent", "/tmp/nonexistent.json")
            assert result["success"] is False
            assert "Query not found" in result["error"]
