"""Data export tools for MS Access database — Phase 1 SDD."""
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
def export_table_csv(sql: str, file_path: str, delimiter: str = ",", header: bool = True, encoding: str = "utf-8", connection_name: str = "default") -> dict:
    """
    Export the result of a SQL query to a CSV file.

    Uses the ACE/Jet Text IISAM for fast server-side CSV generation when
    possible (delimiter=',', encoding supported). Falls back to fetching
    rows in Python and writing via csv.DictWriter.

    Args:
        sql: SQL SELECT query to export
        file_path: Path to the output CSV file
        delimiter: Field delimiter (default ',')
        header: Whether to write header row (default True)
        encoding: Output file encoding (default 'utf-8')
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.export_table_csv(sql, file_path, delimiter, header, encoding)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def export_query_json(query_name: str, file_path: str, pretty: bool = False, connection_name: str = "default") -> dict:
    """
    Export a query to a JSON file.

    Args:
        query_name: Name of the query to export
        file_path: Path to the output JSON file
        pretty: Whether to format JSON with indentation (default False)
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}

    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.export_query_json(query_name, file_path, pretty)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
