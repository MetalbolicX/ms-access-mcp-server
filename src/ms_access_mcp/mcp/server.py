from typing import Optional, Any
import time

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
    """
    global _auth_middleware
    if _auth_middleware is not None:
        return  # Already initialized
    _auth_middleware = ApiKeyMiddleware(api_key=ServerConfig().api_key)
    mcp.add_middleware(_auth_middleware)
    mcp.add_middleware(ToolTelemetryMiddleware())


# Import tool modules to register their @mcp.tool() decorators
from . import connection, schema, crud, export, com, vba, system, persistence, migration, linked_tables, dev_copy, analysis  # noqa: E402, F811

# Re-export all tool functions for backward-compatible imports
from .connection import (  # noqa: E402
    connect_access, disconnect_access, is_connected,
    list_connections, set_active_connection, get_active_connection,
)
from .schema import get_tables, get_table_schema, get_relationships, generate_sql, get_er_diagram  # noqa: E402
from .crud import (  # noqa: E402
    get_queries, create_query, set_query_sql, delete_query,
    create_table, delete_table,
    query_data, insert_data, update_data, delete_data,
)
from .export import export_data  # noqa: E402
from .com import (  # noqa: E402
    launch_access, close_access,
    get_forms, get_reports, get_macros, get_modules,
    open_form, close_form,
    form_exists, get_form_controls, get_control_properties, set_control_property,
    set_control_properties, get_control_event_procedures,
)
from .vba import (  # noqa: E402
    get_vba_projects, get_vba_code,
    set_vba_code, add_vba_procedure,
    compile_vba, save_database, delete_module,
    vba_list_procedures, vba_get_procedure, vba_replace_procedure,
    save_query,
)
from .system import (  # noqa: E402
    get_system_tables, get_object_metadata,
    recover_access, diagnose_environment,
)
from .persistence import (  # noqa: E402
    export_form_to_text, import_form_from_text, delete_form,
    export_report_to_text, import_report_from_text, delete_report,
    export_module_to_text, export_macro_to_text,
    export_query_to_text, import_query_from_text,
    export_all_versioning, import_all_versioning, compare_versioning,
    export_schema_ddl, execute_sql_script,
)
from .migration import extract_schema, upload_schema, transfer_data, get_migration_status  # noqa: E402
from .linked_tables import get_linked_tables, create_linked_table, refresh_linked_table, unlink_table  # noqa: E402
from .dev_copy import (  # noqa: E402
    compact_repair, copy_database,
    export_module_backup, import_module_from_text, restore_module_backup,
    export_form_backup, import_form_from_file, restore_form_backup,
    export_report_backup, import_report_from_file, restore_report_backup,
    create_dev_copy, deploy_dev_copy, discard_dev_copy, get_dev_copy_status,
)
from .analysis import analyze_query  # noqa: E402


def get_asgi_app(transport: str = "http"):
    """Initialize HTTP config and return the FastMCP ASGI application.

    Args:
        transport: HTTP transport type ("http", "streamable-http", "sse")

    Returns:
        The ASGI application suitable for use with uvicorn or TestClient.
    """
    _init_http_config()
    return mcp.http_app(transport=transport, json_response=True, stateless_http=True)


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
