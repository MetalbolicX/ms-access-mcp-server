"""DevCopyService — manages dev copy lifecycle and manifest tracking.

Handles:
- Manifest JSON CRUD at {tempdir}/ms_access_dev/{md5(path)[:8]}.json
- DB copy operations (create/discard/deploy dev copies)
- Delegates object backup/restore to BackupService
"""
import hashlib
import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Optional

from ..adapters.interfaces import IUiAdapter
from .backup_service import BackupService
from .connection import ConnectionService
from .manifest_repository import ManifestRepository


class DevCopyService:
    """Manages dev copy lifecycle and manifest tracking.

    Composes ManifestRepository for JSON CRUD and BackupService for
    object-level backup/restore of VBA modules, forms, and reports.
    """

    # Default backup base directory
    DEFAULT_BACKUP_BASE = os.path.join(tempfile.gettempdir(), "ms_access_dev")

    def __init__(self) -> None:
        self._backup_base_store = self.DEFAULT_BACKUP_BASE
        self._manifest = ManifestRepository()
        self._backup = BackupService(self._backup_base_store)
        # Ensure base directory exists
        os.makedirs(self._backup_base_store, exist_ok=True)

    @property
    def _backup_base(self) -> str:
        """Shared backup base directory, synced with BackupService."""
        return self._backup_base_store

    @_backup_base.setter
    def _backup_base(self, value: str) -> None:
        self._backup_base_store = value
        if hasattr(self, '_backup'):
            self._backup._backup_base = value

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
    # Backup — delegated to BackupService
    # ========================================================================

    def get_backup_dir(self) -> str:
        """Get the default backup directory, creating it if needed.

        Returns:
            Path to {tempdir}/ms_access_dev/backups/
        """
        return self._backup.get_backup_dir()

    def export_module_backup(
        self, adapter: IUiAdapter, module_name: str, backup_dir: str | None = None
    ) -> dict:
        """Export a VBA module's code to a .bas file.

        Delegates to BackupService.
        """
        return self._backup.export_module_backup(adapter, module_name, backup_dir)

    def import_module_from_text(
        self, adapter: IUiAdapter, module_name: str, file_path: str
    ) -> dict:
        """Import a VBA module from a .bas text file.

        Delegates to BackupService.
        """
        return self._backup.import_module_from_text(adapter, module_name, file_path)

    def compile_with_retry(
        self,
        adapter: IUiAdapter,
        module_name: str,
        new_code: str,
        max_retries: int = 3,
    ) -> dict:
        """Compile VBA with retry-on-error and rollback safety.

        Delegates to BackupService.
        """
        return self._backup.compile_with_retry(adapter, module_name, new_code, max_retries)

    def restore_module_backup(
        self, adapter: IUiAdapter, module_name: str, backup_path: str
    ) -> dict:
        """Restore a VBA module from a .bas backup file.

        Delegates to BackupService.
        """
        return self._backup.restore_module_backup(adapter, module_name, backup_path)

    def export_form_backup(
        self, adapter: IUiAdapter, form_name: str, backup_dir: str | None = None
    ) -> dict:
        """Export a form (including VBA code-behind) to a .txt file.

        Delegates to BackupService.
        """
        return self._backup.export_form_backup(adapter, form_name, backup_dir)

    def import_form_from_text(
        self, adapter: IUiAdapter, form_name: str, file_path: str
    ) -> dict:
        """Import a form from a .txt text file.

        Delegates to BackupService.
        """
        return self._backup.import_form_from_text(adapter, form_name, file_path)

    def restore_form_backup(
        self, adapter: IUiAdapter, form_name: str, backup_path: str
    ) -> dict:
        """Restore a form from a .txt backup file.

        Delegates to BackupService.
        """
        return self._backup.restore_form_backup(adapter, form_name, backup_path)

    def export_report_backup(
        self, adapter: IUiAdapter, report_name: str, backup_dir: str | None = None
    ) -> dict:
        """Export a report (including VBA code-behind) to a .txt file.

        Delegates to BackupService.
        """
        return self._backup.export_report_backup(adapter, report_name, backup_dir)

    def import_report_from_file(
        self, adapter: IUiAdapter, report_name: str, file_path: str
    ) -> dict:
        """Import a report from a .txt text file.

        Delegates to BackupService.
        """
        return self._backup.import_report_from_file(adapter, report_name, file_path)

    def restore_report_backup(
        self, adapter: IUiAdapter, report_name: str, backup_path: str
    ) -> dict:
        """Restore a report from a .txt backup file.

        Delegates to BackupService.
        """
        return self._backup.restore_report_backup(adapter, report_name, backup_path)

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
        self, conn_service: ConnectionService, adapter: IUiAdapter, backup_dir: str | None = None
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
            self._backup_base = backup_dir  # triggers property setter, syncs BackupService
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

    def deploy_dev_copy(self, conn_service: ConnectionService, adapter: IUiAdapter, production_path: str | None = None) -> dict:
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

    def discard_dev_copy(self, conn_service: ConnectionService, adapter: IUiAdapter, production_path: str | None = None) -> dict:
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
