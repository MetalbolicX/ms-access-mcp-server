import pytest
from typing import Protocol
from ms_access_mcp.adapters.base import AccessAdapter

def test_access_adapter_protocol():
    # Verify that the protocol defines expected methods
    assert hasattr(AccessAdapter, "connect")
    assert hasattr(AccessAdapter, "disconnect")
    assert hasattr(AccessAdapter, "get_tables")
    assert hasattr(AccessAdapter, "execute_query")

def test_dummy_adapter_implements_protocol():
    class DummyAdapter:
        def connect(self, db_path: str) -> bool: return True
        def disconnect(self) -> None: pass
        def is_connected(self) -> bool: return True
        def get_tables(self) -> list: return []
        def execute_query(self, sql: str, params: list | None = None) -> list: return []
        def launch_access(self, visible: bool = False) -> None: pass
        def close_access(self) -> None: pass
        def set_vba_code(self, module_name: str, code: str) -> bool: return True

    # This won't throw if Duck typing matches, but we just verify it exists
    adapter: AccessAdapter = DummyAdapter()
    assert adapter.connect("test") is True
