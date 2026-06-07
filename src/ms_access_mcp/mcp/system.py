"""System table metadata tools for MS Access."""
from .server import mcp
from .recovery import recover_access, diagnose_environment  # noqa: F401, E402


def _pool():
    """Lazy accessor for connection pool (avoids circular import at module level)."""
    from .container import get_container
    return get_container().connection_pool


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
def get_system_tables(connection_name: str = "default") -> dict:
    """
    Get system tables from the database.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    tables = adapter.get_system_tables()
    return {"success": True, "system_tables": [t.model_dump() for t in tables], "count": len(tables)}


@mcp.tool()
def get_object_metadata(object_name: str, connection_name: str = "default") -> dict:
    """
    Get metadata for a database object.

    Args:
        object_name: Name of the database object
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    metadata = adapter.get_object_metadata(object_name)
    if not metadata:
        return {"success": False, "error": f"Object '{object_name}' not found"}
    return {"success": True, "metadata": metadata}
