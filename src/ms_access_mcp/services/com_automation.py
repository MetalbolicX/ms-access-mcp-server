from typing import Optional
from ..adapters.interfaces import IUiAdapter


class COMAutomationService:
    """Manages Access COM automation (launch, VBA injection, form control)."""

    def __init__(self, adapter: Optional[IUiAdapter] = None):
        self._adapter = adapter
        self._access_running = False

    def set_adapter(self, adapter: IUiAdapter) -> None:
        """Set the adapter for COM operations."""
        self._adapter = adapter

    def launch_access(self, visible: bool = False) -> bool:
        """Launch Microsoft Access application."""
        if self._adapter is None:
            return False
        self._adapter.launch_access(visible)
        self._access_running = True
        return True

    def close_access(self) -> bool:
        """Close Microsoft Access application."""
        if self._adapter is None:
            return False
        self._adapter.close_access()
        self._access_running = False
        return True

    def is_access_running(self) -> bool:
        """Check if Access is currently running."""
        return self._access_running

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Inject VBA code into a module."""
        if self._adapter is None:
            return False
        return self._adapter.set_vba_code(module_name, code)

    def open_form(self, form_name: str) -> bool:
        """Open a form in Access."""
        if self._adapter is None:
            return False
        return self._adapter.open_form(form_name)

    def close_form(self, form_name: str) -> bool:
        """Close an open form."""
        if self._adapter is None:
            return False
        return self._adapter.close_form(form_name)

    def get_control_properties(self, form_name: str, control_name: str) -> dict:
        """Get all properties of a specific control."""
        if self._adapter is None:
            return {}
        return self._adapter.get_control_properties(form_name, control_name)

    def set_control_property(self, form_name: str, control_name: str, property_name: str, value: str) -> bool:
        """Set a property of a control."""
        if self._adapter is None:
            return False
        return self._adapter.set_control_property(form_name, control_name, property_name, value)

    def set_control_properties(self, form_name: str, control_name: str, properties: dict[str, str]) -> dict[str, bool]:
        """Set multiple properties of a control at once."""
        if self._adapter is None:
            return {}
        return self._adapter.set_control_properties(form_name, control_name, properties)

    def get_control_event_procedures(self, form_name: str, control_name: str) -> list[dict]:
        """List event procedures for a specific control in a form."""
        if self._adapter is None:
            return []
        return self._adapter.get_control_event_procedures(form_name, control_name)

    def compile_vba(self) -> dict:
        """Compile VBA code in the database."""
        if self._adapter is None:
            return {"success": False, "error": "No adapter available"}
        return self._adapter.compile_vba()
