"""Dev copy, backup/restore, and compact/repair tools for MS Access."""
from .server import mcp, connection_service, dev_copy_service


# ============================================================================
# COMPACT/REPAIR TOOLS
# ============================================================================


@mcp.tool()
def compact_repair(action: str, source_path: str, dest_path: str, keep_original: bool = True) -> dict:
    """Compact or repair an Access database file.

    Args:
        action: "compact" to compact to a new file, or "repair" to compact in place
        source_path: Path to the .accdb source file
        dest_path: Path for the output file (for compact) or same as source (for repair)
        keep_original: If True, keep original as .bak backup (default True)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.compact_repair(action, source_path, dest_path, keep_original)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def copy_database(source: str, dest: str) -> dict:
    """Copy an Access database file.

    Args:
        source: Path to source .accdb/.mdb file
        dest: Path to destination file
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
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


@mcp.tool()
def export_module_backup(module_name: str, backup_dir: str | None = None) -> dict:
    """Export a VBA module's code to a .bas text file.

    Args:
        module_name: Name of the VBA module to export
        backup_dir: Optional custom backup directory (default: {tempdir}/ms_access_dev/backups/)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.export_module_backup(adapter, module_name, backup_dir)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def import_module_from_text(module_name: str, file_path: str) -> dict:
    """Import a VBA module from a .bas text file.

    Deletes the original module and recreates from the .bas file.
    Creates a NEW module if it doesn't already exist.

    Args:
        module_name: Name of the VBA module to import
        file_path: Path to the .bas text file
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.import_module_from_text(adapter, module_name, file_path)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def restore_module_backup(module_name: str, backup_path: str) -> dict:
    """Restore a VBA module from a .bas backup file.

    Args:
        module_name: Name of the module to restore
        backup_path: Path to the .bas backup file
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.restore_module_backup(adapter, module_name, backup_path)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def export_form_backup(form_name: str, backup_dir: str | None = None) -> dict:
    """Export a form (including VBA code-behind) to a .txt file.

    Args:
        form_name: Name of the form to export
        backup_dir: Optional custom backup directory
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.export_form_backup(adapter, form_name, backup_dir)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def import_form_from_file(form_name: str, file_path: str) -> dict:
    """Import a form from a .txt file on disk.

    Deletes the original form and recreates from the .txt file.
    Unlike import_form_from_text (which takes raw text data), this
    reads the form definition from a file path.

    Args:
        form_name: Name of the form to import
        file_path: Path to the .txt file
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.import_form_from_text(adapter, form_name, file_path)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def restore_form_backup(form_name: str, backup_path: str) -> dict:
    """Restore a form from a .txt backup file.

    Args:
        form_name: Name of the form to restore
        backup_path: Path to the .txt backup file
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.restore_form_backup(adapter, form_name, backup_path)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# FULL DB COPY PIPELINE TOOLS (Dev Copy Lifecycle)
# ============================================================================


@mcp.tool()
def create_dev_copy(backup_dir: str | None = None) -> dict:
    """Create a development copy of the production database.

    Copies the entire .accdb to a temp sandbox, switches the connection to
    the dev copy, and writes a manifest for deploy/discard operations.

    WARNING: Large databases (>500MB) may take considerable time to copy.
    Linked tables may lose their links when copied to a new environment.

    Args:
        backup_dir: Optional custom backup base directory
                   (default: {tempdir}/ms_access_dev/)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.create_dev_copy(connection_service, adapter, backup_dir)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def deploy_dev_copy(production_path: str | None = None) -> dict:
    """Deploy the active dev copy back to production.

    Creates a .bak backup of the current production database, copies the
    dev copy over production, reconnects to production, and removes the
    dev copy manifest.

    SAFETY: A .bak file is always created before overwriting production.

    Args:
        production_path: Optional explicit production path. If not provided,
                        uses the production_path from the dev copy manifest.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.deploy_dev_copy(connection_service, adapter, production_path)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def discard_dev_copy(production_path: str | None = None) -> dict:
    """Discard the active dev copy and reconnect to production.

    Deletes the dev copy file, removes the manifest, and reconnects to
    the production database. Your production changes are lost.

    Args:
        production_path: Optional explicit production path.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = dev_copy_service.discard_dev_copy(connection_service, adapter, production_path)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_dev_copy_status(db_path: str | None = None) -> dict:
    """Get the current dev copy status.

    Returns whether a dev copy is active, and if so, the production and dev
    copy paths, creation timestamp, database size, and linked table info.

    Args:
        db_path: Optional production database path. If not provided,
                uses the production_path from the current manifest.
    """
    if db_path is None:
        # Try to get from current manifest
        try:
            result = dev_copy_service.get_dev_copy_status()
            return result
        except Exception as e:
            return {"active": False, "error": str(e)}
    try:
        result = dev_copy_service.get_dev_copy_status(db_path)
        return result
    except Exception as e:
        return {"active": False, "error": str(e)}
