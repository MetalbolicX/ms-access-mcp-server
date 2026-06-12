"""Macro CRUD tools for MS Access.

Provides 8 MCP tools covering the full macro lifecycle:
- Read/discovery: macro_exists, get_macros, get_macro_properties
- Lifecycle (destructive): create_macro, rename_macro, delete_macro, run_macro

The `import_macro_from_text` companion lives in persistence.py per the
proposal's "Open Questions" decision.
"""
from ._helpers import _com, destructive_guard, require_connected
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


def _ensure_connected(connection_name: str = "default"):
    """Check connection and return adapter, or None if not connected."""
    if not _check_connected(connection_name):
        return None
    return _get_adapter(connection_name)


# ============================================================================
# MACRO DISCOVERY TOOLS (non-destructive)
# ============================================================================


@require_connected()
@mcp.tool()
def macro_exists(macro_name: str, connection_name: str = "default") -> dict:
    """
    Check if a macro exists.

    Args:
        macro_name: Name of the macro to check
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    exists = adapter.macro_exists(macro_name)
    return {"success": True, "exists": exists, "macro": macro_name}


@require_connected()
@mcp.tool()
def get_macros(connection_name: str = "default") -> dict:
    """
    Get all macros in the database.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    macros = adapter.get_macros()
    return {"success": True, "macros": [m.model_dump() for m in macros], "count": len(macros)}


@require_connected()
@mcp.tool()
def get_macro_properties(macro_name: str, connection_name: str = "default") -> dict:
    """
    Get all properties of a macro.

    Args:
        macro_name: Name of the macro
        connection_name: Connection identifier (defaults to "default")
    """
    props = _com().get_macro_properties(macro_name)
    if not props:
        return {"success": False, "error": f"Macro '{macro_name}' not found"}
    return {"success": True, "macro": macro_name, "properties": props}


# ============================================================================
# MACRO LIFECYCLE TOOLS (destructive)
# ============================================================================


@destructive_guard(action="create_macro")
@mcp.tool()
def create_macro(
    macro_name: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Create a new empty macro via LoadFromText.

    This is a destructive action. Set confirm=True to execute, or dry_run=True
    to preview without making changes.

    Args:
        macro_name: Name for the new macro
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the create
        dry_run: If True, returns a preview without executing
    """
    result = _com().create_macro(macro_name)
    return {"success": result, "macro": macro_name}


@destructive_guard(action="rename_macro")
@mcp.tool()
def rename_macro(
    old_name: str,
    new_name: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Rename an existing macro.

    This is a destructive action. Set confirm=True to execute, or dry_run=True
    to preview without making changes.

    Args:
        old_name: Current name of the macro
        new_name: New name for the macro
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the rename
        dry_run: If True, returns a preview without executing
    """
    result = _com().rename_macro(old_name, new_name)
    return {"success": result, "old_name": old_name, "new_name": new_name}


@destructive_guard(action="delete_macro")
@mcp.tool()
def delete_macro(
    macro_name: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Delete an existing macro.

    This is a destructive action. Set confirm=True to execute, or dry_run=True
    to preview without making changes.

    Args:
        macro_name: Name of the macro to delete
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the deletion
        dry_run: If True, returns a preview without executing
    """
    result = _com().delete_macro(macro_name)
    return {"success": result, "macro": macro_name}


@destructive_guard(action="run_macro")
@mcp.tool()
def run_macro(
    macro_name: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Execute a macro.

    This is a destructive action — running a macro can perform arbitrary
    side effects. Set confirm=True to execute, or dry_run=True to preview
    without running.

    Args:
        macro_name: Name of the macro to run
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the run
        dry_run: If True, returns a preview without executing
    """
    result = _com().run_macro(macro_name)
    return {"success": result, "macro": macro_name}
