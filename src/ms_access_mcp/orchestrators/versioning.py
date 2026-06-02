"""Stateless orchestrator wrapping versioning operations.

All methods accept an AccessAdapter and return standardized dicts.
"""
import os
from ..services.dev_copy_service import DevCopyService


class VersioningOrchestrator:
    """Stateless orchestrator wrapping versioning operations.

    All methods accept an AccessAdapter and return standardized dicts.
    """

    def export_all(self, output_dir, adapter, dedup=True, module_ext=".bas"):
        """Export all forms, reports, modules, macros, and queries to a directory structure.

        Args:
            output_dir: Root directory for export
            adapter: AccessAdapter instance
            dedup: If True, skip export when SHA256 of content matches existing file
            module_ext: Extension for module files, '.bas' (default) or '.txt'

        Returns:
            dict with success (bool), error (str|None), and adapter result data
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            result = adapter.export_all_versioning(
                output_dir, dedup=dedup, module_ext=module_ext
            )
            return {"success": True, "error": None, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def import_all(self, input_dir, adapter):
        """Import all objects from a directory structure.

        Args:
            input_dir: Root directory containing exported objects
            adapter: AccessAdapter instance

        Returns:
            dict with success (bool), error (str|None), and adapter result data
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            result = adapter.import_all_versioning(input_dir)
            return {"success": True, "error": None, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def compare(self, export_dir, adapter):
        """Compare objects in the DB against exported files.

        Args:
            export_dir: Directory containing exported objects to compare against
            adapter: AccessAdapter instance

        Returns:
            dict with success (bool), error (str|None), and comparison result
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            result = adapter.compare_versioning(export_dir)
            return {"success": True, "error": None, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_schema_ddl(self, output_dir, adapter):
        """Export table schemas as DDL files.

        Args:
            output_dir: Root directory for DDL output
            adapter: AccessAdapter instance

        Returns:
            dict with success (bool), error (str|None), and adapter result data
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            result = adapter.export_schema_ddl(output_dir)
            return {"success": True, "error": None, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_module_backup(self, module_name, adapter, backup_dir=None):
        """Export a VBA module's code to a .bas file.

        Args:
            module_name: Name of the VBA module to export
            adapter: AccessAdapter instance
            backup_dir: Optional custom backup directory

        Returns:
            dict with success (bool), error (str|None), backup_path, etc.
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            service = DevCopyService()
            result = service.export_module_backup(adapter, module_name, backup_dir)
            return {"success": result.get("success", False), "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def import_module_from_text(self, module_name, file_path, adapter):
        """Import a VBA module from a .bas text file.

        Args:
            module_name: Name of the module to import
            file_path: Path to the .bas file
            adapter: AccessAdapter instance

        Returns:
            dict with success (bool), error (str|None), etc.
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            service = DevCopyService()
            result = service.import_module_from_text(adapter, module_name, file_path)
            return {"success": result.get("success", False), "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_form_backup(self, form_name, adapter, backup_dir=None):
        """Export a form (including VBA code-behind) to a .txt file.

        Args:
            form_name: Name of the form to export
            adapter: AccessAdapter instance
            backup_dir: Optional custom backup directory

        Returns:
            dict with success (bool), error (str|None), backup_path, etc.
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            service = DevCopyService()
            result = service.export_form_backup(adapter, form_name, backup_dir)
            return {"success": result.get("success", False), "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def import_form_from_file(self, form_name, file_path, adapter):
        """Import a form from a .txt text file.

        Args:
            form_name: Name of the form to import
            file_path: Path to the .txt file
            adapter: AccessAdapter instance

        Returns:
            dict with success (bool), error (str|None), etc.
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            service = DevCopyService()
            result = service.import_form_from_text(adapter, form_name, file_path)
            return {"success": result.get("success", False), "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restore_form_backup(self, form_name, backup_path, adapter):
        """Restore a form from a .txt backup file.

        Args:
            form_name: Name of the form to restore
            backup_path: Path to the .txt backup file
            adapter: AccessAdapter instance

        Returns:
            dict with success (bool), error (str|None), etc.
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            service = DevCopyService()
            result = service.restore_form_backup(adapter, form_name, backup_path)
            return {"success": result.get("success", False), "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_report_backup(self, report_name, adapter, backup_dir=None):
        """Export a report (including VBA code-behind) to a .txt file.

        Args:
            report_name: Name of the report to export
            adapter: AccessAdapter instance
            backup_dir: Optional custom backup directory

        Returns:
            dict with success (bool), error (str|None), backup_path, etc.
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            service = DevCopyService()
            result = service.export_report_backup(adapter, report_name, backup_dir)
            return {"success": result.get("success", False), "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def import_report_from_file(self, report_name, file_path, adapter):
        """Import a report from a .txt text file.

        Args:
            report_name: Name of the report to import
            file_path: Path to the .txt file
            adapter: AccessAdapter instance

        Returns:
            dict with success (bool), error (str|None), etc.
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            service = DevCopyService()
            result = service.import_report_from_file(adapter, report_name, file_path)
            return {"success": result.get("success", False), "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restore_report_backup(self, report_name, backup_path, adapter):
        """Restore a report from a .txt backup file.

        Args:
            report_name: Name of the report to restore
            backup_path: Path to the .txt backup file
            adapter: AccessAdapter instance

        Returns:
            dict with success (bool), error (str|None), etc.
        """
        try:
            if not adapter.is_connected():
                return {"success": False, "error": "Not connected"}
            service = DevCopyService()
            result = service.restore_report_backup(adapter, report_name, backup_path)
            return {"success": result.get("success", False), "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def install_git_hook(self, repo_path):
        """Install a pre-commit Git hook that runs export_all with dedup.

        Args:
            repo_path: Path to the Git repository root

        Returns:
            dict with success (bool), error (str|None), message
        """
        try:
            hook_path = os.path.join(repo_path, ".git", "hooks", "pre-commit")
            os.makedirs(os.path.dirname(hook_path), exist_ok=True)
            with open(hook_path, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n# Auto-generated by ms-access-mcp-server\nmacc export-all --dedup\n")
            os.chmod(hook_path, 0o755)
            return {"success": True, "error": None, "message": f"Pre-commit hook installed at {hook_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
