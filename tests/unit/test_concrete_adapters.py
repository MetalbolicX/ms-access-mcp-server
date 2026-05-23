import pytest
import sys
from unittest.mock import patch, MagicMock
from ms_access_mcp.adapters.wincom import WinComAdapter, ComDispatcher
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.base import AccessAdapter


class TestWinComAdapterInstantiation:
    """WinComAdapter instantiation and platform guard."""

    def test_instantiation_creates_dispatcher(self):
        """WinComAdapter creates a ComDispatcher on instantiation (no platform check at __init__)."""
        with patch.object(sys, 'platform', 'linux'):
            adapter = WinComAdapter()
            assert isinstance(adapter, AccessAdapter)
            assert isinstance(adapter._dispatcher, ComDispatcher)
            assert adapter._dispatcher._thread is None  # not started yet
            assert adapter._db_path is None


def test_odbc_adapter_instantiation():
    adapter = OdbcAdapter()
    assert isinstance(adapter, AccessAdapter)
    # Returns False for non-existent file, no exception
    assert adapter.connect("C:\\nonexistent\\dummy.accdb") is False
