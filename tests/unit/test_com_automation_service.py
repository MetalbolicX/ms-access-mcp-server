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

    def test_initialization_with_connection_pool(self):
        """COMAutomationService should accept connection_pool parameter."""
        mock_pool = MagicMock()
        service = COMAutomationService(connection_pool=mock_pool)
        assert service._pool is mock_pool
        assert service._adapter is None

    def test_initialization_with_both_adapter_and_pool(self):
        """COMAutomationService should store both adapter and pool when both provided."""
        mock_adapter = MagicMock()
        mock_pool = MagicMock()
        service = COMAutomationService(adapter=mock_adapter, connection_pool=mock_pool)
        assert service._adapter is mock_adapter
        assert service._pool is mock_pool


class TestGetAdapter:
    """Tests for _get_adapter() method."""

    def test_get_adapter_returns_pool_adapter_when_available(self):
        """_get_adapter should return adapter from pool when pool is set and has adapter."""
        mock_adapter = MagicMock()
        mock_pool = MagicMock()
        mock_pool.get_adapter.return_value = mock_adapter
        service = COMAutomationService(connection_pool=mock_pool)
        result = service._get_adapter()
        assert result is mock_adapter
        mock_pool.get_adapter.assert_called_once()

    def test_get_adapter_falls_back_to_constructor_adapter_when_pool_fails(self):
        """_get_adapter should fall back to _adapter when pool lookup raises KeyError."""
        mock_adapter = MagicMock()
        mock_pool = MagicMock()
        mock_pool.get_adapter.side_effect = KeyError("not found")
        service = COMAutomationService(adapter=mock_adapter, connection_pool=mock_pool)
        result = service._get_adapter()
        assert result is mock_adapter

    def test_get_adapter_falls_back_to_constructor_adapter_when_pool_is_none(self):
        """_get_adapter should fall back to _adapter when no pool is set."""
        mock_adapter = MagicMock()
        service = COMAutomationService(adapter=mock_adapter)
        result = service._get_adapter()
        assert result is mock_adapter

    def test_get_adapter_returns_none_when_no_pool_no_adapter(self):
        """_get_adapter should return None when neither pool nor adapter is set."""
        service = COMAutomationService()
        result = service._get_adapter()
        assert result is None

    def test_get_adapter_returns_none_when_pool_raises_keyerror_and_no_adapter(self):
        """_get_adapter should return None when pool fails and no fallback adapter."""
        mock_pool = MagicMock()
        mock_pool.get_adapter.side_effect = KeyError("not found")
        service = COMAutomationService(connection_pool=mock_pool)
        result = service._get_adapter()
        assert result is None


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