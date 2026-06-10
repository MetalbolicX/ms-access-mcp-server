"""MCP tools for foreign key relationship management (SQL DDL)."""

from ._helpers import guard_destructive
from .container import get_container
from .server import mcp


def _pool():
    return get_container().connection_pool


def _get_adapter(connection_name: str = "default"):
    try:
        return _pool().get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    return _pool().is_connected(connection_name)


def _ensure_connected(connection_name: str = "default"):
    if not _check_connected(connection_name):
        return None
    return _get_adapter(connection_name)


@mcp.tool()
def create_relationship(
    table_name: str,
    relationship_name: str,
    columns: list[str],
    foreign_table: str,
    foreign_columns: list[str],
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create a foreign key relationship (SQL DDL: ALTER TABLE ADD CONSTRAINT FOREIGN KEY).

    Args:
        table_name: Child table containing the foreign key
        relationship_name: Name for the constraint (e.g. FK_Orders_Customers)
        columns: List of column names in the child table
        foreign_table: Parent table being referenced
        foreign_columns: List of column names in the parent table
        connection_name: Connection name (default "default")
        confirm: Must be True to execute destructive operation
        dry_run: If True, return what would be done without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(
        confirm, dry_run, "create_relationship",
        table_name=table_name, relationship_name=relationship_name,
        columns=columns, foreign_table=foreign_table, foreign_columns=foreign_columns,
    )
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.create_relationship(
            table_name, relationship_name, columns, foreign_table, foreign_columns,
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_relationship(
    table_name: str,
    relationship_name: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Delete a foreign key relationship (SQL DDL: ALTER TABLE DROP CONSTRAINT).

    Args:
        table_name: Child table containing the constraint
        relationship_name: Name of the constraint to drop
        connection_name: Connection name (default "default")
        confirm: Must be True to execute destructive operation
        dry_run: If True, return what would be done without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(
        confirm, dry_run, "delete_relationship",
        table_name=table_name, relationship_name=relationship_name,
    )
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        result = adapter.delete_relationship(table_name, relationship_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
