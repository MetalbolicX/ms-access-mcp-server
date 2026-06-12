from __future__ import annotations

import hmac
import os
from typing import TYPE_CHECKING
from fastmcp.server.middleware import Middleware, MiddlewareContext

if TYPE_CHECKING:
    from .services.session import SessionService

try:
    from ms_access_mcp.telemetry.metrics import auth_failures_total
except ImportError:
    auth_failures_total = None  # type: ignore[assignment]


def _emit_auth_failure(reason: str) -> None:
    """Emit auth_failures_total metric with the given reason label."""
    if auth_failures_total is not None:
        auth_failures_total.labels(reason=reason).inc()


class ApiKeyMiddleware(Middleware):
    """Validates Bearer API key on all tool calls and initialize requests.

    The middleware extracts the Authorization header from MCP HTTP requests
    and rejects requests that do not carry a valid Bearer token.
    Uses hmac.compare_digest for constant-time comparison to prevent timing attacks.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("api_key must be a non-empty string")
        self._api_key = api_key
        # Respect ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE toggle
        self._require_auth_on_initialize = os.environ.get(
            "ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE", "false"
        ).lower() in ("true", "1", "yes")

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Validate Bearer token before executing any tool call."""
        if not self._validate_bearer(context):
            _emit_auth_failure(self._auth_failure_reason)
            from mcp.types import ErrorData
            from fastmcp.exceptions import McpError

            raise McpError(
                ErrorData(
                    code=-32001,
                    message="Unauthorized: Bearer token is missing or invalid.",
                )
            )
        return await call_next(context)

    async def on_initialize(self, context: MiddlewareContext, call_next):
        """Allow MCP initialize handshake without auth unless toggle is set."""
        if self._require_auth_on_initialize:
            if not self._validate_bearer(context):
                _emit_auth_failure(self._auth_failure_reason)
                from mcp.types import ErrorData
                from fastmcp.exceptions import McpError

                raise McpError(
                    ErrorData(
                        code=-32001,
                        message="Unauthorized: Bearer token is missing or invalid.",
                    )
                )
        return await call_next(context)

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        """Validate Bearer token before reading resources."""
        if not self._validate_bearer(context):
            _emit_auth_failure(self._auth_failure_reason)
            from mcp.types import ErrorData
            from fastmcp.exceptions import McpError

            raise McpError(
                ErrorData(
                    code=-32001,
                    message="Unauthorized: Bearer token is missing or invalid.",
                )
            )
        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        """Validate Bearer token before listing tools."""
        if not self._validate_bearer(context):
            _emit_auth_failure(self._auth_failure_reason)
            from mcp.types import ErrorData
            from fastmcp.exceptions import McpError

            raise McpError(
                ErrorData(
                    code=-32001,
                    message="Unauthorized: Bearer token is missing or invalid.",
                )
            )
        return await call_next(context)

    async def on_complete(self, context: MiddlewareContext, call_next):
        """Validate Bearer token on completion notifications."""
        if not self._validate_bearer(context):
            _emit_auth_failure(self._auth_failure_reason)
            from mcp.types import ErrorData
            from fastmcp.exceptions import McpError

            raise McpError(
                ErrorData(
                    code=-32001,
                    message="Unauthorized: Bearer token is missing or invalid.",
                )
            )
        return await call_next(context)

    async def on_progress(self, context: MiddlewareContext, call_next):
        """Validate Bearer token on progress notifications."""
        if not self._validate_bearer(context):
            _emit_auth_failure(self._auth_failure_reason)
            from mcp.types import ErrorData
            from fastmcp.exceptions import McpError

            raise McpError(
                ErrorData(
                    code=-32001,
                    message="Unauthorized: Bearer token is missing or invalid.",
                )
            )
        return await call_next(context)

    async def on_set_logging_level(self, context: MiddlewareContext, call_next):
        """Validate Bearer token before setting logging level."""
        if not self._validate_bearer(context):
            _emit_auth_failure(self._auth_failure_reason)
            from mcp.types import ErrorData
            from fastmcp.exceptions import McpError

            raise McpError(
                ErrorData(
                    code=-32001,
                    message="Unauthorized: Bearer token is missing or invalid.",
                )
            )
        return await call_next(context)

    def _validate_bearer(self, context: MiddlewareContext) -> bool:
        """Extract Authorization header and validate Bearer token using hmac.compare_digest.

        Sets self._auth_failure_reason before returning False so callers can emit the metric.
        Emits auth_failures_total metric directly on failure.
        """
        auth_header = self._get_header("authorization") or self._get_header(
            "Authorization"
        )
        if not auth_header:
            self._auth_failure_reason = "missing_token"
            _emit_auth_failure("missing_token")
            return False

        if not auth_header.startswith("Bearer "):
            self._auth_failure_reason = "invalid_format"
            _emit_auth_failure("invalid_format")
            return False

        token = auth_header[7:]  # Strip "Bearer " prefix
        if not hmac.compare_digest(token, self._api_key):
            self._auth_failure_reason = "invalid_token"
            _emit_auth_failure("invalid_token")
            return False

        return True

    @staticmethod
    def _get_header(name: str) -> str | None:
        """Safely extract a header from the current HTTP request."""
        try:
            from fastmcp.server.dependencies import get_http_request

            request = get_http_request()
            return request.headers.get(name)
        except Exception:
            return None


