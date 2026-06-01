"""Connection management tools for MS Access database — Phase 1 SDD.

Tools:
- connect_access(database_path, use_com=False, name=None) → connects named connection
- disconnect_access(name=None) → disconnects named connection
- list_connections() → returns all connections with status (NEW)
- set_active_connection(name) → sets active context (NEW)
- get_active_connection() → returns active connection name (NEW)
- is_connected() → checks connection status
"""
from .server import mcp, connection_service, schema_service, com_automation_service, _path_guard
from ..adapters.wincom import WinComAdapter
from ..adapters.odbc import OdbcAdapter


@mcp.tool()
def connect_access(database_path: str, use_com: bool = False, name: str = "default") -> dict:
    """
    Connect to an Access database.

    Args:
        database_path: Path to .accdb or .mdb file
        use_com: Use COM automation (True) or ODBC only (False)
        name: Named connection identifier (defaults to "default")
    """
    # Validate path against allowed directories when HTTP config is active
    if _path_guard is not None:
        try:
            database_path = _path_guard.validate(database_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}

    adapter = WinComAdapter() if use_com else OdbcAdapter()

    try:
        # Use backward-compatible 2-arg API for the actual connection
        result = connection_service.connect(database_path, adapter)
        if result:
            schema_service.set_adapter(adapter)
            com_automation_service.set_adapter(adapter)
        return {"success": result, "connected": result, "database": database_path, "name": name}
    except KeyError as e:
        return {"success": False, "error": str(e)}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def disconnect_access(name: str = "default") -> dict:
    """
    Disconnect a named connection.

    Args:
        name: Connection identifier to disconnect (defaults to "default")
    """
    try:
        connection_service.disconnect(name)
        return {"success": True, "message": f"Disconnected '{name}'"}
    except KeyError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def list_connections() -> dict:
    """
    List all managed connections with their status.

    Returns:
        dict with connection names and their details (db_path, adapter_type, status)
    """
    connections = connection_service.list()
    result = {}
    for conn_name, state in connections.items():
        result[conn_name] = {
            "database": state.db_path,
            "adapter_type": state.adapter_type,
            "connected": state.adapter.is_connected(),
            "created_at": state.created_at.isoformat(),
        }
    return {
        "success": True,
        "connections": result,
        "count": len(connections),
        "active": connection_service.get_active(),
    }


@mcp.tool()
def set_active_connection(name: str) -> dict:
    """
    Set the active connection context.

    Args:
        name: Connection identifier to make active
    """
    try:
        connection_service.set_active(name)
        return {"success": True, "active": name}
    except KeyError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_active_connection() -> dict:
    """
    Get the name of the currently active connection.
    """
    return {
        "success": True,
        "active": connection_service.get_active(),
    }


@mcp.tool()
def is_connected(connection_name: str = "default") -> dict:
    """
    Check if a connection is established.

    Args:
        connection_name: Connection identifier to check (defaults to "default")
    """
    # Use the connection service's is_connected method for proper mocking support
    connected = connection_service.is_connected(connection_name)
    # Use current_database for backward compatibility
    database = connection_service.current_database
    return {"connected": connected, "database": database, "name": connection_name}
