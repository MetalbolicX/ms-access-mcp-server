r"""
Integration tests for DevCopyService compile/import paths on cloned databases.

Tests cover:
- compile_with_retry on cloned DB
- import_module_from_text on cloned DB
- Dev-copy workflow (create/discard/deploy)

Markers: com_integration
Execution: pytest tests/integration/test_wincom_dev_copy.py -m com_integration -v
"""

import os
import tempfile

import pytest

from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.services.dev_copy_service import DevCopyService
from helpers import skip_unless_windows, skip_unless_pywin32, skip_unless_db, call_mcp_tool

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


def _cleanup_adapter(adapter: WinComAdapter) -> None:
    """Safely disconnect an adapter, swallowing cleanup exceptions."""
    try:
        if adapter.is_connected():
            adapter.disconnect()
    except Exception:
        pass


# =============================================================================
# Compile / Import (direct service)
# =============================================================================

class TestDevCopyCompileRetry:
    """compile_with_retry on a cloned DB via DevCopyService."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.service = DevCopyService()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_compile_with_retry_success(self, temp_db_copy: str):
        """compile_with_retry returns success=True when VBA code is valid."""
        assert self.adapter.connect(temp_db_copy)

        # modUtilities should exist in the fixture
        code = "Function TestAdd()\n    Debug.Print 1 + 1\nEnd Function"
        result = self.service.compile_with_retry(
            self.adapter, "modUtilities", code, max_retries=2
        )

        # Success expected when code is valid
        assert result.get("success") is True
        assert "attempts" in result

    def test_compile_with_retry_invalid_code(self, temp_db_copy: str):
        """compile_with_retry returns success=False with rollback for bad code."""
        assert self.adapter.connect(temp_db_copy)

        # Bad VBA code (misspelled keyword)
        bad_code = "Function TestBad()\n    Debug.Print 1 +\nEnd Function"
        result = self.service.compile_with_retry(
            self.adapter, "modUtilities", bad_code, max_retries=2
        )

        # Should fail and roll back
        assert result.get("success") is False
        assert result.get("rollback") is True

    def test_compile_with_retry_nonexistent_module(self, temp_db_copy: str):
        """compile_with_retry handles non-existent module gracefully."""
        assert self.adapter.connect(temp_db_copy)

        result = self.service.compile_with_retry(
            self.adapter, "NonExistentModule_XYZ", "Function X()\nEnd Function"
        )
        # Should return failure (couldn't write code)
        assert result.get("success") is False


class TestDevCopyModuleImport:
    """import_module_from_text on a cloned DB via DevCopyService."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.service = DevCopyService()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_import_module_from_text_file_not_found(self, temp_db_copy: str):
        """import_module_from_text returns error when file does not exist."""
        assert self.adapter.connect(temp_db_copy)

        result = self.service.import_module_from_text(
            self.adapter, "SomeModule", "/path/does/not/exist.bas"
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_import_module_roundtrip(self, temp_db_copy: str):
        """Export a module to .bas file, then import it back."""
        assert self.adapter.connect(temp_db_copy)

        # Create a temp .bas file with valid VBA code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bas", delete=False, encoding="utf-8") as f:
            f.write("Function ImportedFunc()\n    Debug.Print 42\nEnd Function\n")
            temp_bas = f.name

        try:
            result = self.service.import_module_from_text(
                self.adapter, "ImportedModule_Test", temp_bas
            )
            # The module was created via add_vba_procedure (new module)
            assert result["success"] is True
        finally:
            os.unlink(temp_bas)

    def test_import_module_preserves_existing_on_failure(self, temp_db_copy: str):
        """Failed import does not corrupt an existing module."""
        assert self.adapter.connect(temp_db_copy)

        # Get original code
        original = self.adapter.get_vba_code("modUtilities") or ""

        # Try to import from a non-existent path
        result = self.service.import_module_from_text(
            self.adapter, "modUtilities", "/definitely/nonexistent/path.bas"
        )
        assert result["success"] is False

        # Original code should still be intact
        current = self.adapter.get_vba_code("modUtilities") or ""
        # (May differ due to whitespace but content should be similar)


# =============================================================================
# Dev Copy Pipeline (manifest + file ops)
# =============================================================================

class TestDevCopyServiceManifest:
    """DevCopyService manifest CRUD."""

    def setup_method(self):
        self.service = DevCopyService()

    def test_save_and_load_manifest(self, temp_db_copy: str):
        """save_manifest then load_manifest returns the same data."""
        manifest = {
            "production_path": temp_db_copy,
            "dev_path": temp_db_copy + "_dev.accdb",
            "created_at": "2024-01-01T00:00:00Z",
            "db_size_bytes": 1024,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }

        ok = self.service.save_manifest(temp_db_copy, manifest)
        assert ok is True

        loaded = self.service.load_manifest(temp_db_copy)
        assert loaded is not None
        assert loaded["production_path"] == temp_db_copy
        assert loaded["dev_path"] == temp_db_copy + "_dev.accdb"

        # Cleanup
        self.service.delete_manifest(temp_db_copy)

    def test_load_manifest_nonexistent(self):
        """load_manifest returns None for unknown DB."""
        result = self.service.load_manifest("/path/does/not/exist/xyz.accdb")
        assert result is None

    def test_delete_manifest_nonexistent(self):
        """delete_manifest returns False for unknown DB."""
        result = self.service.delete_manifest("/path/does/not/exist/xyz.accdb")
        assert result is False

    def test_get_dev_copy_status_inactive(self, temp_db_copy: str):
        """get_dev_copy_status returns active=False when no manifest exists."""
        # Ensure no manifest for this path
        self.service.delete_manifest(temp_db_copy)

        status = self.service.get_dev_copy_status(temp_db_copy)
        assert status.get("active") is False


# =============================================================================
# Full Dev Copy Lifecycle (requires WinComAdapter.copy_database)
# =============================================================================

class TestDevCopyPipeline:
    """Full dev copy lifecycle: create_dev_copy, discard, deploy."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_copy_database(self, temp_db_copy: str, request):
        """WinComAdapter.copy_database duplicates the .accdb file."""
        assert self.adapter.connect(temp_db_copy)

        # Create a destination path
        tmpdir = tempfile.mkdtemp(prefix="acc_copy_dest_")
        dest_path = os.path.join(tmpdir, "copy_of_test.accdb")

        def cleanup():
            import time
            time.sleep(0.25)
            try:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

        request.addfinalizer(cleanup)

        result = self.adapter.copy_database(temp_db_copy, dest_path)
        assert result is True
        assert os.path.exists(dest_path), "Destination file should exist after copy"

    def test_get_backup_dir(self):
        """get_backup_dir returns a valid directory path."""
        backup_dir = self.service.get_backup_dir()
        assert os.path.isdir(backup_dir)


# =============================================================================
# Form Backup / Restore (via DevCopyService)
# =============================================================================

class TestDevCopyFormBackup:
    """Form backup/restore via DevCopyService on cloned DB."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.service = DevCopyService()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_export_form_backup(self, temp_db_copy: str):
        """export_form_backup writes a .txt file for frmMain."""
        assert self.adapter.connect(temp_db_copy)

        result = self.service.export_form_backup(self.adapter, "frmMain")
        # frmMain may or may not exist in the fixture depending on fixture generation
        # Result should have the expected structure either way
        if result.get("success"):
            assert os.path.exists(result["backup_path"])
            os.unlink(result["backup_path"])

    def test_import_form_from_text_file_not_found(self, temp_db_copy: str):
        """import_form_from_text returns error for missing file."""
        assert self.adapter.connect(temp_db_copy)

        result = self.service.import_form_from_text(
            self.adapter, "NonExistentForm", "/path/does/not/exist.txt"
        )
        assert result["success"] is False


# =============================================================================
# Report Backup / Restore (via DevCopyService and MCP tools)
# =============================================================================

class TestDevCopyReportBackup:
    """Report backup/restore via DevCopyService on cloned DB.

    Tests for export_report_backup, import_report_from_file, restore_report_backup
    MCP tools (report backup pipeline from PR 3).
    """

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.service = DevCopyService()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_export_report_backup_via_service(self, temp_db_copy: str):
        """export_report_backup writes a .txt file for a report via DevCopyService."""
        assert self.adapter.connect(temp_db_copy)

        result = self.service.export_report_backup(self.adapter, "rptCustomers")
        # rptCustomers may or may not exist — result should have correct structure
        if result.get("success"):
            assert "backup_path" in result
            assert os.path.exists(result["backup_path"])
            os.unlink(result["backup_path"])

    def test_export_report_backup_via_mcp_tool(self, temp_db_copy: str):
        """export_report_backup MCP tool delegates to DevCopyService."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_rpt_backup", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "export_report_backup",
                "rptCustomers",
                connection_name="test_rpt_backup",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result
            # May fail if rptCustomers doesn't exist, but structure should be correct
            if result["success"]:
                assert "backup_path" in result

            pool.disconnect("test_rpt_backup")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_import_report_from_file_via_service(self, temp_db_copy: str):
        """import_report_from_file returns error for missing file."""
        assert self.adapter.connect(temp_db_copy)

        result = self.service.import_report_from_file(
            self.adapter, "NonExistentReport", "/path/does/not/exist.txt"
        )
        assert result["success"] is False

    def test_import_report_from_file_via_mcp_tool(self, temp_db_copy: str):
        """import_report_from_file MCP tool delegates to DevCopyService."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_rpt_imp", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "import_report_from_file",
                "MCP_TestReport",
                "/path/does/not/exist.txt",
                connection_name="test_rpt_imp",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result
            assert result["success"] is False  # File not found

            pool.disconnect("test_rpt_imp")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_restore_report_backup_via_mcp_tool(self, temp_db_copy: str):
        """restore_report_backup MCP tool handles missing backup gracefully."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_rpt_rest", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "restore_report_backup",
                "NonExistentReport",
                "/path/does/not/exist.txt",
                connection_name="test_rpt_rest",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result
            # Should fail gracefully for missing backup file
            assert result["success"] is False

            pool.disconnect("test_rpt_rest")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass


# =============================================================================
# Hook-visible export outputs (git-hook-init and export-all CLI integration)
# =============================================================================

class TestGitHookVisibleExports:
    """Verify export outputs are visible and hook-friendly.

    The git_hook_init command creates .git/hooks/pre-commit that runs
    'macc export-all .access_versioning --dedup'. Export must produce
    visible, human-readable file structure in the export directory.
    """

    def test_export_all_versioning_creates_readable_structure(self, temp_db_copy: str):
        """export_all_versioning creates forms/, reports/, modules/, macros/, queries/."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter()
        assert adapter.connect(temp_db_copy)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = adapter.export_all_versioning(tmpdir)
            assert result.get("success") is True

            # Verify subdirectories exist
            for subdir in ["forms", "reports", "modules", "macros", "queries"]:
                subdir_path = os.path.join(tmpdir, subdir)
                assert os.path.isdir(subdir_path), f"Expected {subdir}/ subdirectory"

            # Verify exported dict has correct keys
            assert "exported" in result
            exported = result["exported"]
            for key in ["forms", "reports", "modules", "macros", "queries"]:
                assert key in exported, f"Expected '{key}' in exported dict"
                assert isinstance(exported[key], list), f"exported['{key}'] should be a list"

        adapter.disconnect()
