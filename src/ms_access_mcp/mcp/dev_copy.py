"""Dev copy, backup/restore, and compact/repair tools for MS Access — Phase 1 SDD.

Note: Dev copy operations work with the active connection and require
the connection pool to have adapter and current_database properties.
"""
from ._helpers import _validate_path, destructive_guard, require_connected
from .container import get_container
from .server import mcp


def _pool():
    """Lazy accessor for connection pool (avoids circular import at module level)."""
    return get_container().connection_pool


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return _pool().get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return _pool().is_connected(connection_name)


def _ensure_connected(connection_name: str = "default"):
    """Check connection and return adapter, or None if not connected."""
    if not _check_connected(connection_name):
        return None
    return _get_adapter(connection_name)


def _dev_copy():
    """Lazy accessor for the dev copy service."""
    return get_container().dev_copy


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return _pool().get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return _pool().is_connected(connection_name)


def _ensure_connected(connection_name: str = "default"):
    """Check connection and return adapter, or None if not connected."""
    if not _check_connected(connection_name):
        return None
    return _get_adapter(connection_name)


def _get_current_db_path(connection_name: str = "default"):
    """Get current database path for a connection."""
    try:
        return _pool().get(connection_name).db_path
    except KeyError:
        return None


# ============================================================================
# COMPACT/REPAIR TOOLS
# ============================================================================


@require_connected()
@mcp.tool()
def compact_repair(action: str, source_path: str, dest_path: str, keep_original: bool = True, connection_name: str = "default") -> dict:
    """
    Compact or repair an Access database file.

    Args:
        action: "compact" to compact to a new file, or "repair" to compact in place
        source_path: Path to the .accdb source file
        dest_path: Path for the output file (for compact) or same as source (for repair)
        keep_original: If True, keep original as .bak backup (default True)
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    # Validate paths
    try:
        source_path = _validate_path(source_path)
        dest_path = _validate_path(dest_path)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.compact_repair(action, source_path, dest_path, keep_original)
        return result
    except NotImplementedError as e:
        return {"success": False, "error": f"This operation requires COM automation ({e}). Use connect_access with use_com=True on Windows."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def copy_database(source: str, dest: str, connection_name: str = "default") -> dict:
    """
    Copy an Access database file.

    Args:
        source: Path to source .accdb/.mdb file
        dest: Path to destination file
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    # Validate paths
    try:
        source = _validate_path(source)
        dest = _validate_path(dest)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.copy_database(source, dest)
        return {"success": result, "source": source, "dest": dest}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# TEXT BACKUP & RESTORE TOOLS (VBA Modules & Forms)
# ============================================================================


