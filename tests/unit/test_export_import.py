"""Tests for DevCopyService text export/import pipeline (Phase 2).

Covers:
- export_module_backup: exports VBA module as .bas file
- import_module_from_text: imports from .bas (deletes existing, creates new if absent)
- restore_module_backup: restores from .bas backup
- export_form_backup: exports form as .txt
- import_form_from_text: imports from .txt (deletes existing)
- restore_form_backup: restores from .txt backup
"""
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from ms_access_mcp.services.dev_copy_service import DevCopyService


class TestExportModuleBackup:
    """Tests for export_module_backup()."""

    def test_export_module_backup_happy_path(self, tmp_path):
        """export_module_backup() creates .bas file with module code."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.export_module_to_text.return_value = "Sub Hello()\n    MsgBox \"Hello\"\nEnd Sub"
        mock_adapter.get_vba_code.return_value = "Sub Hello()\n    MsgBox \"Hello\"\nEnd Sub"

        result = service.export_module_backup(mock_adapter, "mod_funcs")

        assert result["success"] is True
        assert result["module_name"] == "mod_funcs"
        assert ".bas" in result["backup_path"]
        assert os.path.exists(result["backup_path"])
        with open(result["backup_path"]) as f:
            content = f.read()
        assert "Sub Hello()" in content

    def test_export_module_backup_creates_backup_dir(self, tmp_path):
        """export_module_backup() creates the backups subdirectory if missing."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.export_module_to_text.return_value = "Function Test()\nEnd Function"

        result = service.export_module_backup(mock_adapter, "mod_test")

        backups_dir = os.path.join(str(tmp_path), "backups")
        assert os.path.isdir(backups_dir)

    def test_export_module_backup_missing_module(self, tmp_path):
        """export_module_backup() returns error when module not found."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.export_module_to_text.return_value = ""

        result = service.export_module_backup(mock_adapter, "nonexistent_mod")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_export_module_backup_custom_backup_dir(self, tmp_path):
        """export_module_backup() uses custom backup_dir when provided."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        custom_dir = str(tmp_path / "custom_backups")
        mock_adapter = MagicMock()
        mock_adapter.export_module_to_text.return_value = "Function Custom()\nEnd Function"

        result = service.export_module_backup(mock_adapter, "mod_custom", backup_dir=custom_dir)

        assert result["success"] is True
        assert custom_dir in result["backup_path"]


class TestImportModuleFromText:
    """Tests for import_module_from_text()."""

    def test_import_module_from_text_deletes_and_recreates(self, tmp_path):
        """import_module_from_text() deletes existing module then imports from .bas."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        # Create a .bas file to import
        bas_file = tmp_path / "mod_funcs.bas"
        bas_file.write_text("Sub Updated()\n    MsgBox \"Updated\"\nEnd Sub", encoding="utf-8")

        mock_adapter = MagicMock()
        mock_adapter.export_module_to_text.return_value = "Sub Updated()\n    MsgBox \"Updated\"\nEnd Sub"

        # Module exists
        mock_adapter.get_vba_code.return_value = "Original code"

        result = service.import_module_from_text(mock_adapter, "mod_funcs", str(bas_file))

        assert result["success"] is True
        assert result["module_name"] == "mod_funcs"
        mock_adapter.delete_module.assert_called_once_with("mod_funcs")
        mock_adapter.set_vba_code.assert_called_once()

    def test_import_module_from_text_creates_new_module(self, tmp_path):
        """import_module_from_text() CREATES a new module if it doesn't exist."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        bas_file = tmp_path / "brand_new_mod.bas"
        bas_file.write_text("Sub BrandNew()\n    MsgBox \"New\"\nEnd Sub", encoding="utf-8")

        mock_adapter = MagicMock()
        # Module does not exist
        mock_adapter.get_vba_code.return_value = ""

        result = service.import_module_from_text(mock_adapter, "brand_new_mod", str(bas_file))

        assert result["success"] is True
        # delete_module should NOT be called for a new module
        mock_adapter.delete_module.assert_not_called()
        mock_adapter.set_vba_code.assert_called_once()

    def test_import_module_from_text_file_not_found(self, tmp_path):
        """import_module_from_text() returns error when file missing (NO delete)."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = "Existing code"

        result = service.import_module_from_text(
            mock_adapter, "mod_funcs", "/tmp/nonexistent/path.mod"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()
        # Must NOT delete original when file is missing
        mock_adapter.delete_module.assert_not_called()

    def test_import_module_from_text_validates_before_delete(self, tmp_path):
        """File existence is validated BEFORE any delete operation."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = "Existing code"
        # File does NOT exist
        missing_file = tmp_path / "does_not_exist.bas"

        result = service.import_module_from_text(mock_adapter, "mod_funcs", str(missing_file))

        assert result["success"] is False
        # delete_module must never be called when the source file is missing
        mock_adapter.delete_module.assert_not_called()


