from typing import Optional, Any
import time
import signal
import atexit
import logging
from pathlib import Path

# Load .env file before any config initialization (optional dependency)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from ..services.connection import ConnectionPool
from ..services.com_automation import COMAutomationService
from ..services.migration import MigrationService
from ..services.dev_copy_service import DevCopyService
from ..connectors.registry import _default_registry
from .container import get_container
from ..config import ServerConfig
from ..auth import ApiKeyMiddleware
from ..path_guard import PathGuard
from ..telemetry.metrics import tool_calls_total, tool_latency_seconds
from ..telemetry.audit import audit_log
import uvicorn
from fastapi import Request

_logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("MS Access MCP Server")

# Path guard — initialized lazily on first tool call to avoid requiring
# ACCESS_MCP_API_KEY at import time (tests and stdio mode don't need auth).
# Tools that need path validation check: if _path_guard is not None: ...
_path_guard: PathGuard | None = None
_auth_middleware: ApiKeyMiddleware | None = None


class ToolTelemetryMiddleware(Middleware):
    """Middleware that records tool call metrics and audit log entries.

    Tracks:
    - tool_calls_total{tool, status}: increment on each tool call
    - tool_latency_seconds{tool}: histogram of call duration
    - Audit log entries: tool, args_hash, result, duration_ms, caller_ip
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Record metrics and audit log for each tool call."""
        # context.message is CallToolRequestParams with .name and .arguments
        tool_name = getattr(context.message, "name", "unknown") if context.message else "unknown"
        args = getattr(context.message, "arguments", None) or {}
        start = time.perf_counter()
        status = "success"
        try:
            result = await call_next(context)
            return result
        except Exception:
            status = "error"
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # Record Prometheus metrics
            tool_calls_total.labels(tool=tool_name, status=status).inc()
            tool_latency_seconds.labels(tool=tool_name).observe(duration_ms / 1000.0)
            # Write audit log entry (args not logged verbatim — hashed)
            audit_log(tool=tool_name, args=args, result=status, duration_ms=duration_ms)


def _get_path_guard() -> PathGuard | None:
    """Lazily initialize and return the PathGuard.

    Called by tool modules at runtime (not import time) so ServerConfig()
    validation only runs when HTTP mode with auth is used.
    """
    global _path_guard
    if _path_guard is None:
        try:
            config = ServerConfig()
            _path_guard = PathGuard(allowed_dirs=config.allowed_dirs)
        except ValueError:
            # No ACCESS_MCP_API_KEY — stdio mode without auth
            # Use home directory as allowed dir for stdio safety
            from pathlib import Path

            _path_guard = PathGuard(allowed_dirs=[str(Path.home())])
    return _path_guard


def _init_http_config() -> None:
    """Initialize HTTP auth middleware from environment.

    Idempotent: only runs once. Path guard is lazily initialized via
    _get_path_guard() on first tool call, not at import time.

    Auth is SKIPPED when no ACCESS_MCP_API_KEY is set — allowing the server
    to boot in HTTP mode without authentication (auth optional).
    Stdio transport is unaffected by this change.
    """
    global _auth_middleware
    if _auth_middleware is not None:
        return  # Already initialized

    try:
        config = ServerConfig()
    except ValueError:
        # No ACCESS_MCP_API_KEY — HTTP mode without auth
        # Stdio transport (__main__ guard) is unaffected
        _auth_middleware = None
        mcp.add_middleware(ToolTelemetryMiddleware())
        return

    _auth_middleware = ApiKeyMiddleware(api_key=config.api_key)
    mcp.add_middleware(_auth_middleware)
    mcp.add_middleware(ToolTelemetryMiddleware())


# Import tool modules to register their @mcp.tool() decorators
from . import (
    connection,
    schema,
    crud,
    export,
    com,
    vba,
    system,
    persistence,
    migration,
    linked_tables,
    dev_copy,
    analysis,
    reports,
    macros,
    relations,
    raw_sql,
    db_properties,
)  # noqa: E402, F811

