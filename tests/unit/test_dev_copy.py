"""Tests for mcp/dev_copy.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


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
        (server.create_dev_copy, (None,)),
        (server.deploy_dev_copy, (None,)),
        (server.discard_dev_copy, (None,)),
    ])
    def test_dev_copy_tools_return_error_when_not_connected(self, tool_func, args):
        """Each dev_copy tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(tool_func.__globals__, connection_service=mock_conn):
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
        with patch.dict(server.compact_repair.__globals__, connection_service=mock_conn):
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
        with patch.dict(server.compact_repair.__globals__, connection_service=mock_conn):
            result = server.compact_repair("compact", "/src.accdb", "/dst.accdb", True)
            assert result["success"] is False
            assert "File in use" in result["error"]


class TestCopyDatabase:
    """Tests for copy_database tool."""

    def test_copy_database_delegates_to_adapter(self):
        """copy_database should delegate to adapter.copy_database."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.copy_database.return_value = True
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.copy_database.__globals__, connection_service=mock_conn):
            result = server.copy_database("/src.accdb", "/dst.accdb")
            assert result["success"] is True
            mock_conn.adapter.copy_database.assert_called_once_with("/src.accdb", "/dst.accdb")


class TestModuleBackupRestore:
    """Tests for module backup/restore tools."""

    def test_export_module_backup_delegates_to_service(self):
        """export_module_backup should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_dev = MagicMock()
        mock_dev.export_module_backup.return_value = {"success": True, "file_path": "/tmp/bak/modTest.bas"}
        with patch.dict(server.export_module_backup.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.export_module_backup("modTest", None)
            assert result["success"] is True
            mock_dev.export_module_backup.assert_called_once()

    def test_import_module_from_text_delegates_to_service(self):
        """import_module_from_text should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_dev = MagicMock()
        mock_dev.import_module_from_text.return_value = {"success": True}
        with patch.dict(server.import_module_from_text.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.import_module_from_text("modTest", "/tmp/bak/modTest.bas")
            assert result["success"] is True
            mock_dev.import_module_from_text.assert_called_once()

    def test_restore_module_backup_delegates_to_service(self):
        """restore_module_backup should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_dev = MagicMock()
        mock_dev.restore_module_backup.return_value = {"success": True}
        with patch.dict(server.restore_module_backup.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.restore_module_backup("modTest", "/tmp/bak/modTest.bas")
            assert result["success"] is True
            mock_dev.restore_module_backup.assert_called_once()


class TestFormBackupRestore:
    """Tests for form backup/restore tools."""

    def test_export_form_backup_delegates_to_service(self):
        """export_form_backup should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_dev = MagicMock()
        mock_dev.export_form_backup.return_value = {"success": True, "file_path": "/tmp/bak/frmTest.txt"}
        with patch.dict(server.export_form_backup.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.export_form_backup("frmTest", None)
            assert result["success"] is True
            mock_dev.export_form_backup.assert_called_once()

    def test_import_form_from_file_delegates_to_service(self):
        """import_form_from_file should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_dev = MagicMock()
        mock_dev.import_form_from_text.return_value = {"success": True}
        with patch.dict(server.import_form_from_file.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.import_form_from_file("frmTest", "/tmp/bak/frmTest.txt")
            assert result["success"] is True
            mock_dev.import_form_from_text.assert_called_once()

    def test_restore_form_backup_delegates_to_service(self):
        """restore_form_backup should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_conn.adapter
        mock_dev = MagicMock()
        mock_dev.restore_form_backup.return_value = {"success": True}
        with patch.dict(server.restore_form_backup.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.restore_form_backup("frmTest", "/tmp/bak/frmTest.txt")
            assert result["success"] is True
            mock_dev.restore_form_backup.assert_called_once()


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
        with patch.dict(server.create_dev_copy.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
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
        with patch.dict(server.deploy_dev_copy.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.deploy_dev_copy(None)
            assert result["success"] is True
            mock_dev.deploy_dev_copy.assert_called_once()

    def test_discard_dev_copy_delegates_to_service(self):
        """discard_dev_copy should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev = MagicMock()
        mock_dev.discard_dev_copy.return_value = {"success": True}
        with patch.dict(server.discard_dev_copy.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.discard_dev_copy(None)
            assert result["success"] is True
            mock_dev.discard_dev_copy.assert_called_once()

    def test_get_dev_copy_status_delegates_to_service(self):
        """get_dev_copy_status should delegate to dev_copy_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev = MagicMock()
        mock_dev.get_dev_copy_status.return_value = {"success": True, "exists": True}
        with patch.dict(server.get_dev_copy_status.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev):
            result = server.get_dev_copy_status(None)
            assert result["success"] is True
            mock_dev.get_dev_copy_status.assert_called_once()
