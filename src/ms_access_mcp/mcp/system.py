"""System table metadata and persistence/versioning tools for MS Access — Phase 1 SDD."""
import platform
import sys
from .server import mcp, connection_service, schema_service


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return connection_service.get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return connection_service.is_connected(connection_name)


# ============================================================================
# SYSTEM TABLE METADATA TOOLS
# ============================================================================


@mcp.tool()
def get_system_tables(connection_name: str = "default") -> dict:
    """
    Get system tables from the database.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    tables = schema_service.get_system_tables()
    return {"success": True, "system_tables": [t.model_dump() for t in tables], "count": len(tables)}


@mcp.tool()
def get_object_metadata(object_name: str, connection_name: str = "default") -> dict:
    """
    Get metadata for a database object.

    Args:
        object_name: Name of the database object
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    metadata = schema_service.get_object_metadata(object_name)
    if not metadata:
        return {"success": False, "error": f"Object '{object_name}' not found"}
    return {"success": True, "metadata": metadata}


# ============================================================================
# PERSISTENCE & VERSIONING TOOLS
# ============================================================================


@mcp.tool()
def export_form_to_text(form_name: str, connection_name: str = "default") -> dict:
    """
    Export a form to text representation.

    Args:
        form_name: Name of the form to export
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.export_form_to_text(form_name)
    if not result:
        return {"success": False, "error": f"Failed to export form '{form_name}'"}
    return {"success": True, "form": form_name, "data": result}


@mcp.tool()
def import_form_from_text(form_name: str, form_data: str, connection_name: str = "default") -> dict:
    """
    Import a form from text representation.

    Args:
        form_name: Name of the form to create/replace
        form_data: Text representation of the form (from export_form_to_text)
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.import_form_from_text(form_name, form_data)
    return {"success": result, "form": form_name, "message": "Form imported" if result else "Import failed"}


@mcp.tool()
def delete_form(form_name: str, connection_name: str = "default") -> dict:
    """
    Delete a form from the database.

    Args:
        form_name: Name of the form to delete
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.delete_form(form_name)
    return {"success": result, "form": form_name}


@mcp.tool()
def export_report_to_text(report_name: str, connection_name: str = "default") -> dict:
    """
    Export a report to text representation.

    Args:
        report_name: Name of the report to export
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.export_report_to_text(report_name)
    if not result:
        return {"success": False, "error": f"Failed to export report '{report_name}'"}
    return {"success": True, "report": report_name, "data": result}


@mcp.tool()
def import_report_from_text(report_name: str, report_data: str, connection_name: str = "default") -> dict:
    """
    Import a report from text representation.

    Args:
        report_name: Name of the report to create/replace
        report_data: Text representation of the report (from export_report_to_text)
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.import_report_from_text(report_name, report_data)
    return {"success": result, "report": report_name, "message": "Report imported" if result else "Import failed"}


@mcp.tool()
def delete_report(report_name: str, connection_name: str = "default") -> dict:
    """
    Delete a report from the database.

    Args:
        report_name: Name of the report to delete
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.delete_report(report_name)
    return {"success": result, "report": report_name}


@mcp.tool()
def export_module_to_text(module_name: str, connection_name: str = "default") -> dict:
    """
    Export VBA module code as plain text.

    Args:
        module_name: Name of the VBA module to export
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.export_module_to_text(module_name)
    if not result:
        return {"success": False, "error": f"Module '{module_name}' not found or empty"}
    return {"success": True, "module": module_name, "data": result}


@mcp.tool()
def export_macro_to_text(macro_name: str, connection_name: str = "default") -> dict:
    """
    Export macro metadata as plain text.

    Note: Access macros cannot export as code. This returns metadata only.

    Args:
        macro_name: Name of the macro to export
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.export_macro_to_text(macro_name)
    if not result:
        return {"success": False, "error": f"Macro '{macro_name}' not found"}
    return {"success": True, "macro": macro_name, "data": result}


@mcp.tool()
def export_all_versioning(output_dir: str, connection_name: str = "default") -> dict:
    """
    Export all forms, reports, modules, and macros to a directory structure.

    Creates subdirectories: forms/, reports/, modules/, macros/
    Files named: {type}_{name}.txt

    Args:
        output_dir: Directory to export files to
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.export_all(output_dir, adapter, dedup=True, module_ext=".bas")
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def export_query_to_text(query_name: str, connection_name: str = "default") -> dict:
    """
    Export a query definition as text.

    Args:
        query_name: Name of the query to export
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.export_query_to_text(query_name)
    if not result:
        return {"success": False, "error": f"Query '{query_name}' not found or empty"}
    return {"success": True, "query": query_name, "data": result}