# Re-export all tool functions for backward-compatible imports
from .connection import (  # noqa: E402
    connect_access,
    disconnect_access,
    is_connected,
    list_connections,
    set_active_connection,
    get_active_connection,
)
from .schema import (
    get_tables,
    get_table_schema,
    get_relationships,
    generate_sql,
    get_er_diagram,
    get_indexes,
    get_database_statistics,
)  # noqa: E402
from .crud import (  # noqa: E402
    get_queries,
    create_query,
    set_query_sql,
    delete_query,
    create_table,
    delete_table,
    create_index,
    drop_index,
    query_data,
    insert_data,
    update_data,
    delete_data,
    alter_table,
)
from .export import export_data  # noqa: E402
from .com import (  # noqa: E402
    launch_access,
    close_access,
    get_forms,
    get_modules,
    open_form,
    close_form,
    form_exists,
    get_form_controls,
    get_control_properties,
    set_control_property,
    set_control_properties,
    get_control_event_procedures,
    set_control_event_procedure,
    create_form,
    rename_form,
    get_form_properties,
    set_form_property,
    set_form_properties,
    add_control,
    remove_control,
    get_form_sections,
    get_form_section_properties,
    set_form_section_property,
    set_form_section_properties,
)
from .vba import (  # noqa: E402
    get_vba_projects,
    get_vba_code,
    set_vba_code,
    add_vba_procedure,
    compile_vba,
    save_database,
    delete_module,
    create_module,
    rename_module,
    module_exists,
    vba_list_procedures,
    vba_get_procedure,
    vba_replace_procedure,
    save_query,
)
from .system import (  # noqa: E402
    get_system_tables,
    get_object_metadata,
    recover_access,
    diagnose_environment,
)
from .persistence import (  # noqa: E402
    export_form_to_text,
    import_form_from_text,
    delete_form,
    export_report_to_text,
    import_report_from_text,
    delete_report,
    export_module_to_text,
    export_macro_to_text,
    import_macro_from_text,
    export_query_to_text,
    import_query_from_text,
    export_all_versioning,
    import_all_versioning,
    compare_versioning,
    export_schema_ddl,
    execute_sql_script,
)
from .reports import (  # noqa: E402
    report_exists,
    get_reports,
    create_report,
    rename_report,
    get_report_properties,
    set_report_property,
    set_report_properties,
    get_report_controls,
    get_report_control_properties,
    set_report_control_property,
    set_report_control_properties,
    add_report_control,
    remove_report_control,
    get_report_sections,
    get_report_section_properties,
    set_report_section_property,
    set_report_section_properties,
)
from .macros import (  # noqa: E402
    macro_exists,
    get_macros,
    get_macro_properties,
    create_macro,
    rename_macro,
    delete_macro,
    run_macro,
)
from .relations import create_relationship, delete_relationship  # noqa: E402
from .raw_sql import execute_raw_sql  # noqa: E402
from .migration import extract_schema, upload_schema, transfer_data, get_migration_status  # noqa: E402
from .linked_tables import (
    get_linked_tables,
    create_linked_table,
    refresh_linked_table,
    unlink_table,
    upsert_linked_table,
    store_credential,
    clear_credentials,
)  # noqa: E402
from .dev_copy import (  # noqa: E402
    compact_repair,
    copy_database,
    export_module_backup,
    import_module_from_text,
    restore_module_backup,
    export_form_backup,
    import_form_from_file,
    restore_form_backup,
    export_report_backup,
    import_report_from_file,
    restore_report_backup,
    create_dev_copy,
    deploy_dev_copy,
    discard_dev_copy,
    get_dev_copy_status,
)
from .analysis import analyze_query  # noqa: E402
from .db_properties import get_database_properties, set_database_property  # noqa: E402

