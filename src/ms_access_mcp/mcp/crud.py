"""CRUD tools for queries, tables, and data in MS Access database."""
from .server import mcp, connection_service


# ============================================================================
# QUERY CRUD
# ============================================================================


@mcp.tool()
def get_queries() -> dict:
    """Get all saved queries from the database."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        queries = adapter.get_queries()
        return {"success": True, "queries": [q.model_dump() for q in queries], "count": len(queries)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def create_query(name: str, sql: str) -> dict:
    """
    Create a stored query.

    Args:
        name: Name of the query to create
        sql: SQL statement for the query
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_query(name, sql)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def set_query_sql(name: str, sql: str) -> dict:
    """
    Update SQL of an existing query.

    Args:
        name: Name of the existing query
        sql: New SQL statement
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.set_query_sql(name, sql)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_query(name: str) -> dict:
    """
    Delete a stored query.

    Args:
        name: Name of the query to delete
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.delete_query(name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# TABLE CRUD
# ============================================================================


@mcp.tool()
def create_table(table_name: str, columns: list[dict]) -> dict:
    """
    Create a new table in the connected database.

    Args:
        table_name: Name of the table to create
        columns: List of column definitions as dicts with keys:
                 - name (str): Column name
                 - type (str): Data type (Text, Long Integer, Integer, Boolean,
                   Date/Time, Currency, Memo, Double, Single, Binary)
                 - size (int, optional): Size for Text type (default 255)
                 - nullable (bool, optional): Whether column allows NULL (default True)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_table(table_name, columns)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_table(table_name: str) -> dict:
    """
    Delete a table from the connected database.

    Args:
        table_name: Name of the table to delete
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.delete_table(table_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# DATA CRUD
# ============================================================================


@mcp.tool()
def query_data(sql: str, params: list | None = None) -> dict:
    """
    Execute SQL query and return results.

    Args:
        sql: SQL query to execute
        params: Optional list of parameters for parameterized queries
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.execute_query(sql, params)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def insert_data(table_name: str, data: dict | list[dict]) -> dict:
    """
    Insert one or more rows into a table.

    Args:
        table_name: Name of the table
        data: A single dict for one row, or a list of dicts for multiple rows
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.insert_data(table_name, data)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def update_data(table_name: str, set_dict: dict, where_dict: dict | str | None = None) -> dict:
    """
    Update rows in a table.

    Args:
        table_name: Name of the table
        set_dict: Dict of column=value pairs to set
        where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.update_data(table_name, set_dict, where_dict)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_data(table_name: str, where_dict: dict | str | None = None) -> dict:
    """
    Delete rows from a table.

    Args:
        table_name: Name of the table
        where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.delete_data(table_name, where_dict)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
