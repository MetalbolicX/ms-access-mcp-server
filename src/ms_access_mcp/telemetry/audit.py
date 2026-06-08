"""Structured JSON audit logger for tool call auditing.

Opt-in via ACCESS_MCP_AUDIT_LOG_PATH environment variable.
When set, each tool call emits a JSON entry with:
- tool: tool name
- args_hash: SHA256 hash of arguments (not raw args — avoids logging secrets)
- result: "success" or "error"
- duration_ms: elapsed time in milliseconds
- caller_ip: IP address of the caller
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any


def _get_audit_path() -> str | None:
    """Return the audit log path from environment (always reads fresh)."""
    return os.environ.get("ACCESS_MCP_AUDIT_LOG_PATH")


def _hash_args(args: dict[str, Any]) -> str:
    """Return SHA256 hex digest of JSON-serialized arguments."""
    try:
        serialized = json.dumps(args, sort_keys=True, default=str)
    except TypeError:
        serialized = json.dumps({"error": "non-serializable args"}, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _get_caller_ip() -> str:
    """Extract caller IP from the current HTTP request context."""
    try:
        from fastmcp.server.dependencies import get_http_request

        request = get_http_request()
        return request.client.host if request and request.client else "unknown"
    except Exception:
        return "unknown"


def audit_log(tool: str, args: dict[str, Any], result: str, duration_ms: float) -> None:
    """Append a structured JSON audit entry if ACCESS_MCP_AUDIT_LOG_PATH is set.

    Args:
        tool: Name of the tool that was called
        args: Tool arguments (will be hashed, not logged verbatim)
        result: "success" or "error"
        duration_ms: Elapsed time in milliseconds
    """
    audit_path = _get_audit_path()
    if not audit_path:
        return

    entry = {
        "tool": tool,
        "args_hash": _hash_args(args),
        "result": result,
        "duration_ms": round(duration_ms, 2),
        "caller_ip": _get_caller_ip(),
        "timestamp": datetime.now(datetime.UTC).isoformat(),
    }

    try:
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        # Audit logging failures should not break tool execution
        pass
