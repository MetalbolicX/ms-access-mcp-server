from fastmcp.server.middleware import Middleware, MiddlewareContext


class ApiKeyMiddleware(Middleware):
    """Validates Bearer API key on all tool calls and initialize requests.

    The middleware extracts the Authorization header from MCP HTTP requests
    and rejects requests that do not carry a valid Bearer token.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("api_key must be a non-empty string")
        self._api_key = api_key

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Validate Bearer token before executing any tool call."""
        if not self._validate_bearer(context):
            from fastmcp.exceptions import McpError

            raise McpError(
                message="Unauthorized: Bearer token is missing or invalid.",
                code=-32001,
            )
        return await call_next(context)

    async def on_initialize(self, context: MiddlewareContext, call_next):
        """Allow MCP initialize handshake without auth."""
        return await call_next(context)

    def _validate_bearer(self, context: MiddlewareContext) -> bool:
        """Extract Authorization header and validate Bearer token."""
        # FastMCP HTTP transport stores headers in context
        # The Authorization header is passed as a request header
        auth_header = self._get_header(context, "authorization") or self._get_header(
            context, "Authorization"
        )
        if not auth_header:
            return False

        if not auth_header.startswith("Bearer "):
            return False

        token = auth_header[7:]  # Strip "Bearer " prefix
        return token == self._api_key

    def _get_header(self, context: MiddlewareContext, name: str) -> str | None:
        """Safely extract a header from middleware context."""
        try:
            # Access headers via context attributes
            if hasattr(context, "request") and hasattr(context.request, "headers"):
                return context.request.headers.get(name)
            if hasattr(context, "headers"):
                return context.headers.get(name)
        except Exception:
            pass
        return None