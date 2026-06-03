"""Schema and metadata tools for MS Access database — Phase 1 SDD."""
from .server import mcp, connection_service, _path_guard


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return connection_service.get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return connection_service.is_connected(connection_name)


def _get_table_schema(adapter, table_name: str):
    """Find a table by name from the adapter's table list."""
    tables = adapter.get_tables()
    for table in tables:
        if table.name == table_name:
            return table
    return None


@mcp.tool()
def get_tables(connection_name: str = "default") -> dict:
    """
    Get all user tables from the connected database.
    Excludes system tables (MSys*).
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    tables = adapter.get_tables()
    return {"success": True, "tables": [t.model_dump() for t in tables], "count": len(tables)}


@mcp.tool()
def get_table_schema(table_name: str, connection_name: str = "default") -> dict:
    """
    Get detailed schema for a specific table.

    Args:
        table_name: Name of the table
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    table = _get_table_schema(adapter, table_name)
    if table is None:
        return {"success": False, "error": f"Table '{table_name}' not found"}
    return {"success": True, "table": table.model_dump()}


@mcp.tool()
def get_relationships(connection_name: str = "default") -> dict:
    """
    Get all foreign key relationships.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    relationships = adapter.get_relationships()
    return {
        "success": True,
        "relationships": [r.model_dump() for r in relationships],
        "count": len(relationships),
    }


@mcp.tool()
def generate_sql(output_path: str, connection_name: str = "default") -> dict:
    """
    Generate Jet SQL DDL script from the Access database schema.

    Writes CREATE TABLE statements for all tables with primary keys,
    autoincrement, default values, and foreign key constraints.

    Args:
        output_path: Path to write the generated .sql file
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    # Validate output path
    if _path_guard is not None:
        try:
            output_path = _path_guard.validate(output_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}

    return adapter.generate_sql(output_path)


@mcp.tool()
def get_er_diagram(connection_name: str = "default") -> dict:
    """
    Get the database schema as nodes and edges for ER diagram visualization.

    Args:
        connection_name: Connection identifier (defaults to "default")

    Returns:
        nodes: List of table nodes with columns
        edges: List of relationship edges (FK connections)
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    tables = adapter.get_tables()
    relationships = adapter.get_relationships()

    nodes = []
    for table in tables:
        nodes.append({
            "id": table.name,
            "type": "table",
            "data": {
                "label": table.name,
                "columns": [f.model_dump() for f in table.fields],
                "record_count": table.record_count,
            },
        })

    edges = []
    for rel in relationships:
        edges.append({
            "id": rel.name,
            "source": rel.foreign_table,
            "target": rel.table,
            "label": rel.name,
            "animated": False,
        })

    return {
        "success": True,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
