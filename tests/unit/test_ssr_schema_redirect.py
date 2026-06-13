"""Tests for the legacy /schema SSR route redirect to the unified /er-diagram.

Spec requirement: "The legacy /schema route MUST redirect (HTTP 301 or 302)
to the unified explorer route. The redirect MUST be server-side so that
bookmarks and direct links resolve without client JS."

This test exercises the full ASGI app via Starlette TestClient to confirm
the SSR route returns a 302 with Location: /er-diagram. The /er-diagram
route must continue to require an authenticated session.
"""

from __future__ import annotations

import tempfile

import pytest
from starlette.testclient import TestClient

from ms_access_mcp.mcp import server as server_module


@pytest.fixture
def ssr_app(monkeypatch):
    """Build a fresh ASGI app with SSR routes for the redirect tests.

    Resets the server module's lazy globals so a valid env (with API key)
    is used and routes are registered against the current configuration.
    """
    monkeypatch.setenv("ACCESS_MCP_API_KEY", "test-api-key-redirect-1234567890")
    monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", tempfile.gettempdir())
    monkeypatch.setenv("ACCESS_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("ACCESS_MCP_PORT", "8000")

    # Reset lazy globals so get_asgi_app() picks up the env above.
    server_module._config = None
    server_module._path_guard = None
    server_module._auth_middleware = None

    app = server_module.get_asgi_app(transport="http")
    with TestClient(app) as client:
        yield client

    server_module._config = None
    server_module._path_guard = None
    server_module._auth_middleware = None


class TestSchemaRedirect:
    """The /schema SSR route must 302 to /er-diagram, no client JS required."""

    def test_get_schema_redirects_to_er_diagram(self, ssr_app):
        """GET /schema returns 302 with Location: /er-diagram (no auth required)."""
        response = ssr_app.get("/schema", follow_redirects=False)

        assert response.status_code == 302, (
            f"Expected 302 redirect from /schema, got {response.status_code}"
        )
        assert response.headers["location"] == "/er-diagram", (
            f"Expected Location: /er-diagram, got {response.headers.get('location')!r}"
        )

    def test_get_er_diagram_without_session_redirects_to_login(self, ssr_app):
        """GET /er-diagram without an auth cookie redirects to /login (not to /schema).

        This is the triangulation test: it confirms the unified explorer route
        still enforces session auth, so the legacy cleanup did not weaken the
        /er-diagram guard.
        """
        response = ssr_app.get("/er-diagram", follow_redirects=False)

        assert response.status_code == 302
        assert response.headers["location"] == "/login", (
            f"Expected /er-diagram to redirect to /login for unauthenticated "
            f"requests, got {response.headers.get('location')!r}"
        )

    def test_schema_page_template_no_longer_rendered(self, ssr_app):
        """GET /schema must not render the legacy schema.html template.

        The redirect response body is a Starlette RedirectResponse, so the
        body should be empty (no HTML payload from schema.html).
        """
        response = ssr_app.get("/schema", follow_redirects=False)

        assert response.status_code == 302
        body = response.text
        assert "Schema Explorer" not in body, (
            "Legacy schema.html template must not be rendered for /schema requests"
        )
        assert "x-data=\"schemaPage()\"" not in body
