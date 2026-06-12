"""BackupService — object-level backup/restore for VBA modules, forms, and reports.

Handles:
- Export/import templates for serializing Access objects to text files
- Module backup/restore with compile-and-retry logic
- Form and report backup/restore

Adapter type hints use the narrowest applicable protocols (IVbaAdapter for
modules, IFormAdapter for forms/reports). The composite IUiAdapter and the
narrower IVersioningAdapter are also imported for forward-compat and tests.
"""
import os
from typing import Callable, Optional

from ..adapters.interfaces import (
    IFormAdapter,
    IUiAdapter,  # noqa: F401  (composite alias — re-exported for tests)
    IVbaAdapter,
    IVersioningAdapter,  # noqa: F401  (re-exported for tests)
)


class BackupService:
    """Manages object-level backup/restore for VBA modules, forms, and reports.

    Uses a shared backup base directory that should match the one used by
    DevCopyService for consistent paths.
    """

    def __init__(self, backup_base: str) -> None:
        self._backup_base = backup_base
        os.makedirs(self._backup_base, exist_ok=True)

    # ========================================================================
    # Backup Directory
    # ========================================================================

    def get_backup_dir(self) -> str:
        """Get the default backup directory, creating it if needed.

        Returns:
            Path to {backup_base}/backups/
        """
        backup_dir = os.path.join(self._backup_base, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir

    # ========================================================================
    # Text Export/Import Pipeline — shared templates
    # ========================================================================

    def _object_file_path(self, obj_name: str, backup_dir: str | None, ext: str) -> str:
        """Build backup file path for any object type."""
        target_dir = backup_dir if backup_dir else self.get_backup_dir()
        safe_name = obj_name.replace(" ", "_")
        return os.path.join(target_dir, f"{safe_name}{ext}")

    def _export_object(
        self,
        adapter_func: Callable[[str], str],
        obj_name: str,
        backup_dir: str | None,
        name_key: str,
        ext: str,
    ) -> dict:
        """Template for exporting any Access object to a text file.

        Args:
            adapter_func: adapter.export_xxx_to_text callable
            obj_name: Name of the database object
            backup_dir: Optional custom backup directory
            name_key: Key for the object name in result dict (e.g. "form_name", "module_name")
            ext: File extension (".bas", ".txt")
        """
        content = adapter_func(obj_name)
        if not content:
            return {
                "success": False,
                "error": f"Object '{obj_name}' not found or empty",
                name_key: obj_name,
            }

        backup_path = self._object_file_path(obj_name, backup_dir, ext)

        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)

        try:
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(content)
            file_size = os.path.getsize(backup_path)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to write backup file: {e}",
                name_key: obj_name,
            }

        return {
            "success": True,
            "backup_path": backup_path,
            name_key: obj_name,
            "file_size_bytes": file_size,
        }

    def _import_object(
        self,
        adapter_func: Callable[[str, str], bool],
        exists_check: Callable[[str], bool],
        delete_func: Callable[[str], bool],
        obj_name: str,
        file_path: str,
        name_key: str,
    ) -> dict:
        """Template for importing any Access object from a text file.

        Args:
            adapter_func: adapter.import_xxx_from_text callable
            exists_check: adapter.xxx_exists callable
            delete_func: adapter.delete_xxx callable
            obj_name: Name of the database object
            file_path: Path to the text file
            name_key: Key for the object name in result dict
        """
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                name_key: obj_name,
            }

        existed = exists_check(obj_name)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read file: {e}",
                name_key: obj_name,
            }

        if existed:
            if not delete_func(obj_name):
                return {
                    "success": False,
                    "error": f"Failed to delete existing object '{obj_name}'",
                    name_key: obj_name,
                }

        if not adapter_func(obj_name, data):
            return {
                "success": False,
                "error": f"Failed to import '{obj_name}'",
                name_key: obj_name,
            }

        return {"success": True, name_key: obj_name}

    # ========================================================================
    # Text Export/Import Pipeline — VBA Modules
    # ========================================================================

    def export_module_backup(
        self, adapter: IVbaAdapter, module_name: str, backup_dir: str | None = None
    ) -> dict:
        """Export a VBA module's code to a .bas file.

        Args:
            adapter: Access adapter (WinComAdapter)
            module_name: Name of the VBA module to export
            backup_dir: Optional custom backup directory

        Returns:
            dict with success, backup_path, module_name, file_size_bytes
        """
        return self._export_object(
            adapter.export_module_to_text,
            module_name,
            backup_dir,
            "module_name",
            ".bas",
        )

    def import_module_from_text(
        self, adapter: IVbaAdapter, module_name: str, file_path: str
    ) -> dict:
        """Import a VBA module from a .bas text file.

        Validates file exists BEFORE deleting the original module.
        Creates a NEW module if it doesn't already exist.

        Args:
            adapter: Access adapter (WinComAdapter)
            module_name: Name of the module to import
            file_path: Path to the .bas file

        Returns:
            dict with success, module_name, and error if failed
        """
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "module_name": module_name,
            }

        # Check if module already exists
        existing_code = adapter.get_vba_code(module_name)
        module_existed = bool(existing_code)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read file: {e}",
                "module_name": module_name,
            }

        # Delete existing module if it exists
        if module_existed:
            deleted = adapter.delete_module(module_name)
            if not deleted:
                return {
                    "success": False,
                    "error": f"Failed to delete existing module '{module_name}'",
                    "module_name": module_name,
                }

        # compile_with_retry handles both the write and the compilation
        compile_result = self.compile_with_retry(adapter, module_name, code)

        if not compile_result.get("success") and "Failed to write code" in compile_result.get("error", ""):
            return {
                "success": False,
                "error": f"Failed to import module '{module_name}': {compile_result.get('error')}",
                "module_name": module_name,
            }

        return {
            "success": True,
            "module_name": module_name,
            "created": not module_existed,
            "compile": compile_result,
        }

    def compile_with_retry(
        self,
        adapter: IVbaAdapter,
        module_name: str,
        new_code: str,
        max_retries: int = 3,
    ) -> dict:
        """Compile VBA with retry-on-error and rollback safety.

        Writes code to module, attempts compilation up to max_retries times.
        On persistent failure, rolls back to the original state.

        Args:
            adapter: Access adapter (WinComAdapter)
            module_name: Name of the VBA module
            new_code: The code to write before compiling
            max_retries: Maximum compilation attempts (default 3)

        Returns:
            {"success": True, "attempts": N}                    — compiled successfully
            {"success": False, "attempt": N, "remaining": M, "rollback": False, "error": "..."}
                                                                — failed, retry available
            {"success": False, "attempt": 3, "rollback": True, "error": "..."}
                                                                — failed, rolled back
        """
        # Capture original state for rollback
        old_code = adapter.get_vba_code(module_name)
        module_existed = bool(old_code)

        # Write code (existing module gets overwritten, new module gets created)
        if module_existed:
            write_ok = adapter.set_vba_code(module_name, new_code)
        else:
            write_ok = adapter.add_vba_procedure(module_name, "main", new_code)

        if not write_ok:
            return {"success": False, "error": "Failed to write code to module"}

        # Attempt compilation up to max_retries
        last_result = {"error": "Unknown compile error"}
        for attempt in range(1, max_retries + 1):
            result = adapter.compile_vba()
            last_result = result
            if result.get("success"):
                return {"success": True, "attempts": attempt}

        # All retries exhausted — rollback
        if module_existed:
            adapter.set_vba_code(module_name, old_code)
        else:
            adapter.delete_module(module_name)

        return {
            "success": False,
            "attempt": max_retries,
            "rollback": True,
            "error": last_result.get("error", "Compilation failed after max retries"),
        }

    def restore_module_backup(
        self, adapter: IVbaAdapter, module_name: str, backup_path: str
    ) -> dict:
        """Restore a VBA module from a .bas backup file.

        Delegates to import_module_from_text which handles the full
        import + compile + retry workflow.

        Args:
            adapter: Access adapter (WinComAdapter)
            module_name: Name of the module to restore
            backup_path: Path to the .bas backup file

        Returns:
            dict with success, module_name
        """
        return self.import_module_from_text(adapter, module_name, backup_path)

    # ========================================================================
    # Text Export/Import Pipeline — Forms
    # ========================================================================

    def export_form_backup(
        self, adapter: IFormAdapter, form_name: str, backup_dir: str | None = None
    ) -> dict:
        """Export a form (including VBA code-behind) to a .txt file.

        Args:
            adapter: Access adapter (WinComAdapter)
            form_name: Name of the form to export
            backup_dir: Optional custom backup directory

        Returns:
            dict with success, backup_path, form_name, file_size_bytes
        """
        return self._export_object(
            adapter.export_form_to_text,
            form_name,
            backup_dir,
            "form_name",
            ".txt",
        )

    def import_form_from_text(
        self, adapter: IFormAdapter, form_name: str, file_path: str
    ) -> dict:
        """Import a form from a .txt text file.

        Validates file exists BEFORE deleting the original form.

        Args:
            adapter: Access adapter (WinComAdapter)
            form_name: Name of the form to import
            file_path: Path to the .txt file

        Returns:
            dict with success, form_name, and error if failed
        """
        return self._import_object(
            adapter.import_form_from_text,
            adapter.form_exists,
            adapter.delete_form,
            form_name,
            file_path,
            "form_name",
        )

    def restore_form_backup(
        self, adapter: IFormAdapter, form_name: str, backup_path: str
    ) -> dict:
        """Restore a form from a .txt backup file.

        Args:
            adapter: Access adapter (WinComAdapter)
            form_name: Name of the form to restore
            backup_path: Path to the .txt backup file

        Returns:
            dict with success, form_name
        """
        return self.import_form_from_text(adapter, form_name, backup_path)

    # ========================================================================
    # Text Export/Import Pipeline — Reports
    # ========================================================================

    def export_report_backup(
        self, adapter: IFormAdapter, report_name: str, backup_dir: str | None = None
    ) -> dict:
        """Export a report (including VBA code-behind) to a .txt file.

        Args:
            adapter: Access adapter (WinComAdapter)
            report_name: Name of the report to export
            backup_dir: Optional custom backup directory

        Returns:
            dict with success, backup_path, report_name, file_size_bytes
        """
        return self._export_object(
            adapter.export_report_to_text,
            report_name,
            backup_dir,
            "report_name",
            ".txt",
        )

    def import_report_from_file(
        self, adapter: IFormAdapter, report_name: str, file_path: str
    ) -> dict:
        """Import a report from a .txt text file.

        Validates file exists BEFORE deleting the original report.

        Args:
            adapter: Access adapter (WinComAdapter)
            report_name: Name of the report to import
            file_path: Path to the .txt file

        Returns:
            dict with success, report_name, and error if failed
        """
        return self._import_object(
            adapter.import_report_from_text,
            adapter.report_exists,
            adapter.delete_report,
            report_name,
            file_path,
            "report_name",
        )

    def restore_report_backup(
        self, adapter: IFormAdapter, report_name: str, backup_path: str
    ) -> dict:
        """Restore a report from a .txt backup file.

        Args:
            adapter: Access adapter (WinComAdapter)
            report_name: Name of the report to restore
            backup_path: Path to the .txt backup file

        Returns:
            dict with success, report_name
        """
        return self.import_report_from_file(adapter, report_name, backup_path)
