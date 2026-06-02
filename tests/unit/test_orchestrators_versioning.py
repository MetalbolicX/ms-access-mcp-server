"""RED tests for VersioningOrchestrator.

These tests describe the expected API and behavior of VersioningOrchestrator.
They will FAIL until the orchestrator is implemented in Task 1.2.
"""
import pytest
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil


# =============================================================================
# Task 1.1 — RED: Failing tests for VersioningOrchestrator
# =============================================================================


class TestVersioningOrchestratorExportAll:
    """export_all returns standardized dict with success/error keys."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        self.mock_adapter.export_all_versioning.return_value = {
            "success": True,
            "exported": {"forms": 2, "modules": 1},
        }

    def test_returns_dict_with_success_and_error_keys(self):
        """Returns dict containing 'success' (bool) and 'error' (str|None)."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        with patch("ms_access_mcp.orchestrators.versioning.os.makedirs"):
            result = orch.export_all("/tmp/out", self.mock_adapter)

        assert "success" in result
        assert "error" in result
        assert isinstance(result["success"], bool)
        # error is None on success
        assert result["error"] is None

    def test_delegates_to_adapter_export_all_versioning(self):
        """export_all delegates to adapter.export_all_versioning with correct params."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        with patch("ms_access_mcp.orchestrators.versioning.os.makedirs"):
            orch.export_all("/tmp/out", self.mock_adapter, dedup=True, module_ext=".bas")

        self.mock_adapter.export_all_versioning.assert_called_once_with(
            "/tmp/out", dedup=True, module_ext=".bas"
        )

    def test_returns_success_true_when_adapter_succeeds(self):
        """On adapter success, orchestrator returns success=True."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        with patch("ms_access_mcp.orchestrators.versioning.os.makedirs"):
            result = orch.export_all("/tmp/out", self.mock_adapter)

        assert result["success"] is True
        assert result["error"] is None

    def test_returns_error_dict_when_not_connected(self):
        """Not-connected adapter → returns error dict (does not raise)."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.is_connected.return_value = False

        result = orch.export_all("/tmp/out", self.mock_adapter)

        assert result["success"] is False
        assert result["error"] is not None
        assert "not connected" in result["error"].lower()

    def test_returns_error_dict_when_adapter_raises(self):
        """Exception raised by adapter is caught and returned as error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.is_connected.return_value = True
        self.mock_adapter.export_all_versioning.side_effect = RuntimeError("COM error")

        with patch("ms_access_mcp.orchestrators.versioning.os.makedirs"):
            result = orch.export_all("/tmp/out", self.mock_adapter)

        assert result["success"] is False
        assert result["error"] == "COM error"


