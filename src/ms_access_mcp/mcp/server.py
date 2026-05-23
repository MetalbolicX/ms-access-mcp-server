from fastmcp import FastMCP
from ..services.connection import ConnectionService
from ..services.schema import SchemaService
from ..services.com_automation import COMAutomationService
from ..adapters.wincom import WinComAdapter
from ..adapters.odbc import OdbcAdapter
from ..services.migration import MigrationService
from ..config import ServerConfig
from ..auth import ApiKeyMiddleware
from ..path_guard import PathGuard

# Create FastMCP server
mcp = FastMCP("MS Access MCP Server")

# Initialize services
connection_service = ConnectionService()
schema_service = SchemaService()
com_automation_service = COMAutomationService()
migration_service = MigrationService()

# Lazily initialized config and path guard (only for HTTP mode via serve command)
_config: ServerConfig | None = None
_path_guard: PathGuard | None = None
_auth_middleware: ApiKeyMiddleware | None = None


def _init_http_config() -> None:
    """Initialize HTTP config, auth, and path guard from environment."""
    global _config, _path_guard, _auth_middleware
    if _config is None:
        _config = ServerConfig()
        _path_guard = PathGuard(allowed_dirs=_config.allowed_dirs)
        _auth_middleware = ApiKeyMiddleware(api_key=_config.api_key)

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
    # Validate path against allowed directories when HTTP config is active
    if _path_guard is not None:
        try:
            database_path = _path_guard.validate(database_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}

    adapter = WinComAdapter() if use_com else OdbcAdapter()

    result = connection_service.connect(database_path, adapter)
    if result:
        schema_service.set_adapter(adapter)
        com_automation_service.set_adapter(adapter)

    return {"success": result, "connected": result, "database": database_path}


@mcp.tool()
def disconnect_access() -> dict:
    """Disconnect from the current Access database."""
    connection_service.disconnect()
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
    forms = schema_service.get_forms()
    return {"success": True, "forms": [f.model_dump() for f in forms], "count": len(forms)}


@mcp.tool()
def get_reports() -> dict:
    """Get all reports in the database."""
    reports = schema_service.get_reports()
    return {"success": True, "reports": [r.model_dump() for r in reports], "count": len(reports)}


@mcp.tool()
def get_macros() -> dict:
    """Get all macros in the database."""
    macros = schema_service.get_macros()
    return {"success": True, "macros": [m.model_dump() for m in macros], "count": len(macros)}


@mcp.tool()
def get_modules() -> dict:
    """Get all VBA modules in the database."""
    modules = schema_service.get_modules()
    return {"success": True, "modules": [m.model_dump() for m in modules], "count": len(modules)}


@mcp.tool()
def open_form(form_name: str) -> dict:
    """Open a form in Access."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    # Form opening requires Access UI - not implemented in adapter
    return {"success": False, "error": "Not implemented - requires Access UI"}


@mcp.tool()
def close_form(form_name: str) -> dict:
    """Close a form in Access."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    return {"success": False, "error": "Not implemented - requires Access UI"}


# ============================================================================
# VBA EXTENSIBILITY TOOLS
# ============================================================================


@mcp.tool()
def get_vba_projects() -> dict:
    """Get list of VBA projects."""
    project_name = schema_service.get_vba_project_name()
    if project_name:
        return {"success": True, "projects": [project_name], "count": 1}
    return {"success": True, "projects": [], "count": 0}


@mcp.tool()
def get_vba_code(module_name: str) -> dict:
    """
    Get VBA code from a module.

    Args:
        module_name: Name of the VBA module
    """
    code = schema_service.get_vba_code(module_name)
    if not code:
        return {"success": False, "error": f"Module '{module_name}' not found or empty"}
    return {"success": True, "module": module_name, "code": code}


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
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.add_vba_procedure(module_name, procedure_name, code)
    return {"success": result, "module": module_name, "procedure": procedure_name}


@mcp.tool()
def compile_vba() -> dict:
    """Compile VBA code.

    Note: Access COM automation does not reliably expose a stable compile command
    across environments in this project setup, so this operation is currently
    treated as unsupported.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    return {
        "success": False,
        "error": "Not supported in current Access automation context",
    }


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
# FORM & CONTROL DISCOVERY TOOLS
# ============================================================================


@mcp.tool()
def form_exists(form_name: str) -> dict:
    """Check if a form exists."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    exists = schema_service.form_exists(form_name)
    return {"success": True, "exists": exists, "form": form_name}


