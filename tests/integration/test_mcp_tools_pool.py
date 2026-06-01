"""
Integration tests for MCP tools using ConnectionPool with SQLite-backed adapters.

Validates that MCP tool functions correctly use connection_name to route
to the right adapter in the pool, without requiring Windows or MS Access.
"""

import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.services.connection import ConnectionPool, ConnectionState
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.mcp import server as server_module


# ---- SQLite-backed pyodbc mock (same pattern as test_odbc_adapter_sqlite.py) ---

class _SqliteCursor:
    """Wraps sqlite3 cursor to respond like pyodbc cursor."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self._cursor = db.cursor()
        self.description = None

    def execute(self, sql: str, params: tuple | None = None) -> None:
        try:
            if params:
                self._cursor.execute(sql, params)
            else:
                self._cursor.execute(sql)
            self.description = self._cursor.description
        except Exception as e:
            self._cursor = self.db.cursor()
            raise e

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        pass


class _SqliteConnection:
    """Wraps sqlite3 connection to mimic pyodbc.Connection."""

    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA journal_mode=WAL")

    def cursor(self):
        return _SqliteCursor(self.db)

    def close(self):
        self.db.close()


def _sqlite_pyodbc_connect(conn_str: str, autocommit: bool = False) -> _SqliteConnection:
    """Replace pyodbc.connect with sqlite3-backed connection."""
    for part in conn_str.split(";"):
        if part.upper().startswith("DBQ="):
            db_path = part.split("=", 1)[1].strip()
            return _SqliteConnection(db_path)
    for part in conn_str.split(";"):
        if part.upper().startswith("DATA SOURCE="):
            db_path = part.split("=", 1)[1].strip()
            return _SqliteConnection(db_path)
    raise ValueError(f"Cannot extract DB path from: {conn_str}")


# ---- Fixtures ------------------------------------------------------------------

@pytest.fixture
def sqlite_db():
    """Create a temp SQLite database, clean up after."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE __meta (name TEXT)")
    conn.execute("INSERT INTO __meta VALUES ('prod_db')")
    conn.commit()
    conn.close()
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def pool_with_sqlite(sqlite_db):
    """ConnectionPool with one SQLite-backed OdbcAdapter connected as 'default'."""
    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        pool = ConnectionPool()
        state = pool.connect("default", sqlite_db, "odbc")
        assert state is not None
        yield pool
        pool.disconnect("default")


@pytest.fixture
def pool_with_two_adapters(sqlite_db):
    """ConnectionPool with two named SQLite-backed connections ("prod", "dev")."""
    with patch("pyodbc.connect", _sqlite_pyodbc_connect):
        pool = ConnectionPool()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            dev_db_path = f.name

        conn = sqlite3.connect(dev_db_path)
        conn.execute("CREATE TABLE __meta (name TEXT)")
        conn.execute("INSERT INTO __meta VALUES ('dev_db')")
        conn.commit()
        conn.close()

        pool.connect("prod", sqlite_db, "odbc")
        pool.connect("dev", dev_db_path, "odbc")

        yield pool

        pool.disconnect("prod")
        pool.disconnect("dev")
        if os.path.exists(dev_db_path):
            os.unlink(dev_db_path)


# ============================================================================
# Test helper: access a tool function from server_module by name.
# The tool functions are top-level exports in server.py, and connection_service
# is a global in each tool's __globals__ dict.
# ============================================================================


def _call_tool(server, tool_name, *args, **kwargs):
    """Call a tool function by name from server_module, patching its connection_service."""
    connection_service = kwargs.pop("connection_service", None)
    tool_func = getattr(server, tool_name)
    with patch.dict(tool_func.__globals__, connection_service=connection_service):
        return tool_func(*args, **kwargs)


# ---- Tests ---------------------------------------------------------------------

