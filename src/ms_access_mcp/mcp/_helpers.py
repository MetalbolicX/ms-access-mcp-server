"""Shared MCP helper functions — extracted to avoid duplication across MCP modules.

These helpers use lazy imports to avoid circular dependency issues
with the container and connection pool.
"""
from __future__ import annotations


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


def _com():
    """Lazy accessor for COM automation service (avoids circular import at module level)."""
    from .container import get_container
    return get_container().com_automation


def _validate_path(path: str) -> str:
    """Validate a path through PathGuard, returning the absolute path or raising."""
    from .server import _get_path_guard
    guard = _get_path_guard()
    if guard is not None:
        return guard.validate(path)
    return path


def guard_destructive(confirm: bool, dry_run: bool, action: str, **context) -> dict | None:
    """Guard clause for destructive MCP tools.

    Returns a dict (early return) if guard blocks the action, or None to proceed.

    Args:
        confirm: Must be True to proceed with the destructive action
        dry_run: If True, returns a preview dict without executing
        action: Name of the action (e.g. "delete_module")
        **context: Additional context passed through to the response dict

    Returns:
        None if the operation should proceed, or a dict with dry_run=True
        or success=False indicating the guard blocked the action.
    """
    if dry_run:
        return {"dry_run": True, "action": action, **context}
    if not confirm:
        return {"success": False, "error": f"confirm=True required for {action}", **context}
    return None
