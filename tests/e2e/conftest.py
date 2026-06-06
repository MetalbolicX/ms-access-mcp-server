"""
Pytest configuration for E2E workflow tests.

Thin e2e-specific fixtures that wrap integration fixtures and provide
HTTP TestClient setup. All pool tests use SQLite-backed adapters
so they run on any platform.

Cleanup: each test uses explicit try/finally blocks, not autouse fixtures.
Naming: all test-created objects prefixed with __e2e_test_.
"""

import os
import sqlite3
import tempfile
from typing import Any

import pytest
from starlette.testclient import TestClient

from ms_access_mcp.mcp import server as server_module

# ---- Import shared integration fixtures via qualified path -----------------
# Use 'tests.integration.conftest' to avoid helpers.py shadowing in e2e/
from tests.integration.conftest import (
    _sqlite_pyodbc_connect,
    pool_with_sqlite,
    pool_with_two_adapters,
    pool_with_three_adapters,
    sqlite_db,
)
from tests.integration.helpers import call_mcp_tool

__all__ = [
    "e2e_pool",
    "e2e_two_adapters",
    "e2e_three_adapters",
    "temp_export_dir",
    "e2e_http_client",
    "e2e_http_pool_client",
    "e2e_streamable_client",
    "empty_pool",
    "call_mcp_tool",
]


# ---- E2E-specific pool fixtures ------------------------------------------------

@pytest.fixture
def empty_pool():
    """ConnectionPool with no connections — for error-path tests.

    Use this to test behavior when pool has no active connections,
    e.g. disconnect when not connected, query without connection.
    """
    from ms_access_mcp.services.connection import ConnectionPool
    pool = ConnectionPool()
    yield pool
    # Clean up any connections that may have been created during the test
    connected_names = list(pool._pool.keys())
    for name in connected_names:
        try:
            pool.disconnect(name)
        except Exception:
            pass


@pytest.fixture
def e2e_pool(pool_with_sqlite):
    """ConnectionPool with one SQLite-backed OdbcAdapter, named 'default'.

    Wraps pool_with_sqlite from integration conftest.
    Cleanup: disconnect 'default' in try/finally.
    """
    yield pool_with_sqlite


@pytest.fixture
def e2e_two_adapters(pool_with_two_adapters):
    """ConnectionPool with two named SQLite-backed connections ('prod', 'dev').

    Wraps pool_with_two_adapters from integration conftest.
    Cleanup: disconnect both in try/finally.
    """
    yield pool_with_two_adapters


@pytest.fixture
def e2e_three_adapters(pool_with_three_adapters):
    """ConnectionPool with three named SQLite-backed connections ('alpha', 'beta', 'gamma').

    Wraps pool_with_three_adapters from integration conftest.
    Cleanup: disconnect all three in try/finally.
    """
    yield pool_with_three_adapters


# ---- Export directory fixture --------------------------------------------------

@pytest.fixture
def temp_export_dir():
    """Temporary directory for export workflow tests.

    Yields a path string. Cleanup happens automatically via TemporaryDirectory.
    """
    with tempfile.TemporaryDirectory(prefix="e2e_export_") as d:
        yield d


# ---- HTTP TestClient fixture ---------------------------------------------------

