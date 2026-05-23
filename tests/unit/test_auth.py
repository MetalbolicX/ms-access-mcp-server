import pytest
from ms_access_mcp.auth import ApiKeyMiddleware


class TestApiKeyMiddleware:
    """ApiKeyMiddleware validates Bearer tokens on tool calls."""

    def test_middleware_constructs_with_api_key(self):
        """ApiKeyMiddleware accepts api_key and stores it."""
        middleware = ApiKeyMiddleware(api_key="my-secret-key")
        assert middleware._api_key == "my-secret-key"

    def test_middleware_rejects_empty_api_key(self):
        """Empty string api_key raises ValueError."""
        with pytest.raises(ValueError, match="api_key"):
            ApiKeyMiddleware(api_key="")

    def test_middleware_isinstance_middleware(self):
        """ApiKeyMiddleware inherits from Middleware."""
        from fastmcp.server.middleware import Middleware
        middleware = ApiKeyMiddleware(api_key="key")
        assert isinstance(middleware, Middleware)

    def test_middleware_has_on_call_tool_method(self):
        """ApiKeyMiddleware has async on_call_tool method."""
        middleware = ApiKeyMiddleware(api_key="key")
        assert hasattr(middleware, "on_call_tool")
        import inspect
        assert inspect.iscoroutinefunction(middleware.on_call_tool)