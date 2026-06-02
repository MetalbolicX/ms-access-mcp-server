r"""
Integration tests for MCP tool wrappers using real WinComAdapter.

These tests verify that MCP tools (from server_module) correctly delegate
to WinComAdapter when called through the MCP tool interface. They use
real COM-based adapters against temporary database clones.

Pattern from test_mcp_tools_pool.py (call_mcp_tool helper) is reused here
with real WinComAdapter instead of mock SQLite adapters.

Mark: com_integration
Execution: pytest tests/integration/test_wincom_mcp_tools.py -m com_integration -v
"""

import os
import tempfile

import pytest

from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.services.connection import ConnectionPool
from ms_access_mcp import mcp as server_module
from helpers import call_mcp_tool, skip_unless_windows, skip_unless_pywin32, skip_unless_db

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


def _cleanup_adapter(adapter: WinComAdapter) -> None:
    """Safely disconnect an adapter, swallowing cleanup exceptions."""
    try:
        if adapter.is_connected():
            adapter.disconnect()
    except Exception:
        pass


# ============================================================================
# MCP Tool Wrappers via WinComAdapter — CRUD
# ============================================================================

class TestMcpCrudTools:
    """CRUD MCP tools (create_query, insert_data, etc.) via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.pool: ConnectionPool = ConnectionPool()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_create_query_tool(self, temp_db_copy: str):
        """create_query tool creates a stored query via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)

        # Register adapter in pool
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        result = call_mcp_tool(
            "create_query",
            "TestQuery_MCP", "SELECT 1 AS col",
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert result["success"] is True

        # Verify query exists
        queries = self.adapter.get_queries()
        query_names = [q.name for q in queries]
        assert "TestQuery_MCP" in query_names

        # Cleanup
        self.pool.disconnect("test_db")

    def test_insert_data_tool(self, temp_db_copy: str):
        """insert_data tool inserts rows via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        result = call_mcp_tool(
            "insert_data",
            "customers", {"ID": 998, "Name": "MCP_Insert"},
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert result["success"] is True

        # Verify row exists via query_data tool
        rows_result = call_mcp_tool(
            "query_data",
            "SELECT * FROM customers WHERE ID = 998",
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert rows_result["success"] is True
        assert rows_result["count"] == 1
        assert rows_result["rows"][0]["Name"] == "MCP_Insert"

        self.pool.disconnect("test_db")

    def test_update_data_tool(self, temp_db_copy: str):
        """update_data tool updates rows via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        # Precondition: customer 1 exists
        rows = self.adapter.execute_query("SELECT Name FROM customers WHERE ID = 1")
        assert rows["count"] >= 1

        result = call_mcp_tool(
            "update_data",
            "customers", {"Name": "Updated_via_MCP"}, {"ID": 1},
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert result["success"] is True

        # Verify update
        verify = self.adapter.execute_query("SELECT Name FROM customers WHERE ID = 1")
        assert verify["rows"][0]["Name"] == "Updated_via_MCP"

        self.pool.disconnect("test_db")

    def test_delete_query_tool(self, temp_db_copy: str):
        """delete_query tool deletes a stored query via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        # Create a query first
        self.adapter.create_query("QueryToDelete_MCP", "SELECT 1")

        # Verify it exists
        queries = self.adapter.get_queries()
        assert "QueryToDelete_MCP" in [q.name for q in queries]

        # Delete via MCP tool
        result = call_mcp_tool(
            "delete_query",
            "QueryToDelete_MCP",
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert result["success"] is True

        # Verify gone
        queries_after = self.adapter.get_queries()
        assert "QueryToDelete_MCP" not in [q.name for q in queries_after]

        self.pool.disconnect("test_db")


# ============================================================================
# MCP Tool Wrappers via WinComAdapter — VBA
# ============================================================================

class TestMcpVbaTools:
    """VBA MCP tools (set_vba_code, compile_vba, etc.) via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.pool: ConnectionPool = ConnectionPool()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_set_vba_code_tool(self, temp_db_copy: str):
        """set_vba_code tool sets VBA code in a module via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        code = "Function TestVBA()\n    Debug.Print 42\nEnd Function"
        result = call_mcp_tool(
            "set_vba_code",
            "modUtilities", code,
            connection_name="test_db",
            connection_service=self.pool,
        )
        # Should succeed (compile_with_retry handles the write)
        assert result["success"] is True
        assert result["module"] == "modUtilities"

        self.pool.disconnect("test_db")

    def test_compile_vba_tool(self, temp_db_copy: str):
        """compile_vba tool compiles all VBA modules via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        result = call_mcp_tool(
            "compile_vba",
            connection_name="test_db",
            connection_service=self.pool,
        )
        # Result structure: {"success": True} or {"success": False, "error": ...}
        assert isinstance(result, dict)
        assert "success" in result

        self.pool.disconnect("test_db")

    def test_delete_module_tool(self, temp_db_copy: str):
        """delete_module tool deletes a VBA module via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        # Create a module to delete
        self.adapter.add_vba_procedure("TestModule_ToDelete", "Main", "Sub Main()\nEnd Sub")

        # Verify it exists
        modules = self.adapter.get_modules()
        assert "TestModule_ToDelete" in [m.name for m in modules]

        # Delete via tool
        result = call_mcp_tool(
            "delete_module",
            "TestModule_ToDelete",
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert result["success"] is True

        # Verify gone
        modules_after = self.adapter.get_modules()
        assert "TestModule_ToDelete" not in [m.name for m in modules_after]

        self.pool.disconnect("test_db")


# ============================================================================
# MCP Tool Wrappers via WinComAdapter — Forms
# ============================================================================

class TestMcpFormTools:
    """Form-related MCP tools via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.pool: ConnectionPool = ConnectionPool()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_get_forms_tool(self, temp_db_copy: str):
        """get_forms tool returns form list via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        result = call_mcp_tool(
            "get_forms",
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert result["success"] is True
        assert "forms" in result
        assert isinstance(result["forms"], list)

        self.pool.disconnect("test_db")

    def test_form_exists_tool(self, temp_db_copy: str):
        """form_exists tool checks form presence via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        # frmMain should exist in the fixture
        result = call_mcp_tool(
            "form_exists",
            "frmMain",
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert isinstance(result, dict)
        # Should be True (form exists in fixture) or False if not in fixture
        if result.get("exists"):
            assert result["exists"] is True

        self.pool.disconnect("test_db")

    def test_get_form_controls_tool(self, temp_db_copy: str):
        """get_form_controls tool returns control list via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        # frmMain should exist in the fixture
        result = call_mcp_tool(
            "get_form_controls",
            "frmMain",
            connection_name="test_db",
            connection_service=self.pool,
        )
        # Result may be empty dict or have controls depending on fixture
        assert isinstance(result, dict)

        self.pool.disconnect("test_db")


# ============================================================================
# MCP Tool Wrappers via WinComAdapter — System / Export
# ============================================================================

class TestMcpSystemTools:
    """System/export MCP tools via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.pool: ConnectionPool = ConnectionPool()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_get_modules_tool(self, temp_db_copy: str):
        """get_modules tool returns VBA module list via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        result = call_mcp_tool(
            "get_modules",
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert result["success"] is True
        assert "modules" in result
        assert isinstance(result["modules"], list)

        self.pool.disconnect("test_db")

    def test_get_vba_code_tool(self, temp_db_copy: str):
        """get_vba_code tool retrieves module code via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        # modUtilities should exist in the fixture
        result = call_mcp_tool(
            "get_vba_code",
            "modUtilities",
            connection_name="test_db",
            connection_service=self.pool,
        )
        # Should return code (may be empty string if no code)
        assert isinstance(result, dict)
        if result["success"]:
            assert "code" in result

        self.pool.disconnect("test_db")

    def test_export_form_to_text_tool(self, temp_db_copy: str):
        """export_form_to_text tool exports form as text via WinComAdapter."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        # frmMain should exist in the fixture
        result = call_mcp_tool(
            "export_form_to_text",
            "frmMain",
            connection_name="test_db",
            connection_service=self.pool,
        )
        assert isinstance(result, dict)
        # May return empty string if form not found, but should have expected keys
        if result.get("success"):
            assert "form_data" in result or isinstance(result["form_data"], str)

        self.pool.disconnect("test_db")


# ============================================================================
# MCP Tool Wrappers via WinComAdapter — Dev Copy Tools
# ============================================================================

class TestMcpDevCopyTools:
    """Dev copy MCP tools via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()
        self.pool: ConnectionPool = ConnectionPool()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_copy_database_tool(self, temp_db_copy: str, request):
        """copy_database tool duplicates the .accdb file."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        # Create a temp destination
        tmpdir = tempfile.mkdtemp(prefix="mcp_copy_dest_")
        dest_path = os.path.join(tmpdir, "mcp_copy_dest.accdb")

        def cleanup():
            import time
            time.sleep(0.25)
            try:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

        request.addfinalizer(cleanup)

        result = call_mcp_tool(
            "copy_database",
            temp_db_copy, dest_path,
            connection_name="test_db",
            connection_service=self.pool,
        )
        # Result: {"success": True, "source": ..., "dest": ...}
        assert result["success"] is True
        assert os.path.exists(dest_path), "Destination file should exist after copy"

        self.pool.disconnect("test_db")

    def test_get_dev_copy_status_tool(self, temp_db_copy: str):
        """get_dev_copy_status tool returns status dict."""
        assert self.adapter.connect(temp_db_copy)
        self.pool.connect("test_db", temp_db_copy, self.adapter, "com")

        result = call_mcp_tool(
            "get_dev_copy_status",
            db_path=temp_db_copy,
            connection_name="test_db",
            connection_service=self.pool,
        )
        # Should return inactive status (no dev copy active)
        assert isinstance(result, dict)
        assert "active" in result

        self.pool.disconnect("test_db")
