"""Migration tools for MS Access database — Phase 1 SDD."""
from types import SimpleNamespace

from .server import mcp, connection_service, migration_service
from ..adapters.wincom import WinComAdapter


def _find_connection_by_path(database_path: str):
    """Find a pool connection by database path, returning (name, state) or None."""
    try:
        for name, state in connection_service.list().items():
            if state.db_path.replace("\\", "/").lower() == database_path.replace("\\", "/").lower():
                return name, state
    except Exception:
        pass

    # Backward-compatible singleton seam used by older tests and callers.
    current_database = getattr(connection_service, "current_database", None)
    adapter = getattr(connection_service, "adapter", None)
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
    # Try to reuse an existing connection to the same database
    conn_name, state = _find_connection_by_path(database_path)
    if state is not None and connection_service.is_connected(conn_name):
        schema = migration_service.extract_schema(state.adapter, database_path)
        return {"success": True, "schema": schema.model_dump(), "reused_connection": True, "connection_name": conn_name}

    # Create a new adapter and connection
    adapter = WinComAdapter()
    if not adapter.connect(database_path):
        return {"success": False, "error": "Failed to connect to database"}
    schema = migration_service.extract_schema(adapter, database_path)
    adapter.disconnect()
    return {"success": True, "schema": schema.model_dump(), "reused_connection": False}


@mcp.tool()
def upload_schema(target_type: str, connection_string: str, schema_json: dict) -> dict:
    """
    Upload schema to target database.

    Args:
        target_type: Target database type (postgres, mysql, mariadb, sqlite, sqlserver)
        connection_string: Connection string for target database
        schema_json: ExtractedSchema as dict
    """
    from ..models.migration import ExtractedSchema
    schema = ExtractedSchema(**schema_json)
    result = migration_service.upload_schema(target_type, connection_string, schema)
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
) -> dict:
    """
    Transfer data from Access to target database.

    Args:
        target_type: Target database type (postgres, mysql, mariadb, sqlite, sqlserver)
        connection_string: Connection string for target database
        database_path: Path to Access database
        schema_json: Optional ExtractedSchema dict (will extract if not provided)
        transfer_mode: Transfer strategy mode (auto, batch, linked)
        verification_mode: Verification mode (full, count-only)
        table_overrides: Per-table column/WHERE/ORDER BY overrides for flexible transfer.
            Dict keyed by table name; each value is a TableTransferConfig dict:
            {"columns": ["col1", "col2"], "where": "col>0", "order_by": ["col1"]}.
            All fields optional — missing fields default to full-table transfer.
        odbc_connection_string: Optional ODBC connection string override for passthrough.
            When provided, uses this string instead of deriving from the target connector's
            get_odbc_connection_string(). Format: "DRIVER={...};SERVER=...;PORT=...;DATABASE=...;UID=...;PWD=..."
    """
    from ..models.migration import ExtractedSchema, TableTransferConfig

    # Reuse existing connection if available (avoids COM "database already open" error)
    conn_name, state = _find_connection_by_path(database_path)
    owns_connection = False
    if state is not None and connection_service.is_connected(conn_name):
        adapter = state.adapter
    else:
        adapter = WinComAdapter()
        if not adapter.connect(database_path):
            return {"success": False, "error": "Failed to connect to Access database"}
        owns_connection = True

    if schema_json:
        schema = ExtractedSchema(**schema_json)
    else:
        schema = migration_service.extract_schema(adapter, database_path)

    deserialized_overrides: dict[str, TableTransferConfig] | None = None
    if table_overrides is not None:
        deserialized_overrides = {k: TableTransferConfig(**v) for k, v in table_overrides.items()}

    result = migration_service.transfer_data(
        target_type,
        connection_string,
        schema,
        adapter,
        transfer_mode=transfer_mode,
        verification_mode=verification_mode,
        table_overrides=deserialized_overrides,
        odbc_connection_string=odbc_connection_string,
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
    return migration_service.get_job_status(job_id)
