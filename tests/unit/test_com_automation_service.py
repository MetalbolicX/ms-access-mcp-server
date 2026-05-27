import pytest
from unittest.mock import MagicMock
from ms_access_mcp.services.com_automation import COMAutomationService


class TestCOMAutomationServiceInit:
    def test_initialization_no_adapter(self):
        service = COMAutomationService()
        assert service is not None
        assert service._adapter is None
        assert service.is_access_running() is False

    def test_initialization_with_adapter(self):
        mock_adapter = MagicMock()
        service = COMAutomationService(adapter=mock_adapter)
        assert service._adapter is mock_adapter


class TestSetAdapter:
    def test_set_adapter(self):
        service = COMAutomationService()
        mock_adapter = MagicMock()
        service.set_adapter(mock_adapter)
        assert service._adapter is mock_adapter


class TestLaunchAccess:
    def test_launch_access_with_adapter(self):
        mock_adapter = MagicMock()
        service = COMAutomationService(adapter=mock_adapter)
        result = service.launch_access(visible=True)
        assert result is True
        mock_adapter.launch_access.assert_called_once_with(True)
        assert service.is_access_running() is True

    def test_launch_access_without_adapter_returns_false(self):
        service = COMAutomationService()
        result = service.launch_access()
        assert result is False
        assert service.is_access_running() is False


class TestCloseAccess:
    def test_close_access_with_adapter(self):
        mock_adapter = MagicMock()
        service = COMAutomationService(adapter=mock_adapter)
        service.launch_access()
        result = service.close_access()
        assert result is True
        mock_adapter.close_access.assert_called_once()
        assert service.is_access_running() is False

    def test_close_access_without_adapter_returns_false(self):
        service = COMAutomationService()
        result = service.close_access()
        assert result is False


class TestSetVBACode:
    def test_set_vba_code_with_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.set_vba_code.return_value = True
        service = COMAutomationService(adapter=mock_adapter)
        result = service.set_vba_code("Module1", "Sub Test()\nEnd Sub")
        assert result is True
        mock_adapter.set_vba_code.assert_called_once_with("Module1", "Sub Test()\nEnd Sub")

    def test_set_vba_code_without_adapter_returns_false(self):
        service = COMAutomationService()
        result = service.set_vba_code("Module1", "code")
        assert result is False


class TestOpenForm:
    def test_open_form_with_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.open_form.return_value = True
        service = COMAutomationService(adapter=mock_adapter)
        result = service.open_form("MainForm")
        assert result is True
        mock_adapter.open_form.assert_called_once_with("MainForm")

    def test_open_form_without_adapter_returns_false(self):
        service = COMAutomationService()
        result = service.open_form("MainForm")
        assert result is False


class TestCloseForm:
    def test_close_form_with_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.close_form.return_value = True
        service = COMAutomationService(adapter=mock_adapter)
        result = service.close_form("MainForm")
        assert result is True
        mock_adapter.close_form.assert_called_once_with("MainForm")

    def test_close_form_without_adapter_returns_false(self):
        service = COMAutomationService()
        result = service.close_form("MainForm")
        assert result is False


class TestControlProperties:
    def test_get_control_properties_with_adapter(self):
        mock_adapter = MagicMock()
        mock_props = {"Caption": "Hello", "Visible": True}
        mock_adapter.get_control_properties.return_value = mock_props
        service = COMAutomationService(adapter=mock_adapter)
        result = service.get_control_properties("MainForm", "btnSubmit")
        assert result == mock_props
        mock_adapter.get_control_properties.assert_called_once_with("MainForm", "btnSubmit")

    def test_get_control_properties_without_adapter_returns_empty(self):
        service = COMAutomationService()
        result = service.get_control_properties("MainForm", "btnSubmit")
        assert result == {}

    def test_set_control_property_with_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.set_control_property.return_value = True
        service = COMAutomationService(adapter=mock_adapter)
        result = service.set_control_property("MainForm", "btnSubmit", "Caption", "Click Me")
        assert result is True
        mock_adapter.set_control_property.assert_called_once_with("MainForm", "btnSubmit", "Caption", "Click Me")

    def test_set_control_property_without_adapter_returns_false(self):
        service = COMAutomationService()
        result = service.set_control_property("MainForm", "btnSubmit", "Caption", "Click Me")
        assert result is False


class TestCompileVBA:
    def test_compile_vba_with_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.compile_vba.return_value = {"success": True}
        service = COMAutomationService(adapter=mock_adapter)
        result = service.compile_vba()
        assert result == {"success": True}
        mock_adapter.compile_vba.assert_called_once()

    def test_compile_vba_without_adapter_returns_error(self):
        service = COMAutomationService()
        result = service.compile_vba()
        assert result == {"success": False, "error": "No adapter available"}