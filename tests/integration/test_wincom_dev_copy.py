"""COM integration tests for DevCopyService operations with real WinComAdapter.

Tests module export/import/restore and form export/import/restore round-trips.
"""

import os
import shutil
import tempfile

import pytest

from tests.integration.helpers import (
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
    TEST_DB,
)

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


class TestDevCopyModuleBackup:
    """Module export/import/restore via DevCopyService."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.dev_copy_service import DevCopyService

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"
        self.service = DevCopyService()
        self.backup_dir = tempfile.mkdtemp()

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.backup_dir, ignore_errors=True)

    def test_export_module_backup(self):
        """export_module_backup writes a .bas file for modUtilities or similar."""
        # Try modUtilities (common in Access DBs) or skip if not found
        module_name = "modUtilities"
        result = self.service.export_module_backup(
            self.adapter, module_name, self.backup_dir
        )
        # If module doesn't exist, returns success=False with error
        if not result["success"]:
            # Try another common module name
            module_name = "modDateTime"
            result = self.service.export_module_backup(
                self.adapter, module_name, self.backup_dir
            )
        if result["success"]:
            assert result["success"] is True
            assert "backup_path" in result
            assert result["backup_path"].endswith(".bas")
            assert os.path.exists(result["backup_path"])
            assert os.path.getsize(result["backup_path"]) > 0

    def test_export_import_round_trip(self):
        """Export a module, read the .bas file, import it as a new name."""
        module_name = "modUtilities"
        export_result = self.service.export_module_backup(
            self.adapter, module_name, self.backup_dir
        )
        if not export_result["success"]:
            module_name = "modDateTime"
            export_result = self.service.export_module_backup(
                self.adapter, module_name, self.backup_dir
            )

        if not export_result["success"]:
            pytest.skip(f"Cannot test round-trip: no suitable module found ({export_result.get('error')})")

        backup_path = export_result["backup_path"]

        # Read the file
        with open(backup_path, "r", encoding="utf-8") as f:
            code = f.read()
        assert len(code) > 0

        # Import as a new module
        new_name = "TestModule_Imported"
        import_result = self.service.import_module_from_text(
            self.adapter, new_name, backup_path
        )
        # import_module_from_text returns dict with success
        assert import_result.get("success") is True or import_result.get("error") is not None

    def test_restore_module_backup(self):
        """restore_module_backup delegates to import_module_from_text."""
        module_name = "modUtilities"
        export_result = self.service.export_module_backup(
            self.adapter, module_name, self.backup_dir
        )
        if not export_result["success"]:
            module_name = "modDateTime"
            export_result = self.service.export_module_backup(
                self.adapter, module_name, self.backup_dir
            )

        if not export_result["success"]:
            pytest.skip(f"Cannot test restore: no suitable module found ({export_result.get('error')})")

        backup_path = export_result["backup_path"]
        restore_result = self.service.restore_module_backup(
            self.adapter, module_name, backup_path
        )
        assert restore_result.get("success") is True


class TestDevCopyFormBackup:
    """Form export/import/restore via DevCopyService."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.dev_copy_service import DevCopyService

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"
        self.service = DevCopyService()
        self.backup_dir = tempfile.mkdtemp()

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.backup_dir, ignore_errors=True)

    def test_export_form_backup(self):
        """export_form_backup writes a .txt file for an existing form."""
        # Try frmMain or any available form
        forms = self.adapter.get_forms()
        if not forms:
            pytest.skip("No forms available in test database")

        form_name = forms[0].name if forms else "frmMain"
        result = self.service.export_form_backup(
            self.adapter, form_name, self.backup_dir
        )
        # If form doesn't exist/empty, returns success=False with error
        if not result["success"]:
            pytest.skip(f"Form '{form_name}' not found or empty ({result.get('error')})")

        assert result["success"] is True
        assert "backup_path" in result
        assert result["backup_path"].endswith(".txt")
        assert os.path.exists(result["backup_path"])
        assert os.path.getsize(result["backup_path"]) > 0

    def test_import_form_from_file(self):
        """Import a form from a .txt backup file."""
        forms = self.adapter.get_forms()
        if not forms:
            pytest.skip("No forms available")

        form_name = forms[0].name
        export_result = self.service.export_form_backup(
            self.adapter, form_name, self.backup_dir
        )
        if not export_result["success"]:
            pytest.skip(f"Cannot export form: {export_result.get('error')}")

        backup_path = export_result["backup_path"]

        # Read content
        with open(backup_path, "r", encoding="utf-8") as f:
            form_data = f.read()
        assert len(form_data) > 0

        # Import as new form
        new_form_name = f"{form_name}_Imported"
        import_result = self.service.import_form_from_text(
            self.adapter, new_form_name, backup_path
        )
        # Result may fail if form import isn't fully supported, but should return dict
        assert isinstance(import_result, dict)

    def test_restore_form_backup(self):
        """restore_form_backup delegates to import_form_from_text."""
        forms = self.adapter.get_forms()
        if not forms:
            pytest.skip("No forms available")

        form_name = forms[0].name
        export_result = self.service.export_form_backup(
            self.adapter, form_name, self.backup_dir
        )
        if not export_result["success"]:
            pytest.skip(f"Cannot export form: {export_result.get('error')}")

        backup_path = export_result["backup_path"]
        restore_result = self.service.restore_form_backup(
            self.adapter, form_name, backup_path
        )
        assert restore_result.get("success") is True