@mcp.tool()
def import_query_from_text(query_name: str, query_data: str, connection_name: str = "default") -> dict:
    """
    Import a query from text representation.

    Args:
        query_name: Name of the query to create/replace
        query_data: Text representation of the query (SQL or Access query definition)
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.import_query_from_text(query_name, query_data)
    return {"success": result, "query": query_name, "message": "Query imported" if result else "Import failed"}


@mcp.tool()
def export_schema_ddl(output_dir: str, connection_name: str = "default") -> dict:
    """
    Export table schemas as DDL SQL files.

    Writes schema/ddl_tables.sql with CREATE TABLE statements
    and schema/ddl_relationships.sql with ALTER TABLE constraints.

    Args:
        output_dir: Directory to write DDL files to
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.export_schema_ddl(output_dir, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def compare_versioning(export_dir: str, connection_name: str = "default") -> dict:
    """
    Compare database state against an export directory.

    Returns lists of new, missing, changed, and unchanged objects.

    Args:
        export_dir: Directory containing previous exports
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.compare(export_dir, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def import_all_versioning(input_dir: str, connection_name: str = "default") -> dict:
    """
    Import all versioned objects from a directory structure.

    Args:
        input_dir: Directory containing versioned objects
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
        orch = VersioningOrchestrator()
        return orch.import_all(input_dir, adapter)
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def execute_sql_script(script_path: str, connection_name: str = "default") -> dict:
    """
    Execute a Jet SQL script file against the connected Access database.

    Reads a .sql file, splits statements on ';', executes each via DAO.
    All statements run in one transaction - rollback on any failure.

    Args:
        script_path: Path to the .sql file containing Jet SQL statements
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    schema_service.set_adapter(adapter)
    result = schema_service.execute_sql_script(script_path)
    return result


# ============================================================================
# RECOVERY & DIAGNOSTICS TOOLS
# ============================================================================


@mcp.tool()
def recover_access() -> dict:
    """
    Kill hung Microsoft Access processes and reconnect all managed connections.

    Executes taskkill /F /IM MSACCESS.EXE on Windows and attempts to
    reconnect all previously managed connections.

    Returns:
        dict with success status, reconnected connection names, and any errors
    """
    return connection_service.recover_access()


@mcp.tool()
def diagnose_environment() -> dict:
    """
    Provide structured health check of the runtime environment.

    Checks:
    - ACE OLEDB driver availability
    - pywin32 import status
    - COM server launch capability
    - OS platform and Python version
    - Configured allowed directories

    Returns:
        dict with environment diagnostics
    """
    diagnostics: dict = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": sys.version,
        "python_executable": sys.executable,
    }

    # Check ACE OLEDB driver
    try:
        import win32com.client
        diagnostics["pywin32_available"] = True
        diagnostics["pywin32_import"] = "ok"
    except ImportError:
        diagnostics["pywin32_available"] = False
        diagnostics["pywin32_import"] = "not installed"

    # Check ACE OLEDB provider
    if sys.platform == "win32":
        try:
            import winreg
            hklm = winreg.HKEY_LOCAL_MACHINE
            key = winreg.OpenKey(hklm, r"SOFTWARE\Microsoft\Office\16.0\Access Connectivity Engine")
            winreg.CloseKey(key)
            diagnostics["ace_provider"] = "installed"
        except FileNotFoundError:
            diagnostics["ace_provider"] = "not found"
        except PermissionError:
            diagnostics["ace_provider"] = "access denied"
        except Exception as e:
            diagnostics["ace_provider"] = f"error: {e}"
    else:
        diagnostics["ace_provider"] = "windows_only"

    # Check COM server launch (mocked - would require actual COM call)
    if sys.platform == "win32":
        diagnostics["com_server_test"] = "not_tested_in_diagnostics"
    else:
        diagnostics["com_server_test"] = "windows_only"

    # Check allowed directories from config
    try:
        from ..config import ServerConfig
        config = ServerConfig()
        diagnostics["allowed_dirs"] = config.allowed_dirs
        diagnostics["api_key_configured"] = bool(config.api_key)
    except Exception as e:
        diagnostics["config_error"] = str(e)
        diagnostics["allowed_dirs"] = []
        diagnostics["api_key_configured"] = False

    # Overall status
    all_ok = (
        diagnostics.get("pywin32_available", False) and
        diagnostics.get("ace_provider") == "installed" and
        diagnostics.get("allowed_dirs") is not None
    )
    diagnostics["overall_status"] = "ok" if all_ok else "issues_found"

    return {"success": True, "diagnostics": diagnostics}
