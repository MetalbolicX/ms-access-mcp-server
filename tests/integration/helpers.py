"""Shared helpers for integration tests — constants, platform checks, and skip conditions."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ms_access_mcp.mcp import server as server_module

# ---- Database path resolution ------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REPO_FIXTURE_DB = FIXTURE_DIR / "test_db.accdb"

_raw = os.environ.get("ACCESS_TEST_DB")
if _raw:
    TEST_DB = _raw.strip('"').strip("'")
elif REPO_FIXTURE_DB.exists():
    TEST_DB = str(REPO_FIXTURE_DB)
else:
    TEST_DB = ""

# ---- Platform checks ---------------------------------------------------------

IS_WINDOWS = os.name == "nt"


def has_pywin32() -> bool:
    try:
        import win32com  # noqa: F401
        import pythoncom  # noqa: F401
        return True
    except ImportError:
        return False


def has_odbc_driver() -> bool:
    try:
        import pyodbc
        access_keywords = ["access", "mdb", "ace", "mdbtools", "mdbodbc"]
        return any(any(kw in d.lower() for kw in access_keywords) for d in pyodbc.drivers())
    except ImportError:
        return False


def has_db_file() -> bool:
    return bool(TEST_DB) and Path(TEST_DB).exists()


# ---- Pytest skip conditions --------------------------------------------------

skip_unless_windows = pytest.mark.skipif(
    not IS_WINDOWS,
    reason="Windows-only test (requires MS Access COM automation)",
)

skip_unless_pywin32 = pytest.mark.skipif(
    not has_pywin32(),
    reason="Requires pywin32 (Win32COM)",
)

skip_unless_db = pytest.mark.skipif(
    not has_db_file(),
    reason=(
        f"Test database not found. "
        f"Set ACCESS_TEST_DB env var or place a .accdb file at {REPO_FIXTURE_DB}"
    ),
)

skip_unless_odbc_driver = pytest.mark.skipif(
    not has_odbc_driver(),
    reason=(
        "No ODBC driver for MS Access found. "
        "Install: mdbtools + unixodbc (Linux) or Microsoft Access Database Engine (Windows)"
    ),
)


# ---- Shared test helper --------------------------------------------------------

def call_mcp_tool(tool_name: str, *args, connection_service=None, **kwargs):
    """Call an MCP tool function by name, routing it to the given connection_service.

    Patches get_container in each tool module's namespace so that all lazy
    _pool() accesses resolve to the provided connection_service.
    """
    from ms_access_mcp.mcp.container import ServiceContainer
    tool_func = getattr(server_module, tool_name)

    if connection_service is not None:
        mock_container = ServiceContainer(
            connection_pool=connection_service,
            com_automation=None,
            migration=None,
            dev_copy=None,
            connector_registry=None,
        )
        tool_module_name = tool_func.__module__
        # Map tool module name to the actual module object
        module_map = {
            "ms_access_mcp.mcp.crud": getattr(server_module, "crud", None),
            "ms_access_mcp.mcp.schema": getattr(server_module, "schema", None),
            "ms_access_mcp.mcp.connection": getattr(server_module, "connection", None),
            "ms_access_mcp.mcp.vba": getattr(server_module, "vba", None),
            "ms_access_mcp.mcp.linked_tables": getattr(server_module, "linked_tables", None),
            "ms_access_mcp.mcp.export": getattr(server_module, "export", None),
            "ms_access_mcp.mcp.recovery": getattr(server_module, "recovery", None),
            "ms_access_mcp.mcp.system": getattr(server_module, "system", None),
            "ms_access_mcp.mcp.persistence": getattr(server_module, "persistence", None),
            "ms_access_mcp.mcp.com": getattr(server_module, "com", None),
            "ms_access_mcp.mcp.migration": getattr(server_module, "migration", None),
        }
        target_module = module_map.get(tool_module_name)
        if target_module is not None and hasattr(target_module, "get_container"):
            with patch.object(target_module, "get_container", return_value=mock_container):
                return tool_func(*args, **kwargs)
        else:
            # Fallback: patch the global get_container in container module
            with patch("ms_access_mcp.mcp.container.get_container", return_value=mock_container):
                return tool_func(*args, **kwargs)
    else:
        return tool_func(*args, **kwargs)