class TestSaveQueryTool:
    """save_query tool with real SQLite-backed pool and mock adapters."""

    def test_save_query_creates_new_when_no_existing(self, pool_with_sqlite):
        """save_query with overwrite=False creates new query when get_queries returns empty."""
        # Patch get_queries to return empty and create_query to succeed
        adapter = pool_with_sqlite.get_adapter("default")
        adapter.get_queries = MagicMock(return_value=[])
        adapter.create_query = MagicMock(return_value={"success": True})

        result = _call_tool(
            server_module, "save_query",
            "TestQuery", "SELECT 1 AS test",
            overwrite=False,
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is True
        assert result["action"] == "created"
        assert result["query"] == "TestQuery"

    def test_save_query_rejects_existing_without_overwrite(self, pool_with_sqlite):
        """save_query with overwrite=False errors if query exists."""
        adapter = pool_with_sqlite.get_adapter("default")
        mock_query = MagicMock()
        mock_query.name = "DupQuery"
        adapter.get_queries = MagicMock(return_value=[mock_query])

        result = _call_tool(
            server_module, "save_query",
            "DupQuery", "SELECT 2",
            overwrite=False,
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False
        assert "already exists" in result["error"]

    def test_save_query_overwrites_existing(self, pool_with_sqlite):
        """save_query with overwrite=True updates existing query."""
        adapter = pool_with_sqlite.get_adapter("default")
        mock_query = MagicMock()
        mock_query.name = "UpdQuery"
        adapter.get_queries = MagicMock(return_value=[mock_query])
        adapter.set_query_sql = MagicMock(return_value={"success": True})

        result = _call_tool(
            server_module, "save_query",
            "UpdQuery", "SELECT 2 AS num",
            overwrite=True,
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is True
        assert result["action"] == "updated"

    def test_save_query_uses_connection_name(self, pool_with_two_adapters):
        """save_query uses the adapter for the specified connection_name."""
        prod_adapter = pool_with_two_adapters.get_adapter("prod")
        prod_adapter.get_queries = MagicMock(return_value=[])
        prod_adapter.create_query = MagicMock(return_value={"success": True})

        result = _call_tool(
            server_module, "save_query",
            "ProdQuery", "SELECT name FROM __meta",
            overwrite=False, connection_name="prod",
            connection_service=pool_with_two_adapters,
        )
        if not result["success"]:
            print("FAILURE:", result.get("error", "unknown"))
        assert result["success"] is True
        assert result["query"] == "ProdQuery"
        prod_adapter.create_query.assert_called_once_with("ProdQuery", "SELECT name FROM __meta")


class TestVbaListProceduresTool:
    """vba_list_procedures tool with real pool."""

    def test_vba_list_procedures_returns_proper_structure(self, pool_with_sqlite):
        """vba_list_procedures via OdbcAdapter returns None -> tool returns success=True with procedures list."""
        result = _call_tool(
            server_module, "vba_list_procedures",
            "Module1",
            connection_service=pool_with_sqlite,
        )
        # OdbcAdapter.vba_list_procedures returns None, tool treats None as empty list
        assert result["success"] is True
        assert result["module"] == "Module1"
        assert "procedures" in result


class TestVbaGetProcedureTool:
    """vba_get_procedure tool with real pool."""

    def test_vba_get_procedure_returns_not_found(self, pool_with_sqlite):
        """vba_get_procedure returns error via OdbcAdapter when procedure not found."""
        result = _call_tool(
            server_module, "vba_get_procedure",
            "Module1", "NonExistent",
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestVbaReplaceProcedureTool:
    """vba_replace_procedure tool with real pool."""

    def test_vba_replace_procedure_returns_failure(self, pool_with_sqlite):
        """vba_replace_procedure returns error via OdbcAdapter when not WinCom."""
        result = _call_tool(
            server_module, "vba_replace_procedure",
            "Module1", "Proc1", "Sub Proc1()\nEnd Sub",
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False


class TestListConnectionsTool:
    """list_connections from connection.py MCP tool."""

    def test_list_connections_returns_correct_structure(self, pool_with_sqlite, sqlite_db):
        """list_connections returns database/adapter_type for each connection."""
        result = _call_tool(
            server_module, "list_connections",
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is True
        assert "default" in result["connections"]
        conn_info = result["connections"]["default"]
        assert "database" in conn_info
        assert conn_info["database"] == sqlite_db
        assert "adapter_type" in conn_info
        assert conn_info["adapter_type"] == "odbc"

    def test_list_connections_with_multiple(self, pool_with_two_adapters):
        """list_connections returns all named connections."""
        result = _call_tool(
            server_module, "list_connections",
            connection_service=pool_with_two_adapters,
        )
        assert result["success"] is True
        assert "prod" in result["connections"]
        assert "dev" in result["connections"]


class TestGetSystemTablesTool:
    """get_system_tables with real pool."""

    def test_get_system_tables_returns_list(self, pool_with_sqlite):
        """get_system_tables via OdbcAdapter returns a list result."""
        result = _call_tool(
            server_module, "get_system_tables",
            connection_name="default",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "system_tables" in result
        assert isinstance(result["system_tables"], list)


class TestDiagnoseEnvironmentTool:
    """diagnose_environment tool with real pool."""

    def test_diagnose_environment_returns_info(self, pool_with_sqlite):
        """diagnose_environment returns diagnostic info dict."""
        result = _call_tool(
            server_module, "diagnose_environment",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "diagnostics" in result
        assert "platform" in result["diagnostics"]


class TestRecoverAccessTool:
    """recover_access tool with real pool."""

    def test_recover_access_not_supported_on_linux(self, pool_with_sqlite):
        """recover_access returns success=False on non-Windows."""
        result = _call_tool(
            server_module, "recover_access",
            connection_service=pool_with_sqlite,
        )
        assert result["success"] is False
        assert "Not supported" in result["error"]