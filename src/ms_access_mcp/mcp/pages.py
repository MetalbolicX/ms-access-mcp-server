"""SSR page handlers for Jinja2-rendered HTML pages.

Provides page route handlers for the SSR frontend:
- GET /: redirect to /login or /dashboard based on session
- GET /login: login page
- GET /dashboard: main dashboard
- GET /schema: schema explorer
- GET /er-diagram: ER diagram (Vue 3 + Vue Flow)
- GET /jobs: job monitor

Each handler renders the appropriate Jinja2 template with the
page-specific context and session data.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse

# Jinja2 environment is initialized lazily
_jinja_env: Optional[Any] = None


def _get_jinja_env() -> Any:
    """Lazily initialize and return the Jinja2 environment."""
    global _jinja_env
    if _jinja_env is None:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        template_dir = os.environ.get(
            "ACCESS_MCP_TEMPLATE_DIR",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"),
        )
        _jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _jinja_env


def _render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template with the given context."""
    env = _get_jinja_env()
    template = env.get_template(template_name)
    return template.render(**context)


def _get_session_api_key(request: Request, session_service: Any) -> Optional[str]:
    """Extract API key from session cookie if present."""
    cookie_name = getattr(session_service, "cookie_name", "mcp_session")
    cookie_value = request.cookies.get(cookie_name)
    if not cookie_value:
        return None
    return session_service.validate(cookie_value)


async def login_page(request: Request) -> HTMLResponse:
    """Render the login page."""
    context = {
        "request": request,
        "page_title": "Login",
 }
    html = _render_template("login.html", context)
    return HTMLResponse(content=html)


async def dashboard_page(request: Request, api_key: str) -> HTMLResponse:
    """Render the dashboard page with session API key."""
    context = {
        "request": request,
        "page_title": "Dashboard",
        "api_key": api_key,
    }
    html = _render_template("dashboard.html", context)
    return HTMLResponse(content=html)


async def schema_page(request: Request, api_key: str) -> HTMLResponse:
    """Render the schema explorer page."""
    context = {
        "request": request,
        "page_title": "Schema Explorer",
        "api_key": api_key,
    }
    html = _render_template("schema.html", context)
    return HTMLResponse(content=html)


async def er_diagram_page(request: Request, api_key: str) -> HTMLResponse:
    """Render the ER diagram page (Vue 3 + Vue Flow)."""
    context = {
        "request": request,
        "page_title": "ER Diagram",
        "api_key": api_key,
    }
    html = _render_template("er_diagram.html", context)
    return HTMLResponse(content=html)


async def jobs_page(request: Request, api_key: str) -> HTMLResponse:
    """Render the job monitor page."""
    context = {
        "request": request,
        "page_title": "Job Monitor",
        "api_key": api_key,
    }
    html = _render_template("jobs.html", context)
    return HTMLResponse(content=html)
