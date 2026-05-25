"""Data export tools for MS Access database."""
from .server import mcp, connection_service


@mcp.tool()
def export_table_csv(table_or_query_name: str, file_path: str, delimiter: str = ",", header: bool = True) -> dict:
    """
    Export a table or query to a CSV file.

    Args:
        table_or_query_name: Name of the table or query to export
        file_path: Path to the output CSV file
        delimiter: Field delimiter (default ',')
        header: Whether to write header row (default True)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.export_table_csv(table_or_query_name, file_path, delimiter, header)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def export_query_json(query_name: str, file_path: str, pretty: bool = False) -> dict:
    """
    Export a query to a JSON file.

    Args:
        query_name: Name of the query to export
        file_path: Path to the output JSON file
        pretty: Whether to format JSON with indentation (default False)
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    adapter = connection_service.adapter
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    try:
        result = adapter.export_query_json(query_name, file_path, pretty)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
