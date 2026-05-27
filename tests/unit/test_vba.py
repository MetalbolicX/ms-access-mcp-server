"""Tests for mcp/vba.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


class TestVbaConnectionGuards:
    """Tests that VBA tools check connection before executing."""

    def _guard_cases(self):
        """Return list of (tool_name, tool_func, args) for tools that guard connection."""
        return [
            ("set_vba_code", server.set_vba_code, ("modTest", "Sub Test()\nEnd Sub")),
            ("add_vba_procedure", server.add_vba_procedure, ("modTest", "Test", "Sub Test()\nEnd Sub")),
            ("compile_vba", server.compile_vba, ()),
            ("save_database", server.save_database, ()),
            ("delete_module", server.delete_module, ("modTest",)),
        ]

    @pytest.mark.parametrize("tool_name,tool_func,args", [
        ("set_vba_code", server.set_vba_code, ("modTest", "Sub Test()\nEnd Sub")),
        ("add_vba_procedure", server.add_vba_procedure, ("modTest", "Test", "Sub Test()\nEnd Sub")),
        ("compile_vba", server.compile_vba, ()),
        ("save_database", server.save_database, ()),
        ("delete_module", server.delete_module, ("modTest",)),
    ])
    def test_vba_tools_return_error_when_not_connected(self, tool_name, tool_func, args):
        """Each VBA tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(tool_func.__globals__, connection_service=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestGetVbaProjects:
    """Tests for get_vba_projects tool."""

    def test_get_vba_projects_returns_empty_when_no_project(self):
        """get_vba_projects should return empty list when no project found."""
        mock_schema = MagicMock()
        mock_schema.get_vba_project_name.return_value = ""
        with patch.dict(server.get_vba_projects.__globals__, schema_service=mock_schema):
            result = server.get_vba_projects()
            assert result["success"] is True
            assert result["projects"] == []
            assert result["count"] == 0

    def test_get_vba_projects_returns_project_name(self):
        """get_vba_projects should return project name when found."""
        mock_schema = MagicMock()
        mock_schema.get_vba_project_name.return_value = "MyProject"
        with patch.dict(server.get_vba_projects.__globals__, schema_service=mock_schema):
            result = server.get_vba_projects()
            assert result["success"] is True
            assert result["projects"] == ["MyProject"]
            assert result["count"] == 1


class TestGetVbaCode:
    """Tests for get_vba_code tool."""

    def test_get_vba_code_returns_error_for_empty_module(self):
        """get_vba_code should return error when module not found or empty."""
        mock_schema = MagicMock()
        mock_schema.get_vba_code.return_value = ""
        with patch.dict(server.get_vba_code.__globals__, schema_service=mock_schema):
            result = server.get_vba_code("NonExistentModule")
            assert result["success"] is False
            assert "not found" in result["error"].lower()

    def test_get_vba_code_returns_code_on_success(self):
        """get_vba_code should return code when module exists."""
        mock_schema = MagicMock()
        mock_schema.get_vba_code.return_value = "Sub Test()\nEnd Sub"
        with patch.dict(server.get_vba_code.__globals__, schema_service=mock_schema):
            result = server.get_vba_code("modTest")
            assert result["success"] is True
            assert result["module"] == "modTest"
            assert "Sub Test()" in result["code"]


class TestSetVbaCode:
    """Tests for set_vba_code tool."""

    def test_set_vba_code_compiles_with_retry(self):
        """set_vba_code should delegate to dev_copy_service.compile_with_retry."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_dev_copy = MagicMock()
        mock_dev_copy.compile_with_retry.return_value = {"success": True, "module": "modTest"}
        with patch.dict(server.set_vba_code.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev_copy):
            result = server.set_vba_code("modTest", "Sub Test()\nEnd Sub")
            assert result["success"] is True
            mock_dev_copy.compile_with_retry.assert_called_once()


class TestAddVbaProcedure:
    """Tests for add_vba_procedure tool."""

    def test_add_vba_procedure_returns_failure_when_write_fails(self):
        """add_vba_procedure should return failure when adapter.write fails."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.add_vba_procedure.return_value = False
        mock_dev_copy = MagicMock()
        mock_dev_copy.compile_with_retry.return_value = {"success": False}
        with patch.dict(server.add_vba_procedure.__globals__, connection_service=mock_conn, dev_copy_service=mock_dev_copy):
            result = server.add_vba_procedure("modTest", "Test", "Sub Test()\nEnd Sub")
            assert result["success"] is False


class TestDeleteModule:
    """Tests for delete_module tool."""

    def test_delete_module_returns_result(self):
        """delete_module should return result of deletion."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.delete_module.return_value = True
        with patch.dict(server.delete_module.__globals__, connection_service=mock_conn):
            result = server.delete_module("modTest")
            assert result["success"] is True
            assert result["module"] == "modTest"

    def test_delete_module_wraps_exception(self):
        """delete_module should wrap exceptions in error response."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.delete_module.side_effect = RuntimeError("Module in use")
        with patch.dict(server.delete_module.__globals__, connection_service=mock_conn):
            result = server.delete_module("modTest")
            assert result["success"] is False
            assert "Module in use" in result["error"]
