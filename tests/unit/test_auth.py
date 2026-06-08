import pytest
import hmac
from unittest.mock import patch, MagicMock
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


class TestApiKeyMiddlewareHMACComparison:
    """ApiKeyMiddleware uses hmac.compare_digest for constant-time comparison."""

    def test_validate_bearer_calls_hmac_compare_digest_with_correct_args(self):
        """_validate_bearer should call hmac.compare_digest with token and api_key."""
        middleware = ApiKeyMiddleware(api_key="test-secret-key-123")
        mock_context = MagicMock()

        # Mock _get_header to return the authorization header
        with patch.object(middleware, "_get_header", return_value="Bearer test-secret-key-123"):
            with patch("hmac.compare_digest", return_value=True) as mock_compare:
                result = middleware._validate_bearer(mock_context)
                mock_compare.assert_called_once_with("test-secret-key-123", "test-secret-key-123")

    def test_validate_bearer_rejects_wrong_key_via_hmac(self):
        """Wrong key should be rejected via hmac.compare_digest."""
        middleware = ApiKeyMiddleware(api_key="correct-key-abcdefghijk12345678901234567890")
        mock_context = MagicMock()

        with patch.object(middleware, "_get_header", return_value="Bearer wrong-key"):
            with patch("hmac.compare_digest", return_value=False) as mock_compare:
                result = middleware._validate_bearer(mock_context)
                assert result is False
                mock_compare.assert_called_once_with("wrong-key", "correct-key-abcdefghijk12345678901234567890")


class TestApiKeyMiddlewareLifecycleHooks:
    """ApiKeyMiddleware exposes all required lifecycle hooks."""

    def test_has_on_read_resource_hook(self):
        """Middleware should have on_read_resource async hook."""
        middleware = ApiKeyMiddleware(api_key="key")
        assert hasattr(middleware, "on_read_resource")
        import inspect
        assert inspect.iscoroutinefunction(middleware.on_read_resource)

    def test_has_on_list_tools_hook(self):
        """Middleware should have on_list_tools async hook."""
        middleware = ApiKeyMiddleware(api_key="key")
        assert hasattr(middleware, "on_list_tools")
        import inspect
        assert inspect.iscoroutinefunction(middleware.on_list_tools)

    def test_has_on_complete_hook(self):
        """Middleware should have on_complete async hook."""
        middleware = ApiKeyMiddleware(api_key="key")
        assert hasattr(middleware, "on_complete")
        import inspect
        assert inspect.iscoroutinefunction(middleware.on_complete)

    def test_has_on_progress_hook(self):
        """Middleware should have on_progress async hook."""
        middleware = ApiKeyMiddleware(api_key="key")
        assert hasattr(middleware, "on_progress")
        import inspect
        assert inspect.iscoroutinefunction(middleware.on_progress)

    def test_has_on_set_logging_level_hook(self):
        """Middleware should have on_set_logging_level async hook."""
        middleware = ApiKeyMiddleware(api_key="key")
        assert hasattr(middleware, "on_set_logging_level")
        import inspect
        assert inspect.iscoroutinefunction(middleware.on_set_logging_level)


class TestAccessMcpRequireAuthOnInitialize:
    """ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE toggle controls initialize auth."""

    def test_initialize_auth_required_when_env_true(self, monkeypatch):
        """When ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE=true, on_initialize enforces auth."""
        monkeypatch.setenv("ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE", "true")
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "test-key-abcdefghijk12345678901234567890")
        # Import fresh to pick up env var
        from ms_access_mcp.auth import ApiKeyMiddleware
        middleware = ApiKeyMiddleware(api_key="test-key-abcdefghijk12345678901234567890")
        assert middleware._require_auth_on_initialize is True

    def test_initialize_auth_not_required_when_env_false(self, monkeypatch):
        """When ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE=false, on_initialize skips auth."""
        monkeypatch.setenv("ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE", "false")
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "test-key-abcdefghijk12345678901234567890")
        from ms_access_mcp.auth import ApiKeyMiddleware
        middleware = ApiKeyMiddleware(api_key="test-key-abcdefghijk12345678901234567890")
        assert middleware._require_auth_on_initialize is False

    def test_initialize_auth_not_required_when_env_unset(self, monkeypatch):
        """When ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE is unset, default is False."""
        monkeypatch.delenv("ACCESS_MCP_REQUIRE_AUTH_ON_INITIALIZE", raising=False)
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "test-key-abcdefghijk12345678901234567890")
        from ms_access_mcp.auth import ApiKeyMiddleware
        middleware = ApiKeyMiddleware(api_key="test-key-abcdefghijk12345678901234567890")
        assert middleware._require_auth_on_initialize is False


class TestAuthFailureMetrics:
    """ApiKeyMiddleware emits auth_failures_total metric on authentication failures."""

    def test_auth_failure_metric_missing_token_increments_counter(self):
        """When Authorization header is missing, auth_failures_total should be incremented with reason='missing_token'."""
        middleware = ApiKeyMiddleware(api_key="test-key-abcdefghijk12345678901234567890")
        mock_context = MagicMock()

        with patch.object(middleware, "_get_header", return_value=None):
            with patch("ms_access_mcp.auth.auth_failures_total") as mock_counter:
                result = middleware._validate_bearer(mock_context)
                assert result is False
                # Counter should be incremented with reason label
                mock_counter.labels.assert_called_with(reason="missing_token")
                mock_counter.labels(reason="missing_token").inc.assert_called()

    def test_auth_failure_metric_invalid_token_increments_counter(self):
        """When Authorization header is invalid (not Bearer), auth_failures_total should be incremented with reason='invalid_format'."""
        middleware = ApiKeyMiddleware(api_key="test-key-abcdefghijk12345678901234567890")
        mock_context = MagicMock()

        with patch.object(middleware, "_get_header", return_value="Basic dXNlcjpwYXNz"):
            with patch("ms_access_mcp.auth.auth_failures_total") as mock_counter:
                result = middleware._validate_bearer(mock_context)
                assert result is False
                mock_counter.labels.assert_called_with(reason="invalid_format")
                mock_counter.labels(reason="invalid_format").inc.assert_called()

    def test_auth_failure_metric_wrong_token_increments_counter(self):
        """When Bearer token is wrong, auth_failures_total should be incremented with reason='invalid_token'."""
        middleware = ApiKeyMiddleware(api_key="correct-key-abcdefghijk12345678901234567890")
        mock_context = MagicMock()

        with patch.object(middleware, "_get_header", return_value="Bearer wrong-token"):
            with patch("hmac.compare_digest", return_value=False):
                with patch("ms_access_mcp.auth.auth_failures_total") as mock_counter:
                    result = middleware._validate_bearer(mock_context)
                    assert result is False
                    mock_counter.labels.assert_called_with(reason="invalid_token")
                    mock_counter.labels(reason="invalid_token").inc.assert_called()

    def test_auth_failure_metric_valid_token_does_not_increment(self):
        """When Bearer token is correct, auth_failures_total should NOT be incremented."""
        middleware = ApiKeyMiddleware(api_key="correct-key-abcdefghijk12345678901234567890")
        mock_context = MagicMock()

        with patch.object(middleware, "_get_header", return_value="Bearer correct-key-abcdefghijk12345678901234567890"):
            with patch("hmac.compare_digest", return_value=True):
                with patch("ms_access_mcp.auth.auth_failures_total") as mock_counter:
                    result = middleware._validate_bearer(mock_context)
                    assert result is True
                    # Counter inc should NOT be called on success
                    mock_counter.labels.assert_not_called()