from typing import Optional
from ..adapters.base import AccessAdapter


class COMAutomationService:
    """Manages Access COM automation (launch, VBA injection, form control)."""

    def __init__(self, adapter: Optional[AccessAdapter] = None):
        self._adapter = adapter
        self._access_running = False

    def set_adapter(self, adapter: AccessAdapter) -> None:
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
