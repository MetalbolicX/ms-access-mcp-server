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
            result = server.delete_form("TestForm")
            assert result["success"] is True
            assert result["form"] == "TestForm"

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
            result = server.delete_report("TestReport")
            assert result["success"] is True
            assert result["report"] == "TestReport"

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

    def test_export_all_versioning_delegates_to_versioning_orchestrator(self):
        """export_all_versioning should delegate to VersioningOrchestrator.export_all."""
        mock_adapter = MagicMock()
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.export_all.return_value = {"success": True, "exported": 10}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with _patch_pool(persistence_module, mock_adapter):
                result = server.export_all_versioning("/tmp/export")
                mock_orch.export_all.assert_called_once()
                args = mock_orch.export_all.call_args
                assert args[0][0] == "/tmp/export"
                assert args[0][1] == mock_adapter
                assert result["success"] is True

    def test_import_all_versioning_delegates_to_versioning_orchestrator(self):
        """import_all_versioning should delegate to VersioningOrchestrator.import_all."""
        mock_adapter = MagicMock()
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.import_all.return_value = {"success": True, "imported": 5}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with _patch_pool(persistence_module, mock_adapter):
                result = server.import_all_versioning("/tmp/import")
                mock_orch.import_all.assert_called_once()
                args = mock_orch.import_all.call_args
                assert args[0][0] == "/tmp/import"
                assert args[0][1] == mock_adapter
                assert result["success"] is True

    def test_compare_versioning_delegates_to_versioning_orchestrator(self):
        """compare_versioning should delegate to VersioningOrchestrator.compare."""
        mock_adapter = MagicMock()
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.compare.return_value = {"success": True, "new": [], "missing": [], "changed": []}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with _patch_pool(persistence_module, mock_adapter):
                result = server.compare_versioning("/tmp/compare")
                mock_orch.compare.assert_called_once()
                args = mock_orch.compare.call_args
                assert args[0][0] == "/tmp/compare"
                assert args[0][1] == mock_adapter
                assert result["success"] is True

    def test_export_schema_ddl_delegates_to_versioning_orchestrator(self):
        """export_schema_ddl should delegate to VersioningOrchestrator.export_schema_ddl."""
        mock_adapter = MagicMock()
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.export_schema_ddl.return_value = {"success": True, "ddl_tables": "schema/ddl_tables.sql"}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with _patch_pool(persistence_module, mock_adapter):
                result = server.export_schema_ddl("/tmp/ddl")
                mock_orch.export_schema_ddl.assert_called_once()
                args = mock_orch.export_schema_ddl.call_args
                assert args[0][0] == "/tmp/ddl"
                assert args[0][1] == mock_adapter
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

    def test_execute_sql_script_delegates_to_adapter(self):
        """execute_sql_script should delegate to adapter.execute_sql_script."""
        mock_adapter = MagicMock()
        mock_adapter.execute_sql_script.return_value = {"success": True, "statements": 5}
        with _patch_pool(persistence_module, mock_adapter):
            result = server.execute_sql_script("/tmp/script.sql")
            mock_adapter.execute_sql_script.assert_called_once_with("/tmp/script.sql")
            assert result["success"] is True


class TestReportBackupTools:
    """Tests for export_report_backup, import_report_from_file, restore_report_backup.

    These functions are in dev_copy.py (Batch 2), which still uses connection_service.
    So we use the old patch.dict approach for now.
    """

    def test_export_report_backup_delegates_to_versioning_orchestrator(self):
        """export_report_backup should delegate to VersioningOrchestrator."""
        mock_adapter = MagicMock()
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.export_report_backup.return_value = {"success": True, "backup_path": "/tmp/rptTest.txt"}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.dict(server.export_report_backup.__globals__, connection_service=mock_conn):
                result = server.export_report_backup("rptTest", None)
                assert result["success"] is True
                mock_orch.export_report_backup.assert_called_once()
                args = mock_orch.export_report_backup.call_args
                assert args[0][0] == "rptTest"
                assert args[0][1] == mock_adapter

    def test_export_report_backup_returns_error_when_not_connected(self):
        """export_report_backup should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.export_report_backup.__globals__, connection_service=mock_conn):
            result = server.export_report_backup("rptTest", None)
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_import_report_from_file_delegates_to_versioning_orchestrator(self):
        """import_report_from_file should delegate to VersioningOrchestrator."""
        mock_adapter = MagicMock()
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.import_report_from_file.return_value = {"success": True}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.dict(server.import_report_from_file.__globals__, connection_service=mock_conn):
                result = server.import_report_from_file("rptTest", "/tmp/rptTest.txt")
                assert result["success"] is True
                mock_orch.import_report_from_file.assert_called_once()
                args = mock_orch.import_report_from_file.call_args
                assert args[0][0] == "rptTest"
                assert args[0][1] == "/tmp/rptTest.txt"
                assert args[0][2] == mock_adapter

    def test_import_report_from_file_returns_error_when_not_connected(self):
        """import_report_from_file should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.import_report_from_file.__globals__, connection_service=mock_conn):
            result = server.import_report_from_file("rptTest", "/tmp/rptTest.txt")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_restore_report_backup_delegates_to_versioning_orchestrator(self):
        """restore_report_backup should delegate to VersioningOrchestrator."""
        mock_adapter = MagicMock()
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.restore_report_backup.return_value = {"success": True}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.dict(server.restore_report_backup.__globals__, connection_service=mock_conn):
                result = server.restore_report_backup("rptTest", "/tmp/rptTest.txt")
                assert result["success"] is True
                mock_orch.restore_report_backup.assert_called_once()
                args = mock_orch.restore_report_backup.call_args
                assert args[0][0] == "rptTest"
                assert args[0][1] == "/tmp/rptTest.txt"
                assert args[0][2] == mock_adapter

    def test_restore_report_backup_returns_error_when_not_connected(self):
        """restore_report_backup should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(server.restore_report_backup.__globals__, connection_service=mock_conn):
            result = server.restore_report_backup("rptTest", "/tmp/rptTest.txt")
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