@mcp.tool()
def get_form_controls(form_name: str) -> dict:
    """Get all controls in a form."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    controls = schema_service.get_form_controls(form_name)
    return {"success": True, "controls": [c.model_dump() for c in controls], "count": len(controls)}


@mcp.tool()
def get_control_properties(form_name: str, control_name: str) -> dict:
    """Get properties of a control."""
    # Control properties require opening form in design view - limited via COM
    return {"success": False, "error": "Not implemented - requires form design view"}


@mcp.tool()
def set_control_property(form_name: str, control_name: str, property_name: str, value: str) -> dict:
    """Set a property of a control."""
    return {"success": False, "error": "Not implemented - requires form design view"}


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
def import_form_from_text(form_data: str) -> dict:
    """Import a form from text representation."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.import_form_from_text(form_data)
    return {"success": result, "message": "Form imported" if result else "Import failed"}


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
def import_report_from_text(report_data: str) -> dict:
    """Import a report from text representation."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    result = schema_service.import_report_from_text(report_data)
    return {"success": result, "message": "Report imported" if result else "Import failed"}


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


# ============================================================================
# MIGRATION TOOLS
# ============================================================================


@mcp.tool()
def extract_schema(database_path: str) -> dict:
    """Extract schema from an Access database."""
    from ..adapters.wincom import WinComAdapter

    # Reuse active connection when possible to avoid opening the same Access DB
    # in a second COM adapter instance (can fail due to Access COM singleton behavior).
    active_adapter = connection_service.adapter
    active_db = connection_service.current_database
    if active_adapter is not None and active_db and connection_service.is_connected():
        norm_active = active_db.replace("\\", "/").lower()
        norm_target = database_path.replace("\\", "/").lower()
        if norm_active == norm_target:
            schema = migration_service.extract_schema(active_adapter, database_path)
            return {"success": True, "schema": schema.model_dump(), "reused_connection": True}

    adapter = WinComAdapter()
    if not adapter.connect(database_path):
        return {"success": False, "error": "Failed to connect to database"}
    schema = migration_service.extract_schema(adapter, database_path)
    adapter.disconnect()
    return {"success": True, "schema": schema.model_dump(), "reused_connection": False}


@mcp.tool()
def upload_schema(target_type: str, connection_string: str, schema_json: dict) -> dict:
    """Upload schema to target database.
    
    Args:
        target_type: Target database type (postgres, mysql, mariadb, sqlite, sqlserver)
        connection_string: Connection string for target database
        schema_json: ExtractedSchema as dict
    """
    from ..models.migration import ExtractedSchema
    schema = ExtractedSchema(**schema_json)
    result = migration_service.upload_schema(target_type, connection_string, schema)
    return result


@mcp.tool()
def transfer_data(target_type: str, connection_string: str, database_path: str, schema_json: dict | None = None) -> dict:
    """Transfer data from Access to target database.
    
    Args:
        target_type: Target database type (postgres, mysql, mariadb, sqlite, sqlserver)
        connection_string: Connection string for target database
        database_path: Path to Access database
        schema_json: Optional ExtractedSchema dict (will extract if not provided)
    """
    from ..adapters.wincom import WinComAdapter
    from ..models.migration import ExtractedSchema
    
    adapter = WinComAdapter()
    if not adapter.connect(database_path):
        return {"success": False, "error": "Failed to connect to Access database"}
    
    if schema_json:
        schema = ExtractedSchema(**schema_json)
    else:
        schema = migration_service.extract_schema(adapter, database_path)
    
    result = migration_service.transfer_data(target_type, connection_string, schema, adapter)
    adapter.disconnect()
    return result


@mcp.tool()
def get_migration_status(job_id: str) -> dict:
    """Get status of a migration job.

    Args:
        job_id: Migration job ID returned from transfer_data
    """
    return migration_service.get_job_status(job_id)


# ============================================================================
# ER DIAGRAM TOOLS
# ============================================================================


@mcp.tool()
def get_er_diagram() -> dict:
    """
    Get the database schema as nodes and edges for ER diagram visualization.

    Returns:
        nodes: List of table nodes with columns
        edges: List of relationship edges (FK connections)
    """
    tables = schema_service.get_tables()
    relationships = schema_service.get_relationships()

    nodes = []
    for table in tables:
        nodes.append({
            "id": table.name,
            "type": "table",
            "data": {
                "label": table.name,
                "columns": [f.model_dump() for f in table.fields],
                "record_count": table.record_count,
            },
        })

    edges = []
    for rel in relationships:
        edges.append({
            "id": rel.name,
            "source": rel.foreign_table,
            "target": rel.table,
            "label": rel.name,
            "animated": False,
        })

    return {
        "success": True,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def run_http(host: str = "127.0.0.1", port: int = 8000, transport: str = "http") -> None:
    """Run the MCP server with HTTP transport and auth.

    Args:
        host: Bind address (default 127.0.0.1)
        port: Bind port (default 8000)
        transport: HTTP transport type ("http", "streamable-http", "sse")
    """
    _init_http_config()
    mcp.run(transport=transport, host=host, port=port)
