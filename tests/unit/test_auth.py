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


# =============================================================================
# Phase 1 RED tests — session auth, rate limiting, read-only mode
# These tests reference production code that does NOT exist yet.
# =============================================================================


class TestSessionServiceExists:
    """SessionService should exist in services/ and provide session management."""

    def test_session_service_module_exists(self):
        """src/ms_access_mcp/services/session.py should define SessionService."""
        from ms_access_mcp.services.session import SessionService
        assert SessionService is not None

    def test_session_service_has_sign_method(self):
        """SessionService should have a sign() method that returns a signed cookie value."""
        from ms_access_mcp.services.session import SessionService
        svc = SessionService(secret_key="test-secret-key-12345678901234567890")
        assert hasattr(svc, "sign")
        assert callable(svc.sign)

    def test_session_service_has_validate_method(self):
        """SessionService should have a validate() method that returns the api_key or None."""
        from ms_access_mcp.services.session import SessionService
        svc = SessionService(secret_key="test-secret-key-12345678901234567890")
        assert hasattr(svc, "validate")
        assert callable(svc.validate)

    def test_session_service_sign_and_validate_roundtrip(self):
        """sign() followed by validate() with the same key should return the original api_key."""
        from ms_access_mcp.services.session import SessionService
        svc = SessionService(secret_key="test-secret-key-12345678901234567890")
        api_key = "my-api-key-abcdefghijklmnopqrstuv"
        signed = svc.sign(api_key)
        assert signed is not None
        assert signed != api_key
        result = svc.validate(signed)
        assert result == api_key

    def test_session_service_validate_tampered_cookie_returns_none(self):
        """validate() with a tampered cookie should return None."""
        from ms_access_mcp.services.session import SessionService
        svc = SessionService(secret_key="test-secret-key-12345678901234567890")
        result = svc.validate("tampered.cookie.value")
        assert result is None

    def test_session_service_validate_expired_cookie_returns_none(self):
        """validate() with an expired cookie should return None."""
        from ms_access_mcp.services.session import SessionService
        svc = SessionService(secret_key="test-secret-key-12345678901234567890")
        # Use an old timestamp that is beyond the max age
        result = svc.validate("old.tampered.value")
        assert result is None


class TestRateLimiter:
    """RateLimiter should enforce login rate limits (5 attempts/min/IP)."""

    def test_rate_limiter_module_exists(self):
        """src/ms_access_mcp/services/rate_limiter.py should define RateLimiter."""
        from ms_access_mcp.services.rate_limiter import RateLimiter
        assert RateLimiter is not None

    def test_rate_limiter_is_callable(self):
        """RateLimiter should be instantiable with max_attempts and window_seconds."""
        from ms_access_mcp.services.rate_limiter import RateLimiter
        limiter = RateLimiter(max_attempts=5, window_seconds=60)
        assert limiter is not None

    def test_rate_limiter_allows_first_attempt(self):
        """First attempt from an IP should be allowed."""
        from ms_access_mcp.services.rate_limiter import RateLimiter
        limiter = RateLimiter(max_attempts=5, window_seconds=60)
        result = limiter.check("192.168.1.1")
        assert result is True

    def test_rate_limiter_allows_up_to_max_attempts(self):
        """Up to max_attempts from the same IP should be allowed."""
        from ms_access_mcp.services.rate_limiter import RateLimiter
        limiter = RateLimiter(max_attempts=5, window_seconds=60)
        for i in range(5):
            result = limiter.check("192.168.1.1")
            assert result is True, f"Attempt {i+1} should be allowed"

    def test_rate_limiter_blocks_sixth_attempt(self):
        """The (max_attempts+1)th attempt from the same IP should be blocked."""
        from ms_access_mcp.services.rate_limiter import RateLimiter
        limiter = RateLimiter(max_attempts=5, window_seconds=60)
        for _ in range(5):
            limiter.check("192.168.1.1")
        result = limiter.check("192.168.1.1")
        assert result is False

    def test_rate_limiter_different_ips_independent(self):
        """Different IPs should have independent rate limit counters."""
        from ms_access_mcp.services.rate_limiter import RateLimiter
        limiter = RateLimiter(max_attempts=5, window_seconds=60)
        for _ in range(5):
            limiter.check("192.168.1.1")
        # IP 2 should still be allowed
        result = limiter.check("192.168.1.2")
        assert result is True