@require_connected()
@mcp.tool()
def export_module_backup(module_name: str, backup_dir: str | None = None, connection_name: str = "default") -> dict:
    """
    Export a VBA module's code to a .bas text file.

    Args:
        module_name: Name of the VBA module to export
        backup_dir: Optional custom backup directory (default: {tempdir}/ms_access_dev/backups/)
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.export_module_backup(module_name, adapter, backup_dir)
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def import_module_from_text(module_name: str, file_path: str, connection_name: str = "default") -> dict:
    """
    Import a VBA module from a .bas text file.

    Deletes the original module and recreates from the .bas file.
    Creates a NEW module if it doesn't already exist.

    Args:
        module_name: Name of the VBA module to import
        file_path: Path to the .bas text file
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        file_path = _validate_path(file_path)
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.import_module_from_text(module_name, file_path, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def restore_module_backup(module_name: str, backup_path: str, connection_name: str = "default") -> dict:
    """
    Restore a VBA module from a .bas backup file.

    Args:
        module_name: Name of the module to restore
        backup_path: Path to the .bas backup file
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        backup_path = _validate_path(backup_path)
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.restore_module_backup(module_name, backup_path, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def export_form_backup(form_name: str, backup_dir: str | None = None, connection_name: str = "default") -> dict:
    """
    Export a form (including VBA code-behind) to a .txt file.

    Args:
        form_name: Name of the form to export
        backup_dir: Optional custom backup directory
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.export_form_backup(form_name, adapter, backup_dir)
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def import_form_from_file(form_name: str, file_path: str, connection_name: str = "default") -> dict:
    """
    Import a form from a .txt file on disk.

    Deletes the original form and recreates from the .txt file.
    Unlike import_form_from_text (which takes raw text data), this
    reads the form definition from a file path.

    Args:
        form_name: Name of the form to import
        file_path: Path to the .txt file
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        file_path = _validate_path(file_path)
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.import_form_from_file(form_name, file_path, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def restore_form_backup(form_name: str, backup_path: str, connection_name: str = "default") -> dict:
    """
    Restore a form from a .txt backup file.

    Args:
        form_name: Name of the form to restore
        backup_path: Path to the .txt backup file
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        backup_path = _validate_path(backup_path)
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.restore_form_backup(form_name, backup_path, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def export_report_backup(report_name: str, backup_dir: str | None = None, connection_name: str = "default") -> dict:
    """
    Export a report (including VBA code-behind) to a .txt file.

    Args:
        report_name: Name of the report to export
        backup_dir: Optional custom backup directory
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.export_report_backup(report_name, adapter, backup_dir)
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def import_report_from_file(report_name: str, file_path: str, connection_name: str = "default") -> dict:
    """
    Import a report from a .txt text file.

    Args:
        report_name: Name of the report to import
        file_path: Path to the .txt file
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        file_path = _validate_path(file_path)
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.import_report_from_file(report_name, file_path, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


@require_connected()
@mcp.tool()
def restore_report_backup(report_name: str, backup_path: str, connection_name: str = "default") -> dict:
    """
    Restore a report from a .txt backup file.

    Args:
        report_name: Name of the report to restore
        backup_path: Path to the .txt backup file
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    try:
        backup_path = _validate_path(backup_path)
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.restore_report_backup(report_name, backup_path, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# FULL DB COPY PIPELINE TOOLS (Dev Copy Lifecycle)
# ============================================================================


@require_connected()
@mcp.tool()
def create_dev_copy(backup_dir: str | None = None, connection_name: str = "default") -> dict:
    """
    Create a development copy of the production database.

    Copies the entire .accdb to a temp sandbox, switches the connection to
    the dev copy, and writes a manifest for deploy/discard operations.

    WARNING: Large databases (>500MB) may take considerable time to copy.
    Linked tables may lose their links when copied to a new environment.

    Args:
        backup_dir: Optional custom backup base directory
                   (default: {tempdir}/ms_access_dev/)
        connection_name: Connection identifier (defaults to "default")

    Note: This function works with the active connection and temporarily
    disconnects/reconnects during the operation.
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = _dev_copy().create_dev_copy(_pool(), adapter, backup_dir)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@destructive_guard(action="deploy_dev_copy")
@mcp.tool()
def deploy_dev_copy(production_path: str | None = None, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Deploy the active dev copy back to production.

    Creates a .bak backup of the current production database, copies the
    dev copy over production, reconnects to production, and removes the
    dev copy manifest.

    SAFETY: A .bak file is always created before overwriting production.

    Args:
        production_path: Optional explicit production path. If not provided,
                        uses the production_path from the dev copy manifest.
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to proceed with deployment
        dry_run: If True, returns preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = _dev_copy().deploy_dev_copy(_pool(), adapter, production_path)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@destructive_guard(action="discard_dev_copy")
@mcp.tool()
def discard_dev_copy(production_path: str | None = None, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Discard the active dev copy and reconnect to production.

    Deletes the dev copy file, removes the manifest, and reconnects to
    the production database. Your production changes are lost.

    Args:
        production_path: Optional explicit production path.
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to proceed with discard
        dry_run: If True, returns preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = _dev_copy().discard_dev_copy(_pool(), adapter, production_path)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_dev_copy_status(db_path: str | None = None) -> dict:
    """
    Get the current dev copy status.

    Returns whether a dev copy is active, and if so, the production and dev
    copy paths, creation timestamp, database size, and linked table info.

    Args:
        db_path: Optional production database path. If not provided,
                uses the production_path from the current manifest.
    """
    if db_path is None:
        try:
            result = _dev_copy().get_dev_copy_status()
            return result
        except Exception as e:
            return {"active": False, "error": str(e)}
    try:
        result = _dev_copy().get_dev_copy_status(db_path)
        return result
    except Exception as e:
        return {"active": False, "error": str(e)}
