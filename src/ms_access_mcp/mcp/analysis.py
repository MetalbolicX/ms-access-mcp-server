"""Query analysis MCP tool."""
from .server import mcp


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


@mcp.tool()
def analyze_query(
    sql: str,
    params: list | None = None,
    connection_name: str = "default",
    dry_run: bool = False,
    sample_size: int = 0,
) -> dict:
    """
    Analyze query performance and return complexity, timing, and schema analysis.

    Args:
        sql: SQL query to analyze
        params: Optional parameters for parameterized queries (ODBC only)
        connection_name: Connection identifier (defaults to "default")
        dry_run: If True, skip execution and only analyze structure
        sample_size: If > 0, fetch approximate sample with TOP N

    Returns:
        dict with execution, complexity, schema_analysis, and recommendations
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        from ..services.query_analyzer import QueryAnalyzerService

        result = QueryAnalyzerService.analyze(
            sql=sql,
            params=params,
            adapter=adapter,
            dry_run=dry_run,
            sample_size=sample_size,
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}