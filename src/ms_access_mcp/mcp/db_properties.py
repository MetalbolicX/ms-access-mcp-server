"""Database property tools for MS Access — PR3 of add-missing-mcp-tools.

Two MCP tools:
- get_database_properties: read-only — returns categorized DAO properties
- set_database_property: destructive — guarded by confirm/dry_run

The underlying work lives in adapters/db_operations.py (DbOperations class).
The ComOnlyAdapterMixin raises NotImplementedError for these methods, so only
WinComAdapter (COM-only) is capable of serving them.
"""

from ._helpers import destructive_guard, require_connected
from .container import get_container
from .server import mcp


def _pool():
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
# READ TOOL (non-destructive)
# ============================================================================


@require_connected()
@mcp.tool()
def get_database_properties(
    names: list[str] | None = None,
    connection_name: str = "default",
) -> dict:
    """
    Get database properties (DAO `CurrentDb.Properties`).

    Returns properties grouped by category:
      - startup: AppTitle, StartupForm, AllowFullMenus, etc.
      - app: Author, Company, Description, etc.
      - project: Path, Name, ProjectType (from CurrentProject)
      - all: every non-internal property

    Args:
        names: Optional list of property names to filter to (case-insensitive).
            If None (default), all properties are returned.
        connection_name: Connection identifier (defaults to "default")

    Returns:
        dict with `success=True` and `properties` (the categorized dict),
        or `success=False` with `error` if not connected.

    Note: exceptions raised by the adapter are NOT caught — they propagate
    to the MCP framework for visibility.
    """
    properties = _get_adapter(connection_name).get_database_properties(names)
    return {"success": True, "properties": properties}


# ============================================================================
# WRITE TOOL (destructive)
# ============================================================================


@destructive_guard(action="set_database_property")
@mcp.tool()
def set_database_property(
    name: str,
    value: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Create or update a database property (DAO `CurrentDb.Properties`).

    If the property already exists, its value is updated. Otherwise a new
    property is created with an auto-detected DAO type (Boolean → Long →
    Double → Text) and appended to the database.

    This is a destructive action — it modifies the database file. Set
    confirm=True to execute, or dry_run=True to preview without making
    changes.

    Args:
        name: Property name to create/update.
        value: New value as a string. The DAO type is inferred from the
            value unless `type` is provided at the adapter level.
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the write.
        dry_run: If True, returns a preview without executing.

    Returns:
        dict with `success=True` and `property`/`value` keys, or
        `success=False` with `error`, or `dry_run=True` with a preview.

    Note: exceptions raised by the adapter are NOT caught — they propagate
    to the MCP framework for visibility.
    """
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}

    success = adapter.set_database_property(name, value)
    return {"success": success, "property": name, "value": value}