# Tool registry for SSR browser-based tool proxy
_TOOL_REGISTRY: dict[str, Any] = {
    "connect_access": connect_access,
    "disconnect_access": disconnect_access,
    "is_connected": is_connected,
    "get_tables": get_tables,
    "get_table_schema": get_table_schema,
    "get_relationships": get_relationships,
    "get_queries": get_queries,
    "get_database_statistics": get_database_statistics,
    "get_forms": get_forms,
    "get_reports": get_reports,
    "get_macros": get_macros,
    "get_modules": get_modules,
    "get_er_diagram": get_er_diagram,
    "get_migration_status": get_migration_status,
}


def get_asgi_app(transport: str = "http"):
    """Initialize HTTP config and return the FastMCP ASGI application.

    Integrates SSR page routes, API endpoints, and static asset serving
    alongside the MCP protocol at /mcp/.

    Args:
        transport: HTTP transport type ("http", "streamable-http", "sse")

    Returns:
        The ASGI application suitable for use with uvicorn or TestClient.
    """
    _init_http_config()
    app = mcp.http_app(transport=transport, json_response=True, stateless_http=True)

    # Routes must be registered BEFORE the root static mount /
    # so SSR pages take priority over the static file fallback.
    _add_ssr_routes(app)
    _mount_ssr_static(app)
    return app


def _mount_ssr_static(app: Any) -> None:
    """Mount static assets for SSR pages (build output + root files)."""
    from pathlib import Path

    # server.py is at src/ms_access_mcp/mcp/server.py — 4 levels to project root
    project_root = Path(__file__).parent.parent.parent.parent
    frontend_dist = project_root / "frontend" / "dist"
    if not frontend_dist.exists():
        return

    from starlette.staticfiles import StaticFiles

    # Mount build JS/CSS at /dist/assets/
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/dist/assets", StaticFiles(directory=str(assets_dir)), name="ssr_assets")

    # Serve favicon and icons via route (avoids mounting at / which
    # would interfere with MCP paths like /mcp/)
    _add_static_routes(app, frontend_dist)


def _add_static_routes(app: Any, frontend_dist: Path) -> None:
    """Register routes for individual root-level static files."""
    from starlette.responses import FileResponse, Response
    from starlette.requests import Request

    for filename in ("favicon.svg", "icons.svg"):
        file_path = frontend_dist / filename
        if not file_path.exists():
            continue

        async def serve_file(request: Request, _file_path: Path = file_path) -> Response:
            return FileResponse(str(_file_path))

        app.add_route(f"/{filename}", serve_file, methods=["GET"])


