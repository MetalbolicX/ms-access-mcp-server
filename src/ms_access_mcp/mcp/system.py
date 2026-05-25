"""System table metadata and persistence/versioning tools for MS Access."""
from .server import mcp, connection_service, schema_service


# ============================================================================
# SYSTEM TABLE METADATA TOOLS
# ============================================================================


@mcp.tool()
def get_system_tables() -> dict:
    """Get system tables from the database."""
    tables = schema_service.get_system_tables()
    return {"success": True, "system_tables": [t.model_dump() for t in tables], "count": len(tables)}


@mcp.tool()
def get_object_metadata(object_name: str) -> dict:
    """Get metadata for a database object."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    metadata = schema_service.get_object_metadata(object_name)
    if not metadata:
        return {"success": False, "error": f"Object '{object_name}' not found"}
    return {"success": True, "metadata": metadata}


# ============================================================================
# PERSISTENCE & VERSIONING TOOLS
# ============================================================================


@mcp.tool()
def export_form_to_text(form_name: str) -> dict:
    """Export a form to text representation."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.export_form_to_text(form_name)
    if not result:
        return {"success": False, "error": f"Failed to export form '{form_name}'"}
    return {"success": True, "form": form_name, "data": result}


@mcp.tool()
def import_form_from_text(form_name: str, form_data: str) -> dict:
    """Import a form from text representation.

    Args:
        form_name: Name of the form to create/replace
        form_data: Text representation of the form (from export_form_to_text)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.import_form_from_text(form_name, form_data)
    return {"success": result, "form": form_name, "message": "Form imported" if result else "Import failed"}


@mcp.tool()
def delete_form(form_name: str) -> dict:
    """Delete a form from the database."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.delete_form(form_name)
    return {"success": result, "form": form_name}


@mcp.tool()
def export_report_to_text(report_name: str) -> dict:
    """Export a report to text representation."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.export_report_to_text(report_name)
    if not result:
        return {"success": False, "error": f"Failed to export report '{report_name}'"}
    return {"success": True, "report": report_name, "data": result}


@mcp.tool()
def import_report_from_text(report_name: str, report_data: str) -> dict:
    """Import a report from text representation.

    Args:
        report_name: Name of the report to create/replace
        report_data: Text representation of the report (from export_report_to_text)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.import_report_from_text(report_name, report_data)
    return {"success": result, "report": report_name, "message": "Report imported" if result else "Import failed"}


@mcp.tool()
def delete_report(report_name: str) -> dict:
    """Delete a report from the database."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.delete_report(report_name)
    return {"success": result, "report": report_name}


@mcp.tool()
def export_module_to_text(module_name: str) -> dict:
    """Export VBA module code as plain text.

    Args:
        module_name: Name of the VBA module to export
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.export_module_to_text(module_name)
    if not result:
        return {"success": False, "error": f"Module '{module_name}' not found or empty"}
    return {"success": True, "module": module_name, "data": result}


@mcp.tool()
def export_macro_to_text(macro_name: str) -> dict:
    """Export macro metadata as plain text.

    Note: Access macros cannot export as code. This returns metadata only.

    Args:
        macro_name: Name of the macro to export
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.export_macro_to_text(macro_name)
    if not result:
        return {"success": False, "error": f"Macro '{macro_name}' not found"}
    return {"success": True, "macro": macro_name, "data": result}


@mcp.tool()
def export_all_versioning(output_dir: str) -> dict:
    """Export all forms, reports, modules, and macros to a directory structure.

    Creates subdirectories: forms/, reports/, modules/, macros/
    Files named: {type}_{name}.txt

    Args:
        output_dir: Directory to export files to
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.export_all_versioning(output_dir)
    return result


@mcp.tool()
def execute_sql_script(script_path: str) -> dict:
    """
    Execute a Jet SQL script file against the connected Access database.

    Reads a .sql file, splits statements on ';', executes each via DAO.
    All statements run in one transaction - rollback on any failure.

    Args:
        script_path: Path to the .sql file containing Jet SQL statements
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.execute_sql_script(script_path)
    return result
