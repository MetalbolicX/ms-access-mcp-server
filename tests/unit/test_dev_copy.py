"""Tests for mcp/dev_copy.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import dev_copy as dev_copy_module


class TestDevopyConnectionGuards:
    """Tests that dev_copy tools check connection before executing."""

    # Tools that guard on connection_service.is_connected()
    @pytest.mark.parametrize("tool_func,args", [
        (server.compact_repair, ("compact", "/src.accdb", "/dst.accdb", True)),
        (server.copy_database, ("/src.accdb", "/dst.accdb")),
        (server.export_module_backup, ("modTest", None)),
        (server.import_module_from_text, ("modTest", "/tmp/bak/modTest.bas")),
        (server.restore_module_backup, ("modTest", "/tmp/bak/modTest.bas")),
        (server.export_form_backup, ("frmTest", None)),
        (server.import_form_from_file, ("frmTest", "/tmp/bak/frmTest.txt")),
        (server.restore_form_backup, ("frmTest", "/tmp/bak/frmTest.txt")),
        (server.export_report_backup, ("rptTest", None)),
        (server.import_report_from_file, ("rptTest", "/tmp/bak/rptTest.txt")),
        (server.restore_report_backup, ("rptTest", "/tmp/bak/rptTest.txt")),
        (server.create_dev_copy, (None,)),
        (server.deploy_dev_copy, (None,)),
        (server.discard_dev_copy, (None,)),
    ])
    def test_dev_copy_tools_return_error_when_not_connected(self, tool_func, args):
        """Each dev_copy tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestCompactRepair:
    """Tests for compact_repair tool."""

    def test_compact_repair_delegates_to_adapter(self):
        """compact_repair should delegate to adapter.compact_repair."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.compact_repair.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = server.compact_repair("compact", "/src.accdb", "/dst.accdb", True)
            assert result["success"] is True
            mock_conn.adapter.compact_repair.assert_called_once_with("compact", "/src.accdb", "/dst.accdb", True)

    def test_compact_repair_wraps_exception(self):
        """compact_repair should wrap exceptions in error response."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.compact_repair.side_effect = RuntimeError("File in use")
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = server.compact_repair("compact", "/src.accdb", "/dst.accdb", True)
            assert result["success"] is False
            assert "File in use" in result["error"]

    def test_compact_repair_returns_com_only_error_on_not_implemented(self):
        """compact_repair should return COM-only error dict when adapter raises NotImplementedError."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.compact_repair.side_effect = NotImplementedError("Jet SQL cannot compact")
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = server.compact_repair("compact", "/src.accdb", "/dst.accdb", True)
            assert result["success"] is False
            assert "COM automation" in result["error"]
            assert "use_com=True" in result["error"]

    def test_compact_repair_value_error_wrapped_normally(self):
        """compact_repair should wrap ValueError normally via str(e)."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.compact_repair.side_effect = ValueError("Invalid action 'bad'")
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = server.compact_repair("bad", "/src.accdb", "/dst.accdb", True)
            assert result["success"] is False
            assert "Invalid action" in result["error"]
            assert "bad" in result["error"]


