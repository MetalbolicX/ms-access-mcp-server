"""Connection management tools for MS Access database — Phase 1 SDD.

Tools:
- connect_access(database_path, use_com=False, backend=None, name=None) → connects named connection
- create_access_database(database_path, name="default", connect=True) → creates blank .accdb
- disconnect_access(name=None) → disconnects named connection
- list_connections() → returns all connections with status (NEW)
- set_active_connection(name) → sets active context (NEW)
- get_active_connection() → returns active connection name (NEW)
- is_connected() → checks connection status
"""

import os
import sys
from typing import Literal, Optional

from .server import mcp, _get_path_guard

from ..adapters.wincom import WinComAdapter
from ..adapters.odbc import OdbcAdapter
from ..services.database_bootstrap import create_blank_database


def _pool():
    """Lazy accessor for connection pool (avoids circular import at module level)."""
    from .container import get_container

    return get_container().connection_pool


def _format_connect_response(state, database_path, name):
    """Build a standardized connect response dict.

    Shared by ``connect_access`` and ``create_access_database`` so both
    tools return the same response shape (``success``, ``connected``,
    ``database``, ``name``, optional ``error``). When ``state`` is truthy
    the connect succeeded; when falsy the response describes the
    failure with ``connected=False`` and a human-readable ``error``.
    """
    if state:
        return {
            "success": True,
            "connected": True,
            "database": database_path,
            "name": name,
        }
    return {
        "success": False,
        "connected": False,
        "database": database_path,
        "name": name,
        "error": f"connect failed for {name}",
    }


@mcp.tool()
def connect_access(
    database_path: str,
    use_com: bool = False,
    name: str = "default",
    password: str = "",
    backend: Optional[Literal["odbc", "com", "dao", "auto"]] = None,
) -> dict:
    """
    Connect to an Access database.

    Args:
        database_path: Path to .accdb or .mdb file
        use_com: Use COM automation (True) or ODBC only (False). Kept for
            backward compatibility — ignored when ``backend`` is set.
        name: Named connection identifier (defaults to "default")
        password: Optional database password for password-protected DBs
        backend: Explicit backend selector (slice 2 of
            dao-first-linked-tables-properties). One of ``"odbc"``,
            ``"com"``, ``"dao"``, or ``"auto"`` (default). When set,
            takes precedence over ``use_com``.
    """
    # Validate path against allowed directories when HTTP config is active
    path_guard = _get_path_guard()
    if path_guard is not None:
        try:
            database_path = path_guard.validate(database_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}

    # Resolve adapter_type: explicit backend param wins over use_com.
    # When both are unset, fall back to the legacy use_com behaviour.
    if backend is not None:
        adapter_type: Literal["odbc", "com", "dao", "auto"] = backend
    else:
        adapter_type = "com" if use_com else "odbc"

    try:
        # Use the new named connection API with password support
        state = _pool().connect(name, database_path, adapter_type, password=password)
        return _format_connect_response(state, database_path, name)
    except KeyError as e:
        return {"success": False, "error": str(e)}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def create_access_database(
    database_path: str,
    name: str = "default",
    connect: bool = True,
) -> dict:
    """
    Create a blank ``.accdb`` database on Windows and optionally connect to it.

    This is a bootstrap tool: it does not require an existing connection
    and can be the first call against a fresh deployment. The tool
    short-circuits on non-Windows hosts (REQ-8) and refuses to overwrite
    an existing file (REQ-3). When ``connect=True`` (the default), the
    newly created database is also registered as a named connection in
    the connection pool; when ``connect=False`` only the file is
    created on disk and the caller can connect later.

    Args:
        database_path: Absolute path where the new ``.accdb`` will be
            created. Parent directory must already exist (the tool does
            not auto-create parent directories).
        name: Named connection identifier used when ``connect=True``
            (defaults to ``"default"``).
        connect: If ``True`` (default), the new database is connected
            via the COM adapter after creation. If ``False``, only the
            file is created.

    Returns:
        dict with ``success``, ``database`` (path), ``connected``
        (whether a connection was established), and ``name`` (the
        connection name). On failure, includes ``error``.
    """
    # Validate path against allowed directories when HTTP config is active.
    path_guard = _get_path_guard()
    if path_guard is not None:
        try:
            database_path = path_guard.validate(database_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}

    # REQ-8: refuse on non-Windows BEFORE any pywin32 work happens.
    # The bootstrap service also guards on sys.platform, but we short
    # circuit here so the user sees a tool-shaped error (not the
    # service's internal "PlatformUnsupported" code).
    if sys.platform != "win32":
        return {
            "success": False,
            "error": "create_access_database requires Windows",
        }

    # REQ-3: refuse to overwrite an existing file. We do not check
    # whether the path is a directory vs. a file — ``os.path.exists``
    # is True for both, and we want to reject either way (creating a
    # ``.accdb`` on top of a directory is never valid).
    if os.path.exists(database_path):
        return {
            "success": False,
            "error": f"File already exists: {database_path}",
            "database": database_path,
        }

    # Name-collision short-circuit: pool.connect() raises KeyError when
    # the name is already in the pool. We check first so the user gets
    # a clean tool-shaped error (and so we don't waste a bootstrap
    # round-trip if the caller forgot to disconnect the old one).
    if connect and name in _pool().list():
        return {
            "success": False,
            "error": f"Connection '{name}' already exists; disconnect it first",
            "database": database_path,
        }

    # Bootstrap: delegate the actual COM/DAO work to the service.
    bootstrap = create_blank_database(database_path)
    if not bootstrap.success:
        return {
            "success": False,
            "error": bootstrap.error,
            "database": database_path,
        }

    # Optional connect: route through the shared response helper so
    # both tools share one shape.
    if connect:
        try:
            state = _pool().connect(name, database_path, "com", password="")
        except KeyError as e:
            return {
                "success": False,
                "error": f"Connection '{name}' already exists: {e}",
                "database": database_path,
            }
        except RuntimeError as e:
            return {
                "success": False,
                "error": str(e),
                "database": database_path,
            }
        return _format_connect_response(state, database_path, name)

    # connect=False: file was created but we did NOT register a
    # connection. The "connected=False" field tells the caller that
    # a follow-up connect_access is required to use the database.
    return {
        "success": True,
        "database": database_path,
        "connected": False,
        "name": name,
    }


@mcp.tool()
def disconnect_access(name: str = "default") -> dict:
    """
    Disconnect a named connection.

    Args:
        name: Connection identifier to disconnect (defaults to "default")
    """
    try:
        _pool().disconnect(name)
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
    connections = _pool().list()
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
        "active": _pool().get_active(),
    }


@mcp.tool()
def set_active_connection(name: str) -> dict:
    """
    Set the active connection context.

    Args:
        name: Connection identifier to make active
    """
    try:
        _pool().set_active(name)
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
        "active": _pool().get_active(),
    }


@mcp.tool()
def is_connected(connection_name: str = "default") -> dict:
    """
    Check if a connection is established.

    Args:
        connection_name: Connection identifier to check (defaults to "default")
    """
    pool = _pool()
    connected = pool.is_connected(connection_name)
    database = pool.current_database
    return {"connected": connected, "database": database, "name": connection_name}
