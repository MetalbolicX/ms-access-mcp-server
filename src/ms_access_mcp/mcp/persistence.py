"""Persistence/versioning tools — export/import Access objects as text files."""
from .server import mcp


def _pool():
    """Lazy accessor for connection pool (avoids circular import at module level)."""
    from .container import get_container
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


# ============================================================================
# FORM PERSISTENCE
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
    result = adapter.export_form_to_text(form_name)
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
    result = adapter.import_form_from_text(form_name, form_data)
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
    result = adapter.delete_form(form_name)
    return {"success": result, "form": form_name}


# ============================================================================
# REPORT PERSISTENCE
# ============================================================================


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
    result = adapter.export_report_to_text(report_name)
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
    result = adapter.import_report_from_text(report_name, report_data)
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
    result = adapter.delete_report(report_name)
    return {"success": result, "report": report_name}


# ============================================================================
# MODULE / MACRO / QUERY PERSISTENCE
# ============================================================================


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
    result = adapter.export_module_to_text(module_name)
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
    result = adapter.export_macro_to_text(macro_name)
    if not result:
        return {"success": False, "error": f"Macro '{macro_name}' not found"}
    return {"success": True, "macro": macro_name, "data": result}


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
    result = adapter.export_query_to_text(query_name)
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
    result = adapter.import_query_from_text(query_name, query_data)
    return {"success": result, "query": query_name, "message": "Query imported" if result else "Import failed"}


# ============================================================================
# BULK VERSIONING OPERATIONS
# ============================================================================


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
    result = adapter.execute_sql_script(script_path)
    return result