# ---- Destructive tool registry ----

DESTRUCTIVE_TOOLS = frozenset([
    "delete_table",
    "create_query",
    "set_vba_code",
    "execute_raw_sql",
    "delete_query",
    "create_table",
    "delete_data",
    "insert_data",
    "update_data",
    "alter_table",
    "drop_index",
    "create_index",
    "delete_relationship",
    "create_relationship",
    "delete_form",
    "delete_report",
    "delete_module",
    "import_form_from_text",
    "import_report_from_text",
    "import_module_from_text",
    "import_macro_from_text",
    "import_query_from_text",
    "restore_form_backup",
    "restore_report_backup",
    "restore_module_backup",
    "discard_dev_copy",
])


class ReadOnlyMiddleware(Middleware):
    """Blocks destructive tool calls when ACCESS_MCP_READONLY=true.

    Inspects the tool name from the middleware context and raises
    McpError with code -32003 and 403 Forbidden when a destructive
    tool is called while read-only mode is active.
    """

    def __init__(self, readonly: bool = False):
        self._readonly = readonly

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Block destructive tools if readonly mode is enabled."""
        if not self._readonly:
            return await call_next(context)

        tool_name = getattr(context.message, "name", None) if context.message else None
        if tool_name in DESTRUCTIVE_TOOLS:
            from mcp.types import ErrorData
            from fastmcp.exceptions import McpError

            raise McpError(
                ErrorData(
                    code=-32003,
                    message="Server is in read-only mode",
                )
            )
        return await call_next(context)


class SessionMiddleware(Middleware):
    """Resolves API key from session cookie OR Bearer header.

    Provides dual authentication path:
    - Session cookie (httpOnly): via itsdangerous-signed session
    - Bearer header: existing MCP client compatibility

    The session cookie is checked only when no Bearer token is present.
    """

    def __init__(self, session_service: SessionService, api_key: str):
        self._session_service = session_service
        self._api_key = api_key

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Authenticate via cookie or Bearer before executing tool."""
        if not self._validate_session_or_bearer(context):
            from mcp.types import ErrorData
            from fastmcp.exceptions import McpError

            raise McpError(
                ErrorData(
                    code=-32001,
                    message="Unauthorized: Bearer token or session cookie is missing or invalid.",
                )
            )
        return await call_next(context)

    async def on_initialize(self, context: MiddlewareContext, call_next):
        """Allow MCP initialize handshake without auth."""
        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        """Allow tools listing without auth."""
        return await call_next(context)

    def _validate_session_or_bearer(self, context: MiddlewareContext) -> bool:
        """Validate either Bearer token or session cookie.

        Returns True if either authentication method succeeds.
        """
        # Check Bearer first (MCP client compatibility)
        if self._validate_bearer(context):
            return True
        # Fall back to session cookie
        return self._validate_cookie(context)

    def _validate_bearer(self, context: MiddlewareContext) -> bool:
        """Validate Bearer token using hmac.compare_digest."""
        auth_header = self._get_header("authorization") or self._get_header(
            "Authorization"
        )
        if not auth_header or not auth_header.startswith("Bearer "):
            return False
        token = auth_header[7:]
        import hmac as _hmac
        return _hmac.compare_digest(token, self._api_key)

    def _validate_cookie(self, context: MiddlewareContext) -> bool:
        """Validate session cookie via SessionService."""
        cookie_value = self._get_cookie(self._session_service.cookie_name)
        if not cookie_value:
            return False
        api_key = self._session_service.validate(cookie_value)
        return api_key is not None

    @staticmethod
    def _get_header(name: str) -> str | None:
        """Safely extract a header from the current HTTP request."""
        try:
            from fastmcp.server.dependencies import get_http_request

            request = get_http_request()
            return request.headers.get(name)
        except Exception:
            return None

    @staticmethod
    def _get_cookie(name: str) -> str | None:
        """Safely extract a cookie from the current HTTP request."""
        try:
            from fastmcp.server.dependencies import get_http_request

            request = get_http_request()
            cookie_header = request.headers.get("cookie") or request.headers.get("Cookie")
            if not cookie_header:
                return None
            # Parse "name=value; name2=value2" style header
            for part in cookie_header.split(";"):
                part = part.strip()
                if "=" in part:
                    cookie_name, cookie_val = part.split("=", 1)
                    if cookie_name.strip() == name:
                        return cookie_val.strip()
            return None
        except Exception:
            return None