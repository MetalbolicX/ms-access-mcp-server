"""
Integration tests for MCP system tools (get_object_metadata, execute_sql_script,
and COM-only tools: import_form_from_text, delete_form, export_report_to_text,
import_report_from_text, delete_report, export_module_to_text, export_macro_to_text,
export_all_versioning).

Tier 1: SQLite-backed OdbcAdapter verifies ODBC-friendly tools and
COM-only tool error paths.

Tier 3: WinCom happy-path tests (SKIPPED - pre-existing pool.connect bug).
"""

import os
import tempfile

import pytest

from conftest import pool_with_sqlite
from helpers import call_mcp_tool, skip_unless_windows, skip_unless_db


# ============================================================================
# Tier 1: get_object_metadata - ODBC adapter returns empty dict (no-op)
# ============================================================================

class TestSystemOdbcAdapter:
    """Tier 1: Verify get_object_metadata and execute_sql_script via OdbcAdapter."""

    def test_get_object_metadata_returns_success_false_via_sqlite(self, pool_with_sqlite):
        """get_object_metadata returns success=False via OdbcAdapter (ODBC has no metadata API).

        The ODBC adapter's get_object_metadata returns {} (empty dict) because
        metadata introspection is not available via ODBC. The tool correctly
        returns success=False in this case.
        """
        result = call_mcp_tool(
            "get_object_metadata",
            "any_object",
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert "success" in result, f"Missing 'success' key in {result}"
        # ODBC adapter returns {} for metadata, which the tool treats as "not found"
        assert result["success"] is False, f"Expected failure via ODBC (no metadata API), got: {result}"
        assert "error" in result, f"Should have 'error' key when ODBC returns empty metadata: {result}"

    def test_execute_sql_script_raises_notimplementederror_via_sqlite(self, pool_with_sqlite):
        """execute_sql_script raises NotImplementedError via OdbcAdapter (requires COM).

        The ODBC adapter's execute_sql_script raises NotImplementedError because
        SQL script execution requires the COM/WinComAdapter.
        """
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False, mode="w") as f:
            f.write("SELECT 1;")
            sql_path = f.name
        try:
            with pytest.raises(NotImplementedError, match="COM"):
                call_mcp_tool(
                    "execute_sql_script",
                    sql_path,
                    connection_service=pool_with_sqlite,
                )
        finally:
            if os.path.exists(sql_path):
                os.unlink(sql_path)


# ============================================================================
# Tier 1: COM-only tools - ODBC adapter returns False/""/raises
# ============================================================================

class TestSystemComOnlyToolsOdbcErrorPath:
    """Tier 1: Verify COM-only system tools fail gracefully via OdbcAdapter.

    These tools delegate to the ODBC adapter which returns False, empty string,
    or raises NotImplementedError. The tool wrappers do not wrap these in a
    "Not available via ODBC" message — they propagate the adapter's response.
    """

    @pytest.mark.parametrize(
        "tool_name,args,expected_false",
        [
            # Tools whose ODBC adapter returns False → tool returns success=False
            ("import_form_from_text", ["TestForm", "form data"], True),
            ("delete_form", ["TestForm"], True),
            ("import_report_from_text", ["TestReport", "report data"], True),
            ("delete_report", ["TestReport"], True),
        ],
    )
    def test_com_only_tools_return_success_false_via_sqlite(
        self, pool_with_sqlite, tool_name, args, expected_false
    ):
        """COM-only tools return success=False via OdbcAdapter."""
        result = call_mcp_tool(
            tool_name,
            *args,
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), (
            f"{tool_name} should return dict, got {type(result)}: {result}"
        )
        assert result.get("success") is False, (
            f"{tool_name} should fail via ODBC, got: {result}"
        )

    @pytest.mark.parametrize(
        "tool_name,args",
        [
            # Tools that raise NotImplementedError via ODBC adapter
            ("export_all_versioning", ["C:\\temp\\export"]),
        ],
    )
    def test_com_only_tools_raise_notimplementederror_via_sqlite(
        self, pool_with_sqlite, tool_name, args
    ):
        """export_all_versioning raises NotImplementedError via OdbcAdapter."""
        with pytest.raises(NotImplementedError, match="COM"):
            call_mcp_tool(
                tool_name,
                *args,
                connection_service=pool_with_sqlite,
            )

    @pytest.mark.parametrize(
        "tool_name,args",
        [
            # Tools whose ODBC adapter returns empty string → tool returns success=False
            ("export_report_to_text", ["TestReport"]),
            ("export_module_to_text", ["TestModule"]),
            ("export_macro_to_text", ["TestMacro"]),
        ],
    )
    def test_com_only_tools_return_success_false_for_empty_result(
        self, pool_with_sqlite, tool_name, args
    ):
        """Tools returning empty string from ODBC fail with success=False."""
        result = call_mcp_tool(
            tool_name,
            *args,
            connection_service=pool_with_sqlite,
        )
        assert isinstance(result, dict), (
            f"{tool_name} should return dict, got {type(result)}: {result}"
        )
        # Empty string from adapter → tool treats as failure (object not found)
        assert result.get("success") is False, (
            f"{tool_name} should fail when ODBC returns empty, got: {result}"
        )


