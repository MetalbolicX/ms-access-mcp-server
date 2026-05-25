"""Migration tools for MS Access database."""
from .server import mcp, connection_service, migration_service


@mcp.tool()
def extract_schema(database_path: str) -> dict:
    """Extract schema from an Access database."""
    from ..adapters.wincom import WinComAdapter

    # Reuse active connection when possible to avoid opening the same Access DB
    # in a second COM adapter instance (can fail due to Access COM singleton behavior).
    active_adapter = connection_service.adapter
    active_db = connection_service.current_database
    if active_adapter is not None and active_db and connection_service.is_connected():
        norm_active = active_db.replace("\\", "/").lower()
        norm_target = database_path.replace("\\", "/").lower()
        if norm_active == norm_target:
            schema = migration_service.extract_schema(active_adapter, database_path)
            return {"success": True, "schema": schema.model_dump(), "reused_connection": True}

    adapter = WinComAdapter()
    if not adapter.connect(database_path):
        return {"success": False, "error": "Failed to connect to database"}
    schema = migration_service.extract_schema(adapter, database_path)
    adapter.disconnect()
    return {"success": True, "schema": schema.model_dump(), "reused_connection": False}


@mcp.tool()
def upload_schema(target_type: str, connection_string: str, schema_json: dict) -> dict:
    """Upload schema to target database.
    
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
def transfer_data(target_type: str, connection_string: str, database_path: str, schema_json: dict | None = None) -> dict:
    """Transfer data from Access to target database.
    
    Args:
        target_type: Target database type (postgres, mysql, mariadb, sqlite, sqlserver)
        connection_string: Connection string for target database
        database_path: Path to Access database
        schema_json: Optional ExtractedSchema dict (will extract if not provided)
    """
    from ..adapters.wincom import WinComAdapter
    from ..models.migration import ExtractedSchema
    
    adapter = WinComAdapter()
    if not adapter.connect(database_path):
        return {"success": False, "error": "Failed to connect to Access database"}
    
    if schema_json:
        schema = ExtractedSchema(**schema_json)
    else:
        schema = migration_service.extract_schema(adapter, database_path)
    
    result = migration_service.transfer_data(target_type, connection_string, schema, adapter)
    adapter.disconnect()
    return result


@mcp.tool()
def get_migration_status(job_id: str) -> dict:
    """Get status of a migration job.

    Args:
        job_id: Migration job ID returned from transfer_data
    """
    return migration_service.get_job_status(job_id)
