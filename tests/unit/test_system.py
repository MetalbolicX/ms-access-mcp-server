"""Tests for mcp/system.py and mcp/persistence.py tool bindings.

These tools are re-exported from mcp/server.py. The modules now use _pool()
lazy accessor instead of connection_service, so we patch module._pool.
"""
import sys
import pytest
from unittest.mock import patch, MagicMock

# Import server first to resolve circular dependency
from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import system as system_module
from ms_access_mcp.mcp import persistence as persistence_module
from ms_access_mcp.mcp import recovery as recovery_module
from ms_access_mcp.mcp import dev_copy as dev_copy_module


def _patch_pool(module, mock_adapter=None):
    """Patch module._pool with a mock connection pool.

    Sets up mock_pool.is_connected = True and mock_pool.get_adapter = mock_adapter.
    """
    mock_pool = MagicMock()
    mock_pool.is_connected.return_value = True
    mock_pool.get_adapter.return_value = mock_adapter or MagicMock()
    return patch.object(module, '_pool', return_value=mock_pool)


class TestSystemToolConnectionGuards:
    """Test that all system tools properly guard connection state."""

    def test_get_object_metadata_returns_error_when_not_connected(self):
        """get_object_metadata should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(system_module, '_pool', return_value=mock_pool):
            result = server.get_object_metadata("TestObject")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_form_to_text_returns_error_when_not_connected(self):
        """export_form_to_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.export_form_to_text("TestForm")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_form_from_text_returns_error_when_not_connected(self):
        """import_form_from_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.import_form_from_text("TestForm", "some data")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_delete_form_returns_error_when_not_connected(self):
        """delete_form should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.delete_form("TestForm")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_report_to_text_returns_error_when_not_connected(self):
        """export_report_to_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.export_report_to_text("TestReport")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_report_from_text_returns_error_when_not_connected(self):
        """import_report_from_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.import_report_from_text("TestReport", "some data")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_delete_report_returns_error_when_not_connected(self):
        """delete_report should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.delete_report("TestReport")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_module_to_text_returns_error_when_not_connected(self):
        """export_module_to_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.export_module_to_text("TestModule")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_macro_to_text_returns_error_when_not_connected(self):
        """export_macro_to_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.export_macro_to_text("TestMacro")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_all_versioning_returns_error_when_not_connected(self):
        """export_all_versioning should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.export_all_versioning("/tmp/export")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_execute_sql_script_returns_error_when_not_connected(self):
        """execute_sql_script should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.execute_sql_script("/tmp/script.sql")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestSystemToolSuccessPaths:
    """Test successful paths for system tools."""

    def test_get_object_metadata_returns_not_found_for_unknown_object(self):
        """get_object_metadata should return not found for unknown object."""
        mock_adapter = MagicMock()
        mock_adapter.get_object_metadata.return_value = None
        with _patch_pool(system_module, mock_adapter):
            result = server.get_object_metadata("UnknownObject")
            assert result["success"] is False
            assert "not found" in result["error"]

    def test_get_object_metadata_returns_metadata_on_success(self):
        """get_object_metadata should return metadata for known object."""
        mock_adapter = MagicMock()
        mock_adapter.get_object_metadata.return_value = {"name": "TestTable", "type": "table"}
        with _patch_pool(system_module, mock_adapter):
            result = server.get_object_metadata("TestTable")
            assert result["success"] is True
            assert result["metadata"]["name"] == "TestTable"

    def test_export_form_to_text_returns_not_found_when_failed(self):
        """export_form_to_text should return error when form export fails."""
        mock_adapter = MagicMock()
        mock_adapter.export_form_to_text.return_value = None
        with _patch_pool(persistence_module, mock_adapter):
            result = server.export_form_to_text("NonExistentForm")
            assert result["success"] is False
            assert "Failed to export" in result["error"]

    def test_export_form_to_text_returns_data_on_success(self):
        """export_form_to_text should return form data on successful export."""
        mock_adapter = MagicMock()
        mock_adapter.export_form_to_text.return_value = "Form code here"
        with _patch_pool(persistence_module, mock_adapter):
            result = server.export_form_to_text("TestForm")
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert result["data"] == "Form code here"

    def test_import_form_from_text_returns_success_on_success(self):
        """import_form_from_text should return success when import succeeds."""
        mock_adapter = MagicMock()
        mock_adapter.import_form_from_text.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.import_form_from_text("TestForm", "some data")
            assert result["success"] is True
            assert result["form"] == "TestForm"

    def test_import_form_from_text_returns_failure_on_failure(self):
        """import_form_from_text should return failure when import fails."""
        mock_adapter = MagicMock()
        mock_adapter.import_form_from_text.return_value = False
        with _patch_pool(persistence_module, mock_adapter):
            result = server.import_form_from_text("TestForm", "some data")
            assert result["success"] is False
            assert result["form"] == "TestForm"

    def test_delete_form_returns_result(self):
        """delete_form should return result of deletion."""
        mock_adapter = MagicMock()
        mock_adapter.delete_form.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.delete_form("TestForm", confirm=True)
            assert result["success"] is True
            assert result["form"] == "TestForm"

    def test_delete_form_rejected_without_confirm(self):
        """delete_form must require confirm=True."""
        mock_adapter = MagicMock()
        mock_adapter.delete_form.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.delete_form("TestForm")
            assert result["success"] is False
            assert "confirm=True" in result["error"]
            mock_adapter.delete_form.assert_not_called()

    def test_delete_form_dry_run_returns_preview(self):
        """delete_form with dry_run=True returns preview without executing."""
        mock_adapter = MagicMock()
        mock_adapter.delete_form.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.delete_form("TestForm", confirm=True, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "delete_form"
            assert result["form_name"] == "TestForm"
            mock_adapter.delete_form.assert_not_called()

    def test_export_report_to_text_returns_data_on_success(self):
        """export_report_to_text should return report data on success."""
        mock_adapter = MagicMock()
        mock_adapter.export_report_to_text.return_value = "Report code here"
        with _patch_pool(persistence_module, mock_adapter):
            result = server.export_report_to_text("TestReport")
            assert result["success"] is True
            assert result["report"] == "TestReport"
            assert result["data"] == "Report code here"

    def test_import_report_from_text_returns_success_on_success(self):
        """import_report_from_text should return success when import succeeds."""
        mock_adapter = MagicMock()
        mock_adapter.import_report_from_text.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.import_report_from_text("TestReport", "some data")
            assert result["success"] is True
            assert result["report"] == "TestReport"

    def test_delete_report_returns_result(self):
        """delete_report should return result of deletion."""
        mock_adapter = MagicMock()
        mock_adapter.delete_report.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.delete_report("TestReport", confirm=True)
            assert result["success"] is True
            assert result["report"] == "TestReport"

    def test_delete_report_rejected_without_confirm(self):
        """delete_report must require confirm=True."""
        mock_adapter = MagicMock()
        mock_adapter.delete_report.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.delete_report("TestReport")
            assert result["success"] is False
            assert "confirm=True" in result["error"]
            mock_adapter.delete_report.assert_not_called()

    def test_delete_report_dry_run_returns_preview(self):
        """delete_report with dry_run=True returns preview without executing."""
        mock_adapter = MagicMock()
        mock_adapter.delete_report.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.delete_report("TestReport", confirm=True, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "delete_report"
            assert result["report_name"] == "TestReport"
            mock_adapter.delete_report.assert_not_called()

    def test_export_module_to_text_returns_data_on_success(self):
        """export_module_to_text should return module data on success."""
        mock_adapter = MagicMock()
        mock_adapter.export_module_to_text.return_value = "Sub TestModule()\nEnd Sub"
        with _patch_pool(persistence_module, mock_adapter):
            result = server.export_module_to_text("TestModule")
            assert result["success"] is True
            assert result["module"] == "TestModule"
            assert "Sub TestModule()" in result["data"]

    def test_export_module_to_text_returns_not_found_for_empty(self):
        """export_module_to_text should return not found for empty module."""
        mock_adapter = MagicMock()
        mock_adapter.export_module_to_text.return_value = None
        with _patch_pool(persistence_module, mock_adapter):
            result = server.export_module_to_text("EmptyModule")
            assert result["success"] is False
            assert "not found" in result["error"]

    def test_export_macro_to_text_returns_metadata_on_success(self):
        """export_macro_to_text should return macro metadata on success."""
        mock_adapter = MagicMock()
        mock_adapter.export_macro_to_text.return_value = {"name": "TestMacro", "type": "macro"}
        with _patch_pool(persistence_module, mock_adapter):
            result = server.export_macro_to_text("TestMacro")
            assert result["success"] is True
            assert result["macro"] == "TestMacro"
            assert result["data"]["name"] == "TestMacro"

    def test_import_macro_from_text_delegates_to_adapter(self):
        """import_macro_from_text should delegate to adapter.import_macro_from_text."""
        mock_adapter = MagicMock()
        mock_adapter.import_macro_from_text.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.import_macro_from_text("TestMacro", "<macro/>", confirm=True)
            mock_adapter.import_macro_from_text.assert_called_once_with("TestMacro", "<macro/>")
            assert result["success"] is True
            assert result["macro"] == "TestMacro"

    def test_import_macro_from_text_returns_error_when_not_connected(self):
        """import_macro_from_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.import_macro_from_text("TestMacro", "<macro/>", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_macro_from_text_blocked_without_confirmation(self):
        """import_macro_from_text with confirm=False should be blocked by guard."""
        mock_adapter = MagicMock()
        with _patch_pool(persistence_module, mock_adapter):
            result = server.import_macro_from_text("TestMacro", "<macro/>")
            assert result["success"] is False
            assert "confirm=True required" in result["error"]
            mock_adapter.import_macro_from_text.assert_not_called()

    def test_import_macro_from_text_dry_run_returns_preview(self):
        """import_macro_from_text with dry_run=True should return preview without executing."""
        mock_adapter = MagicMock()
        with _patch_pool(persistence_module, mock_adapter):
            result = server.import_macro_from_text("TestMacro", "<macro/>", confirm=True, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "import_macro_from_text"
            assert result["macro"] == "TestMacro"
            mock_adapter.import_macro_from_text.assert_not_called()

    def test_import_macro_from_text_returns_failure_on_failure(self):
        """import_macro_from_text with adapter returning False should return success=False."""
        mock_adapter = MagicMock()
        mock_adapter.import_macro_from_text.return_value = False
        with _patch_pool(persistence_module, mock_adapter):
            result = server.import_macro_from_text("TestMacro", "<macro/>", confirm=True)
            assert result["success"] is False
            assert result["macro"] == "TestMacro"

    def test_export_all_versioning_delegates_to_versioning_orchestrator(self, tmp_path):
        """export_all_versioning should call adapter.export_all_versioning directly."""
        mock_adapter = MagicMock()
        mock_adapter.export_all_versioning.return_value = {"success": True, "exported": 10}
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        with patch.object(persistence_module, "_pool", return_value=mock_pool):
            result = server.export_all_versioning(str(tmp_path / "export"))
            mock_adapter.export_all_versioning.assert_called_once()
            assert result["success"] is True

    def test_import_all_versioning_delegates_to_versioning_orchestrator(self, tmp_path):
        """import_all_versioning should call adapter.import_all_versioning directly."""
        mock_adapter = MagicMock()
        mock_adapter.import_all_versioning.return_value = {"success": True, "exported": 10}
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        with patch.object(persistence_module, "_pool", return_value=mock_pool):
            result = server.import_all_versioning(str(tmp_path / "import"))
            mock_adapter.import_all_versioning.assert_called_once()
            assert result["success"] is True

    def test_compare_versioning_delegates_to_versioning_orchestrator(self, tmp_path):
        """compare_versioning should call adapter.compare_versioning directly."""
        mock_adapter = MagicMock()
        mock_adapter.compare_versioning.return_value = {"success": True, "exported": 10}
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        with patch.object(persistence_module, "_pool", return_value=mock_pool):
            result = server.compare_versioning(str(tmp_path / "compare"))
            mock_adapter.compare_versioning.assert_called_once()
            assert result["success"] is True

    def test_export_schema_ddl_delegates_to_versioning_orchestrator(self, tmp_path):
        """export_schema_ddl should call adapter.export_schema_ddl directly."""
        mock_adapter = MagicMock()
        mock_adapter.export_schema_ddl.return_value = {"success": True, "exported": 10}
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        with patch.object(persistence_module, "_pool", return_value=mock_pool):
            result = server.export_schema_ddl(str(tmp_path / "ddl"))
            mock_adapter.export_schema_ddl.assert_called_once()
            assert result["success"] is True

    def test_export_query_to_text_delegates_to_adapter(self):
        """export_query_to_text should delegate to adapter.export_query_to_text."""
        mock_adapter = MagicMock()
        mock_adapter.export_query_to_text.return_value = "SELECT * FROM Table1"
        with _patch_pool(persistence_module, mock_adapter):
            result = server.export_query_to_text("q1")
            mock_adapter.export_query_to_text.assert_called_once_with("q1")
            assert result["success"] is True
            assert result["query"] == "q1"
            assert result["data"] == "SELECT * FROM Table1"

    def test_export_query_to_text_returns_error_when_not_connected(self):
        """export_query_to_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.export_query_to_text("q1")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_query_from_text_delegates_to_adapter(self):
        """import_query_from_text should delegate to adapter.import_query_from_text."""
        mock_adapter = MagicMock()
        mock_adapter.import_query_from_text.return_value = True
        with _patch_pool(persistence_module, mock_adapter):
            result = server.import_query_from_text("q1", "SELECT 1")
            mock_adapter.import_query_from_text.assert_called_once_with("q1", "SELECT 1")
            assert result["success"] is True

    def test_import_query_from_text_returns_error_when_not_connected(self):
        """import_query_from_text should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.import_query_from_text("q1", "SELECT 1")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_export_schema_ddl_returns_error_when_not_connected(self):
        """export_schema_ddl should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.export_schema_ddl("/tmp/ddl")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_all_versioning_returns_error_when_not_connected(self):
        """import_all_versioning should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(persistence_module, '_pool', return_value=mock_pool):
            result = server.import_all_versioning("/tmp/import")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_execute_sql_script_delegates_to_adapter(self, tmp_path):
        """execute_sql_script should delegate to adapter.execute_sql_script."""
        mock_adapter = MagicMock()
        mock_adapter.execute_sql_script.return_value = {"success": True, "statements": 5}
        with _patch_pool(persistence_module, mock_adapter):
            result = server.execute_sql_script(str(tmp_path / "script.sql"))
            mock_adapter.execute_sql_script.assert_called_once_with(str(tmp_path / "script.sql"))
            assert result["success"] is True


class TestReportBackupTools:
    """Tests for export_report_backup, import_report_from_file, restore_report_backup.

    These functions are in dev_copy.py (Batch 2), now migrated to use _pool() accessor.
    """

    def test_export_report_backup_delegates_to_versioning_orchestrator(self):
        """export_report_backup should call _dev_copy().export_report_backup directly."""
        mock_adapter = MagicMock()
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        mock_dev_copy = MagicMock()
        mock_dev_copy.export_report_backup.return_value = {"success": True, "backup_path": "/tmp/rptTest.txt"}
        with patch.object(dev_copy_module, "_pool", return_value=mock_conn):
            with patch.object(dev_copy_module, "_dev_copy", return_value=mock_dev_copy):
                result = server.export_report_backup("rptTest", None)
                assert result["success"] is True
                mock_dev_copy.export_report_backup.assert_called_once()

    def test_export_report_backup_returns_error_when_not_connected(self):
        """export_report_backup should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = server.export_report_backup("rptTest", None)
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_report_from_file_delegates_to_versioning_orchestrator(self, tmp_path):
        """import_report_from_file should call _dev_copy().import_report_from_file directly."""
        mock_adapter = MagicMock()
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        mock_dev_copy = MagicMock()
        mock_dev_copy.import_report_from_file.return_value = {"success": True, "backup_path": "/tmp/rptTest.txt"}
        with patch.object(dev_copy_module, "_pool", return_value=mock_conn):
            with patch.object(dev_copy_module, "_dev_copy", return_value=mock_dev_copy):
                result = server.import_report_from_file("rptTest", str(tmp_path / "rptTest.txt"))
                assert result["success"] is True
                mock_dev_copy.import_report_from_file.assert_called_once()

    def test_import_report_from_file_returns_error_when_not_connected(self):
        """import_report_from_file should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = server.import_report_from_file("rptTest", "/tmp/rptTest.txt")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_restore_report_backup_delegates_to_versioning_orchestrator(self, tmp_path):
        """restore_report_backup should call _dev_copy().restore_report_backup directly."""
        mock_adapter = MagicMock()
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        mock_dev_copy = MagicMock()
        mock_dev_copy.restore_report_backup.return_value = {"success": True, "backup_path": "/tmp/rptTest.txt"}
        with patch.object(dev_copy_module, "_pool", return_value=mock_conn):
            with patch.object(dev_copy_module, "_dev_copy", return_value=mock_dev_copy):
                result = server.restore_report_backup("rptTest", str(tmp_path / "rptTest.txt"))
                assert result["success"] is True
                mock_dev_copy.restore_report_backup.assert_called_once()

    def test_restore_report_backup_returns_error_when_not_connected(self):
        """restore_report_backup should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = server.restore_report_backup("rptTest", None)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestRecoverAccessTool:
    """Tests for recover_access tool."""

    def test_recover_access_delegates_to_connection_service(self):
        """recover_access should delegate to _pool().recover_access."""
        mock_pool = MagicMock()
        mock_pool.recover_access.return_value = {"success": True, "reconnected": ["default"]}
        with patch.object(recovery_module, '_pool', return_value=mock_pool):
            result = server.recover_access()
            mock_pool.recover_access.assert_called_once()
            assert result["success"] is True

    def test_recover_access_accepts_confirm_parameter(self):
        """recover_access should accept confirm: bool = True parameter."""
        # Check that the function signature accepts confirm
        import inspect
        sig = inspect.signature(server.recover_access)
        params = list(sig.parameters.keys())
        assert "confirm" in params, f"recover_access should have 'confirm' param, got: {params}"
        # Default should be True
        default = sig.parameters["confirm"].default
        assert default is True, f"recover_access confirm default should be True, got: {default}"

    def test_recover_access_rejects_confirm_false(self):
        """recover_access with confirm=False should return error (confirm required)."""
        mock_pool = MagicMock()
        mock_pool.recover_access.return_value = {"success": False, "error": "confirm=True required"}
        with patch.object(recovery_module, '_pool', return_value=mock_pool):
            result = server.recover_access(confirm=False)
            assert result["success"] is False
            assert "confirm" in result.get("error", "").lower()

    def test_recover_access_executes_with_confirm_true(self):
        """recover_access with confirm=True should execute taskkill via pool."""
        mock_pool = MagicMock()
        mock_pool.recover_access.return_value = {
            "success": True,
            "reconnected": ["default"],
            "confirm_required": None,
        }
        with patch.object(recovery_module, '_pool', return_value=mock_pool):
            result = server.recover_access(confirm=True)
            assert result["success"] is True


class TestDiagnoseEnvironmentTool:
    """Tests for diagnose_environment tool."""

    def test_diagnose_environment_returns_success(self):
        """diagnose_environment should return success True."""
        result = server.diagnose_environment()
        assert result["success"] is True

    def test_diagnose_environment_contains_platform_keys(self):
        """diagnose_environment diagnostics should contain platform and python_version."""
        result = server.diagnose_environment()
        assert "platform" in result["diagnostics"]
        assert "python_version" in result["diagnostics"]

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_diagnose_environment_has_pywin32_false_on_linux(self):
        """On Linux, pywin32_available should be False."""
        result = server.diagnose_environment()
        assert result["diagnostics"]["pywin32_available"] is False

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_diagnose_environment_has_ace_provider_windows_only_on_linux(self):
        """On Linux, ace_provider should be windows_only."""
        result = server.diagnose_environment()
        assert result["diagnostics"]["ace_provider"] == "windows_only"

    def test_diagnose_environment_returns_allowed_dirs_list(self):
        """diagnose_environment should return allowed_dirs as a list."""
        result = server.diagnose_environment()
        assert isinstance(result["diagnostics"]["allowed_dirs"], list)
