"""Tests for mcp/com.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import com as com_module


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
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_set_control_event_procedure_returns_error_when_not_connected(self):
        """set_control_event_procedure should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_event_procedure("TestForm", "btnSave", "Click", "code")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestLaunchAccess:
    """Tests for launch_access tool."""

    def test_launch_access_delegates_to_adapter(self):
        """launch_access should delegate to adapter.launch_access."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.launch_access.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.launch_access(visible=True)
            assert result["success"] is True
            assert result["access_running"] is True
            mock_adapter.launch_access.assert_called_once_with(True)


class TestCloseAccess:
    """Tests for close_access tool."""

    def test_close_access_delegates_to_adapter(self):
        """close_access should delegate to adapter.close_access."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.close_access.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.close_access()
            assert result["success"] is True
            assert result["access_running"] is False
            mock_adapter.close_access.assert_called_once()


class TestFormDiscoveryTools:
    """Tests for form discovery tools (get_forms, get_modules). get_macros moved to test_macros.py."""

    def test_get_forms_returns_form_dump(self):
        """get_forms should return success with form list."""
        mock_form = MagicMock()
        mock_form.model_dump.return_value = {"name": "TestForm"}
        mock_adapter = MagicMock()
        mock_adapter.get_forms.return_value = [mock_form]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_forms()
            assert result["success"] is True
            assert result["count"] == 1
            assert result["forms"][0]["name"] == "TestForm"

    def test_get_modules_returns_module_dump(self):
        """get_modules should return success with module list."""
        mock_module = MagicMock()
        mock_module.model_dump.return_value = {"name": "modTest"}
        mock_adapter = MagicMock()
        mock_adapter.get_modules.return_value = [mock_module]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_modules()
            assert result["success"] is True
            assert result["count"] == 1


class TestControlTools:
    """Tests for form control tools."""

    def test_open_form_returns_message(self):
        """open_form should return result with form name and message."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.open_form.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.open_form("TestForm")
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert "opened" in result["message"].lower()

    def test_get_control_properties_returns_error_when_not_found(self):
        """get_control_properties should return error when control not found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_control_properties.return_value = {}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_control_properties("TestForm", "NonExistent")
            assert result["success"] is False
            assert "not found" in result["error"].lower()

    def test_get_control_properties_returns_props_on_success(self):
        """get_control_properties should return properties when control found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_control_properties.return_value = {"Name":"txtName","BackColor":16777215}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_control_properties("TestForm", "txtName")
            assert result["success"] is True
            assert result["control"] == "txtName"
            assert "BackColor" in result["properties"]

    def test_set_control_property_returns_result(self):
        """set_control_property should return success/failure based on result."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_control_property.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_property("TestForm", "txtName", "BackColor", "16777215", confirm=True)
            assert result["success"] is True
            assert result["property"] == "BackColor"

    def test_form_exists_returns_exists_flag(self):
        """form_exists should return exists flag."""
        mock_adapter = MagicMock()
        mock_adapter.form_exists.return_value = True
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.form_exists("TestForm")
            assert result["success"] is True
            assert result["exists"] is True


class TestSetControlProperties:
    """Tests for set_control_properties tool."""

    def test_set_control_properties_returns_results(self):
        """set_control_properties should return per-property success dict."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_control_properties.return_value = {"Visible": True, "Width": False}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_properties("TestForm", "txtName", {"Visible": "True", "Width": "200"}, confirm=True)
            assert result["success"] is True
            assert "properties" in result
            assert result["properties"]["Visible"] is True

    def test_set_control_properties_empty_result_returns_error(self):
        """set_control_properties should return error when control not found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_control_properties.return_value = {}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_properties("TestForm", "NonExistent", {"Width": "200"}, confirm=True)
            assert result["success"] is False
            assert "not found" in result["error"].lower()


