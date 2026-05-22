import pytest
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.base import AccessAdapter


def test_wincom_adapter_instantiation():
    adapter = WinComAdapter()
    assert isinstance(adapter, AccessAdapter)
    # Returns False for non-existent file, no exception
    assert adapter.connect("C:\\nonexistent\\dummy.accdb") is False


def test_odbc_adapter_instantiation():
    adapter = OdbcAdapter()
    assert isinstance(adapter, AccessAdapter)
    # Returns False for non-existent file, no exception
    assert adapter.connect("C:\\nonexistent\\dummy.accdb") is False