def _add_ssr_routes(app: Any) -> None:
    """Register SSR page routes and API endpoints on the app."""
    from starlette.responses import RedirectResponse, JSONResponse
    from starlette.requests import Request
    import hmac
    from .container import get_container
    from ..config import ServerConfig
    from .pages import login_page, dashboard_page, schema_page, er_diagram_page, jobs_page

    def _require_session(request: Request) -> tuple[str | None, Any]:
        """Return (api_key, None) or (None, redirect)."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return None, RedirectResponse(url="/login", status_code=302)
        api_key = _get_session_api_key(request, session_svc)
        if not api_key:
            return None, RedirectResponse(url="/login", status_code=302)
        return api_key, None

    # ── SSR Page Routes ──────────────────────────────────────────

    async def ssr_root(request: Request):
        """Root path redirects to /dashboard if authenticated, else /login."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return RedirectResponse(url="/login", status_code=302)
        api_key = _get_session_api_key(request, session_svc)
        if api_key:
            return RedirectResponse(url="/dashboard", status_code=302)
        return RedirectResponse(url="/login", status_code=302)

    app.add_route("/", ssr_root, methods=["GET"])

    async def ssr_login(request: Request):
        """Login page (always accessible)."""
        return await login_page(request)

    app.add_route("/login", ssr_login, methods=["GET"])

    async def ssr_dashboard(request: Request):
        """Dashboard page (requires session)."""
        api_key, error = _require_session(request)
        if error:
            return error
        return await dashboard_page(request, api_key)

    app.add_route("/dashboard", ssr_dashboard, methods=["GET"])

    async def ssr_schema(request: Request):
        """Schema explorer page (requires session)."""
        api_key, error = _require_session(request)
        if error:
            return error
        return await schema_page(request, api_key)

    app.add_route("/schema", ssr_schema, methods=["GET"])

    async def ssr_er_diagram(request: Request):
        """ER diagram page (requires session)."""
        api_key, error = _require_session(request)
        if error:
            return error
        return await er_diagram_page(request, api_key)

    app.add_route("/er-diagram", ssr_er_diagram, methods=["GET"])

    async def ssr_jobs(request: Request):
        """Job monitor page (requires session)."""
        api_key, error = _require_session(request)
        if error:
            return error
        return await jobs_page(request, api_key)

    app.add_route("/jobs", ssr_jobs, methods=["GET"])

    # ── API Endpoints ────────────────────────────────────────────

    async def api_login(request: Request):
        """Login endpoint — validates API key and sets session cookie."""
        from ..services.rate_limiter import RateLimiter

        client_ip = request.client.host if request.client else "unknown"
        container = get_container()
        rate_limiter = container.rate_limiter

        if rate_limiter and not rate_limiter.check(client_ip):
            retry_after = rate_limiter.get_retry_after(client_ip) if rate_limiter else 60
            return JSONResponse(
                {"error": "Too many login attempts. Please try again later."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        try:
            body = await request.json()
            api_key_input = body.get("api_key", "")
        except Exception:
            return JSONResponse({"error": "Invalid request body"}, status_code=400)

        try:
            config = ServerConfig()
        except ValueError:
            return JSONResponse({"error": "Server configuration error"}, status_code=500)

        if not hmac.compare_digest(api_key_input, config.api_key):
            return JSONResponse({"error": "Invalid API key"}, status_code=401)

        session_svc = container.session_service
        if session_svc is None:
            return JSONResponse({"error": "Session service not configured"}, status_code=500)

        signed = session_svc.sign(config.api_key)
        response = JSONResponse({"success": True})
        response.set_cookie(
            key=session_svc.cookie_name,
            value=signed,
            max_age=session_svc.max_age,
            httponly=True,
            samesite="Lax",
            secure=False,
        )
        return response

    app.add_route("/api/login", api_login, methods=["POST"])

    async def api_logout(request: Request):
        """Logout endpoint — clears session cookie."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return JSONResponse({"success": True})

        response = JSONResponse({"success": True})
        params = session_svc.clear_cookie_params()
        response.delete_cookie(key=params["name"])
        return response

    app.add_route("/api/logout", api_logout, methods=["POST"])

    async def api_tools_call(request: Request):
        """Tool proxy for browser-based tool execution via session auth."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return JSONResponse({"error": "Session service not configured"}, status_code=500)

        api_key = _get_session_api_key(request, session_svc)
        if not api_key:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        try:
            body = await request.json()
            tool_name = body.get("name")
            arguments = body.get("arguments", {})
        except Exception:
            return JSONResponse({"error": "Invalid request body"}, status_code=400)

        tool_fn = _TOOL_REGISTRY.get(tool_name)
        if tool_fn is None:
            return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=400)

        try:
            import inspect
            import asyncio

            if inspect.iscoroutinefunction(tool_fn):
                result = await tool_fn(**arguments)
            else:
                result = tool_fn(**arguments)
            return JSONResponse(
                {"success": True, **result} if isinstance(result, dict) else {"success": True, "result": result}
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    app.add_route("/api/tools/call", api_tools_call, methods=["POST"])


def get_ssr_app():
    """Create a FastAPI app that wraps SSR pages alongside the MCP server.

    Returns:
        A FastAPI ASGI app with SSR routes at /, /login, /dashboard, /schema,
        /er-diagram, /jobs, plus /api/login, /api/logout, /api/tools/call.
 """
    from fastapi import FastAPI, Request
    from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
    from .pages import (
        login_page,
        dashboard_page,
        schema_page,
        er_diagram_page,
        jobs_page,
    )

    app = FastAPI(title="MS Access MCP SSR")

    # Mount build assets at /dist/assets/ for SSR pages
    from pathlib import Path
    # get_ssr_app is at src/ms_access_mcp/mcp/server.py — 4 levels to project root
    dist_assets = Path(__file__).parent.parent.parent.parent / "frontend" / "dist" / "assets"
    if dist_assets.exists():
        from starlette.staticfiles import StaticFiles
        app.mount("/dist/assets", StaticFiles(directory=str(dist_assets)), name="assets")

    # Import services lazily to avoid circular imports
    from .container import get_container

    @app.get("/")
    async def root(request: Request):
        """Root path redirects to /dashboard if authenticated, else /login."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return RedirectResponse(url="/login", status_code=302)
        api_key = _get_session_api_key(request, session_svc)
        if api_key:
            return RedirectResponse(url="/dashboard", status_code=302)
        return RedirectResponse(url="/login", status_code=302)

    @app.get("/login", response_class=HTMLResponse)
    async def login(request: Request):
        """Login page (always accessible, even when authenticated)."""
        return await login_page(request)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Dashboard page (requires session)."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return RedirectResponse(url="/login", status_code=302)
        api_key = _get_session_api_key(request, session_svc)
        if not api_key:
            return RedirectResponse(url="/login", status_code=302)
        return await dashboard_page(request, api_key)

    @app.get("/schema", response_class=HTMLResponse)
    async def schema_explorer(request: Request):
        """Schema explorer page (requires session)."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return RedirectResponse(url="/login", status_code=302)
        api_key = _get_session_api_key(request, session_svc)
        if not api_key:
            return RedirectResponse(url="/login", status_code=302)
        return await schema_page(request, api_key)

    @app.get("/er-diagram", response_class=HTMLResponse)
    async def er_diagram(request: Request):
        """ER diagram page (requires session)."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return RedirectResponse(url="/login", status_code=302)
        api_key = _get_session_api_key(request, session_svc)
        if not api_key:
            return RedirectResponse(url="/login", status_code=302)
        return await er_diagram_page(request, api_key)

    @app.get("/jobs", response_class=HTMLResponse)
    async def jobs(request: Request):
        """Job monitor page (requires session)."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return RedirectResponse(url="/login", status_code=302)
        api_key = _get_session_api_key(request, session_svc)
        if not api_key:
            return RedirectResponse(url="/login", status_code=302)
        return await jobs_page(request, api_key)

    @app.post("/api/login")
    async def api_login(request: Request):
        """Login endpoint — validates API key and sets session cookie."""
        from ..services.rate_limiter import RateLimiter
        from ..config import ServerConfig

        client_ip = request.client.host if request.client else "unknown"
        container = get_container()
        rate_limiter = container.rate_limiter

        if rate_limiter and not rate_limiter.check(client_ip):
            retry_after = rate_limiter.get_retry_after(client_ip) if rate_limiter else 60
            return JSONResponse(
                {"error": "Too many login attempts. Please try again later."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        try:
            body = await request.json()
            api_key_input = body.get("api_key", "")
        except Exception:
            return JSONResponse({"error": "Invalid request body"}, status_code=400)

        try:
            config = ServerConfig()
        except ValueError:
            return JSONResponse({"error": "Server configuration error"}, status_code=500)

        import hmac
        if not hmac.compare_digest(api_key_input, config.api_key):
            return JSONResponse({"error": "Invalid API key"}, status_code=401)

        # Sign and return session cookie
        session_svc = container.session_service
        if session_svc is None:
            return JSONResponse({"error": "Session service not configured"}, status_code=500)

        signed = session_svc.sign(config.api_key)
        response = JSONResponse({"success": True})
        response.set_cookie(
            key=session_svc.cookie_name,
            value=signed,
            max_age=session_svc.max_age,
            httponly=True,
            samesite="Lax",
            secure=False,  # TODO: True in production with HTTPS
        )
        return response

    @app.post("/api/logout")
    async def api_logout(request: Request):
        """Logout endpoint — clears session cookie."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return JSONResponse({"success": True})

        response = JSONResponse({"success": True})
        params = session_svc.clear_cookie_params()
        response.delete_cookie(key=params["name"])
        return response

    @app.post("/api/tools/call")
    async def api_tools_call(request: Request):
        """Tool proxy for browser-based tool execution via session auth."""
        container = get_container()
        session_svc = container.session_service
        if session_svc is None:
            return JSONResponse({"error": "Session service not configured"}, status_code=500)

        api_key = _get_session_api_key(request, session_svc)
        if not api_key:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        try:
            body = await request.json()
            tool_name = body.get("name")
            arguments = body.get("arguments", {})
        except Exception:
            return JSONResponse({"error": "Invalid request body"}, status_code=400)

        # Look up the tool function from the server module's exports
        tool_fn = _TOOL_REGISTRY.get(tool_name)
        if tool_fn is None:
            return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=400)

        try:
            import inspect

            if inspect.iscoroutinefunction(tool_fn):
                result = await tool_fn(**arguments)
            else:
                result = tool_fn(**arguments)
            return JSONResponse({"success": True, **result} if isinstance(result, dict) else {"success": True, "result": result})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    return app


def _get_session_api_key(request: Request, session_service) -> str | None:
    """Extract API key from session cookie."""
    cookie_name = getattr(session_service, "cookie_name", "mcp_session")
    cookie_value = request.cookies.get(cookie_name)
    if not cookie_value:
        return None
    return session_service.validate(cookie_value)


def run_http(
    host: str = "127.0.0.1",
    port: int = 8000,
    transport: str = "http",
    app: Optional[Any] = None,
    ssl_keyfile: Optional[str] = None,
    ssl_certfile: Optional[str] = None,
) -> None:
    """Run the MCP server with HTTP transport and auth.

    Args:
        host: Bind address (default 127.0.0.1)
        port: Bind port (default 8000)
        transport: HTTP transport type ("http", "streamable-http", "sse")
        app: Optional ASGI app to use (for testing). If not provided,
             creates app via get_asgi_app().
        ssl_keyfile: Optional path to SSL key file for TLS.
        ssl_certfile: Optional path to SSL certificate file for TLS.
    """
    if app is None:
        app = get_asgi_app(transport=transport)
    uvicorn.run(app, host=host, port=port, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)


def _graceful_shutdown() -> None:
    """Clean up all resources on process exit.

    Called via atexit and signal handlers to ensure proper cleanup when the
    server process is terminated (e.g., when opencode closes the session).
    This prevents orphaned MS Access instances and COM object leaks.
    """
    try:
        container = get_container()
        # Disconnect all connections in the pool to clean up COM/ODBC resources
        for name in list(container.connection_pool.list().keys()):
            try:
                container.connection_pool.disconnect(name)
            except Exception as e:
                _logger.debug(f"Error disconnecting '{name}' during shutdown: {e}")
    except Exception as e:
        _logger.debug(f"Error during graceful shutdown: {e}")


def _handle_signal(signum: int, frame: Any) -> None:
    """Signal handler for graceful shutdown on SIGTERM/SIGINT." + " """
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    _logger.info(f"Received {sig_name}, initiating graceful shutdown...")
    _graceful_shutdown()
    # Re-raise the signal to allow default handling
    raise SystemExit(0)


# Register signal handlers and atexit cleanup for graceful shutdown
# This ensures COM resources are properly released when the session is terminated
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _handle_signal)
if hasattr(signal, "SIGINT"):
    signal.signal(signal.SIGINT, _handle_signal)
atexit.register(_graceful_shutdown)


if __name__ == "__main__":
    mcp.run(transport="stdio")


def __getattr__(name):
    """Resolve legacy module-level service names to container properties (PEP 562)."""
    _mapping = {
        "connection_service": "connection_pool",
        "com_automation_service": "com_automation",
        "migration_service": "migration",
        "dev_copy_service": "dev_copy",
    }
    if name in _mapping:
        return getattr(get_container(), _mapping[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
