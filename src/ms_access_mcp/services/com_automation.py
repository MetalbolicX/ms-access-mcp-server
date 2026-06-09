from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import ConnectionPool

from ..adapters.interfaces import IUiAdapter


class COMAutomationService:
    """Manages Access COM automation (launch, VBA injection, form control)."""

    def __init__(
        self,
        adapter: Optional[IUiAdapter] = None,
        connection_pool: Optional["ConnectionPool"] = None,
    ):
        self._adapter = adapter
        self._pool = connection_pool
        self._access_running = False

    def _get_adapter(self) -> Optional[IUiAdapter]:
        """Get the adapter for COM operations.

        Resolves adapter from connection_pool first, falls back to constructor adapter.
        """
        if self._pool is not None:
            try:
                return self._pool.get_adapter()
            except KeyError:
                pass
        return self._adapter

    def launch_access(self, visible: bool = False) -> bool:
        """Launch Microsoft Access application."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        adapter.launch_access(visible)
        self._access_running = True
        return True

    def close_access(self) -> bool:
        """Close Microsoft Access application."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        adapter.close_access()
        self._access_running = False
        return True

    def is_access_running(self) -> bool:
        """Check if Access is currently running."""
        return self._access_running

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Inject VBA code into a module."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.set_vba_code(module_name, code)

    def open_form(self, form_name: str) -> bool:
        """Open a form in Access."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.open_form(form_name)

    def close_form(self, form_name: str) -> bool:
        """Close an open form."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.close_form(form_name)

    def get_control_properties(self, form_name: str, control_name: str) -> dict:
        """Get all properties of a specific control."""
        adapter = self._get_adapter()
        if adapter is None:
            return {}
        return adapter.get_control_properties(form_name, control_name)

    def set_control_property(self, form_name: str, control_name: str, property_name: str, value: str) -> bool:
        """Set a property of a control."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.set_control_property(form_name, control_name, property_name, value)

    def set_control_properties(self, form_name: str, control_name: str, properties: dict[str, str]) -> dict[str, bool]:
        """Set multiple properties of a control at once."""
        adapter = self._get_adapter()
        if adapter is None:
            return {}
        return adapter.set_control_properties(form_name, control_name, properties)

    def get_control_event_procedures(self, form_name: str, control_name: str) -> list[dict]:
        """List event procedures for a specific control in a form."""
        adapter = self._get_adapter()
        if adapter is None:
            return []
        return adapter.get_control_event_procedures(form_name, control_name)

    def compile_vba(self) -> dict:
        """Compile VBA code in the database."""
        adapter = self._get_adapter()
        if adapter is None:
            return {"success": False, "error": "No adapter available"}
        return adapter.compile_vba()

    def create_form(self, form_name: str, record_source: str = "", template_name: str = "", properties: dict[str, Any] | None = None) -> bool:
        """Create a new form."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.create_form(form_name, record_source, template_name, properties)

    def rename_form(self, old_name: str, new_name: str) -> bool:
        """Rename a form."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.rename_form(old_name, new_name)

    def get_form_properties(self, form_name: str) -> dict:
        """Get all properties of a form."""
        adapter = self._get_adapter()
        if adapter is None:
            return {}
        return adapter.get_form_properties(form_name)

    def set_form_property(self, form_name: str, property_name: str, value: str) -> bool:
        """Set a single property of a form."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.set_form_property(form_name, property_name, value)

    def set_form_properties(self, form_name: str, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple properties of a form at once."""
        adapter = self._get_adapter()
        if adapter is None:
            return {}
        return adapter.set_form_properties(form_name, properties)

    def add_control(self, form_name: str, control_type: str, control_name: str, section: int = 0, properties: dict[str, Any] | None = None) -> bool:
        """Add a control to a form."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.add_control(form_name, control_type, control_name, section, properties)

    def remove_control(self, form_name: str, control_name: str) -> bool:
        """Remove a control from a form."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.remove_control(form_name, control_name)

    def get_form_sections(self, form_name: str) -> list:
        """Get all sections of a form."""
        adapter = self._get_adapter()
        if adapter is None:
            return []
        return adapter.get_form_sections(form_name)

    def get_form_section_properties(self, form_name: str, section_id: int) -> dict:
        """Get all properties of a specific form section."""
        adapter = self._get_adapter()
        if adapter is None:
            return {}
        return adapter.get_form_section_properties(form_name, section_id)

    def set_form_section_property(self, form_name: str, section_id: int, property_name: str, value: str) -> bool:
        """Set a single property of a form section."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.set_form_section_property(form_name, section_id, property_name, value)

    def set_form_section_properties(self, form_name: str, section_id: int, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple properties of a form section at once."""
        adapter = self._get_adapter()
        if adapter is None:
            return {}
        return adapter.set_form_section_properties(form_name, section_id, properties)

    def set_control_event_procedure(self, form_name: str, control_name: str, event_name: str, code: str) -> bool:
        """Set a control's event procedure."""
        adapter = self._get_adapter()
        if adapter is None:
            return False
        return adapter.set_control_event_procedure(form_name, control_name, event_name, code)
