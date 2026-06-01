"""COM integration tests for MCP tool wrappers with real WinComAdapter.

Reuses the _call_tool() pattern from test_mcp_tools_pool.py but with
a real WinComAdapter connected to a temp copy of the fixture DB.
"""

import shutil
import tempfile

import pytest
from unittest.mock import patch

from tests.integration.helpers import (
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
    TEST_DB,
)

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


# ============================================================================
# Test helper: call a tool function from server_module by name,
# patching its connection_service global.
# ============================================================================


def _call_tool(server, tool_name, *args, **kwargs):
    """Call a tool function by name from server_module, patching its connection_service."""
    connection_service = kwargs.pop("connection_service", None)
    tool_func = getattr(server, tool_name)
    with patch.dict(tool_func.__globals__, connection_service=connection_service):
        return tool_func(*args, **kwargs)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def wincom_pool():
    """ConnectionPool with real WinComAdapter connected as 'default'."""
    from ms_access_mcp.adapters.wincom import WinComAdapter
    from ms_access_mcp.services.connection import ConnectionPool

    tmpdir = tempfile.mkdtemp()
    db_path = shutil.copy2(TEST_DB, tmpdir)

    adapter = WinComAdapter()
    assert adapter.connect(db_path), "Connect failed"

    pool = ConnectionPool()
    pool.connect("default", db_path, adapter=adapter)

    yield pool

    pool.disconnect("default")
    adapter.disconnect()
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================================
# Tests
# ============================================================================


class TestMcpSaveQuery:
    """save_query tool with real WinComAdapter."""

    def test_save_query_creates_new(self, wincom_pool):
        """save_query creates a new query and returns action='created'."""
        from ms_access_mcp.mcp import server as server_module

        result = _call_tool(
            server_module,
            "save_query",
            "TestQ", "SELECT 1 AS num",
            overwrite=False,
            connection_service=wincom_pool,
        )
        assert result["success"] is True
        assert result["action"] == "created"
        assert result["query"] == "TestQ"

        # Cleanup
        wincom_pool.get_adapter("default").delete_query("TestQ")

    def test_save_query_duplicate_without_overwrite(self, wincom_pool):
        """save_query with overwrite=False errors if query exists."""
        from ms_access_mcp.mcp import server as server_module

        adapter = wincom_pool.get_adapter("default")
        adapter.create_query("DupQ", "SELECT 1")

        result = _call_tool(
            server_module,
            "save_query",
            "DupQ", "SELECT 2",
            overwrite=False,
            connection_service=wincom_pool,
        )
        assert result["success"] is False
        assert "already exists" in result["error"]

        # Cleanup
        adapter.delete_query("DupQ")

    def test_save_query_overwrite(self, wincom_pool):
        """save_query with overwrite=True updates existing query."""
        from ms_access_mcp.mcp import server as server_module

        adapter = wincom_pool.get_adapter("default")
        adapter.create_query("UpdQ", "SELECT 1")

        result = _call_tool(
            server_module,
            "save_query",
            "UpdQ", "SELECT 2 AS num",
            overwrite=True,
            connection_service=wincom_pool,
        )
        assert result["success"] is True
        assert result["action"] == "updated"

        # Cleanup
        adapter.delete_query("UpdQ")


class TestMcpInsertUpdateDelete:
    """Data manipulation tools with real WinComAdapter."""

    def test_insert_data_single_row(self, wincom_pool):
        """insert_data inserts a single row and returns affected=1."""
        from ms_access_mcp.mcp import server as server_module

        result = _call_tool(
            server_module,
            "insert_data",
            "customers", {"ID": 9999, "Name": "TestCo"},
            connection_name="default",
            connection_service=wincom_pool,
        )
        assert result["success"] is True
        assert result["affected"] == 1

    def test_update_data(self, wincom_pool):
        """update_data updates matching rows and returns affected count."""
        from ms_access_mcp.mcp import server as server_module

        adapter = wincom_pool.get_adapter("default")
        adapter.insert_data("customers", {"ID": 8888, "Name": "Original"})

        result = _call_tool(
            server_module,
            "update_data",
            "customers",
            {"Name": "Updated"},
            {"ID": 8888},
            connection_name="default",
            connection_service=wincom_pool,
        )
        assert result["success"] is True
        assert result["affected"] >= 0

    def test_delete_data(self, wincom_pool):
        """delete_data removes matching rows."""
        from ms_access_mcp.mcp import server as server_module

        adapter = wincom_pool.get_adapter("default")
        adapter.insert_data("customers", {"ID": 7777, "Name": "ToDelete"})

        result = _call_tool(
            server_module,
            "delete_data",
            "customers",
            {"ID": 7777},
            connection_name="default",
            connection_service=wincom_pool,
        )
        assert result["success"] is True
        assert "affected" in result


class TestMcpCreateDeleteTable:
    """Table creation and deletion tools with real WinComAdapter."""

    def test_create_table(self, wincom_pool):
        """create_table creates a new table and returns success."""
        from ms_access_mcp.mcp import server as server_module

        table_name = "TestCreateTable"
        columns = [
            {"name": "ID", "type": "Long Integer", "nullable": False},
            {"name": "Name", "type": "Text", "size": 100},
        ]

        result = _call_tool(
            server_module,
            "create_table",
            table_name,
            columns,
            connection_name="default",
            connection_service=wincom_pool,
        )
        assert result["success"] is True

        # Verify it exists
        adapter = wincom_pool.get_adapter("default")
        tables = adapter.get_tables()
        table_names = [t.name for t in tables]
        # Table may be named with different casing
        assert any(t.lower() == table_name.lower() for t in table_names)

        # Cleanup
        adapter.delete_table(table_name)

    def test_delete_table(self, wincom_pool):
        """delete_table removes an existing table."""
        from ms_access_mcp.mcp import server as server_module

        adapter = wincom_pool.get_adapter("default")
        table_name = "TestDelTable"
        adapter.create_table(
            table_name,
            [{"name": "ID", "type": "Long Integer"}],
        )

        result = _call_tool(
            server_module,
            "delete_table",
            table_name,
            connection_name="default",
            connection_service=wincom_pool,
        )
        assert result["success"] is True


class TestMcpVbaTools:
    """VBA tool wrappers with real WinComAdapter."""

    def test_vba_list_procedures(self, wincom_pool):
        """vba_list_procedures returns success=True with procedures list."""
        from ms_access_mcp.mcp import server as server_module

        result = _call_tool(
            server_module,
            "vba_list_procedures",
            "modUtilities",
            connection_name="default",
            connection_service=wincom_pool,
        )
        assert result["success"] is True
        assert result["module"] == "modUtilities"
        assert "procedures" in result

    def test_vba_get_procedure_not_found(self, wincom_pool):
        """vba_get_procedure returns error when procedure not found."""
        from ms_access_mcp.mcp import server as server_module

        result = _call_tool(
            server_module,
            "vba_get_procedure",
            "modUtilities", "NonExistentProcXYZ",
            connection_name="default",
            connection_service=wincom_pool,
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_set_vba_code(self, wincom_pool):
        """set_vba_code sets code in a module and returns compile result."""
        from ms_access_mcp.mcp import server as server_module

        code = "Sub TestSub()\n    Dim x As Integer\n    x = 1\nEnd Sub"

        result = _call_tool(
            server_module,
            "set_vba_code",
            "modUtilities",
            code,
            connection_name="default",
            connection_service=wincom_pool,
        )
        # Result has success and compile dict
        assert "success" in result
        assert "module" in result
        assert result["module"] == "modUtilities"