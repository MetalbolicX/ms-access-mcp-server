"""Linked table tools for MS Access database — Phase 1 SDD."""
from .server import mcp
from .container import get_container
from ._helpers import guard_destructive

from ..orchestrators.credential_vault import CredentialVault
from ..orchestrators.connect_policy import ConnectPolicy


def _get_vault() -> CredentialVault:
    """Accessor for the shared credential vault from the service container.

    This function is the seam that tests patch to inject a mock vault.
    Always delegates to get_container() so tests that reset the container
    get a fresh vault each time.
    """
    return get_container().credential_vault


# Lazy import to avoid circular dependency issues at module load time
def _get_orchestrator():
    from ..orchestrators.linked_table_service import LinkedTableService
    return LinkedTableService()


def _pool():
    """Lazy accessor for the connection pool."""
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


def _ensure_connected(connection_name: str = "default"):
    """Check connection and return adapter, or None if not connected."""
    if not _check_connected(connection_name):
        return None
    return _get_adapter(connection_name)


@mcp.tool()
def get_linked_tables(connection_name: str = "default") -> dict:
    """
    Get all linked tables from the connected database.

    Linked tables connect to external data sources (ODBC, Access, Excel, etc.)
    via connection strings stored in the TableDef's Connect property.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
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
    # Validate connect_string via ConnectPolicy before any adapter operations
    policy = ConnectPolicy()
    result = policy.validate(connect_string)
    if not result.allowed:
        return {"success": False, "error": "; ".join(result.reasons)}
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
def refresh_linked_table(
    name: str,
    connection_name: str = "default",
    connect_string: str | None = None,
    password: str | None = None,
    server_id: str | None = None,
) -> dict:
    """
    Refresh the link for a linked table.

    Useful when the remote table schema has changed.

    Args:
        name: Name of the linked table to refresh
        connection_name: Connection identifier (defaults to "default")
        connect_string: Optional new connection string (e.g., "ODBC;DSN=NewDSN")
        password: Optional password for re-injection during refresh
        server_id: Optional server_id to retrieve password from vault
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    # Validate connect_string via ConnectPolicy if provided
    if connect_string is not None:
        policy = ConnectPolicy()
        validation_result = policy.validate(connect_string)
        if not validation_result.allowed:
            return {"success": False, "error": "; ".join(validation_result.reasons)}
    try:
        # Handle server_id: if provided without password, retrieve from vault
        effective_password = password
        if server_id is not None and password is None:
            effective_password = _get_vault().retrieve(server_id)
            if effective_password is None:
                return {
                    "success": False,
                    "error": f"server_id '{server_id}' not found in credential store. "
                             "Use store_credential first.",
                }
        # Store password in vault if both server_id and password provided
        if server_id is not None and password is not None:
            _get_vault().store(server_id, password)
            effective_password = password

        # Inject password into connect_string if provided
        effective_connect_string = connect_string
        if effective_password and connect_string:
            sep = ";" if not connect_string.endswith(";") else ""
            effective_connect_string = f"{connect_string}{sep}PWD={effective_password}"
        result = adapter.refresh_linked_table(name, connect_string=effective_connect_string)
        return result
    except NotImplementedError as e:
        return {"success": False, "error": f"This operation requires COM automation ({e}). Use connect_access with use_com=True on Windows."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def unlink_table(name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Unlink (delete) a linked table definition.

    This removes the linked table entry from the database without affecting
    the remote data source.

    Args:
        name: Name of the linked table to unlink
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to proceed with unlink
        dry_run: If True, returns preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "unlink_table", name=name)
    if guard is not None:
        return guard
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


@mcp.tool()
def store_credential(server_id: str, password: str, connection_name: str = "default") -> dict:
    """
    Store a credential in the vault for later use with server_id.

    The stored password can be retrieved automatically by upsert_linked_table
    and refresh_linked_table when server_id is provided without password.

    Args:
        server_id: Unique identifier for the server/connection
        password: Plaintext password to store securely
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    try:
        _get_vault().store(server_id, password)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def clear_credentials(connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Clear all stored credentials from the vault.

    Use this to securely wipe all cached passwords when they are no longer needed.

    Args:
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to proceed with clearing all credentials
        dry_run: If True, returns preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "clear_credentials")
    if guard is not None:
        return guard
    try:
        _get_vault().clear()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def upsert_linked_table(
    local_name: str,
    remote_name: str,
    connect_string: str,
    connection_name: str = "default",
    password: str | None = None,
    preserve_hidden: bool = True,
    server_id: str | None = None,
) -> dict:
    """
    Upsert a linked table — create, refresh, or recreate based on current state.

    Resolves to exactly one of three actions:
    - create: table does not exist
    - refresh: table exists with matching remote name
    - recreate: table exists but remote name differs

    Args:
        local_name: Local table name in the .accdb
        remote_name: Remote table name (e.g., 'dbo.Orders')
        connect_string: ODBC or other connection string (e.g., "ODBC;DSN=MyDSN")
        connection_name: Connection identifier (defaults to "default")
        password: Optional password for re-injection during refresh/recreate
        preserve_hidden: If True, preserve dbHiddenObject flag on recreate (default True)
        server_id: Optional server_id to retrieve password from vault (if password not provided)
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    # Validate connect_string via ConnectPolicy before any operations
    policy = ConnectPolicy()
    validation_result = policy.validate(connect_string)
    if not validation_result.allowed:
        return {"success": False, "error": "; ".join(validation_result.reasons)}
    try:
        # Handle server_id: if provided without password, retrieve from vault
        effective_password = password
        if server_id is not None and password is None:
            effective_password = _get_vault().retrieve(server_id)
            if effective_password is None:
                return {
                    "success": False,
                    "error": f"server_id '{server_id}' not found in credential store. "
                             "Use store_credential first.",
                }
        # Store password in vault if both server_id and password provided
        if server_id is not None and password is not None:
            _get_vault().store(server_id, password)
            effective_password = password

        service = _get_orchestrator()
        result = service.upsert_linked_table(
            adapter,
            local_name=local_name,
            remote_name=remote_name,
            connect_string=connect_string,
            password=effective_password,
            preserve_hidden=preserve_hidden,
        )
        return result
    except NotImplementedError as e:
        return {"success": False, "error": f"This operation requires COM automation ({e}). Use connect_access with use_com=True on Windows."}
    except Exception as e:
        return {"success": False, "error": str(e)}