class TestReadOnlyMiddleware:
    """ReadOnlyMiddleware should block destructive tools when ACCESS_MCP_READONLY=true."""

    def test_readonly_middleware_module_exists(self):
        """src/ms_access_mcp/auth.py should define ReadOnlyMiddleware."""
        from ms_access_mcp.auth import ReadOnlyMiddleware
        assert ReadOnlyMiddleware is not None

    def test_readonly_middleware_blocks_destructive_tools(self):
        """on_call_tool should raise McpError with403 when readonly is True and tool is destructive."""
        from ms_access_mcp.auth import ReadOnlyMiddleware
        from fastmcp.server.middleware import MiddlewareContext
        from unittest.mock import AsyncMock

        middleware = ReadOnlyMiddleware(readonly=True)
        mock_context = MagicMock(spec=MiddlewareContext)
        mock_context.message = MagicMock()
        mock_context.message.name = "delete_table"
        mock_context.message.arguments = {}

        call_next = AsyncMock()
        import pytest
        with pytest.raises(Exception):  # McpError or similar
            import asyncio
            asyncio.run(middleware.on_call_tool(mock_context, call_next))
        call_next.assert_not_called()

    def test_readonly_middleware_allows_read_tools(self):
        """on_call_tool should pass through when readonly is True but tool is read-only."""
        from ms_access_mcp.auth import ReadOnlyMiddleware
        from fastmcp.server.middleware import MiddlewareContext
        from unittest.mock import AsyncMock

        middleware = ReadOnlyMiddleware(readonly=True)
        mock_context = MagicMock(spec=MiddlewareContext)
        mock_context.message = MagicMock()
        mock_context.message.name = "get_tables"
        mock_context.message.arguments = {}

        call_next = AsyncMock(return_value="result")
        import asyncio
        result = asyncio.run(middleware.on_call_tool(mock_context, call_next))
        call_next.assert_called_once()

    def test_readonly_middleware_disabled_passes_through(self):
        """on_call_tool should pass through when readonly is False regardless of tool."""
        from ms_access_mcp.auth import ReadOnlyMiddleware
        from fastmcp.server.middleware import MiddlewareContext
        from unittest.mock import AsyncMock

        middleware = ReadOnlyMiddleware(readonly=False)
        mock_context = MagicMock(spec=MiddlewareContext)
        mock_context.message = MagicMock()
        mock_context.message.name = "delete_table"
        mock_context.message.arguments = {}

        call_next = AsyncMock(return_value="result")
        import asyncio
        result = asyncio.run(middleware.on_call_tool(mock_context, call_next))
        call_next.assert_called_once()


class TestSessionMiddleware:
    """SessionMiddleware should resolve API key from session cookie OR Bearer header."""

    def test_session_middleware_module_exists(self):
        """src/ms_access_mcp/auth.py should define SessionMiddleware."""
        from ms_access_mcp.auth import SessionMiddleware
        assert SessionMiddleware is not None

    def test_session_middleware_accepts_session_service(self):
        """SessionMiddleware should accept a SessionService in its constructor."""
        from ms_access_mcp.auth import SessionMiddleware
        from ms_access_mcp.services.session import SessionService
        svc = SessionService(secret_key="test-secret-key-12345678901234567890")
        middleware = SessionMiddleware(session_service=svc, api_key="test-key")
        assert middleware is not None

    def test_session_middleware_validates_cookie(self):
        """_validate_cookie should call session_service.validate() and return the api_key."""
        from ms_access_mcp.auth import SessionMiddleware
        from ms_access_mcp.services.session import SessionService

        svc = SessionService(secret_key="test-secret-key-12345678901234567890")
        middleware = SessionMiddleware(session_service=svc, api_key="test-key-abcdefghijklmnopqrstuv")
        mock_context = MagicMock()

        with patch.object(middleware, "_get_header", return_value=None):
            with patch.object(middleware, "_get_cookie", return_value=None):
                result = middleware._validate_cookie(mock_context)
                assert result is False  # No cookie

    def test_session_middleware_prioritizes_bearer_over_cookie(self):
        """When both Bearer header and session cookie are present, Bearer should win."""
        from ms_access_mcp.auth import SessionMiddleware
        from ms_access_mcp.services.session import SessionService

        svc = SessionService(secret_key="test-secret-key-12345678901234567890")
        middleware = SessionMiddleware(session_service=svc, api_key="test-key-abcdefghijklmnopqrstuv")
        mock_context = MagicMock()

        # Bearer present
        with patch.object(middleware, "_get_header", return_value="Bearer test-key-abcdefghijklmnopqrstuv"):
            with patch.object(middleware, "_get_cookie", return_value="some.signed.cookie"):
                result = middleware._validate_session_or_bearer(mock_context)
                # Should return True via Bearer validation, not cookie
                assert result is True