"""Migration tools for MS Access database — Phase 1 SDD."""
from types import SimpleNamespace

from .server import mcp, _get_path_guard
from .container import get_container
from ._helpers import _validate_path
from ..services.backend_selector import BackendSelector, SCHEMA_CAPS, DATA_READ_CAPS


def _pool():
    """Lazy accessor for the connection pool."""
    return get_container().connection_pool


def _migration():
    """Lazy accessor for the migration service."""
    return get_container().migration


def _find_connection_by_path(database_path: str):
    """Find a pool connection by database path, returning (name, state) or None."""
    try:
        for name, state in _pool().list().items():
            if state.db_path.replace("\\", "/").lower() == database_path.replace("\\", "/").lower():
                return name, state
    except Exception:
        pass

    # Backward-compatible singleton seam used by older tests and callers.
    current_database = getattr(_pool(), "current_database", None)
    adapter = getattr(_pool(), "adapter", None)
    if current_database and adapter is not None:
        if current_database.replace("\\", "/").lower() == database_path.replace("\\", "/").lower():
            return "default", SimpleNamespace(adapter=adapter, db_path=current_database)
    return None, None


@mcp.tool()
def extract_schema(database_path: str) -> dict:
    """
    Extract schema from an Access database.

    Args:
        database_path: Path to the Access database to extract schema from
    """
    # Validate path
    try:
        database_path = _validate_path(database_path)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Try to reuse an existing connection to the same database
    conn_name, state = _find_connection_by_path(database_path)
    if state is not None and _pool().is_connected(conn_name):
        schema = _migration().extract_schema(state.adapter, database_path)
        return {"success": True, "schema": schema.model_dump(), "reused_connection": True, "connection_name": conn_name}

    # Route through BackendSelector to get an adapter with schema introspection capabilities
    adapter = BackendSelector.get_adapter(
        db_path=database_path,
        backend="odbc",
        capabilities=SCHEMA_CAPS,
    )
    if not adapter.connect(database_path):
        return {"success": False, "error": "Failed to connect to database"}
    schema = _migration().extract_schema(adapter, database_path)
    adapter.disconnect()
    return {"success": True, "schema": schema.model_dump(), "reused_connection": False}


@mcp.tool()
def upload_schema(
    target_type: str,
    connection_string: str,
    schema_json: dict,
    server_id: str | None = None,
) -> dict:
    """
    Upload schema to target database.

    Args:
        target_type: Target database type (postgres, mysql, mariadb, sqlite, sqlserver)
        connection_string: Connection string for target database (password-less when server_id is used)
        schema_json: ExtractedSchema as dict
        server_id: Optional server_id to retrieve password from the shared credential vault.
            When provided, the password is injected into connection_string before use.
    """
    from ..models.migration import ExtractedSchema

    effective_connection_string = connection_string
    if server_id is not None:
        vault = get_container().credential_vault
        password = vault.retrieve(server_id)
        if password is None:
            return {
                "success": False,
                "error": f"server_id '{server_id}' not found in credential vault. "
                         "Use store_credential first.",
            }
        # Inject PWD into the password-less connection string
        sep = ";" if not connection_string.endswith(";") else ""
        effective_connection_string = f"{connection_string}{sep}PWD={password}"

    schema = ExtractedSchema(**schema_json)
    result = _migration().upload_schema(target_type, effective_connection_string, schema)
    return result


@mcp.tool()
def transfer_data(
    target_type: str,
    connection_string: str,
    database_path: str,
    schema_json: dict | None = None,
    transfer_mode: str = "auto",
    verification_mode: str = "full",
    table_overrides: dict | None = None,
    odbc_connection_string: str | None = None,
    server_id: str | None = None,
) -> dict:
    """
    Transfer data from Access to target database.

    Args:
        target_type: Target database type (postgres, mysql, mariadb, sqlite, sqlserver)
        connection_string: Connection string for target database (password-less when server_id is used)
        database_path: Path to Access database
        schema_json: Optional ExtractedSchema dict (will extract if not provided)
        transfer_mode: Transfer strategy mode (auto, batch, linked)
        verification_mode: Verification mode (full, count-only)
        table_overrides: Per-table column/WHERE/ORDER_BY overrides for flexible transfer.
            Dict keyed by table name; each value is a TableTransferConfig dict:
            {"columns": ["col1", "col2"], "where": "col>0", "order_by": ["col1"]}.
            All fields optional — missing fields default to full-table transfer.
        odbc_connection_string: Optional ODBC connection string override for passthrough.
            When provided, uses this string instead of deriving from the target connector's
            get_odbc_connection_string(). Format: "DRIVER={...};SERVER=...;PORT=...;DATABASE=...;UID=...;PWD=..."
        server_id: Optional server_id to retrieve password from the shared credential vault.
            When provided, the password is injected into connection_string and odbc_connection_string before use.
    """
    from ..models.migration import ExtractedSchema, TableTransferConfig

    effective_connection_string = connection_string
    effective_odbc_connection_string = odbc_connection_string

    if server_id is not None:
        vault = get_container().credential_vault
        password = vault.retrieve(server_id)
        if password is None:
            return {
                "success": False,
                "error": f"server_id '{server_id}' not found in credential vault. "
                         "Use store_credential first.",
            }
        # Inject PWD into the password-less connection string
        sep = ";" if not connection_string.endswith(";") else ""
        effective_connection_string = f"{connection_string}{sep}PWD={password}"
        # Inject PWD into the password-less odbc_connection_string if provided
        if odbc_connection_string is not None:
            odbc_sep = ";" if not odbc_connection_string.endswith(";") else ""
            effective_odbc_connection_string = f"{odbc_connection_string}{odbc_sep}PWD={password}"

    # Validate database path
    try:
        database_path = _validate_path(database_path)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Reuse existing connection if available
    conn_name, state = _find_connection_by_path(database_path)
    owns_connection = False
    if state is not None and _pool().is_connected(conn_name):
        adapter = state.adapter
    else:
        adapter = BackendSelector.get_adapter(
            db_path=database_path,
            backend="odbc",
            capabilities=DATA_READ_CAPS,
        )
        if not adapter.connect(database_path):
            return {"success": False, "error": "Failed to connect to Access database"}
        owns_connection = True

    if schema_json:
        schema = ExtractedSchema(**schema_json)
    else:
        schema = _migration().extract_schema(adapter, database_path)

    deserialized_overrides: dict[str, TableTransferConfig] | None = None
    if table_overrides is not None:
        deserialized_overrides = {k: TableTransferConfig(**v) for k, v in table_overrides.items()}

    result = _migration().transfer_data(
        target_type,
        effective_connection_string,
        schema,
        adapter,
        transfer_mode=transfer_mode,
        verification_mode=verification_mode,
        table_overrides=deserialized_overrides,
        odbc_connection_string=effective_odbc_connection_string,
    )
    if owns_connection:
        adapter.disconnect()
    return result


@mcp.tool()
def get_migration_status(job_id: str) -> dict:
    """
    Get status of a migration job.

    Args:
        job_id: Migration job ID returned from transfer_data
    """
    return _migration().get_job_status(job_id)
