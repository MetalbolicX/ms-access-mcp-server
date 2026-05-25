from fastmcp import FastMCP
from ..services.connection import ConnectionService
from ..services.schema import SchemaService
from ..services.com_automation import COMAutomationService
from ..adapters.wincom import WinComAdapter
from ..adapters.odbc import OdbcAdapter
from ..services.migration import MigrationService
from ..services.dev_copy_service import DevCopyService
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
dev_copy_service = DevCopyService()

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
def get_relationships() -> dict:
    """Get all foreign key relationships."""
    relationships = schema_service.get_relationships()
    return {
        "success": True,
        "relationships": [r.model_dump() for r in relationships],
        "count": len(relationships),
    }


@mcp.tool()
def get_queries() -> dict:
    """Get all saved queries from the database."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        queries = adapter.get_queries()
        return {"success": True, "queries": [q.model_dump() for q in queries], "count": len(queries)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def create_query(name: str, sql: str) -> dict:
    """
    Create a stored query.

    Args:
        name: Name of the query to create
        sql: SQL statement for the query
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_query(name, sql)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def set_query_sql(name: str, sql: str) -> dict:
    """
    Update SQL of an existing query.

    Args:
        name: Name of the existing query
        sql: New SQL statement
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.set_query_sql(name, sql)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_query(name: str) -> dict:
    """
    Delete a stored query.

    Args:
        name: Name of the query to delete
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.delete_query(name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def create_table(table_name: str, columns: list[dict]) -> dict:
    """
    Create a new table in the connected database.

    Args:
        table_name: Name of the table to create
        columns: List of column definitions as dicts with keys:
                 - name (str): Column name
                 - type (str): Data type (Text, Long Integer, Integer, Boolean,
                   Date/Time, Currency, Memo, Double, Single, Binary)
                 - size (int, optional): Size for Text type (default 255)
                 - nullable (bool, optional): Whether column allows NULL (default True)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_table(table_name, columns)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_table(table_name: str) -> dict:
    """
    Delete a table from the connected database.

    Args:
        table_name: Name of the table to delete
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.delete_table(table_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def query_data(sql: str, params: list | None = None) -> dict:
    """
    Execute SQL query and return results.

    Args:
        sql: SQL query to execute
        params: Optional list of parameters for parameterized queries
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.execute_query(sql, params)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def insert_data(table_name: str, data: dict | list[dict]) -> dict:
    """
    Insert one or more rows into a table.

    Args:
        table_name: Name of the table
        data: A single dict for one row, or a list of dicts for multiple rows
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.insert_data(table_name, data)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def update_data(table_name: str, set_dict: dict, where_dict: dict | str | None = None) -> dict:
    """
    Update rows in a table.

    Args:
        table_name: Name of the table
        set_dict: Dict of column=value pairs to set
        where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.update_data(table_name, set_dict, where_dict)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_data(table_name: str, where_dict: dict | str | None = None) -> dict:
    """
    Delete rows from a table.

    Args:
        table_name: Name of the table
        where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.delete_data(table_name, where_dict)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def export_table_csv(table_or_query_name: str, file_path: str, delimiter: str = ",", header: bool = True) -> dict:
    """
    Export a table or query to a CSV file.

    Args:
        table_or_query_name: Name of the table or query to export
        file_path: Path to the output CSV file
        delimiter: Field delimiter (default ',')
        header: Whether to write header row (default True)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.export_table_csv(table_or_query_name, file_path, delimiter, header)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def export_query_json(query_name: str, file_path: str, pretty: bool = False) -> dict:
    """
    Export a query to a JSON file.

    Args:
        query_name: Name of the query to export
        file_path: Path to the output JSON file
        pretty: Whether to format JSON with indentation (default False)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.export_query_json(query_name, file_path, pretty)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


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
    """Open a form in Access (appears on the server desktop)."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    result = com_automation_service.open_form(form_name)
    return {"success": result, "form": form_name, "message": "Form opened" if result else "Failed to open form"}


@mcp.tool()
def close_form(form_name: str) -> dict:
    """Close an open form."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    result = com_automation_service.close_form(form_name)
    return {"success": result, "form": form_name, "message": "Form closed" if result else "Failed to close form"}


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

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    # Compile with retry
    compile_result = dev_copy_service.compile_with_retry(adapter, module_name, code)
    return {
        "success": compile_result.get("success", False),
        "module": module_name,
        "compile": compile_result,
    }


@mcp.tool()
def add_vba_procedure(module_name: str, procedure_name: str, code: str) -> dict:
    """Add a VBA procedure to a module."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    # Write code first
    write_ok = adapter.add_vba_procedure(module_name, procedure_name, code)
    if not write_ok:
        return {"success": False, "module": module_name, "procedure": procedure_name}

    # Compile with retry
    compile_result = dev_copy_service.compile_with_retry(adapter, module_name, code)
    return {
        "success": compile_result.get("success", False),
        "module": module_name,
        "procedure": procedure_name,
        "compile": compile_result,
    }


@mcp.tool()
def compile_vba() -> dict:
    """Compile VBA code in the database.

    Attempts to compile all VBA modules. Returns structured result
    with success status and error message on failure.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    result = adapter.compile_vba()
    return result


@mcp.tool()
def save_database() -> dict:
    """Save all VBA modules and database changes.

    Persists any in-memory VBA module changes to the .accdb file.
    Use this after creating or editing VBA code to avoid losing
    changes when Access is closed.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    result = adapter.save_database()
    return result


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
    """Get all properties of a specific control in a form.

    Opens the form in design view, reads the control's properties,
    then closes the form.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    props = com_automation_service.get_control_properties(form_name, control_name)
    if not props:
        return {"success": False, "error": f"Control '{control_name}' not found in form '{form_name}'"}
    return {"success": True, "form": form_name, "control": control_name, "properties": props}


@mcp.tool()
def set_control_property(form_name: str, control_name: str, property_name: str, value: str) -> dict:
    """Set a property of a control in a form.

    Opens the form in design view, sets the property, and saves.
    Some properties (ControlType, Name) are read-only and will fail.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    result = com_automation_service.set_control_property(form_name, control_name, property_name, value)
    return {"success": result, "form": form_name, "control": control_name, "property": property_name, "value": value}


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


# ============================================================================
# LINKED TABLE TOOLS
# ============================================================================


@mcp.tool()
def get_linked_tables() -> dict:
    """Get all linked tables from the connected database.

    Linked tables connect to external data sources (ODBC, Access, Excel, etc.)
    via connection strings stored in the TableDef's Connect property.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.get_linked_tables()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def create_linked_table(name: str, source_table: str, connect_string: str) -> dict:
    """Create a linked table definition.

    Args:
        name: Name for the linked table in the Access database
        source_table: Name of the remote table to link to
        connect_string: ODBC or other connection string (e.g., "ODBC;DSN=MyDSN")
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_linked_table(name, source_table, connect_string)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def refresh_linked_table(name: str) -> dict:
    """Refresh the link for a linked table.

    Useful when the remote table schema has changed.

    Args:
        name: Name of the linked table to refresh
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.refresh_linked_table(name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def unlink_table(name: str) -> dict:
    """Unlink (delete) a linked table definition.

    This removes the linked table entry from the database without affecting
    the remote data source.

    Args:
        name: Name of the linked table to unlink
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.unlink_table(name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_http(host: str = "127.0.0.1", port: int = 8000, transport: str = "http") -> None:
    """Run the MCP server with HTTP transport and auth.

    Args:
        host: Bind address (default 127.0.0.1)
        port: Bind port (default 8000)
        transport: HTTP transport type ("http", "streamable-http", "sse")
    """
    _init_http_config()
    mcp.run(transport=transport, host=host, port=port)


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
def import_form_from_text(form_name: str, file_path: str) -> dict:
    """Import a form from a .txt text file.

    Deletes the original form and recreates from the .txt file.

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
