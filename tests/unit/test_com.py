"""Tests for mcp/com.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


class TestComToolsConnectionGuards:
    """Tests that COM tools check connection state before executing."""

    @pytest.mark.parametrize("tool_func,args", [
        (server.open_form, ("TestForm",)),
        (server.close_form, ("TestForm",)),
        (server.form_exists, ("TestForm",)),
        (server.get_form_controls, ("TestForm",)),
        (server.get_control_properties, ("TestForm", "txtName")),
        (server.set_control_property, ("TestForm", "txtName", "BackColor", "16777215")),
        (server.set_control_properties, ("TestForm", "txtName", {"BackColor": "16777215"})),
        (server.get_control_event_procedures, ("TestForm", "txtName")),
        (server.get_control_event_procedures, ("TestForm",)),  # empty control_name = all events
    ])
    def test_com_tools_return_error_when_not_connected(self, tool_func, args):
        """Each COM tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.dict(tool_func.__globals__, connection_service=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestLaunchAccess:
    """Tests for launch_access tool."""

    def test_launch_access_delegates_to_com_service(self):
        """launch_access should delegate to com_automation_service.launch_access."""
        mock_com = MagicMock()
        mock_com.launch_access.return_value = True
        mock_com.is_access_running.return_value = True
        with patch.dict(server.launch_access.__globals__, com_automation_service=mock_com):
            result = server.launch_access(visible=True)
            assert result["success"] is True
            assert result["access_running"] is True
            mock_com.launch_access.assert_called_once()


class TestCloseAccess:
    """Tests for close_access tool."""

    def test_close_access_delegates_to_com_service(self):
        """close_access should delegate to com_automation_service.close_access."""
        mock_com = MagicMock()
        mock_com.close_access.return_value = True
        mock_com.is_access_running.return_value = False
        with patch.dict(server.close_access.__globals__, com_automation_service=mock_com):
            result = server.close_access()
            assert result["success"] is True
            assert result["access_running"] is False


class TestFormDiscoveryTools:
    """Tests for form discovery tools (get_forms, get_reports, get_macros, get_modules)."""

    def test_get_forms_returns_form_dump(self):
        """get_forms should return success with form list."""
        mock_form = MagicMock()
        mock_form.model_dump.return_value = {"name": "TestForm"}
        mock_schema = MagicMock()
        mock_schema.get_forms.return_value = [mock_form]
        with patch.dict(server.get_forms.__globals__, schema_service=mock_schema):
            result = server.get_forms()
            assert result["success"] is True
            assert result["count"] == 1
            assert result["forms"][0]["name"] == "TestForm"

    def test_get_reports_returns_report_dump(self):
        """get_reports should return success with report list."""
        mock_report = MagicMock()
        mock_report.model_dump.return_value = {"name": "TestReport"}
        mock_schema = MagicMock()
        mock_schema.get_reports.return_value = [mock_report]
        with patch.dict(server.get_reports.__globals__, schema_service=mock_schema):
            result = server.get_reports()
            assert result["success"] is True
            assert result["count"] == 1

    def test_get_macros_returns_macro_dump(self):
        """get_macros should return success with macro list."""
        mock_macro = MagicMock()
        mock_macro.model_dump.return_value = {"name": "TestMacro"}
        mock_schema = MagicMock()
        mock_schema.get_macros.return_value = [mock_macro]
        with patch.dict(server.get_macros.__globals__, schema_service=mock_schema):
            result = server.get_macros()
            assert result["success"] is True
            assert result["count"] == 1

    def test_get_modules_returns_module_dump(self):
        """get_modules should return success with module list."""
        mock_module = MagicMock()
        mock_module.model_dump.return_value = {"name": "modTest"}
        mock_schema = MagicMock()
        mock_schema.get_modules.return_value = [mock_module]
        with patch.dict(server.get_modules.__globals__, schema_service=mock_schema):
            result = server.get_modules()
            assert result["success"] is True
            assert result["count"] == 1


class TestControlTools:
    """Tests for form control tools."""

    def test_open_form_returns_message(self):
        """open_form should return result with form name and message."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.open_form.return_value = True
        with patch.dict(server.open_form.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.open_form("TestForm")
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert "opened" in result["message"].lower()

    def test_get_control_properties_returns_error_when_not_found(self):
        """get_control_properties should return error when control not found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_control_properties.return_value = {}
        with patch.dict(server.get_control_properties.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.get_control_properties("TestForm", "NonExistent")
            assert result["success"] is False
            assert "not found" in result["error"].lower()

    def test_get_control_properties_returns_props_on_success(self):
        """get_control_properties should return properties when control found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_control_properties.return_value = {"Name":"txtName","BackColor":16777215}
        with patch.dict(server.get_control_properties.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.get_control_properties("TestForm", "txtName")
            assert result["success"] is True
            assert result["control"] == "txtName"
            assert "BackColor" in result["properties"]

    def test_set_control_property_returns_result(self):
        """set_control_property should return success/failure based on result."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_control_property.return_value = True
        with patch.dict(server.set_control_property.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.set_control_property("TestForm", "txtName", "BackColor", "16777215")
            assert result["success"] is True
            assert result["property"] == "BackColor"

    def test_form_exists_returns_exists_flag(self):
        """form_exists should return exists flag."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_schema = MagicMock()
        mock_schema.form_exists.return_value = True
        with patch.dict(server.form_exists.__globals__, connection_service=mock_conn, schema_service=mock_schema):
            result = server.form_exists("TestForm")
            assert result["success"] is True
            assert result["exists"] is True


class TestSetControlProperties:
    """Tests for set_control_properties tool."""

    def test_set_control_properties_returns_results(self):
        """set_control_properties should return per-property success dict."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_control_properties.return_value = {"Visible": True, "Width": False}
        with patch.dict(server.set_control_properties.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.set_control_properties("TestForm", "txtName", {"Visible": "True", "Width": "200"})
            assert result["success"] is True
            assert "properties" in result
            assert result["properties"]["Visible"] is True

    def test_set_control_properties_empty_result_returns_error(self):
        """set_control_properties should return error when control not found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_control_properties.return_value = {}
        with patch.dict(server.set_control_properties.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.set_control_properties("TestForm", "NonExistent", {"Width": "200"})
            assert result["success"] is False
            assert "not found" in result["error"].lower()


class TestGetControlEventProcedures:
    """Tests for get_control_event_procedures tool."""

    def test_get_control_event_procedures_all_events(self):
        """get_control_event_procedures should return all events when control_name is empty."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_control_event_procedures.return_value = [
            {"procedure_name": "cmdSave_Click", "event_name": "Click", "code": "Sub cmdSave_Click()\nEnd Sub", "start_line": 1},
            {"procedure_name": "cmdSave_Enter", "event_name": "Enter", "code": "Sub cmdSave_Enter()\nEnd Sub", "start_line": 7},
        ]
        with patch.dict(server.get_control_event_procedures.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.get_control_event_procedures("TestForm", "")
            assert result["success"] is True
            assert result["count"] == 2
            assert result["control"] == "(all)"

    def test_get_control_event_procedures_filtered(self):
        """get_control_event_procedures should filter by control_name."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_control_event_procedures.return_value = [
            {"procedure_name": "cmdSave_Click", "event_name": "Click", "code": "Sub cmdSave_Click()\nEnd Sub", "start_line": 1},
        ]
        with patch.dict(server.get_control_event_procedures.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.get_control_event_procedures("TestForm", "cmdSave")
            assert result["success"] is True
            assert result["control"] == "cmdSave"
            assert result["count"] == 1

    def test_get_control_event_procedures_form_module_not_found(self):
        """get_control_event_procedures should return error when form module not found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_control_event_procedures.return_value = None
        with patch.dict(server.get_control_event_procedures.__globals__, connection_service=mock_conn, com_automation_service=mock_com):
            result = server.get_control_event_procedures("NonExistentForm", "")
            assert result["success"] is False
            assert "not found" in result["error"].lower()
