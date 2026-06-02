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
    """Call an MCP tool function by name, patching its connection_service.

    Uses patch.dict on the tool's __globals__ to ensure the connection_service
    binding in each tool module (created at import time via 'from .server import
    connection_service') is correctly replaced for the duration of the call.
    """
    tool_func = getattr(server_module, tool_name)
    with patch.dict(tool_func.__globals__, connection_service=connection_service):
        return tool_func(*args, **kwargs)
