"""VBA Extensibility tools for MS Access database — Phase 1 SDD."""
from .server import mcp
from .container import get_container
from ._helpers import guard_destructive


def _pool():
    return get_container().connection_pool


def _dev_copy():
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


@mcp.tool()
def get_vba_projects(connection_name: str = "default") -> dict:
    """
    Get list of VBA projects.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    project_name = adapter.get_vba_project_name()
    if project_name:
        return {"success": True, "projects": [project_name], "count": 1}
    return {"success": True, "projects": [], "count": 0}


@mcp.tool()
def get_vba_code(module_name: str, connection_name: str = "default") -> dict:
    """
    Get VBA code from a module.

    Args:
        module_name: Name of the VBA module
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    code = adapter.get_vba_code(module_name)
    if not code:
        return {"success": False, "error": f"Module '{module_name}' not found or empty"}
    return {"success": True, "module": module_name, "code": code}


@mcp.tool()
def set_vba_code(module_name: str, code: str, connection_name: str = "default", confirm: bool = False) -> dict:
    """
    Set VBA code in a module.

    Args:
        module_name: Name of the VBA module
        code: VBA code to inject
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to overwrite existing code
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    guard = guard_destructive(confirm, False, "set_vba_code", module_name=module_name)
    if guard is not None:
        return guard

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    # Compile with retry
    compile_result = _dev_copy().compile_with_retry(adapter, module_name, code)
    return {
        "success": compile_result.get("success", False),
        "module": module_name,
        "compile": compile_result,
    }


@mcp.tool()
def add_vba_procedure(module_name: str, procedure_name: str, code: str, connection_name: str = "default") -> dict:
    """
    Add a VBA procedure to a module.

    Args:
        module_name: Name of the VBA module
        procedure_name: Name of the procedure to add
        code: VBA code for the procedure
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    # Write code first
    write_ok = adapter.add_vba_procedure(module_name, procedure_name, code)
    if not write_ok:
        return {"success": False, "module": module_name, "procedure": procedure_name}

    # Compile with retry
    compile_result = _dev_copy().compile_with_retry(adapter, module_name, code)
    return {
        "success": compile_result.get("success", False),
        "module": module_name,
        "procedure": procedure_name,
        "compile": compile_result,
    }


@mcp.tool()
def compile_vba(connection_name: str = "default") -> dict:
    """
    Compile VBA code in the database.

    Attempts to compile all VBA modules. Returns structured result
    with success status and error message on failure.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    result = adapter.compile_vba()
    return result


@mcp.tool()
def save_database(connection_name: str = "default") -> dict:
    """
    Save all VBA modules and database changes.

    Persists any in-memory VBA module changes to the .accdb file.
    Use this after creating or editing VBA code to avoid losing
    changes when Access is closed.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    result = adapter.save_database()
    return result


@mcp.tool()
def delete_module(module_name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Delete a VBA module from the database.

    Args:
        module_name: Name of the VBA module to delete
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the deletion
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    guard = guard_destructive(confirm, dry_run, "delete_module", module_name=module_name)
    if guard is not None:
        return guard

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.delete_module(module_name)
        return {"success": result, "module": module_name}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def vba_list_procedures(module_name: str, connection_name: str = "default") -> dict:
    """
    List all procedures in a VBA module with their line ranges.

    Args:
        module_name: Name of the VBA module to inspect
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    procedures = adapter.vba_list_procedures(module_name)
    return {"success": True, "module": module_name, "procedures": procedures}


@mcp.tool()
def vba_get_procedure(module_name: str, procedure_name: str, connection_name: str = "default") -> dict:
    """
    Get the full source code of a specific VBA procedure.

    Args:
        module_name: Name of the VBA module
        procedure_name: Name of the procedure to retrieve
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    result = adapter.vba_get_procedure(module_name, procedure_name)
    if not result:
        return {"success": False, "error": f"Procedure '{procedure_name}' not found in module '{module_name}'"}
    return {"success": True, "module": module_name, **result}


@mcp.tool()
def vba_replace_procedure(module_name: str, procedure_name: str, code: str, connection_name: str = "default") -> dict:
    """
    Replace a VBA procedure's body with new code.

    Preserves the procedure signature. The code should include the full
    procedure (Sub/Function statement through End Sub/End Function).

    Args:
        module_name: Name of the VBA module
        procedure_name: Name of the procedure to replace
        code: New VBA code for the procedure
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    success = adapter.vba_replace_procedure(module_name, procedure_name, code)
    if not success:
        return {"success": False, "error": f"Failed to replace procedure '{procedure_name}' in module '{module_name}'"}

    return {"success": True, "module": module_name, "procedure": procedure_name}


@mcp.tool()
def save_query(query_name: str, sql: str, overwrite: bool = False, connection_name: str = "default") -> dict:
    """
    Save or update a saved query definition in the Access database.

    If overwrite=False and the query exists, returns an error.
    If overwrite=True, checks if the query exists first, then creates or updates.

    Args:
        query_name: Name of the query
        sql: SQL statement for the query
        overwrite: If True, update existing query; if False, error if exists
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    if overwrite:
        # Try to get the existing query first
        existing_queries = adapter.get_queries()
        query_exists = any(q.name == query_name for q in existing_queries)

        if query_exists:
            result = adapter.set_query_sql(query_name, sql)
            if result.get("success"):
                return {"success": True, "query": query_name, "action": "updated"}
            return {"success": False, "error": f"Failed to update query: {result.get('error', 'Unknown error')}"}
        else:
            result = adapter.create_query(query_name, sql)
            if result.get("success"):
                return {"success": True, "query": query_name, "action": "created"}
            return {"success": False, "error": f"Failed to create query: {result.get('error', 'Unknown error')}"}
    else:
        # Check if query already exists
        existing_queries = adapter.get_queries()
        query_exists = any(q.name == query_name for q in existing_queries)

        if query_exists:
            return {"success": False, "error": f"Query '{query_name}' already exists. Use overwrite=True to update."}

        result = adapter.create_query(query_name, sql)
        if result.get("success"):
            return {"success": True, "query": query_name, "action": "created"}
        return {"success": False, "error": f"Failed to create query: {result.get('error', 'Unknown error')}"}