class TestRestoreModuleBackup:
    """Tests for restore_module_backup()."""

    def test_restore_module_backup_delegates_to_import(self, tmp_path):
        """restore_module_backup() delegates to import_module_from_text with backup path."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        backup_path = tmp_path / "mod_funcs_backup.bas"
        backup_path.write_text("Sub Restored()\nEnd Sub", encoding="utf-8")

        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = "Old code"

        with patch.object(service, "import_module_from_text") as mock_import:
            mock_import.return_value = {"success": True, "module_name": "mod_funcs"}

            result = service.restore_module_backup(mock_adapter, "mod_funcs", str(backup_path))

            assert result["success"] is True
            mock_import.assert_called_once_with(mock_adapter, "mod_funcs", str(backup_path))


class TestExportFormBackup:
    """Tests for export_form_backup()."""

    def test_export_form_backup_happy_path(self, tmp_path):
        """export_form_backup() creates .txt file with form data."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.export_form_to_text.return_value = "FormData: TestForm\nProp: Value"

        result = service.export_form_backup(mock_adapter, "TestForm")

        assert result["success"] is True
        assert result["form_name"] == "TestForm"
        assert ".txt" in result["backup_path"]
        assert os.path.exists(result["backup_path"])

    def test_export_form_backup_missing_form(self, tmp_path):
        """export_form_backup() returns error when form not found."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.export_form_to_text.return_value = ""

        result = service.export_form_backup(mock_adapter, "nonexistent_form")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_export_form_backup_custom_backup_dir(self, tmp_path):
        """export_form_backup() uses custom backup_dir when provided."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        custom_dir = str(tmp_path / "custom_forms")
        mock_adapter = MagicMock()
        mock_adapter.export_form_to_text.return_value = "Form: CustomForm"

        result = service.export_form_backup(mock_adapter, "CustomForm", backup_dir=custom_dir)

        assert result["success"] is True
        assert custom_dir in result["backup_path"]


class TestImportFormFromText:
    """Tests for import_form_from_text()."""

    def test_import_form_from_text_deletes_and_imports(self, tmp_path):
        """import_form_from_text() deletes existing form then imports from .txt."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        txt_file = tmp_path / "TestForm.txt"
        txt_file.write_text("FormData: UpdatedForm\nProp: NewValue", encoding="utf-8")

        mock_adapter = MagicMock()
        mock_adapter.form_exists.return_value = True
        mock_adapter.export_form_to_text.return_value = "FormData: UpdatedForm"

        result = service.import_form_from_text(mock_adapter, "TestForm", str(txt_file))

        assert result["success"] is True
        mock_adapter.delete_form.assert_called_once_with("TestForm")
        mock_adapter.import_form_from_text.assert_called_once()

    def test_import_form_from_text_file_not_found(self, tmp_path):
        """import_form_from_text() returns error when file missing (NO delete)."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.form_exists.return_value = True

        result = service.import_form_from_text(
            mock_adapter, "TestForm", "/tmp/nonexistent/form.txt"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()
        mock_adapter.delete_form.assert_not_called()

    def test_import_form_from_text_validates_before_delete(self, tmp_path):
        """File existence is validated BEFORE any delete operation."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_adapter = MagicMock()
        mock_adapter.form_exists.return_value = True
        missing_file = tmp_path / "does_not_exist.txt"

        result = service.import_form_from_text(mock_adapter, "TestForm", str(missing_file))

        assert result["success"] is False
        mock_adapter.delete_form.assert_not_called()


class TestRestoreFormBackup:
    """Tests for restore_form_backup()."""

    def test_restore_form_backup_delegates_to_import(self, tmp_path):
        """restore_form_backup() delegates to import_form_from_text with backup path."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        backup_path = tmp_path / "TestForm_backup.txt"
        backup_path.write_text("FormData: RestoredForm", encoding="utf-8")

        mock_adapter = MagicMock()
        mock_adapter.form_exists.return_value = True

        with patch.object(service, "import_form_from_text") as mock_import:
            mock_import.return_value = {"success": True, "form_name": "TestForm"}

            result = service.restore_form_backup(mock_adapter, "TestForm", str(backup_path))

            assert result["success"] is True
            mock_import.assert_called_once_with(mock_adapter, "TestForm", str(backup_path))