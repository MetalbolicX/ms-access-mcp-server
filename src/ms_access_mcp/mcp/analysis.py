"""Query analysis MCP tool."""
from .server import mcp
from ._helpers import _get_adapter, _check_connected


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
