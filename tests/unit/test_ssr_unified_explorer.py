"""Integration test for the unified /er-diagram SSR route.

Spec requirement: "The explorer MUST render explicit, non-blocking states
for loading, empty, and error conditions in each pane, and MUST NOT leave
a pane blank or freeze the other pane."

This test exercises the unified explorer end-to-end through the SSR
app and confirms the page is delivered with everything the client-side
Vue bundle needs to render its loading / empty / error states:

  1. The page returns 200 to an authenticated request.
  2. The page contains the `<div id="vue-app">` mount point that the
     Vue bundle attaches to.
  3. The page references the `/dist/assets/er-diagram.iife.js` bundle
     that drives the diagram pane (including its loading/empty/error
     states).
  4. The page is the unified explorer shell, not a leftover from the
     legacy Alpine.js schema page.
  5. The session-auth gate still works (unauthenticated requests
     redirect to /login, not /schema).

The actual loading/empty/error state rendering for each pane is
covered at the component level in
`frontend/src/components/SchemaListPanel.spec.ts` and
`frontend/src/views/ErDiagramView.spec.ts`. This integration test
proves the server-side delivery contract that the client bundle
depends on.
"""

from __future__ import annotations

import tempfile

import pytest
from starlette.testclient import TestClient

from ms_access_mcp.mcp import server as server_module

# A long-enough API key to satisfy the `min 32 chars` requirement on
# ServerConfig validation.
_TEST_API_KEY = "test-api-key-unified-explorer-1234567890"


@pytest.fixture
def ssr_app(monkeypatch):
    """Build a fresh ASGI app with SSR routes for the unified-explorer tests.

    Resets the server module's lazy globals so a valid env (with API key)
    is used and routes are registered against the current configuration.
    The fixture yields a Starlette TestClient bound to the app.
    """
    monkeypatch.setenv("ACCESS_MCP_API_KEY", _TEST_API_KEY)
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


def _login(client: TestClient) -> None:
    """Authenticate the test client against /api/login.

    On success, the response sets the session cookie on the client so
    subsequent /er-diagram requests pass the session guard.
    """
    response = client.post("/api/login", json={"api_key": _TEST_API_KEY})
    assert response.status_code == 200, (
        f"Login should succeed with a valid API key, got {response.status_code}: "
        f"{response.text}"
    )


class TestUnifiedExplorerSsrDelivery:
    """The /er-diagram SSR route serves the unified explorer shell.

    These tests are the integration layer for the
    unified-schema-explorer change. They boot the real ASGI app,
    authenticate, and assert that the HTML response contains the
    mount point and JS bundle the client-side Vue 3 app needs to
    render the diagram pane's loading/empty/error states.
    """

    def test_get_er_diagram_returns_200_for_authenticated_request(self, ssr_app):
        """The unified explorer page must return 200 once the user is signed in."""
        _login(ssr_app)
        response = ssr_app.get("/er-diagram", follow_redirects=False)

        assert response.status_code == 200, (
            f"Expected 200 for authenticated /er-diagram, got {response.status_code}"
        )

    def test_er_diagram_html_contains_vue_mount_point(self, ssr_app):
        """The response must include the <div id='vue-app'> mount point.

        The Vue 3 bundle attaches to this element on page load. Without
        it, the bundle has no place to mount and the loading/empty/error
        states from the diagram pane never render.
        """
        _login(ssr_app)
        response = ssr_app.get("/er-diagram", follow_redirects=False)
        body = response.text

        assert 'id="vue-app"' in body, (
            "Unified explorer SSR response must include the Vue mount point "
            "<div id='vue-app'> so the client bundle can attach."
        )

    def test_er_diagram_html_references_the_er_diagram_bundle(self, ssr_app):
        """The response must include a <script> reference to er-diagram.iife.js.

        The library-mode build of the unified explorer is the bundle that
        contains ErDiagramView.vue and its loading/empty/error rendering
        logic. The SSR template must reference it so the page can boot.
        """
        _login(ssr_app)
        response = ssr_app.get("/er-diagram", follow_redirects=False)
        body = response.text

        assert "/dist/assets/er-diagram.iife.js" in body, (
            "Unified explorer SSR response must reference the "
            "/dist/assets/er-diagram.iife.js bundle."
        )

    def test_er_diagram_html_references_the_app_stylesheet(self, ssr_app):
        """The response must include the shared stylesheet link.

        The unified explorer CSS variables (used by the diagram's
        loading/empty/error states) come from /dist/assets/styles.css.
        Without the link, the page renders unstyled.
        """
        _login(ssr_app)
        response = ssr_app.get("/er-diagram", follow_redirects=False)
        body = response.text

        assert "/dist/assets/styles.css" in body, (
            "Unified explorer SSR response must reference the shared "
            "stylesheet /dist/assets/styles.css."
        )

    def test_er_diagram_does_not_render_legacy_alpine_schema_template(self, ssr_app):
        """The unified explorer must not include any legacy Alpine.js markers.

        Regression guard for the PR1 cleanup. The legacy
        `templates/schema.html` used Alpine.js (x-data="schemaPage()")
        and rendered an h1 with "Schema Explorer". The unified explorer
        is Vue-rendered, so neither of those markers should appear in
        the SSR response.
        """
        _login(ssr_app)
        response = ssr_app.get("/er-diagram", follow_redirects=False)
        body = response.text

        # The Alpine.js hook used by the legacy page.
        assert 'x-data="schemaPage()"' not in body, (
            "Legacy Alpine.js schemaPage() hook must not appear in the "
            "unified explorer SSR response."
        )
        # The legacy page also used these specific section ids.
        assert 'id="schema-page"' not in body, (
            "Legacy #schema-page id must not appear in the unified "
            "explorer SSR response."
        )

    def test_er_diagram_session_guard_still_redirects_to_login(self, ssr_app):
        """The /er-diagram route still requires a session (triangulation).

        Confirms that the PR1 cleanup did not weaken the auth gate on
        the unified explorer route. A request without the session
        cookie must be redirected to /login — never to the deleted
        /schema endpoint.
        """
        response = ssr_app.get("/er-diagram", follow_redirects=False)

        assert response.status_code == 302, (
            f"Expected 302 from /er-diagram for unauthenticated request, "
            f"got {response.status_code}"
        )
        assert response.headers["location"] == "/login", (
            f"Expected /er-diagram unauthenticated redirect to /login, "
            f"got {response.headers.get('location')!r}"
        )
