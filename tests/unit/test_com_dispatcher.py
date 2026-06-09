"""ComDispatcher unit tests — PID-scoped taskkill (PR 1 Task 1.3 RED)."""

from __future__ import annotations

import concurrent.futures
import sys
from unittest.mock import MagicMock, patch, call

import pytest


class TestComDispatcherPidScopedTaskkill:
    """Test that _release_com_safe uses /PID instead of /IM when graceful Quit fails.

    PR 1 Task 1.3 RED: Verify subprocess.run is called with /PID not /IM after
    Access.Quit() times out on Windows.
    """

    def test_release_com_safe_uses_pid_based_taskkill_when_quit_fails(self):
        """When Access.Quit() times out, _release_com_safe must kill by PID not /IM.

        The PID is extracted via win32process.GetWindowThreadProcessId(hWnd).
        This ensures only the spawned Access instance is killed, not all instances.
        """
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()

        # Simulate connected state with a mock Access app
        mock_app = MagicMock()
        mock_app.hWndAccessApp.return_value = 12345  # HWND for the Access window

        dispatcher._access_app = mock_app
        dispatcher._ado_conn = MagicMock()
        dispatcher._current_db = MagicMock()

        with patch("ms_access_mcp.adapters.com_dispatcher.subprocess.run") as mock_run:
            # Patch the module-level reference so the inner import picks it up
            with patch("ms_access_mcp.adapters.com_dispatcher.concurrent.futures.ThreadPoolExecutor") as mock_tpe_cls:
                mock_tpe = MagicMock()
                mock_future = MagicMock()
                mock_future.result.side_effect = concurrent.futures.TimeoutError("Quit timed out")
                mock_tpe.__enter__ = MagicMock(return_value=mock_tpe)
                mock_tpe.__exit__ = MagicMock(return_value=None)
                mock_tpe.submit.return_value = mock_future
                mock_tpe_cls.return_value = mock_tpe

                with patch("win32process.GetWindowThreadProcessId", return_value=(0, 9876)):
                    dispatcher._release_com_safe()

                    # Verify taskkill was called with /PID, not /IM
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args[0][0]  # first positional arg
                    assert "/PID" in call_args, f"Expected /PID in taskkill args, got: {call_args}"
                    assert "/IM" not in call_args, f"Expected NO /IM in taskkill args, got: {call_args}"
                    assert "9876" in call_args, f"Expected PID 9876 in taskkill args, got: {call_args}"

    def test_release_com_safe_falls_back_to_im_when_hwnd_fails(self):
        """When GetWindowThreadProcessId fails, _release_com_safe must fall back to /IM MSACCESS.EXE."""
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()

        mock_app = MagicMock()
        dispatcher._access_app = mock_app
        dispatcher._ado_conn = MagicMock()
        dispatcher._current_db = MagicMock()

        with patch("ms_access_mcp.adapters.com_dispatcher.subprocess.run") as mock_run:
            with patch("ms_access_mcp.adapters.com_dispatcher.concurrent.futures.ThreadPoolExecutor") as mock_tpe_cls:
                mock_tpe = MagicMock()
                mock_future = MagicMock()
                mock_future.result.side_effect = concurrent.futures.TimeoutError("Quit timed out")
                mock_tpe.__enter__ = MagicMock(return_value=mock_tpe)
                mock_tpe.__exit__ = MagicMock(return_value=None)
                mock_tpe.submit.return_value = mock_future
                mock_tpe_cls.return_value = mock_tpe

                with patch("win32process.GetWindowThreadProcessId", side_effect=Exception("HWND unavailable")):
                    dispatcher._release_com_safe()

                    call_args = mock_run.call_args[0][0]
                    assert "/IM" in call_args, f"Expected /IM fallback, got: {call_args}"
                    assert "MSACCESS.EXE" in call_args, f"Expected MSACCESS.EXE in fallback, got: {call_args}"


class TestComDispatcherLogging:
    """Test that bare except blocks in _release_com_safe log warnings instead of silently passing."""

    def test_release_com_safe_logs_cleanup_warnings(self):
        """_release_com_safe must log warnings when cleanup operations fail."""
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher._access_app = None
        dispatcher._ado_conn = MagicMock()
        dispatcher._current_db = MagicMock()

        # MockADO.Close() raises — should be caught and logged
        dispatcher._ado_conn.Close.side_effect = RuntimeError("ADO already closed")

        with patch("ms_access_mcp.adapters.com_dispatcher.logger") as mock_logger:
            dispatcher._release_com_safe()

            # logger.warning should have been called for the ADO error
            mock_logger.warning.assert_called()
            # Verify the warning message mentions the error
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("ADO Close" in c or "RuntimeError" in c for c in warning_calls)