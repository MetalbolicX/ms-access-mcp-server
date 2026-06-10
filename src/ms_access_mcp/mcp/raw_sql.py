"""MCP tool for executing raw SQL statements against the connected database."""

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


@mcp.tool()
def execute_raw_sql(
    sql: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Execute a raw SQL statement against the connected database.

    Args:
        sql: SQL statement to execute (INSERT/UPDATE/DELETE/DDL)
        connection_name: Connection name (default "default")
        confirm: Must be True to execute the statement
        dry_run: If True, return what would be done without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(
        confirm,
        dry_run,
        "execute_raw_sql",
        sql=sql,
    )
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    try:
        rows_affected = adapter.execute_raw_sql(sql)
        return {"success": True, "rows_affected": rows_affected}
    except Exception as e:
        return {"success": False, "error": str(e)}
