"""Tests for mcp/system.py tool bindings.

These tools are defined in mcp/system.py and re-exported from mcp/server.py.
Due to the circular import architecture (system.py <-> server.py), function
globals are bound to a shared namespace that requires direct globals patching.
"""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


# Helper to patch both connection and schema services at the function globals level
def _patch_func_globals(func, mock_conn=None, mock_schema=None):
    """Patch services directly in function's __globals__ dict to overcome circular import issues."""
    patches = []
    if mock_conn is not None:
        patches.append(patch.dict(func.__globals__, connection_service=mock_conn))
    if mock_schema is not None:
        patches.append(patch.dict(func.__globals__, schema_service=mock_schema))
    return patches


class TestSystemToolConnectionGuards:
    """Test that all system tools properly guard connection state."""

    def test_get_object_metadata_returns_error_when_not_connected(self):
        """get_object_metadata should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.get_object_metadata.__globals__, connection_service=mock_conn):
            result = server.get_object_metadata("TestObject")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_form_to_text_returns_error_when_not_connected(self):
        """export_form_to_text should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.export_form_to_text.__globals__, connection_service=mock_conn):
            result = server.export_form_to_text("TestForm")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_form_from_text_returns_error_when_not_connected(self):
        """import_form_from_text should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.import_form_from_text.__globals__, connection_service=mock_conn):
            result = server.import_form_from_text("TestForm", "some data")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_delete_form_returns_error_when_not_connected(self):
        """delete_form should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.delete_form.__globals__, connection_service=mock_conn):
            result = server.delete_form("TestForm")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_report_to_text_returns_error_when_not_connected(self):
        """export_report_to_text should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.export_report_to_text.__globals__, connection_service=mock_conn):
            result = server.export_report_to_text("TestReport")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_report_from_text_returns_error_when_not_connected(self):
        """import_report_from_text should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.import_report_from_text.__globals__, connection_service=mock_conn):
            result = server.import_report_from_text("TestReport", "some data")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_delete_report_returns_error_when_not_connected(self):
        """delete_report should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.delete_report.__globals__, connection_service=mock_conn):
            result = server.delete_report("TestReport")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_module_to_text_returns_error_when_not_connected(self):
        """export_module_to_text should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.export_module_to_text.__globals__, connection_service=mock_conn):
            result = server.export_module_to_text("TestModule")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_macro_to_text_returns_error_when_not_connected(self):
        """export_macro_to_text should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.export_macro_to_text.__globals__, connection_service=mock_conn):
            result = server.export_macro_to_text("TestMacro")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_all_versioning_returns_error_when_not_connected(self):
        """export_all_versioning should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.export_all_versioning.__globals__, connection_service=mock_conn):
            result = server.export_all_versioning("/tmp/export")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_execute_sql_script_returns_error_when_not_connected(self):
        """execute_sql_script should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.execute_sql_script.__globals__, connection_service=mock_conn):
            result = server.execute_sql_script("/tmp/script.sql")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestSystemToolSuccessPaths:
    """Test successful paths for system tools."""

    def test_get_object_metadata_returns_not_found_for_unknown_object(self):
        """get_object_metadata should return not found for unknown object."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.get_object_metadata.return_value = None

        with patch.dict(server.get_object_metadata.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.get_object_metadata("UnknownObject")
            assert result["success"] is False
            assert "not found" in result["error"]

    def test_get_object_metadata_returns_metadata_on_success(self):
        """get_object_metadata should return metadata for known object."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.get_object_metadata.return_value = {"name": "TestTable", "type": "table"}

        with patch.dict(server.get_object_metadata.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.get_object_metadata("TestTable")
            assert result["success"] is True
            assert result["metadata"]["name"] == "TestTable"

    def test_export_form_to_text_returns_not_found_when_failed(self):
        """export_form_to_text should return error when form export fails."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.export_form_to_text.return_value = None

        with patch.dict(server.export_form_to_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.export_form_to_text("NonExistentForm")
            assert result["success"] is False
            assert "Failed to export" in result["error"]

    def test_export_form_to_text_returns_data_on_success(self):
        """export_form_to_text should return form data on successful export."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.export_form_to_text.return_value = "Form code here"

        with patch.dict(server.export_form_to_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.export_form_to_text("TestForm")
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert result["data"] == "Form code here"

    def test_import_form_from_text_returns_success_on_success(self):
        """import_form_from_text should return success when import succeeds."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.import_form_from_text.return_value = True

        with patch.dict(server.import_form_from_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.import_form_from_text("TestForm", "some data")
            assert result["success"] is True
            assert result["form"] == "TestForm"

    def test_import_form_from_text_returns_failure_on_failure(self):
        """import_form_from_text should return failure when import fails."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.import_form_from_text.return_value = False

        with patch.dict(server.import_form_from_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.import_form_from_text("TestForm", "some data")
            assert result["success"] is False
            assert result["form"] == "TestForm"

    def test_delete_form_returns_result(self):
        """delete_form should return result of deletion."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.delete_form.return_value = True

        with patch.dict(server.delete_form.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.delete_form("TestForm")
            assert result["success"] is True
            assert result["form"] == "TestForm"

    def test_export_report_to_text_returns_data_on_success(self):
        """export_report_to_text should return report data on success."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.export_report_to_text.return_value = "Report code here"

        with patch.dict(server.export_report_to_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.export_report_to_text("TestReport")
            assert result["success"] is True
            assert result["report"] == "TestReport"
            assert result["data"] == "Report code here"

    def test_import_report_from_text_returns_success_on_success(self):
        """import_report_from_text should return success when import succeeds."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.import_report_from_text.return_value = True

        with patch.dict(server.import_report_from_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.import_report_from_text("TestReport", "some data")
            assert result["success"] is True
            assert result["report"] == "TestReport"

    def test_delete_report_returns_result(self):
        """delete_report should return result of deletion."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.delete_report.return_value = True

        with patch.dict(server.delete_report.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.delete_report("TestReport")
            assert result["success"] is True
            assert result["report"] == "TestReport"

    def test_export_module_to_text_returns_data_on_success(self):
        """export_module_to_text should return module data on success."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.export_module_to_text.return_value = "Sub TestModule()\nEnd Sub"

        with patch.dict(server.export_module_to_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.export_module_to_text("TestModule")
            assert result["success"] is True
            assert result["module"] == "TestModule"
            assert "Sub TestModule()" in result["data"]

    def test_export_module_to_text_returns_not_found_for_empty(self):
        """export_module_to_text should return not found for empty module."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.export_module_to_text.return_value = None

        with patch.dict(server.export_module_to_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.export_module_to_text("EmptyModule")
            assert result["success"] is False
            assert "not found" in result["error"]

    def test_export_macro_to_text_returns_metadata_on_success(self):
        """export_macro_to_text should return macro metadata on success."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.export_macro_to_text.return_value = {"name": "TestMacro", "type": "macro"}

        with patch.dict(server.export_macro_to_text.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.export_macro_to_text("TestMacro")
            assert result["success"] is True
            assert result["macro"] == "TestMacro"
            assert result["data"]["name"] == "TestMacro"

    def test_export_all_versioning_delegates_to_schema_service(self):
        """export_all_versioning should delegate to schema_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.export_all_versioning.return_value = {"success": True, "exported": 10}

        with patch.dict(server.export_all_versioning.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.export_all_versioning("/tmp/export")
            mock_schema.export_all_versioning.assert_called_once_with("/tmp/export")
            assert result["success"] is True

    def test_execute_sql_script_delegates_to_schema_service(self):
        """execute_sql_script should delegate to schema_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.execute_sql_script.return_value = {"success": True, "statements": 5}

        with patch.dict(server.execute_sql_script.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.execute_sql_script("/tmp/script.sql")
            mock_schema.execute_sql_script.assert_called_once_with("/tmp/script.sql")
            assert result["success"] is True
