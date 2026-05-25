"""VBA Extensibility tools for MS Access database."""
from .server import mcp, connection_service, schema_service, dev_copy_service


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


@mcp.tool()
def delete_module(module_name: str) -> dict:
    """Delete a VBA module from the database.

    Args:
        module_name: Name of the VBA module to delete
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.delete_module(module_name)
        return {"success": result, "module": module_name}
    except Exception as e:
        return {"success": False, "error": str(e)}
