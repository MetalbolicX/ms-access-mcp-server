from fastmcp import FastMCP
from ..services.connection import ConnectionService
from ..services.schema import SchemaService
from ..services.com_automation import COMAutomationService
from ..adapters.wincom import WinComAdapter
from ..adapters.odbc import OdbcAdapter

# Create FastMCP server
mcp = FastMCP("MS Access MCP Server")

# Initialize services
connection_service = ConnectionService()
schema_service = SchemaService()
com_automation_service = COMAutomationService()

# Track which adapter is active
_active_adapter = None

# ============================================================================
# CONNECTION MANAGEMENT TOOLS
# ============================================================================


@mcp.tool()
def connect_access(database_path: str, use_com: bool = False) -> dict:
    """
    Connect to an Access database.

    Args:
        database_path: Path to .accdb or .mdb file
        use_com: Use COM automation (True) or ODBC only (False)
    """
    global _active_adapter
    adapter = WinComAdapter() if use_com else OdbcAdapter()
    _active_adapter = adapter

    result = connection_service.connect(database_path, adapter)
    if result:
        schema_service.set_adapter(adapter)
        com_automation_service.set_adapter(adapter)

    return {"success": result, "connected": result, "database": database_path}


@mcp.tool()
def disconnect_access() -> dict:
    """Disconnect from the current Access database."""
    global _active_adapter
    connection_service.disconnect()
    _active_adapter = None
    return {"success": True, "message": "Disconnected"}


@mcp.tool()
def is_connected() -> dict:
    """Check if connected to an Access database."""
    connected = connection_service.is_connected()
    return {"connected": connected, "database": connection_service.current_database}


# ============================================================================
# DATA ACCESS OBJECT MODELS TOOLS
# ============================================================================


@mcp.tool()
def get_tables() -> dict:
    """
    Get all user tables from the connected database.
    Excludes system tables (MSys*).
    """
    tables = schema_service.get_tables()
    return {"success": True, "tables": [t.model_dump() for t in tables], "count": len(tables)}


@mcp.tool()
def get_table_schema(table_name: str) -> dict:
    """
    Get detailed schema for a specific table.

    Args:
        table_name: Name of the table
    """
    table = schema_service.get_table_schema(table_name)
    if table is None:
        return {"success": False, "error": f"Table '{table_name}' not found"}
    return {"success": True, "table": table.model_dump()}


@mcp.tool()
def get_queries() -> dict:
    """Get all saved queries from the database."""
    queries = schema_service.get_queries()
    return {"success": True, "queries": [q.model_dump() for q in queries], "count": len(queries)}


@mcp.tool()
def get_relationships() -> dict:
    """Get all foreign key relationships."""
    relationships = schema_service.get_relationships()
    return {
        "success": True,
        "relationships": [r.model_dump() for r in relationships],
        "count": len(relationships),
    }


# ============================================================================
# COM AUTOMATION TOOLS
# ============================================================================


@mcp.tool()
def launch_access(visible: bool = False) -> dict:
    """
    Launch Microsoft Access application.

    Args:
        visible: Whether to show Access window (default False)
    """
    result = com_automation_service.launch_access(visible)
    return {"success": result, "access_running": com_automation_service.is_access_running()}


@mcp.tool()
def close_access() -> dict:
    """Close Microsoft Access application."""
    result = com_automation_service.close_access()
    return {"success": result, "access_running": com_automation_service.is_access_running()}


@mcp.tool()
def get_forms() -> dict:
    """Get all forms in the database."""
    # Stub - requires COM
    return {"success": True, "forms": [], "count": 0}


@mcp.tool()
def get_reports() -> dict:
    """Get all reports in the database."""
    # Stub - requires COM
    return {"success": True, "reports": [], "count": 0}


@mcp.tool()
def get_macros() -> dict:
    """Get all macros in the database."""
    # Stub - requires COM
    return {"success": True, "macros": [], "count": 0}


@mcp.tool()
def get_modules() -> dict:
    """Get all VBA modules in the database."""
    # Stub - requires COM
    return {"success": True, "modules": [], "count": 0}


@mcp.tool()
def open_form(form_name: str) -> dict:
    """Open a form in Access."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented - requires COM"}


@mcp.tool()
def close_form(form_name: str) -> dict:
    """Close a form in Access."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented - requires COM"}


# ============================================================================
# VBA EXTENSIBILITY TOOLS
# ============================================================================


@mcp.tool()
def get_vba_projects() -> dict:
    """Get list of VBA projects."""
    # Stub - requires COM
    return {"success": True, "projects": []}


@mcp.tool()
def get_vba_code(module_name: str) -> dict:
    """
    Get VBA code from a module.

    Args:
        module_name: Name of the VBA module
    """
    # Stub - requires COM
    return {"success": False, "error": "Not implemented - requires COM"}


@mcp.tool()
def set_vba_code(module_name: str, code: str) -> dict:
    """
    Set VBA code in a module.

    Args:
        module_name: Name of the VBA module
        code: VBA code to inject
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = com_automation_service.set_vba_code(module_name, code)
    return {"success": result, "module": module_name}


@mcp.tool()
def add_vba_procedure(module_name: str, procedure_name: str, code: str) -> dict:
    """Add a VBA procedure to a module."""
    # Stub
    return {"success": False, "error": "Not implemented"}


@mcp.tool()
def compile_vba() -> dict:
    """Compile VBA code."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented - requires COM"}


# ============================================================================
# SYSTEM TABLE METADATA TOOLS
# ============================================================================


@mcp.tool()
def get_system_tables() -> dict:
    """Get system tables from the database."""
    # Stub - requires COM
    return {"success": True, "system_tables": [], "count": 0}


@mcp.tool()
def get_object_metadata(object_name: str) -> dict:
    """Get metadata for a database object."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


# ============================================================================
# FORM & CONTROL DISCOVERY TOOLS
# ============================================================================


@mcp.tool()
def form_exists(form_name: str) -> dict:
    """Check if a form exists."""
    # Stub - requires COM
    return {"success": True, "exists": False}


@mcp.tool()
def get_form_controls(form_name: str) -> dict:
    """Get all controls in a form."""
    # Stub - requires COM
    return {"success": True, "controls": [], "count": 0}


@mcp.tool()
def get_control_properties(form_name: str, control_name: str) -> dict:
    """Get properties of a control."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


@mcp.tool()
def set_control_property(form_name: str, control_name: str, property_name: str, value: str) -> dict:
    """Set a property of a control."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


# ============================================================================
# PERSISTENCE & VERSIONING TOOLS
# ============================================================================


@mcp.tool()
def export_form_to_text(form_name: str) -> dict:
    """Export a form to text representation."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


@mcp.tool()
def import_form_from_text(form_data: str) -> dict:
    """Import a form from text representation."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


@mcp.tool()
def delete_form(form_name: str) -> dict:
    """Delete a form from the database."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


@mcp.tool()
def export_report_to_text(report_name: str) -> dict:
    """Export a report to text representation."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


@mcp.tool()
def import_report_from_text(report_data: str) -> dict:
    """Import a report from text representation."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


@mcp.tool()
def delete_report(report_name: str) -> dict:
    """Delete a report from the database."""
    # Stub - requires COM
    return {"success": False, "error": "Not implemented"}


if __name__ == "__main__":
    mcp.run()
