"""DevCopyService — manages dev copy lifecycle and manifest tracking.

Handles:
- Manifest JSON CRUD at {tempdir}/ms_access_dev/{md5(path)[:8]}.json
- Backup directory creation and management
- DB copy operations (create/discard/deploy dev copies)
"""
import hashlib
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol, Optional

from ..adapters.base import AccessAdapter
from .connection import ConnectionService
from .manifest_repository import ManifestRepository


class DevCopyService:
    """Manages dev copy lifecycle and manifest tracking.

    The manifest tracks the relationship between production and development
    database copies so we can deploy or discard changes safely.
    """

    # Default backup base directory
    DEFAULT_BACKUP_BASE = os.path.join(tempfile.gettempdir(), "ms_access_dev")

    def __init__(self) -> None:
        self._backup_base = self.DEFAULT_BACKUP_BASE
        self._manifest = ManifestRepository()
        # Ensure base directory exists
        os.makedirs(self._backup_base, exist_ok=True)

    # ========================================================================
    # Manifest CRUD — delegated to ManifestRepository
    # ========================================================================

    def _manifest_path(self, db_path: str) -> str:
        """Compute manifest file path for a given database path.

        Uses short md5 hash for readability.
        """
        return self._manifest._manifest_path(db_path)

    def save_manifest(self, db_path: str, manifest: dict) -> bool:
        """Write manifest JSON to {backup_base}/ms_access_dev/{hash}.json.

        Args:
            db_path: Production database path (used to derive hash key)
            manifest: Dict with keys: production_path, dev_path, created_at,
                      db_size_bytes, has_linked_tables, linked_table_count, deployed_at

        Returns:
            True on success, False on failure
        """
        return self._manifest.save_manifest(db_path, manifest)

    def load_manifest(self, db_path: str) -> Optional[dict]:
        """Load manifest from {backup_base}/ms_access_dev/{hash}.json.

        Args:
            db_path: Production database path (used to derive hash key)

        Returns:
            Manifest dict or None if not found
        """
        return self._manifest.load_manifest(db_path)

    def delete_manifest(self, db_path: str) -> bool:
        """Delete manifest file.

        Args:
            db_path: Production database path (used to derive hash key)

        Returns:
            True if deleted, False if not found or error
        """
        return self._manifest.delete_manifest(db_path)

    # ========================================================================
    # Backup Directory
    # ========================================================================

    def get_backup_dir(self) -> str:
        """Get the default backup directory, creating it if needed.

        Returns:
            Path to {tempdir}/ms_access_dev/backups/
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
        self, adapter: AccessAdapter, module_name: str, backup_dir: str | None = None
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
        self, adapter: AccessAdapter, module_name: str, file_path: str
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

        # compile_with_retry handles both the write (add_vba_procedure for new modules)
        # and the compilation with retry/rollback
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
        adapter: AccessAdapter,
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
        self, adapter: AccessAdapter, module_name: str, backup_path: str
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
        self, adapter: AccessAdapter, form_name: str, backup_dir: str | None = None
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
        self, adapter: AccessAdapter, form_name: str, file_path: str
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
        self, adapter: AccessAdapter, form_name: str, backup_path: str
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
        self, adapter: AccessAdapter, report_name: str, backup_dir: str | None = None
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
        self, adapter: AccessAdapter, report_name: str, file_path: str
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
        self, adapter: AccessAdapter, report_name: str, backup_path: str
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

    # ========================================================================
    # Full DB Copy Pipeline
    # ========================================================================

    def _dev_copy_path(self, prod_path: str) -> str:
        """Compute the dev copy directory path for a production database.

        Uses short md5 hash of the production path.
        Dev copy file is placed inside with _dev.accdb suffix.

        Args:
            prod_path: Path to the production .accdb file

        Returns:
            Path to the dev copy directory (not the file)
        """
        short_hash = hashlib.md5(prod_path.encode()).hexdigest()[:8]
        dev_dir = os.path.join(self._backup_base, short_hash)
        prod_name = os.path.basename(prod_path)
        name_without_ext, ext = os.path.splitext(prod_name)
        dev_file = f"{name_without_ext}_dev{ext}"
        return os.path.join(dev_dir, dev_file)

    def _db_size_mb(self, path: str) -> float:
        """Get database file size in MB."""
        try:
            return os.path.getsize(path) / (1024 * 1024)
        except OSError:
            return 0.0

    def create_dev_copy(
        self, conn_service: ConnectionService, adapter: AccessAdapter, backup_dir: str | None = None
    ) -> dict:
        """Copy the production database to a dev sandbox and switch connection.

        Copies the entire .accdb to {tempdir}/ms_access_dev/{hash}/, switches the
        connection to the dev copy, and writes a manifest for deploy/discard ops.

        Args:
            conn_service: ConnectionService instance
            adapter: Access adapter (WinComAdapter)
            backup_dir: Optional custom backup base (defaults to tempdir/ms_access_dev)

        Returns:
            dict with success, dev_path, manifest_path, warnings (if any)
        """
        prod_path = conn_service.current_database
        if not prod_path:
            return {"success": False, "error": "Not connected to a database"}

        # Check if dev copy already active
        existing = self.load_manifest(prod_path)
        if existing is not None:
            return {"success": False, "error": "Dev copy already active"}

        if backup_dir:
            self._backup_base = backup_dir
            os.makedirs(self._backup_base, exist_ok=True)

        dev_path = self._dev_copy_path(prod_path)
        dev_dir = os.path.dirname(dev_path)
        os.makedirs(dev_dir, exist_ok=True)

        # Copy DB to dev location
        copy_ok = adapter.copy_database(prod_path, dev_path)
        if not copy_ok:
            return {"success": False, "error": f"Failed to copy database to {dev_path}"}

        # Get linked table info for warnings
        warnings: list[str] = []
        linked_result = adapter.get_linked_tables()
        has_linked = False
        linked_count = 0
        if linked_result.get("success") and linked_result.get("linked_tables"):
            has_linked = True
            linked_count = len(linked_result["linked_tables"])
            warnings.append(
                f"Database has {linked_count} linked table(s). "
                "Links may break when copied to a new environment."
            )

        # Check size for large DB warning
        size_mb = self._db_size_mb(dev_path)
        if size_mb > 500:
            warnings.append(
                f"Large database ({size_mb:.1f} MB). Copy may take considerable time."
            )

        # Disconnect from prod, connect to dev copy
        conn_service.disconnect()
        conn_service.connect(dev_path, adapter)

        # Build and save manifest
        manifest = {
            "production_path": prod_path,
            "dev_path": dev_path,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "db_size_bytes": os.path.getsize(dev_path) if os.path.exists(dev_path) else 0,
            "has_linked_tables": has_linked,
            "linked_table_count": linked_count,
            "deployed_at": None,
        }
        save_ok = self.save_manifest(prod_path, manifest)
        if not save_ok:
            return {"success": False, "error": "Failed to save dev copy manifest"}

        result: dict = {
            "success": True,
            "dev_path": dev_path,
            "manifest_path": self._manifest_path(prod_path),
            "production_path": prod_path,
        }
        if warnings:
            result["warnings"] = warnings

        return result

    def deploy_dev_copy(self, conn_service: ConnectionService, adapter: AccessAdapter, production_path: str | None = None) -> dict:
        """Deploy the active dev copy back to production.

        Creates a .bak backup of production, copies the dev copy over production,
        reconnects to production, and removes the manifest.

        Args:
            conn_service: ConnectionService instance
            adapter: Access adapter (WinComAdapter)
            production_path: Optional explicit production path. If not provided,
                uses conn_service.current_database to find the manifest.

        Returns:
            dict with success, production_path, bak_path
        """
        # Resolve production path: use explicit param, or current connection
        db_path = production_path if production_path else conn_service.current_database
        if not db_path:
            return {"success": False, "error": "Not connected to a database"}

        # Load manifest using production path
        manifest = self.load_manifest(db_path)
        if manifest is None:
            return {"success": False, "error": "No active dev copy"}

        dev_path = manifest.get("dev_path")
        actual_prod_path = manifest.get("production_path", db_path)

        if not dev_path or not os.path.exists(dev_path):
            return {"success": False, "error": "Dev copy database not found or empty"}

        # Integrity validation: file must exist and have size > 0
        if os.path.getsize(dev_path) == 0:
            return {"success": False, "error": "Dev copy database is empty"}

        # Create .bak backup of production
        bak_path = actual_prod_path + ".bak"
        copy_ok = adapter.copy_database(actual_prod_path, bak_path)
        if not copy_ok:
            return {"success": False, "error": f"Failed to create backup at {bak_path}"}

        # Copy dev over production
        copy_ok = adapter.copy_database(dev_path, actual_prod_path)
        if not copy_ok:
            return {"success": False, "error": "Failed to copy dev database to production"}

        # Reconnect to production
        conn_service.reconnect(actual_prod_path)

        # Delete manifest
        self.delete_manifest(actual_prod_path)

        return {
            "success": True,
            "production_path": actual_prod_path,
            "bak_path": bak_path,
        }

    def discard_dev_copy(self, conn_service: ConnectionService, adapter: AccessAdapter, production_path: str | None = None) -> dict:
        """Discard the active dev copy and reconnect to production.

        Deletes the dev copy, removes the manifest, and reconnects to production.

        Args:
            conn_service: ConnectionService instance
            adapter: Access adapter (WinComAdapter)
            production_path: Optional explicit production path.

        Returns:
            dict with success, production_path
        """
        # Resolve production path
        db_path = production_path if production_path else conn_service.current_database
        if not db_path:
            return {"success": False, "error": "Not connected to a database"}

        # Load manifest
        manifest = self.load_manifest(db_path)
        if manifest is None:
            return {"success": False, "error": "No active dev copy"}

        actual_prod_path = manifest.get("production_path", db_path)
        dev_path = manifest.get("dev_path")

        # Delete dev copy file if it exists
        if dev_path and os.path.exists(dev_path):
            try:
                os.remove(dev_path)
            except OSError:
                return {"success": False, "error": f"Failed to delete dev copy at {dev_path}"}

        # Delete manifest
        self.delete_manifest(actual_prod_path)

        # Reconnect to production
        conn_service.reconnect(actual_prod_path)

        return {
            "success": True,
            "production_path": actual_prod_path,
        }

    def get_dev_copy_status(self, db_path: str | None = None) -> dict:
        """Get the current dev copy status.

        Args:
            db_path: Optional production database path. Uses current_database if not provided.

        Returns:
            dict with active (bool), and if active: production_path, dev_path,
            created_at, db_size_bytes, has_linked_tables, linked_table_count
        """
        if db_path is None:
            # Can't determine without a path — return inactive
            return {"active": False}

        manifest = self.load_manifest(db_path)
        if manifest is None:
            return {"active": False}

        return {
            "active": True,
            "production_path": manifest.get("production_path"),
            "dev_path": manifest.get("dev_path"),
            "created_at": manifest.get("created_at"),
            "db_size_bytes": manifest.get("db_size_bytes"),
            "has_linked_tables": manifest.get("has_linked_tables", False),
            "linked_table_count": manifest.get("linked_table_count", 0),
        }