class TestVersioningOrchestratorImportAll:
    """import_all delegates to adapter.import_all_versioning."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        self.mock_adapter.import_all_versioning.return_value = {
            "success": True,
            "imported": 5,
        }

    def test_returns_standardized_dict(self):
        """Returns dict with success (bool) and error (str|None)."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        result = orch.import_all("/tmp/in", self.mock_adapter)

        assert "success" in result
        assert "error" in result
        assert isinstance(result["success"], bool)

    def test_delegates_to_adapter_import_all_versioning(self):
        """import_all delegates to adapter.import_all_versioning."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        orch.import_all("/tmp/in", self.mock_adapter)

        self.mock_adapter.import_all_versioning.assert_called_once_with("/tmp/in")

    def test_returns_error_dict_when_not_connected(self):
        """Not-connected adapter → returns error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.is_connected.return_value = False

        result = orch.import_all("/tmp/in", self.mock_adapter)

        assert result["success"] is False
        assert "not connected" in result["error"].lower()

    def test_returns_error_dict_when_adapter_raises(self):
        """Exception from adapter is returned as error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.is_connected.return_value = True
        self.mock_adapter.import_all_versioning.side_effect = ValueError("Import failed")

        result = orch.import_all("/tmp/in", self.mock_adapter)

        assert result["success"] is False
        assert result["error"] == "Import failed"


class TestVersioningOrchestratorCompare:
    """compare delegates to adapter.compare_versioning."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        self.mock_adapter.compare_versioning.return_value = {
            "new": [],
            "missing": [],
            "changed": [],
            "unchanged": [],
        }

    def test_returns_standardized_dict(self):
        """Returns dict with success (bool) and error (str|None)."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        result = orch.compare("/tmp/compare", self.mock_adapter)

        assert "success" in result
        assert "error" in result

    def test_delegates_to_adapter_compare_versioning(self):
        """compare delegates to adapter.compare_versioning."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        orch.compare("/tmp/compare", self.mock_adapter)

        self.mock_adapter.compare_versioning.assert_called_once_with("/tmp/compare")

    def test_returns_error_dict_when_not_connected(self):
        """Not-connected adapter → returns error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.is_connected.return_value = False

        result = orch.compare("/tmp/compare", self.mock_adapter)

        assert result["success"] is False
        assert "not connected" in result["error"].lower()


class TestVersioningOrchestratorExportSchemaDDL:
    """export_schema_ddl delegates to adapter.export_schema_ddl."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        self.mock_adapter.export_schema_ddl.return_value = {
            "success": True,
            "ddl_tables": "/tmp/ddl/tables.sql",
        }

    def test_returns_standardized_dict(self):
        """Returns dict with success (bool) and error (str|None)."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        result = orch.export_schema_ddl("/tmp/ddl", self.mock_adapter)

        assert "success" in result
        assert "error" in result

    def test_delegates_to_adapter_export_schema_ddl(self):
        """export_schema_ddl delegates to adapter.export_schema_ddl."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        orch.export_schema_ddl("/tmp/ddl", self.mock_adapter)

        self.mock_adapter.export_schema_ddl.assert_called_once_with("/tmp/ddl")

    def test_returns_error_dict_when_not_connected(self):
        """Not-connected adapter → returns error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.is_connected.return_value = False

        result = orch.export_schema_ddl("/tmp/ddl", self.mock_adapter)

        assert result["success"] is False
        assert "not connected" in result["error"].lower()


# =============================================================================
# Task 1.3 — TRIANGULATE: Additional tests for backup/restore, git hook, errors
# =============================================================================


class TestVersioningOrchestratorBackupRestoreMethods:
    """Module/form/report backup and restore methods use DevCopyService."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True

    def test_export_module_backup_delegates_to_dev_copy_service(self):
        """export_module_backup delegates to DevCopyService.export_module_backup."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        mock_service = MagicMock()
        mock_service.export_module_backup.return_value = {
            "success": True,
            "backup_path": "/tmp/backup/modTest.bas",
            "module_name": "modTest",
        }

        with patch("ms_access_mcp.orchestrators.versioning.DevCopyService", return_value=mock_service):
            result = orch.export_module_backup("modTest", self.mock_adapter, "/tmp/backup")

        mock_service.export_module_backup.assert_called_once()
        assert result["success"] is True

    def test_export_module_backup_returns_error_when_not_connected(self):
        """Not-connected adapter → returns error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.is_connected.return_value = False

        result = orch.export_module_backup("modTest", self.mock_adapter)

        assert result["success"] is False
        assert "not connected" in result["error"].lower()

    def test_import_module_from_text_delegates_to_dev_copy_service(self):
        """import_module_from_text delegates to DevCopyService.import_module_from_text."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        mock_service = MagicMock()
        mock_service.import_module_from_text.return_value = {
            "success": True,
            "module_name": "modTest",
        }

        with patch("ms_access_mcp.orchestrators.versioning.DevCopyService", return_value=mock_service):
            result = orch.import_module_from_text("modTest", "/tmp/modTest.bas", self.mock_adapter)

        mock_service.import_module_from_text.assert_called_once()
        assert result["success"] is True

    def test_export_form_backup_delegates_to_dev_copy_service(self):
        """export_form_backup delegates to DevCopyService.export_form_backup."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        mock_service = MagicMock()
        mock_service.export_form_backup.return_value = {
            "success": True,
            "backup_path": "/tmp/backup/formTest.txt",
            "form_name": "formTest",
        }

        with patch("ms_access_mcp.orchestrators.versioning.DevCopyService", return_value=mock_service):
            result = orch.export_form_backup("formTest", self.mock_adapter, "/tmp/backup")

        mock_service.export_form_backup.assert_called_once()
        assert result["success"] is True

    def test_restore_form_backup_delegates_to_dev_copy_service(self):
        """restore_form_backup delegates to DevCopyService.restore_form_backup."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        mock_service = MagicMock()
        mock_service.restore_form_backup.return_value = {"success": True, "form_name": "formTest"}

        with patch("ms_access_mcp.orchestrators.versioning.DevCopyService", return_value=mock_service):
            result = orch.restore_form_backup("formTest", "/tmp/backup/formTest.txt", self.mock_adapter)

        mock_service.restore_form_backup.assert_called_once()
        assert result["success"] is True

    def test_export_report_backup_delegates_to_dev_copy_service(self):
        """export_report_backup delegates to DevCopyService.export_report_backup."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        mock_service = MagicMock()
        mock_service.export_report_backup.return_value = {
            "success": True,
            "backup_path": "/tmp/backup/reportTest.txt",
            "report_name": "reportTest",
        }

        with patch("ms_access_mcp.orchestrators.versioning.DevCopyService", return_value=mock_service):
            result = orch.export_report_backup("reportTest", self.mock_adapter, "/tmp/backup")

        mock_service.export_report_backup.assert_called_once()
        assert result["success"] is True

    def test_import_report_from_file_delegates_to_dev_copy_service(self):
        """import_report_from_file delegates to DevCopyService.import_report_from_file."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        mock_service = MagicMock()
        mock_service.import_report_from_file.return_value = {"success": True, "report_name": "reportTest"}

        with patch("ms_access_mcp.orchestrators.versioning.DevCopyService", return_value=mock_service):
            result = orch.import_report_from_file("reportTest", "/tmp/backup/reportTest.txt", self.mock_adapter)

        mock_service.import_report_from_file.assert_called_once()
        assert result["success"] is True

    def test_restore_report_backup_delegates_to_dev_copy_service(self):
        """restore_report_backup delegates to DevCopyService.restore_report_backup."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        mock_service = MagicMock()
        mock_service.restore_report_backup.return_value = {"success": True, "report_name": "reportTest"}

        with patch("ms_access_mcp.orchestrators.versioning.DevCopyService", return_value=mock_service):
            result = orch.restore_report_backup("reportTest", "/tmp/backup/reportTest.txt", self.mock_adapter)

        mock_service.restore_report_backup.assert_called_once()
        assert result["success"] is True