@pytest.fixture
def e2e_http_client(monkeypatch):
    """Starlette TestClient for MCP HTTP endpoint with authorized requests.

    Sets ACCESS_MCP_API_KEY env, resets server module globals, calls
    _init_http_config(), then yields TestClient(http_app(json_response=True,
    stateless_http=True)).

    Note: uses class scope so lifespan is shared across all test methods
    in TestHttpWorkflow (avoids StreamableHTTPSessionManager re-init issues).

    Workflow:
        1. Set ACCESS_MCP_API_KEY env + ACCESS_MCP_HOST/PORT/ALLOWED_DIRS
        2. Reset server_module._config, _path_guard, _auth_middleware to None
        3. Call server_module._init_http_config()
        4. Yield TestClient(server_module.mcp.http_app(...))
        5. (no autouse teardown — each test manages its own session via try/finally)
    """
    api_key = "test-e2e-api-key-12345"
    allowed_dir = tempfile.gettempdir()

    for key, val in {
        "ACCESS_MCP_API_KEY": api_key,
        "ACCESS_MCP_HOST": "127.0.0.1",
        "ACCESS_MCP_PORT": "8000",
        "ACCESS_MCP_ALLOWED_DIRS": allowed_dir,
    }.items():
        monkeypatch.setenv(key, val)

    # Reset HTTP globals so _init_http_config re-initializes with new env
    server_module._config = None
    server_module._path_guard = None
    server_module._auth_middleware = None

    server_module._init_http_config()

    app = server_module.mcp.http_app(json_response=True, stateless_http=True)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def e2e_streamable_client(monkeypatch):
    """TestClient for streamable-http transport.

    Sets ACCESS_MCP_API_KEY env, resets server module globals, calls
    _init_http_config(), then yields TestClient(http_app(transport="streamable-http",
    json_response=True, stateless_http=True)).
    """
    api_key = "test-e2e-api-key-12345"
    allowed_dir = tempfile.gettempdir()

    for key, val in {
        "ACCESS_MCP_API_KEY": api_key,
        "ACCESS_MCP_HOST": "127.0.0.1",
        "ACCESS_MCP_PORT": "8000",
        "ACCESS_MCP_ALLOWED_DIRS": allowed_dir,
    }.items():
        monkeypatch.setenv(key, val)

    # Reset HTTP globals so _init_http_config re-initializes with new env
    server_module._config = None
    server_module._path_guard = None
    server_module._auth_middleware = None

    server_module._init_http_config()

    app = server_module.mcp.http_app(transport="streamable-http", json_response=True, stateless_http=True)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def e2e_http_pool_client(monkeypatch):
    """Starlette TestClient for MCP HTTP with SQLite-backed connection pool injected.

    This fixture provides a fully-connected HTTP test client that can execute
    the complete MCP lifecycle: initialize → connect → create_table → insert_data
    → query_data → disconnect, all over HTTP JSON-RPC 2.0 transport.

    Key difference from e2e_http_client: the connection_service is monkeypatched
    with a SQLite-backed ConnectionPool so database operations actually work.

    Workflow:
        1. Set ACCESS_MCP_API_KEY env + ACCESS_MCP_HOST/PORT/ALLOWED_DIRS
        2. Reset server_module globals (_config, _path_guard, _auth_middleware)
        3. Create temp SQLite db with __meta table (lifecycle_db marker)
        4. Create ConnectionPool with SQLite-backed OdbcAdapter (patch pyodbc.connect)
        5. Monkeypatch connection_service in BOTH server AND connection modules
        6. Call server_module._init_http_config()
        7. Yield TestClient(server_module.mcp.http_app(json_response=True, stateless_http=True))
        8. (no autouse teardown — each test manages its own session via try/finally)
    """
    from unittest.mock import patch
    from ms_access_mcp.mcp import connection as connection_module
    from ms_access_mcp.mcp import crud as crud_module

    api_key = "test-e2e-api-key-12345"
    allowed_dir = tempfile.gettempdir()

    for key, val in {
        "ACCESS_MCP_API_KEY": api_key,
        "ACCESS_MCP_HOST": "127.0.0.1",
        "ACCESS_MCP_PORT": "8000",
        "ACCESS_MCP_ALLOWED_DIRS": allowed_dir,
    }.items():
        monkeypatch.setenv(key, val)

    # Reset HTTP globals so _init_http_config re-initializes with new env
    server_module._config = None
    server_module._path_guard = None
    server_module._auth_middleware = None

    # Create temp SQLite db
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE __meta (name TEXT)")
    conn.execute("INSERT INTO __meta VALUES ('lifecycle_db')")
    conn.commit()
    conn.close()

    # Create pool with SQLite-backed adapter inside the patch scope
    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        pool = server_module.connection_service.__class__()
        pool.connect("default", db_path, "odbc")

    # Inject pool into server_module, connection_module, AND crud_module namespaces.
    # Each module does 'from .server import connection_service' at module load,
    # creating its own binding that persists unless individually patched.
    monkeypatch.setattr(server_module, "connection_service", pool)
    monkeypatch.setattr(connection_module, "connection_service", pool)
    monkeypatch.setattr(crud_module, "connection_service", pool)

    server_module._init_http_config()

    app = server_module.mcp.http_app(json_response=True, stateless_http=True)
    with TestClient(app) as client:
        yield client