class TestSetControlPropertyDestructive:
    """Tests for set_control_property destructive guard."""

    def test_set_control_property_blocked_without_confirmation(self):
        """set_control_property with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_property("TestForm", "txtName", "BackColor", "16777215", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_control_property_dry_run_returns_preview(self):
        """set_control_property with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_property("TestForm", "txtName", "BackColor", "16777215", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_control_property"
            assert result["form_name"] == "TestForm"
            assert result["control_name"] == "txtName"
            assert result["property_name"] == "BackColor"
            assert result["value"] == "16777215"

    def test_set_control_property_success_with_confirmation(self):
        """set_control_property with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_control_property.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_property("TestForm", "txtName", "BackColor", "16777215", confirm=True)
            assert result["success"] is True
            mock_adapter.set_control_property.assert_called_once_with("TestForm", "txtName", "BackColor", "16777215")


class TestSetControlPropertiesDestructive:
    """Tests for set_control_properties destructive guard."""

    def test_set_control_properties_blocked_without_confirmation(self):
        """set_control_properties with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_properties("TestForm", "txtName", {"BackColor": "16777215"}, confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_control_properties_dry_run_returns_preview(self):
        """set_control_properties with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_properties("TestForm", "txtName", {"BackColor": "16777215"}, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_control_properties"
            assert result["form_name"] == "TestForm"
            assert result["control_name"] == "txtName"

    def test_set_control_properties_success_with_confirmation(self):
        """set_control_properties with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_control_properties.return_value = {"BackColor": True}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_properties("TestForm", "txtName", {"BackColor": "16777215"}, confirm=True)
            assert result["success"] is True
            assert result["properties"]["BackColor"] is True


class TestGetControlEventProcedures:
    """Tests for get_control_event_procedures tool."""

    def test_get_control_event_procedures_all_events(self):
        """get_control_event_procedures should return all events when control_name is empty."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_control_event_procedures.return_value = [
            {"procedure_name": "cmdSave_Click", "event_name": "Click", "code": "Sub cmdSave_Click()\nEnd Sub", "start_line": 1},
            {"procedure_name": "cmdSave_Enter", "event_name": "Enter", "code": "Sub cmdSave_Enter()\nEnd Sub", "start_line": 7},
        ]
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_control_event_procedures("TestForm", "")
            assert result["success"] is True
            assert result["count"] == 2
            assert result["control"] == "(all)"

    def test_get_control_event_procedures_filtered(self):
        """get_control_event_procedures should filter by control_name."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_control_event_procedures.return_value = [
            {"procedure_name": "cmdSave_Click", "event_name": "Click", "code": "Sub cmdSave_Click()\nEnd Sub", "start_line": 1},
        ]
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_control_event_procedures("TestForm", "cmdSave")
            assert result["success"] is True
            assert result["control"] == "cmdSave"
            assert result["count"] == 1

    def test_get_control_event_procedures_form_module_not_found(self):
        """get_control_event_procedures should return empty list when form module not found."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_control_event_procedures.return_value = []  # Empty list = not found (never None)
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_control_event_procedures("NonExistentForm", "")
            assert result["success"] is True  # Returns success with empty list
            assert result["count"] == 0


class TestFormManipulationToolsConnectionGuards:
    """Connection guard tests for the 5 new form manipulation tools."""

    @pytest.mark.parametrize("tool_func,args", [
        (server.create_form, ("TestForm",)),
        (server.get_form_properties, ("TestForm",)),
        (server.rename_form, ("OldName", "NewName")),
        (server.set_form_property, ("TestForm", "Caption", "New Caption")),
        (server.set_form_properties, ("TestForm", {"Caption": "New Caption"})),
        (server.add_control, ("TestForm", "TextBox", "txtNew")),
        (server.remove_control, ("TestForm", "txtOld")),
        # Form section tools
        (server.get_form_sections, ("TestForm",)),
        (server.get_form_section_properties, ("TestForm", 0)),
        (server.set_form_section_property, ("TestForm", 0, "Height", "1000")),
        (server.set_form_section_properties, ("TestForm", 0, {"Height": "1000"})),
    ])
    def test_tool_returns_error_when_not_connected(self, tool_func, args):
        """Each form manipulation tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestCreateForm:
    """Tests for create_form tool."""

    def test_create_form_success_returns_form_name(self):
        """create_form with adapter returning True should return success with form."""
        mock_adapter = MagicMock()
        mock_adapter.create_form.return_value = True
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.create_form("TestForm", record_source="SELECT * FROM Customers")
            assert result["success"] is True
            assert result["form"] == "TestForm"

    def test_create_form_failure_returns_error(self):
        """create_form with adapter returning False should return success=False."""
        mock_adapter = MagicMock()
        mock_adapter.create_form.return_value = False
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.create_form("TestForm")
            assert result["success"] is False
            assert "form" in result


class TestRenameForm:
    """Tests for rename_form tool — destructive."""

    def test_rename_form_blocked_without_confirmation(self):
        """rename_form with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.rename_form("OldName", "NewName", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_rename_form_dry_run_returns_preview(self):
        """rename_form with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.rename_form("OldName", "NewName", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "rename_form"
            assert result["old_name"] == "OldName"
            assert result["new_name"] == "NewName"

    def test_rename_form_success_with_confirmation(self):
        """rename_form with confirm=True should delegate to adapter and return success."""
        mock_adapter = MagicMock()
        mock_adapter.rename_form.return_value = True
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.rename_form("OldName", "NewName", confirm=True)
            assert result["success"] is True
            mock_adapter.rename_form.assert_called_once_with("OldName", "NewName")


class TestGetFormProperties:
    """Tests for get_form_properties tool."""

    def test_get_form_properties_success_returns_dict(self):
        """get_form_properties should return success with properties dict."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_form_properties.return_value = {"Caption": "Test Form", "RecordSource": "Customers"}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_form_properties("TestForm")
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert "properties" in result
            assert result["properties"]["Caption"] == "Test Form"

    def test_get_form_properties_empty_returns_error(self):
        """get_form_properties with empty dict should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_form_properties.return_value = {}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_form_properties("NonExistentForm")
            assert result["success"] is False
            assert "error" in result


class TestSetFormProperty:
    """Tests for set_form_property tool — destructive."""

    def test_set_form_property_blocked_without_confirmation(self):
        """set_form_property with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_property("TestForm", "Caption", "New Caption", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_form_property_dry_run_returns_preview(self):
        """set_form_property with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_property("TestForm", "Caption", "New Caption", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_form_property"
            assert result["form_name"] == "TestForm"

    def test_set_form_property_success_with_confirmation(self):
        """set_form_property with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_form_property.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_property("TestForm", "Caption", "New Caption", confirm=True)
            assert result["success"] is True
            mock_adapter.set_form_property.assert_called_once()


class TestSetFormProperties:
    """Tests for set_form_properties tool — destructive batch."""

    def test_set_form_properties_blocked_without_confirmation(self):
        """set_form_properties with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_properties("TestForm", {"Caption": "New"}, confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_form_properties_dry_run_returns_preview(self):
        """set_form_properties with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_properties("TestForm", {"Caption": "New"}, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_form_properties"

    def test_set_form_properties_success_with_confirmation(self):
        """set_form_properties with confirm=True should return success with per-property results."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_form_properties.return_value = {"Caption": True, "Width": False}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_properties("TestForm", {"Caption": "New", "Width": "1000"}, confirm=True)
            assert result["success"] is True
            assert "properties" in result
            assert result["properties"]["Caption"] is True


class TestAddControl:
    """Tests for add_control tool — destructive."""

    def test_add_control_blocked_without_confirmation(self):
        """add_control with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.add_control("TestForm", "TextBox", "txtNew", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_add_control_dry_run_returns_preview(self):
        """add_control with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.add_control("TestForm", "TextBox", "txtNew", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "add_control"
            assert result["form_name"] == "TestForm"
            assert result["control_name"] == "txtNew"
            assert result["control_type"] == "TextBox"

    def test_add_control_success_with_confirmation(self):
        """add_control with confirm=True should delegate to COM service and return success."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.add_control.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.add_control("TestForm", "TextBox", "txtNew", section=0, properties={"Width": "200"}, confirm=True)
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert result["control"] == "txtNew"
            assert result["control_type"] == "TextBox"
            mock_adapter.add_control.assert_called_once_with("TestForm", "TextBox", "txtNew", 0, {"Width": "200"})

    def test_add_control_adapter_returns_false(self):
        """add_control with confirm=True but adapter returns False should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.add_control.return_value = False
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.add_control("TestForm", "Label", "lblNew", confirm=True)
            assert result["success"] is False
            assert result["form"] == "TestForm"
            assert result["control"] == "lblNew"


class TestRemoveControl:
    """Tests for remove_control tool — destructive."""

    def test_remove_control_blocked_without_confirmation(self):
        """remove_control with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.remove_control("TestForm", "txtOld", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_remove_control_dry_run_returns_preview(self):
        """remove_control with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.remove_control("TestForm", "txtOld", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "remove_control"
            assert result["form_name"] == "TestForm"
            assert result["control_name"] == "txtOld"

    def test_remove_control_success_with_confirmation(self):
        """remove_control with confirm=True should delegate to COM service and return success."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.remove_control.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.remove_control("TestForm", "txtOld", confirm=True)
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert result["control"] == "txtOld"
            mock_adapter.remove_control.assert_called_once_with("TestForm", "txtOld")

    def test_remove_control_adapter_returns_false(self):
        """remove_control with confirm=True but adapter returns False should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.remove_control.return_value = False
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.remove_control("TestForm", "txtOld", confirm=True)
            assert result["success"] is False
            assert result["form"] == "TestForm"
            assert result["control"] == "txtOld"


class TestGetFormSections:
    """Tests for get_form_sections tool."""

    def test_get_form_sections_success_returns_list(self):
        """get_form_sections should return success with sections list."""
        mock_adapter = MagicMock()
        mock_adapter.get_form_sections.return_value = [
            {"index": 0, "name": "detail", "section_type": "acDetail", "visible": True, "height": 1000},
            {"index": 1, "name": "header", "section_type": "acHeader", "visible": True, "height": 500},
        ]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_form_sections("TestForm")
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert "sections" in result
            assert len(result["sections"]) == 2

    def test_get_form_sections_empty_returns_error(self):
        """get_form_sections with empty list should return success=False."""
        mock_adapter = MagicMock()
        mock_adapter.get_form_sections.return_value = []
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_form_sections("NonExistentForm")
            assert result["success"] is False
            assert "error" in result


class TestGetFormSectionProperties:
    """Tests for get_form_section_properties tool."""

    def test_get_form_section_properties_success_returns_dict(self):
        """get_form_section_properties should return success with properties dict."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_form_section_properties.return_value = {"Height": 1000, "Visible": True}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_form_section_properties("TestForm", 0)
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert result["section_id"] == 0
            assert "properties" in result
            assert result["properties"]["Height"] == 1000

    def test_get_form_section_properties_empty_returns_error(self):
        """get_form_section_properties with empty dict should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_form_section_properties.return_value = {}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.get_form_section_properties("TestForm", 1)
            assert result["success"] is False
            assert "error" in result


class TestSetFormSectionProperty:
    """Tests for set_form_section_property tool — destructive."""

    def test_set_form_section_property_blocked_without_confirmation(self):
        """set_form_section_property with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_section_property("TestForm", 0, "Height", "1000", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_form_section_property_dry_run_returns_preview(self):
        """set_form_section_property with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_section_property("TestForm", 0, "Height", "1000", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_form_section_property"
            assert result["form_name"] == "TestForm"
            assert result["section_id"] == 0
            assert result["property_name"] == "Height"

    def test_set_form_section_property_success_with_confirmation(self):
        """set_form_section_property with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_form_section_property.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_section_property("TestForm", 0, "Height", "1000", confirm=True)
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert result["section_id"] == 0
            assert result["property_name"] == "Height"
            assert result["value"] == "1000"
            mock_adapter.set_form_section_property.assert_called_once_with("TestForm", 0, "Height", "1000")

    def test_set_form_section_property_adapter_returns_false(self):
        """set_form_section_property with confirm=True but adapter returns False should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_form_section_property.return_value = False
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_section_property("TestForm", 0, "Height", "1000", confirm=True)
            assert result["success"] is False
            assert result["form"] == "TestForm"
            assert result["section_id"] == 0


class TestSetFormSectionProperties:
    """Tests for set_form_section_properties tool — destructive batch."""

    def test_set_form_section_properties_blocked_without_confirmation(self):
        """set_form_section_properties with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_section_properties("TestForm", 0, {"Height": "1000"}, confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_form_section_properties_dry_run_returns_preview(self):
        """set_form_section_properties with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_section_properties("TestForm", 0, {"Height": "1000"}, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_form_section_properties"
            assert result["form_name"] == "TestForm"
            assert result["section_id"] == 0

    def test_set_form_section_properties_success_with_confirmation(self):
        """set_form_section_properties with confirm=True should return success with per-property results."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_form_section_properties.return_value = {"Height": True, "Visible": True}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_section_properties("TestForm", 0, {"Height": "1000", "Visible": "True"}, confirm=True)
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert result["section_id"] == 0
            assert "properties" in result
            assert result["properties"]["Height"] is True

    def test_set_form_section_properties_empty_result_returns_error(self):
        """set_form_section_properties with empty result should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_form_section_properties.return_value = {}
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_form_section_properties("TestForm", 0, {"Height": "1000"}, confirm=True)
            assert result["success"] is False
            assert "error" in result


class TestSetControlEventProcedure:
    """Tests for set_control_event_procedure tool — destructive."""

    def test_set_control_event_procedure_blocked_without_confirmation(self):
        """set_control_event_procedure with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_event_procedure("TestForm", "btnSave", "Click", "Sub btnSave_Click()\nEnd Sub", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_control_event_procedure_dry_run_returns_preview(self):
        """set_control_event_procedure with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_event_procedure("TestForm", "btnSave", "Click", "Sub btnSave_Click()\nEnd Sub", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_control_event_procedure"
            assert result["form_name"] == "TestForm"
            assert result["control_name"] == "btnSave"
            assert result["event_name"] == "Click"

    def test_set_control_event_procedure_success_with_confirmation(self):
        """set_control_event_procedure with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_control_event_procedure.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_event_procedure("TestForm", "btnSave", "Click", "Sub btnSave_Click()\nEnd Sub", confirm=True)
            assert result["success"] is True
            assert result["form"] == "TestForm"
            assert result["control"] == "btnSave"
            assert result["event_name"] == "Click"
            mock_adapter.set_control_event_procedure.assert_called_once_with("TestForm", "btnSave", "Click", "Sub btnSave_Click()\nEnd Sub")

    def test_set_control_event_procedure_adapter_returns_false(self):
        """set_control_event_procedure with confirm=True but adapter returns False should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.set_control_event_procedure.return_value = False
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(com_module, '_pool', return_value=mock_conn):
            result = server.set_control_event_procedure("TestForm", "btnSave", "Click", "code", confirm=True)
            assert result["success"] is False
            assert result["form"] == "TestForm"
            assert result["control"] == "btnSave"