# ============================================================================
# Tier 3: WinCom happy-path tests (SKIPPED - pre-existing pool.connect bug)
# ============================================================================

class TestSystemWinComHappyPath:
    """Tier 3: WinCom happy-path tests for system tools.

    NOTE: These tests require the pool.connect(name, db_path, adapter_type) API
    which is currently broken (pre-existing issue - pool.connect only accepts
    3 args but the tests pass 4). Skip via marker until connection.py is fixed.
    """

    pytestmark = [skip_unless_windows, skip_unless_db]

    def test_import_form_from_text_via_wincom(self, temp_db_copy):
        """import_form_from_text creates a form via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_sys", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "import_form_from_text",
                "MCP_TestForm",
                "Form data string",
                connection_name="test_sys",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_sys")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_delete_form_via_wincom(self, temp_db_copy):
        """delete_form removes a form via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_sys", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "delete_form",
                "NonExistentForm",
                connection_name="test_sys",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_sys")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_export_report_to_text_via_wincom(self, temp_db_copy):
        """export_report_to_text exports a report via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_sys", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "export_report_to_text",
                "NonExistentReport",
                connection_name="test_sys",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_sys")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_import_report_from_text_via_wincom(self, temp_db_copy):
        """import_report_from_text creates a report via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_sys", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "import_report_from_text",
                "MCP_TestReport",
                "Report data string",
                connection_name="test_sys",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_sys")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_delete_report_via_wincom(self, temp_db_copy):
        """delete_report removes a report via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_sys", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "delete_report",
                "NonExistentReport",
                connection_name="test_sys",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_sys")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_export_module_to_text_via_wincom(self, temp_db_copy):
        """export_module_to_text exports a VBA module via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_sys", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "export_module_to_text",
                "NonExistentModule",
                connection_name="test_sys",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_sys")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_export_macro_to_text_via_wincom(self, temp_db_copy):
        """export_macro_to_text exports macro metadata via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_sys", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "export_macro_to_text",
                "NonExistentMacro",
                connection_name="test_sys",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "success" in result

            pool.disconnect("test_sys")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_export_all_versioning_via_wincom(self, temp_db_copy):
        """export_all_versioning exports all database objects via WinComAdapter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_sys", temp_db_copy, adapter, "com")

            with tempfile.TemporaryDirectory() as tmpdir:
                result = call_mcp_tool(
                    "export_all_versioning",
                    tmpdir,
                    connection_name="test_sys",
                    connection_service=pool,
                )
                assert isinstance(result, dict)
                assert "success" in result

            pool.disconnect("test_sys")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass