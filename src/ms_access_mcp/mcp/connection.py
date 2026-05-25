"""Connection management tools for MS Access database."""
from .server import mcp, connection_service, schema_service, com_automation_service, _path_guard
from ..adapters.wincom import WinComAdapter
from ..adapters.odbc import OdbcAdapter


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
