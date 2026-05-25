"""Linked table tools for MS Access database."""
from .server import mcp, connection_service


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