class TestCopyDatabase:
    """Tests for copy_database tool."""

    def test_copy_database_delegates_to_adapter(self):
        """copy_database should delegate to adapter.copy_database."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.copy_database.return_value = True
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
            result = server.copy_database("/src.accdb", "/dst.accdb")
            assert result["success"] is True
            mock_conn.adapter.copy_database.assert_called_once_with("/src.accdb", "/dst.accdb")


class TestModuleBackupRestore:
    """Tests for module backup/restore tools."""

    def test_export_module_backup_delegates_to_versioning_orchestrator(self):
        """export_module_backup should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.export_module_backup.return_value = {"success": True, "backup_path": "/tmp/bak/modTest.bas"}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.export_module_backup("modTest", None)
                assert result["success"] is True
                mock_orch.export_module_backup.assert_called_once()
                args = mock_orch.export_module_backup.call_args
                assert args[0][0] == "modTest"  # module_name
                assert args[0][1] == mock_adapter  # adapter

    def test_import_module_from_text_delegates_to_versioning_orchestrator(self):
        """import_module_from_text should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.import_module_from_text.return_value = {"success": True}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.import_module_from_text("modTest", "/tmp/bak/modTest.bas")
                assert result["success"] is True
                mock_orch.import_module_from_text.assert_called_once()
                args = mock_orch.import_module_from_text.call_args
                assert args[0][0] == "modTest"  # module_name
                assert args[0][1] == "/tmp/bak/modTest.bas"  # file_path
                assert args[0][2] == mock_adapter  # adapter

    def test_restore_module_backup_delegates_to_versioning_orchestrator(self):
        """restore_module_backup should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.restore_module_backup.return_value = {"success": True}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.restore_module_backup("modTest", "/tmp/bak/modTest.bas")
                assert result["success"] is True
                mock_orch.restore_module_backup.assert_called_once()
                args = mock_orch.restore_module_backup.call_args
                assert args[0][0] == "modTest"  # module_name
                assert args[0][1] == "/tmp/bak/modTest.bas"  # backup_path
                assert args[0][2] == mock_adapter  # adapter


class TestFormBackupRestore:
    """Tests for form backup/restore tools."""

    def test_export_form_backup_delegates_to_versioning_orchestrator(self):
        """export_form_backup should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.export_form_backup.return_value = {"success": True, "backup_path": "/tmp/bak/frmTest.txt"}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.export_form_backup("frmTest", None)
                assert result["success"] is True
                mock_orch.export_form_backup.assert_called_once()
                args = mock_orch.export_form_backup.call_args
                assert args[0][0] == "frmTest"  # form_name
                assert args[0][1] == mock_adapter  # adapter

    def test_import_form_from_file_delegates_to_versioning_orchestrator(self):
        """import_form_from_file should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.import_form_from_file.return_value = {"success": True}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.import_form_from_file("frmTest", "/tmp/bak/frmTest.txt")
                assert result["success"] is True
                mock_orch.import_form_from_file.assert_called_once()
                args = mock_orch.import_form_from_file.call_args
                assert args[0][0] == "frmTest"  # form_name
                assert args[0][1] == "/tmp/bak/frmTest.txt"  # file_path
                assert args[0][2] == mock_adapter  # adapter

    def test_restore_form_backup_delegates_to_versioning_orchestrator(self):
        """restore_form_backup should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.restore_form_backup.return_value = {"success": True}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.restore_form_backup("frmTest", "/tmp/bak/frmTest.txt")
                assert result["success"] is True
                mock_orch.restore_form_backup.assert_called_once()
                args = mock_orch.restore_form_backup.call_args
                assert args[0][0] == "frmTest"  # form_name
                assert args[0][1] == "/tmp/bak/frmTest.txt"  # backup_path
                assert args[0][2] == mock_adapter  # adapter


class TestReportBackupRestore:
    """Tests for report backup/restore tools."""

    def test_export_report_backup_delegates_to_versioning_orchestrator(self):
        """export_report_backup should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.export_report_backup.return_value = {"success": True, "backup_path": "/tmp/bak/rptTest.txt"}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.export_report_backup("rptTest", None)
                assert result["success"] is True
                mock_orch.export_report_backup.assert_called_once()
                args = mock_orch.export_report_backup.call_args
                assert args[0][0] == "rptTest"  # report_name
                assert args[0][1] == mock_adapter  # adapter

    def test_import_report_from_file_delegates_to_versioning_orchestrator(self):
        """import_report_from_file should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.import_report_from_file.return_value = {"success": True}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.import_report_from_file("rptTest", "/tmp/bak/rptTest.txt")
                assert result["success"] is True
                mock_orch.import_report_from_file.assert_called_once()
                args = mock_orch.import_report_from_file.call_args
                assert args[0][0] == "rptTest"  # report_name
                assert args[0][1] == "/tmp/bak/rptTest.txt"  # file_path
                assert args[0][2] == mock_adapter  # adapter

    def test_restore_report_backup_delegates_to_versioning_orchestrator(self):
        """restore_report_backup should delegate to VersioningOrchestrator."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter
        mock_orch = MagicMock()
        mock_orch.restore_report_backup.return_value = {"success": True}
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator", return_value=mock_orch):
            with patch.object(dev_copy_module, '_pool', return_value=mock_conn):
                result = server.restore_report_backup("rptTest", "/tmp/bak/rptTest.txt")
                assert result["success"] is True
                mock_orch.restore_report_backup.assert_called_once()
                args = mock_orch.restore_report_backup.call_args
                assert args[0][0] == "rptTest"  # report_name
                assert args[0][1] == "/tmp/bak/rptTest.txt"  # backup_path
                assert args[0][2] == mock_adapter  # adapter


