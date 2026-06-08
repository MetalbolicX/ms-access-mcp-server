import hmac
import os
from fastmcp.server.middleware import Middleware, MiddlewareContext

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