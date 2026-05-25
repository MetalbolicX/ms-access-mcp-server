"""Schema and metadata tools for MS Access database."""
from .server import mcp, connection_service, schema_service, _path_guard


@mcp.tool()
def get_tables() -> dict:
    """
    Get all user tables from the connected database.
    Excludes system tables (MSys*).
    """
    tables = schema_service.get_tables()
    return {"success": True, "tables": [t.model_dump() for t in tables], "count": len(tables)}


@mcp.tool()
def get_table_schema(table_name: str) -> dict:
    """
    Get detailed schema for a specific table.

    Args:
        table_name: Name of the table
    """
    table = schema_service.get_table_schema(table_name)
    if table is None:
        return {"success": False, "error": f"Table '{table_name}' not found"}
    return {"success": True, "table": table.model_dump()}


@mcp.tool()
def get_relationships() -> dict:
    """Get all foreign key relationships."""
    relationships = schema_service.get_relationships()
    return {
        "success": True,
        "relationships": [r.model_dump() for r in relationships],
        "count": len(relationships),
    }


@mcp.tool()
def generate_sql(output_path: str) -> dict:
    """Generate Jet SQL DDL script from the Access database schema.

    Writes CREATE TABLE statements for all tables with primary keys,
    autoincrement, default values, and foreign key constraints.

    Args:
        output_path: Path to write the generated .sql file
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
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
def get_er_diagram() -> dict:
    """
    Get the database schema as nodes and edges for ER diagram visualization.

    Returns:
        nodes: List of table nodes with columns
        edges: List of relationship edges (FK connections)
    """
    tables = schema_service.get_tables()
    relationships = schema_service.get_relationships()

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