class TestDevCopyLifecycle:
    """Tests for dev copy lifecycle tools."""

    def test_create_dev_copy_delegates_to_service(self):
        """create_dev_copy should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_dev = MagicMock()
        mock_dev.create_dev_copy.return_value = {"success": True, "dev_path": "/tmp/dev.accdb"}
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn), \
             patch.object(dev_copy_module, '_dev_copy', return_value=mock_dev):
            result = server.create_dev_copy(None)
            assert result["success"] is True
            mock_dev.create_dev_copy.assert_called_once()

    def test_deploy_dev_copy_delegates_to_service(self):
        """deploy_dev_copy should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_dev = MagicMock()
        mock_dev.deploy_dev_copy.return_value = {"success": True}
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn), \
             patch.object(dev_copy_module, '_dev_copy', return_value=mock_dev):
            result = server.deploy_dev_copy(None, confirm=True)
            assert result["success"] is True
            mock_dev.deploy_dev_copy.assert_called_once()

    def test_deploy_dev_copy_rejected_without_confirm(self):
        """deploy_dev_copy must require confirm=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev = MagicMock()
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn), \
             patch.object(dev_copy_module, '_dev_copy', return_value=mock_dev):
            result = server.deploy_dev_copy(None)
            assert result["success"] is False
            assert "confirm=True" in result["error"]
            mock_dev.deploy_dev_copy.assert_not_called()

    def test_deploy_dev_copy_dry_run_returns_preview(self):
        """deploy_dev_copy with dry_run=True returns preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev = MagicMock()
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn), \
             patch.object(dev_copy_module, '_dev_copy', return_value=mock_dev):
            result = server.deploy_dev_copy(None, confirm=True, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "deploy_dev_copy"
            mock_dev.deploy_dev_copy.assert_not_called()

    def test_discard_dev_copy_delegates_to_service(self):
        """discard_dev_copy should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev = MagicMock()
        mock_dev.discard_dev_copy.return_value = {"success": True}
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn), \
             patch.object(dev_copy_module, '_dev_copy', return_value=mock_dev):
            result = server.discard_dev_copy(None, confirm=True)
            assert result["success"] is True
            mock_dev.discard_dev_copy.assert_called_once()

    def test_discard_dev_copy_rejected_without_confirm(self):
        """discard_dev_copy must require confirm=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev = MagicMock()
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn), \
             patch.object(dev_copy_module, '_dev_copy', return_value=mock_dev):
            result = server.discard_dev_copy(None)
            assert result["success"] is False
            assert "confirm=True" in result["error"]
            mock_dev.discard_dev_copy.assert_not_called()

    def test_discard_dev_copy_dry_run_returns_preview(self):
        """discard_dev_copy with dry_run=True returns preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev = MagicMock()
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn), \
             patch.object(dev_copy_module, '_dev_copy', return_value=mock_dev):
            result = server.discard_dev_copy(None, confirm=True, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "discard_dev_copy"
            mock_dev.discard_dev_copy.assert_not_called()

    def test_get_dev_copy_status_delegates_to_service(self):
        """get_dev_copy_status should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev = MagicMock()
        mock_dev.get_dev_copy_status.return_value = {"success": True, "exists": True}
        with patch.object(dev_copy_module, '_pool', return_value=mock_conn), \
             patch.object(dev_copy_module, '_dev_copy', return_value=mock_dev):
            result = server.get_dev_copy_status(None)
            assert result["success"] is True
            mock_dev.get_dev_copy_status.assert_called_once()
