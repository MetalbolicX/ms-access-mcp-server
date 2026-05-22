import pytest
from ms_access_mcp.services.com_automation import COMAutomationService

def test_com_automation_service_initialization():
    service = COMAutomationService()
    assert service is not None

def test_com_automation_service_access_not_running():
    service = COMAutomationService()
    assert service.is_access_running() is False