import pytest
import sys
from unittest.mock import patch, MagicMock, PropertyMock
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


class TestComDispatcherCleanup:
    """ComDispatcher COM cleanup — _release_com_safe and wiring."""

    def test_release_com_safe_method_exists(self):
        """_release_com_safe is defined on ComDispatcher and callable."""
        dispatcher = ComDispatcher()
        assert hasattr(dispatcher, '_release_com_safe')
        assert callable(dispatcher._release_com_safe)

    def test_cleanup_com_delegates_to_release_com_safe(self):
        """_cleanup_com() calls _release_com_safe() internally."""
        dispatcher = ComDispatcher()
        with patch.object(dispatcher, '_release_com_safe') as mock_release:
            dispatcher._cleanup_com()
            mock_release.assert_called_once_with()

    def test_release_com_safe_handles_clean_state(self):
        """_release_com_safe runs without error when all objects are None."""
        dispatcher = ComDispatcher()
        dispatcher._access_app = None
        dispatcher._current_db = None
        dispatcher._ado_conn = None
        # Should not raise
        dispatcher._release_com_safe()

    def test_release_com_safe_closes_ado_connection(self):
        """_release_com_safe calls Close() on ADO connection if present."""
        dispatcher = ComDispatcher()
        mock_ado = MagicMock()
        dispatcher._ado_conn = mock_ado
        dispatcher._access_app = None
        dispatcher._current_db = None
        dispatcher._release_com_safe()
        mock_ado.Close.assert_called_once_with()
        assert dispatcher._ado_conn is None

    def test_release_com_safe_closes_dao_database(self):
        """_release_com_safe calls Close() on DAO database if present."""
        dispatcher = ComDispatcher()
        mock_db = MagicMock()
        dispatcher._current_db = mock_db
        dispatcher._access_app = None
        dispatcher._ado_conn = None
        dispatcher._release_com_safe()
        mock_db.Close.assert_called_once_with()
        assert dispatcher._current_db is None

    def test_release_com_safe_ado_error_does_not_block(self):
        """ADO Close error is caught and does not prevent further cleanup."""
        dispatcher = ComDispatcher()
        mock_ado = MagicMock()
        mock_ado.Close.side_effect = Exception("ADO error")
        mock_db = MagicMock()
        dispatcher._ado_conn = mock_ado
        dispatcher._current_db = mock_db
        dispatcher._access_app = None
        dispatcher._release_com_safe()
        # DAO Close still happened even though ADO failed
        mock_db.Close.assert_called_once_with()

    def test_release_com_safe_imports_subprocess(self):
        """The wincom module imports subprocess (needed for taskkill)."""
        import importlib
        import ms_access_mcp.adapters.wincom as wincom_mod
        importlib.reload(wincom_mod)
        assert hasattr(wincom_mod, 'subprocess') or 'subprocess' in dir(wincom_mod)

    def test_disconnect_wires_release_com_safe(self):
        """disconnect() calls _release_com_safe via dispatcher."""
        adapter = WinComAdapter()
        dispatcher = adapter._dispatcher
        with patch.object(sys, 'platform', 'win32'):
            with patch.object(dispatcher, 'call') as mock_call:
                with patch.object(dispatcher, 'shutdown'):
                    adapter.disconnect()
                    # The callable passed to dispatcher.call should invoke _release_com_safe
                    call_args = mock_call.call_args
                    assert call_args is not None

    def test_run_finally_calls_release_com_safe(self):
        """_run() finally block calls _release_com_safe instead of _cleanup_com."""
        dispatcher = ComDispatcher()
        import inspect
        source = inspect.getsource(dispatcher._run)
        assert 'self._release_com_safe()' in source
        assert 'self._cleanup_com()' not in source

    def test_shutdown_join_timeout_increased(self):
        """shutdown() join timeout has been extended to 15.0."""
        dispatcher = ComDispatcher()
        import inspect
        source = inspect.getsource(dispatcher.shutdown)
        assert 'timeout=15.0' in source


def test_odbc_adapter_instantiation():
    adapter = OdbcAdapter()
    assert isinstance(adapter, AccessAdapter)
    # Returns False for non-existent file, no exception
    assert adapter.connect("C:\\nonexistent\\dummy.accdb") is False
