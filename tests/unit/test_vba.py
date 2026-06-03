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
        ("vba_list_procedures", server.vba_list_procedures, ("modTest",)),
        ("vba_get_procedure", server.vba_get_procedure, ("modTest", "ProcName")),
        ("vba_replace_procedure", server.vba_replace_procedure, ("modTest", "ProcName", "Sub ProcName()\nEnd Sub")),
        ("save_query", server.save_query, ("QueryName", "SELECT 1")),
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
        mock_adapter = MagicMock()
        mock_adapter.get_vba_project_name.return_value = ""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.dict(server.get_vba_projects.__globals__, connection_service=mock_conn):
            result = server.get_vba_projects()
            assert result["success"] is True
            assert result["projects"] == []
            assert result["count"] == 0

    def test_get_vba_projects_returns_project_name(self):
        """get_vba_projects should return project name when found."""
        mock_adapter = MagicMock()
        mock_adapter.get_vba_project_name.return_value = "MyProject"
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.dict(server.get_vba_projects.__globals__, connection_service=mock_conn):
            result = server.get_vba_projects()
            assert result["success"] is True
            assert result["projects"] == ["MyProject"]
            assert result["count"] == 1


class TestGetVbaCode:
    """Tests for get_vba_code tool."""

    def test_get_vba_code_returns_error_for_empty_module(self):
        """get_vba_code should return error when module not found or empty."""
        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = ""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.dict(server.get_vba_code.__globals__, connection_service=mock_conn):
            result = server.get_vba_code("NonExistentModule")
            assert result["success"] is False
            assert "not found" in result["error"].lower()

    def test_get_vba_code_returns_code_on_success(self):
        """get_vba_code should return code when module exists."""
        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = "Sub Test()\nEnd Sub"
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.dict(server.get_vba_code.__globals__, connection_service=mock_conn):
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
        mock_conn.get_adapter.return_value = mock_conn.adapter
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
        mock_conn.get_adapter.return_value = mock_conn.adapter
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
        mock_conn.get_adapter.return_value = mock_conn.adapter
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
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.delete_module.__globals__, connection_service=mock_conn):
            result = server.delete_module("modTest")
            assert result["success"] is False
            assert "Module in use" in result["error"]


class TestVbaListProcedures:
    """Tests for vba_list_procedures tool."""

    def test_vba_list_procedures_returns_empty_list(self):
        """vba_list_procedures should return empty list for empty module."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.vba_list_procedures.return_value = []
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.vba_list_procedures.__globals__, connection_service=mock_conn):
            result = server.vba_list_procedures("Module1")
            assert result["success"] is True
            assert result["procedures"] == []

    def test_vba_list_procedures_returns_procedures(self):
        """vba_list_procedures should return procedure list."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.vba_list_procedures.return_value = [
            {"name": "Init", "type": "Sub", "start_line": 1, "line_count": 10},
            {"name": "Validate", "type": "Function", "start_line": 12, "line_count": 25},
        ]
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.vba_list_procedures.__globals__, connection_service=mock_conn):
            result = server.vba_list_procedures("Module1")
            assert result["success"] is True
            assert len(result["procedures"]) == 2
            assert result["procedures"][0]["name"] == "Init"


class TestVbaGetProcedure:
    """Tests for vba_get_procedure tool."""

    def test_vba_get_procedure_returns_procedure(self):
        """vba_get_procedure should return procedure code."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.vba_get_procedure.return_value = {
            "name": "Init",
            "type": "Sub",
            "code": "Sub Init()\nMsgBox \"hi\"\nEnd Sub",
            "signature": "Sub Init()",
        }
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.vba_get_procedure.__globals__, connection_service=mock_conn):
            result = server.vba_get_procedure("Module1", "Init")
            assert result["success"] is True
            assert result["name"] == "Init"
            assert result["type"] == "Sub"
            assert "MsgBox" in result["code"]

    def test_vba_get_procedure_returns_error_when_not_found(self):
        """vba_get_procedure should return error when procedure not found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.vba_get_procedure.return_value = {}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.vba_get_procedure.__globals__, connection_service=mock_conn):
            result = server.vba_get_procedure("Module1", "NonExistent")
            assert result["success"] is False
            assert "not found" in result["error"].lower()


class TestVbaReplaceProcedure:
    """Tests for vba_replace_procedure tool."""

    def test_vba_replace_procedure_success(self):
        """vba_replace_procedure should return success on successful replacement."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.vba_replace_procedure.return_value = True
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.vba_replace_procedure.__globals__, connection_service=mock_conn):
            result = server.vba_replace_procedure("Module1", "Init", "Sub Init()\nMsgBox \"new\"\nEnd Sub")
            assert result["success"] is True
            assert result["procedure"] == "Init"

    def test_vba_replace_procedure_failure(self):
        """vba_replace_procedure should return error on failure."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.vba_replace_procedure.return_value = False
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.vba_replace_procedure.__globals__, connection_service=mock_conn):
            result = server.vba_replace_procedure("Module1", "NonExistent", "Sub Foo()\nEnd Sub")
            assert result["success"] is False
            assert "Failed to replace" in result["error"]


class TestSaveQuery:
    """Tests for save_query tool."""

    def test_save_query_creates_new_query(self):
        """save_query should create a new query when overwrite=False and name is unique."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.get_queries.return_value = []
        mock_conn.adapter.create_query.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.save_query.__globals__, connection_service=mock_conn):
            result = server.save_query("MyQuery", "SELECT * FROM Users")
            assert result["success"] is True
            assert result["action"] == "created"
            assert result["query"] == "MyQuery"

    def test_save_query_returns_error_if_exists_no_overwrite(self):
        """save_query should return error if query exists and overwrite=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_query = MagicMock()
        mock_query.name = "MyQuery"
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.get_queries.return_value = [mock_query]
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.save_query.__globals__, connection_service=mock_conn):
            result = server.save_query("MyQuery", "SELECT * FROM Users", overwrite=False)
            assert result["success"] is False
            assert "already exists" in result["error"]

    def test_save_query_updates_existing_with_overwrite(self):
        """save_query should update existing query when overwrite=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_query = MagicMock()
        mock_query.name = "MyQuery"
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.get_queries.return_value = [mock_query]
        mock_conn.adapter.set_query_sql.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.save_query.__globals__, connection_service=mock_conn):
            result = server.save_query("MyQuery", "SELECT * FROM NewTable", overwrite=True)
            assert result["success"] is True
            assert result["action"] == "updated"

    def test_save_query_creates_if_not_exists_with_overwrite(self):
        """save_query should create query if it doesn't exist even with overwrite=True."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.get_queries.return_value = []
        mock_conn.adapter.create_query.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.dict(server.save_query.__globals__, connection_service=mock_conn):
            result = server.save_query("NewQuery", "SELECT 1", overwrite=True)
            assert result["success"] is True
            assert result["action"] == "created"
