import pytest
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.base import AccessAdapter

def test_wincom_adapter_instantiation():
    adapter = WinComAdapter()
    assert isinstance(adapter, AccessAdapter)
    
    with pytest.raises(NotImplementedError):
        adapter.connect("dummy.accdb")

def test_odbc_adapter_instantiation():
    adapter = OdbcAdapter()
    assert isinstance(adapter, AccessAdapter)
    
    with pytest.raises(NotImplementedError):
        adapter.connect("dummy.accdb")
