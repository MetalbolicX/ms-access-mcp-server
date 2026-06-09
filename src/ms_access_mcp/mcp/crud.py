"""CRUD tools for queries, tables, and data in MS Access database — Phase 1 SDD."""
from .server import mcp
from ._helpers import guard_destructive


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


# ============================================================================
# QUERY CRUD
# ============================================================================


@mcp.tool()
def get_queries(connection_name: str = "default") -> dict:
    """Get all saved queries from the database."""
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        queries = adapter.get_queries()
        return {"success": True, "queries": [q.model_dump() for q in queries], "count": len(queries)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def create_query(name: str, sql: str, connection_name: str = "default") -> dict:
    """
    Create a stored query.

    Args:
        name: Name of the query to create
        sql: SQL statement for the query
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_query(name, sql)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def set_query_sql(name: str, sql: str, connection_name: str = "default") -> dict:
    """
    Update SQL of an existing query.

    Args:
        name: Name of the existing query
        sql: New SQL statement
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.set_query_sql(name, sql)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_query(name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Delete a stored query.

    Args:
        name: Name of the query to delete
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the deletion
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    if dry_run:
        return {"dry_run": True, "action": "delete_query", "name": name}

    if not confirm:
        return {"success": False, "error": "confirm=True required for destructive operation (delete_query)"}

    adapter = _get_adapter(connection_name)
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
def create_table(table_name: str, columns: list[dict], connection_name: str = "default") -> dict:
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
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_table(table_name, columns)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_table(table_name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Delete a table from the connected database.

    Args:
        table_name: Name of the table to delete
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the deletion
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    if dry_run:
        return {"dry_run": True, "action": "delete_table", "table_name": table_name}

    if not confirm:
        return {"success": False, "error": "confirm=True required for destructive operation (delete_table)"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.delete_table(table_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# INDEX CRUD
# ============================================================================


@mcp.tool()
def create_index(
    table_name: str,
    index_name: str,
    columns: list[str],
    unique: bool = False,
    ignore_null: bool = False,
    connection_name: str = "default",
) -> dict:
    """
    Create an index on one or more columns.

    Args:
        table_name: Name of the table to create index on.
        index_name: Name for the new index.
        columns: List of column names to include in the index.
        unique: If True, creates a UNIQUE index (default False).
        ignore_null: If True, adds WITH IGNORE NULL clause (default False).
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_index(table_name, index_name, columns, unique, ignore_null)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def drop_index(table_name: str, index_name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Drop an index from a table.

    Args:
        table_name: Name of the table the index belongs to.
        index_name: Name of the index to drop.
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the deletion
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    if dry_run:
        return {"dry_run": True, "action": "drop_index", "table_name": table_name, "index_name": index_name}

    if not confirm:
        return {"success": False, "error": "confirm=True required for destructive operation (drop_index)"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.drop_index(table_name, index_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# DATA CRUD
# ============================================================================


@mcp.tool()
def query_data(sql: str, params: list | None = None, connection_name: str = "default") -> dict:
    """
    Execute SQL query and return results.

    Args:
        sql: SQL query to execute
        params: Optional list of parameters for parameterized queries
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.execute_query(sql, params)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def insert_data(table_name: str, data: dict | list[dict], connection_name: str = "default") -> dict:
    """
    Insert one or more rows into a table.

    Args:
        table_name: Name of the table
        data: A single dict for one row, or a list of dicts for multiple rows
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.insert_data(table_name, data)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def update_data(table_name: str, set_dict: dict, where_dict: dict | str | None = None, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Update rows in a table.

    Args:
        table_name: Name of the table
        set_dict: Dict of column=value pairs to set
        where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True when where_dict is None (mass update)
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    # Mass update (where_dict is None) requires confirm; targeted update proceeds
    if where_dict is None:
        guard = guard_destructive(confirm, dry_run, "update_data", table_name=table_name, set_dict=set_dict, where_dict=where_dict)
        if guard is not None:
            return guard

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.update_data(table_name, set_dict, where_dict)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_data(table_name: str, where_dict: dict | str | None = None, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Delete rows from a table.

    Args:
        table_name: Name of the table
        where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the deletion
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    if dry_run:
        return {"dry_run": True, "action": "delete_data", "table_name": table_name, "where_dict": where_dict}

    if not confirm:
        return {"success": False, "error": "confirm=True required for destructive operation (delete_data)"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.delete_data(table_name, where_dict)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# SCHEMA ALTER
# ============================================================================


@mcp.tool()
def alter_table(table_name: str, operations: list[dict], connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Alter table schema by adding, dropping, modifying columns, or renaming.

    Args:
        table_name: Name of the table to alter
        operations: List of operation dicts with:
            - action: "add_column" | "drop_column" | "modify_column" | "rename_table" | "rename_column"
            - params: dict with operation-specific keys:
                add_column: {"name": str, "type": str, "size": int?, "nullable": bool?}
                drop_column: {"name": str}
                modify_column: {"name": str, "type": str?, "size": int?, "nullable": bool?}
                rename_table: {"new_name": str}
                rename_column: {"name": str, "new_name": str}
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True for drop_column action
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    if dry_run:
        return {"dry_run": True, "table_name": table_name, "operations": operations}

    # Check for drop_column operations that require confirm=True
    for op in operations:
        if op.get("action") == "drop_column" and not confirm:
            return {"success": False, "error": "confirm=True required for drop_column action"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.alter_table(table_name, operations)
        return result
    except NotImplementedError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
