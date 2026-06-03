"""Data export tool for MS Access database — Strategy-pattern driven.

Replaces the old ``export_table_csv`` / ``export_query_json`` with a single
``export_data`` tool that accepts a ``format`` parameter (``csv``, ``json``,
``excel``).
"""
from .server import mcp, connection_service


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return connection_service.get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return connection_service.is_connected(connection_name)


@mcp.tool()
def export_data(
    sql: str,
    file_path: str,
    format: str = "csv",
    delimiter: str = ",",
    header: bool = True,
    encoding: str = "utf-8",
    pretty: bool = False,
    sheet_name: str = "Sheet1",
    connection_name: str = "default",
) -> dict:
    """Export the result of a SQL SELECT query to a file in the given format.

    Uses the Strategy pattern behind the scenes — each format has a dedicated
    strategy that tries an Access-engine IISAM fast path first (for CSV and
    Excel) and falls back to a Python-side writer when the engine is
    unavailable.

    Args:
        sql: Raw ``SELECT`` query to execute.  No automatic wrapping — pass
            the exact SQL you want to run.
        file_path: Destination file path (e.g. ``"/tmp/report.csv"``,
            ``"/tmp/data.xlsx"``).
        format: Output format — ``"csv"`` (default), ``"json"``, or
            ``"excel"``.
        delimiter: CSV field delimiter (default ``","``).  Only used when
            ``format="csv"``.
        header: Whether to write a header row (default ``True``).  Only
            used when ``format="csv"``.
        encoding: Output file encoding (default ``"utf-8"``).  Only used
            when ``format="csv"``.
        pretty: Whether to indent the JSON output (default ``False``).
            Only used when ``format="json"``.
        sheet_name: Worksheet name inside the Excel workbook (default
            ``"Sheet1"``).  Only used when ``format="excel"``.
        connection_name: Connection identifier (defaults to ``"default"``).

    Returns:
        A dict with ``success`` (bool), ``rows_exported`` (int),
        ``file_path`` (str), and optionally ``error`` (str).
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        # Forward format-specific options as keyword arguments
        options = {}
        if format == "csv":
            options = {"delimiter": delimiter, "header": header, "encoding": encoding}
        elif format == "json":
            options = {"pretty": pretty}
        elif format == "excel":
            options = {"sheet_name": sheet_name}

        result = adapter.export_data(sql, file_path, format, **options)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