class TestVersioningOrchestratorInstallGitHook:
    """install_git_hook creates a pre-commit hook file."""

    def test_creates_pre_commit_hook_file(self):
        """install_git_hook creates the .git/hooks/pre-commit file."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake .git/hooks directory structure
            hooks_dir = os.path.join(tmpdir, ".git", "hooks")
            os.makedirs(hooks_dir, exist_ok=True)

            result = orch.install_git_hook(tmpdir)

            assert result["success"] is True
            hook_path = os.path.join(hooks_dir, "pre-commit")
            assert os.path.exists(hook_path)
            with open(hook_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "macc export-all --dedup" in content

    def test_returns_error_for_missing_repo_path(self):
        """Non-existent repo path → returns error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        result = orch.install_git_hook("Z:\\nonexistent\\path\\to\\repo")

        assert result["success"] is False
        assert result["error"] is not None

    def test_returns_error_when_cannot_create_hooks_dir(self):
        """Cannot create hooks directory → returns error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        # Force an OSError by patching os.makedirs to raise
        with patch("ms_access_mcp.orchestrators.versioning.os.makedirs", side_effect=OSError("Access denied")):
            result = orch.install_git_hook("C:\\tmp\\fake_repo")

        assert result["success"] is False
        assert result["error"] is not None


class TestVersioningOrchestratorExceptionWrapping:
    """Adapter exceptions are caught and returned as error dicts."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True

    def test_value_error_from_adapter_becomes_error_dict(self):
        """Adapter raises ValueError → orchestrator returns error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.export_all_versioning.side_effect = ValueError("Invalid path")

        with patch.object(self.mock_adapter, "is_connected", return_value=True):
            with patch("ms_access_mcp.orchestrators.versioning.os.makedirs"):
                result = orch.export_all("/tmp/out", self.mock_adapter)

        assert result["success"] is False
        assert "Invalid path" in result["error"]

    def test_generic_exception_from_adapter_becomes_error_dict(self):
        """Adapter raises Exception → orchestrator returns error dict."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.compare_versioning.side_effect = RuntimeError("Unexpected error")

        with patch.object(self.mock_adapter, "is_connected", return_value=True):
            result = orch.compare("/tmp/compare", self.mock_adapter)

        assert result["success"] is False
        assert "Unexpected error" in result["error"]


class TestVersioningOrchestratorAllMethodsStandardized:
    """Verify all methods return standardized key set."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True

    def test_export_all_has_standard_keys(self):
        """export_all returns dict with success and error keys."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.export_all_versioning.return_value = {"success": True, "exported": {}}

        with patch("ms_access_mcp.orchestrators.versioning.os.makedirs"):
            result = orch.export_all("/tmp/out", self.mock_adapter)

        assert "success" in result
        assert "error" in result
        assert isinstance(result["success"], bool)

    def test_import_all_has_standard_keys(self):
        """import_all returns dict with success and error keys."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.import_all_versioning.return_value = {"success": True, "imported": {}}

        result = orch.import_all("/tmp/in", self.mock_adapter)

        assert "success" in result
        assert "error" in result

    def test_compare_has_standard_keys(self):
        """compare returns dict with success and error keys."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.compare_versioning.return_value = {"success": True, "new": [], "missing": [], "changed": [], "unchanged": []}

        result = orch.compare("/tmp/compare", self.mock_adapter)

        assert "success" in result
        assert "error" in result

    def test_export_schema_ddl_has_standard_keys(self):
        """export_schema_ddl returns dict with success and error keys."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        self.mock_adapter.export_schema_ddl.return_value = {"success": True, "ddl_tables": "/tmp/tables.sql"}

        result = orch.export_schema_ddl("/tmp/ddl", self.mock_adapter)

        assert "success" in result
        assert "error" in result

    def test_install_git_hook_has_standard_keys(self):
        """install_git_hook returns dict with success and error keys."""
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator

        orch = VersioningOrchestrator()
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = os.path.join(tmpdir, ".git", "hooks")
            os.makedirs(hooks_dir, exist_ok=True)
            result = orch.install_git_hook(tmpdir)

        assert "success" in result
        assert "error" in result
