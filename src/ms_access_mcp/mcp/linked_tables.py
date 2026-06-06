"""Linked table tools for MS Access database — Phase 1 SDD."""
from .server import mcp, connection_service


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return connection_service.get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return connection_service.is_connected(connection_name)


@mcp.tool()
def get_linked_tables(connection_name: str = "default") -> dict:
    """
    Get all linked tables from the connected database.

    Linked tables connect to external data sources (ODBC, Access, Excel, etc.)
    via connection strings stored in the TableDef's Connect property.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.get_linked_tables()
        return result
    except NotImplementedError as e:
        return {"success": False, "error": f"This operation requires COM automation ({e}). Use connect_access with use_com=True on Windows."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def create_linked_table(name: str, source_table: str, connect_string: str, connection_name: str = "default") -> dict:
    """
    Create a linked table definition.

    Args:
        name: Name for the linked table in the Access database
        source_table: Name of the remote table to link to
        connect_string: ODBC or other connection string (e.g., "ODBC;DSN=MyDSN")
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_linked_table(name, source_table, connect_string)
        return result
    except NotImplementedError as e:
        return {"success": False, "error": f"This operation requires COM automation ({e}). Use connect_access with use_com=True on Windows."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def refresh_linked_table(name: str, connection_name: str = "default") -> dict:
    """
    Refresh the link for a linked table.

    Useful when the remote table schema has changed.

    Args:
        name: Name of the linked table to refresh
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.refresh_linked_table(name)
        return result
    except NotImplementedError as e:
        return {"success": False, "error": f"This operation requires COM automation ({e}). Use connect_access with use_com=True on Windows."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def unlink_table(name: str, connection_name: str = "default") -> dict:
    """
    Unlink (delete) a linked table definition.

    This removes the linked table entry from the database without affecting
    the remote data source.

    Args:
        name: Name of the linked table to unlink
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.unlink_table(name)
        return result
    except NotImplementedError as e:
        return {"success": False, "error": f"This operation requires COM automation ({e}). Use connect_access with use_com=True on Windows."}
    except Exception as e:
        return {"success": False, "error": str(e)}
