"""Shared MCP helper functions — extracted to avoid duplication across MCP modules.

These helpers use lazy imports to avoid circular dependency issues
with the container and connection pool.
"""
from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any


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


def _ensure_connected(connection_name: str = "default"):
    """Check connection and return adapter, or None if not connected.

    Returns:
        The adapter for the named connection if connected, otherwise None.
        Does NOT raise exceptions.
    """
    if not _check_connected(connection_name):
        return None
    return _get_adapter(connection_name)


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


_DEFAULT_NOT_CONNECTED = {"success": False, "error": "Not connected"}
_GUARD_SKIP_PARAMS = frozenset({"confirm", "dry_run", "connection_name"})


def _resolve_check_connected(func: Callable) -> Callable:
    """Resolve the ``_check_connected`` function for a wrapped tool.

    Prefers the function's own module-level ``_check_connected`` (so tests can
    patch ``module._pool`` and have the change propagate), falling back to the
    shared helper when the module does not define its own.
    """
    check_connected = func.__globals__.get("_check_connected")
    if check_connected is not None:
        return check_connected
    return _check_connected


def require_connected(error_return: dict | None = None) -> Callable:
    """Decorator that ensures a connection is active before running an MCP tool.

    Inspects the wrapped function's signature to discover the ``connection_name``
    kwarg (defaulting to ``"default"``), verifies the connection is active, and
    returns ``error_return`` (or a default error dict) if not. Otherwise the
    wrapped function is invoked with the original arguments.

    The connection check delegates to the function's own module's
    ``_check_connected`` (if defined) so existing tests that patch module-level
    ``_pool`` continue to work, and falls back to the shared helper otherwise.

    Args:
        error_return: Optional dict to return when disconnected. Defaults to
            ``{"success": False, "error": "Not connected"}``.

    Returns:
        Decorator that wraps an MCP tool function.
    """
    sentinel = error_return if error_return is not None else _DEFAULT_NOT_CONNECTED

    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            connection_name = bound.arguments.get("connection_name", "default")
            check_connected = _resolve_check_connected(func)
            if not check_connected(connection_name):
                return sentinel
            return func(*args, **kwargs)

        return wrapper

    return decorator


def destructive_guard(action: str) -> Callable:
    """Decorator that wraps destructive MCP tools with the standard guard dance.

    Combines :func:`require_connected` and :func:`guard_destructive` in a single
    decorator. The wrapped function must accept ``connection_name``, ``confirm``,
    and ``dry_run`` keyword arguments. All other function parameters are
    auto-derived from the call and forwarded as context to ``guard_destructive``.

    Args:
        action: Name of the destructive action (e.g. ``"delete_query"``).

    Returns:
        Decorator that wraps a destructive MCP tool function.
    """

    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        context_param_names = [
            name for name in sig.parameters if name not in _GUARD_SKIP_PARAMS
        ]

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            connection_name = arguments.get("connection_name", "default")
            check_connected = _resolve_check_connected(func)
            if not check_connected(connection_name):
                return _DEFAULT_NOT_CONNECTED
            confirm = arguments.get("confirm", False)
            dry_run = arguments.get("dry_run", False)
            context = {
                name: arguments[name] for name in context_param_names if name in arguments
            }
            guard = guard_destructive(confirm, dry_run, action, **context)
            if guard is not None:
                return guard
            return func(*args, **kwargs)

        return wrapper

    return decorator
