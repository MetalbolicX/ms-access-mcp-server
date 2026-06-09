"""Tests for mcp/reports.py tool bindings — PR1 Core/CRUD/Properties."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import reports as reports_module


class TestReportExists:
    """Tests for report_exists tool."""

    def test_report_exists_returns_true_when_exists(self):
        """report_exists should return exists=True when report is found."""
        mock_adapter = MagicMock()
        mock_adapter.report_exists.return_value = True
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.report_exists("TestReport")
            assert result["success"] is True
            assert result["exists"] is True
            assert result["report"] == "TestReport"

    def test_report_exists_returns_false_when_not_found(self):
        """report_exists should return exists=False when report not found."""
        mock_adapter = MagicMock()
        mock_adapter.report_exists.return_value = False
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.report_exists("NonExistentReport")
            assert result["success"] is True
            assert result["exists"] is False
            assert result["report"] == "NonExistentReport"

    def test_report_exists_returns_error_when_not_connected(self):
        """report_exists should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.report_exists("TestReport")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestCreateReport:
    """Tests for create_report tool."""

    def test_create_report_success_returns_report_name(self):
        """create_report with adapter returning True should return success."""
        mock_adapter = MagicMock()
        mock_adapter.create_report.return_value = True
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.create_report("TestReport", record_source="SELECT * FROM Customers")
            assert result["success"] is True
            assert result["report_name"] == "TestReport"

    def test_create_report_failure_returns_error(self):
        """create_report with adapter returning False should return success=False."""
        mock_adapter = MagicMock()
        mock_adapter.create_report.return_value = False
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.create_report("TestReport")
            assert result["success"] is False
            assert "report_name" in result

    def test_create_report_returns_error_when_not_connected(self):
        """create_report should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.create_report("TestReport")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestRenameReport:
    """Tests for rename_report tool — destructive."""

    def test_rename_report_blocked_without_confirmation(self):
        """rename_report with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.rename_report("OldName", "NewName", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_rename_report_dry_run_returns_preview(self):
        """rename_report with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.rename_report("OldName", "NewName", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "rename_report"
            assert result["old_name"] == "OldName"
            assert result["new_name"] == "NewName"

    def test_rename_report_success_with_confirmation(self):
        """rename_report with confirm=True should delegate to adapter."""
        mock_adapter = MagicMock()
        mock_adapter.rename_report.return_value = True
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.rename_report("OldName", "NewName", confirm=True)
            assert result["success"] is True
            mock_adapter.rename_report.assert_called_once_with("OldName", "NewName")

    def test_rename_report_returns_error_when_not_connected(self):
        """rename_report should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.rename_report("OldName", "NewName", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestGetReportProperties:
    """Tests for get_report_properties tool."""

    def test_get_report_properties_success_returns_dict(self):
        """get_report_properties should return success with properties dict."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_report_properties.return_value = {"Caption": "Test Report", "RecordSource": "Customers"}
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.get_report_properties("TestReport")
            assert result["success"] is True
            assert result["report"] == "TestReport"
            assert "properties" in result
            assert result["properties"]["Caption"] == "Test Report"

    def test_get_report_properties_empty_returns_error(self):
        """get_report_properties with empty dict should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_report_properties.return_value = {}
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.get_report_properties("NonExistentReport")
            assert result["success"] is False
            assert "error" in result

    def test_get_report_properties_returns_error_when_not_connected(self):
        """get_report_properties should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.get_report_properties("TestReport")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestSetReportProperty:
    """Tests for set_report_property tool — destructive."""

    def test_set_report_property_blocked_without_confirmation(self):
        """set_report_property with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_property("TestReport", "Caption", "New Caption", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_report_property_dry_run_returns_preview(self):
        """set_report_property with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_property("TestReport", "Caption", "New Caption", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_report_property"
            assert result["report_name"] == "TestReport"

    def test_set_report_property_success_with_confirmation(self):
        """set_report_property with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_report_property.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.set_report_property("TestReport", "Caption", "New Caption", confirm=True)
            assert result["success"] is True
            mock_com.set_report_property.assert_called_once()

    def test_set_report_property_returns_error_when_not_connected(self):
        """set_report_property should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_property("TestReport", "Caption", "New Caption", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestSetReportProperties:
    """Tests for set_report_properties tool — destructive batch."""

    def test_set_report_properties_blocked_without_confirmation(self):
        """set_report_properties with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_properties("TestReport", {"Caption": "New"}, confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_report_properties_dry_run_returns_preview(self):
        """set_report_properties with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_properties("TestReport", {"Caption": "New"}, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_report_properties"

    def test_set_report_properties_success_with_confirmation(self):
        """set_report_properties with confirm=True should return success with per-property results."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_report_properties.return_value = {"Caption": True, "Width": False}
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.set_report_properties("TestReport", {"Caption": "New", "Width": "1000"}, confirm=True)
            assert result["success"] is True
            assert "properties" in result
            assert result["properties"]["Caption"] is True

    def test_set_report_properties_empty_result_returns_error(self):
        """set_report_properties with empty result should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_report_properties.return_value = {}
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.set_report_properties("TestReport", {"Caption": "New"}, confirm=True)
            assert result["success"] is False
            assert "error" in result

    def test_set_report_properties_returns_error_when_not_connected(self):
        """set_report_properties should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_properties("TestReport", {"Caption": "New"}, confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


# =============================================================================
# PR2: REPORT CONTROL TOOLS
# =============================================================================


class TestGetReportControls:
    """Tests for get_report_controls tool."""

    def test_get_report_controls_success_returns_controls(self):
        """get_report_controls should return success with controls list."""
        mock_control = MagicMock()
        mock_control.model_dump.return_value = {"name": "txtName", "type": "TextBox", "properties": {"Visible": "True"}}
        mock_adapter = MagicMock()
        mock_adapter.get_report_controls.return_value = [mock_control]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.get_report_controls("TestReport")
            assert result["success"] is True
            assert result["count"] == 1
            assert result["controls"][0]["name"] == "txtName"

    def test_get_report_controls_empty_returns_empty_list(self):
        """get_report_controls with no controls should return empty list."""
        mock_adapter = MagicMock()
        mock_adapter.get_report_controls.return_value = []
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.get_report_controls("TestReport")
            assert result["success"] is True
            assert result["count"] == 0
            assert result["controls"] == []

    def test_get_report_controls_returns_error_when_not_connected(self):
        """get_report_controls should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.get_report_controls("TestReport")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestGetReportControlProperties:
    """Tests for get_report_control_properties tool."""

    def test_get_report_control_properties_success_returns_props(self):
        """get_report_control_properties should return success with properties dict."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_report_control_properties.return_value = {"Visible": "True", "Width": "1000"}
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.get_report_control_properties("TestReport", "txtName")
            assert result["success"] is True
            assert result["control"] == "txtName"
            assert result["properties"]["Visible"] == "True"

    def test_get_report_control_properties_empty_returns_error(self):
        """get_report_control_properties with empty dict should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_report_control_properties.return_value = {}
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.get_report_control_properties("TestReport", "NonExistent")
            assert result["success"] is False
            assert "error" in result

    def test_get_report_control_properties_returns_error_when_not_connected(self):
        """get_report_control_properties should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.get_report_control_properties("TestReport", "txtName")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestSetReportControlProperty:
    """Tests for set_report_control_property tool — destructive."""

    def test_set_report_control_property_blocked_without_confirmation(self):
        """set_report_control_property with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_control_property("TestReport", "txtName", "Visible", "False", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_report_control_property_dry_run_returns_preview(self):
        """set_report_control_property with dry_run=True should return preview."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_control_property("TestReport", "txtName", "Visible", "False", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_report_control_property"
            assert result["control_name"] == "txtName"

    def test_set_report_control_property_success_with_confirmation(self):
        """set_report_control_property with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_report_control_property.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.set_report_control_property("TestReport", "txtName", "Visible", "False", confirm=True)
            assert result["success"] is True
            mock_com.set_report_control_property.assert_called_once()

    def test_set_report_control_property_returns_error_when_not_connected(self):
        """set_report_control_property should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_control_property("TestReport", "txtName", "Visible", "False", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestSetReportControlProperties:
    """Tests for set_report_control_properties tool — destructive batch."""

    def test_set_report_control_properties_blocked_without_confirmation(self):
        """set_report_control_properties with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_control_properties("TestReport", "txtName", {"Visible": "False"}, confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_set_report_control_properties_dry_run_returns_preview(self):
        """set_report_control_properties with dry_run=True should return preview."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_control_properties("TestReport", "txtName", {"Visible": "False"}, dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_report_control_properties"

    def test_set_report_control_properties_success_with_confirmation(self):
        """set_report_control_properties with confirm=True should return success."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_report_control_properties.return_value = {"Visible": True, "Width": False}
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.set_report_control_properties("TestReport", "txtName", {"Visible": "False", "Width": "1000"}, confirm=True)
            assert result["success"] is True
            assert result["properties"]["Visible"] is True

    def test_set_report_control_properties_empty_result_returns_error(self):
        """set_report_control_properties with empty result should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.set_report_control_properties.return_value = {}
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.set_report_control_properties("TestReport", "txtName", {"Visible": "False"}, confirm=True)
            assert result["success"] is False
            assert "error" in result

    def test_set_report_control_properties_returns_error_when_not_connected(self):
        """set_report_control_properties should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.set_report_control_properties("TestReport", "txtName", {"Visible": "False"}, confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestAddReportControl:
    """Tests for add_report_control tool — destructive."""

    def test_add_report_control_blocked_without_confirmation(self):
        """add_report_control with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.add_report_control("TestReport", "TextBox", "txtNew", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_add_report_control_dry_run_returns_preview(self):
        """add_report_control with dry_run=True should return preview."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.add_report_control("TestReport", "TextBox", "txtNew", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "add_report_control"

    def test_add_report_control_success_with_confirmation(self):
        """add_report_control with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.add_report_control.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.add_report_control("TestReport", "TextBox", "txtNew", confirm=True)
            assert result["success"] is True
            mock_com.add_report_control.assert_called_once()

    def test_add_report_control_returns_error_when_not_connected(self):
        """add_report_control should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.add_report_control("TestReport", "TextBox", "txtNew", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestRemoveReportControl:
    """Tests for remove_report_control tool — destructive."""

    def test_remove_report_control_blocked_without_confirmation(self):
        """remove_report_control with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.remove_report_control("TestReport", "txtName", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_remove_report_control_dry_run_returns_preview(self):
        """remove_report_control with dry_run=True should return preview."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.remove_report_control("TestReport", "txtName", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "remove_report_control"

    def test_remove_report_control_success_with_confirmation(self):
        """remove_report_control with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.remove_report_control.return_value = True
        with patch.object(reports_module, '_pool', return_value=mock_conn), \
             patch.object(reports_module, '_com', return_value=mock_com):
            result = server.remove_report_control("TestReport", "txtName", confirm=True)
            assert result["success"] is True
            mock_com.remove_report_control.assert_called_once()

    def test_remove_report_control_returns_error_when_not_connected(self):
        """remove_report_control should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(reports_module, '_pool', return_value=mock_conn):
            result = server.remove_report_control("TestReport", "txtName", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]
