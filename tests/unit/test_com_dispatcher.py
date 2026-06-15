"""ComDispatcher unit tests — PID-scoped taskkill (PR 1 Task 1.3 RED)."""

from __future__ import annotations

import concurrent.futures
import sys
from unittest.mock import MagicMock, call, patch

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
            with patch(
                "ms_access_mcp.adapters.com_dispatcher.concurrent.futures.ThreadPoolExecutor"
            ) as mock_tpe_cls:
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
                    assert "/IM" not in call_args, (
                        f"Expected NO /IM in taskkill args, got: {call_args}"
                    )
                    assert "9876" in call_args, (
                        f"Expected PID 9876 in taskkill args, got: {call_args}"
                    )

    def test_release_com_safe_falls_back_to_im_when_hwnd_fails(self):
        """When GetWindowThreadProcessId fails, _release_com_safe must fall back to /IM MSACCESS.EXE."""
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()

        mock_app = MagicMock()
        dispatcher._access_app = mock_app
        dispatcher._ado_conn = MagicMock()
        dispatcher._current_db = MagicMock()

        with patch("ms_access_mcp.adapters.com_dispatcher.subprocess.run") as mock_run:
            with patch(
                "ms_access_mcp.adapters.com_dispatcher.concurrent.futures.ThreadPoolExecutor"
            ) as mock_tpe_cls:
                mock_tpe = MagicMock()
                mock_future = MagicMock()
                mock_future.result.side_effect = concurrent.futures.TimeoutError("Quit timed out")
                mock_tpe.__enter__ = MagicMock(return_value=mock_tpe)
                mock_tpe.__exit__ = MagicMock(return_value=None)
                mock_tpe.submit.return_value = mock_future
                mock_tpe_cls.return_value = mock_tpe

                with patch(
                    "win32process.GetWindowThreadProcessId",
                    side_effect=Exception("HWND unavailable"),
                ):
                    dispatcher._release_com_safe()

                    call_args = mock_run.call_args[0][0]
                    assert "/IM" in call_args, f"Expected /IM fallback, got: {call_args}"
                    assert "MSACCESS.EXE" in call_args, (
                        f"Expected MSACCESS.EXE in fallback, got: {call_args}"
                    )


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


class TestComDispatcherHealthTracking:
    """Slice 1 of dao-first-linked-tables-properties: unhealthy-state flag.

    The flag starts True, flips to False on ``mark_unhealthy()``, and
    resets to True via ``reset_health()`` or ``shutdown()``.
    """

    def test_starts_healthy(self):
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        assert dispatcher.is_healthy() is True

    def test_mark_unhealthy_flips_flag(self):
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.mark_unhealthy()
        assert dispatcher.is_healthy() is False

    def test_mark_unhealthy_is_idempotent(self):
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.mark_unhealthy()
        dispatcher.mark_unhealthy()
        assert dispatcher.is_healthy() is False

    def test_reset_health_restores_flag(self):
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.mark_unhealthy()
        assert dispatcher.is_healthy() is False
        dispatcher.reset_health()
        assert dispatcher.is_healthy() is True

    def test_shutdown_resets_health(self):
        """After shutdown, a fresh dispatcher instance is healthy again.

        ``shutdown()`` tears down the thread and resets the flag, so a
        reconnect (slice 2) starts from a known-good state.
        """
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher.mark_unhealthy()
        dispatcher.shutdown()
        assert dispatcher.is_healthy() is True


class TestComDispatcherIsConnectedDaoOnly:
    """Slice 2 of dao-first-linked-tables-properties: is_connected() in DAO-only mode.

    The dispatcher can hold either an Access.Application + Database
    pair (Access/COM mode) or just a long-lived DAO ``Database``
    handle (DAO-only mode, used by ``DaoAdapter``). ``is_connected()``
    must return ``True`` in both modes when a usable handle is held.
    """

    def test_is_connected_false_when_nothing_open(self):
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        assert dispatcher.is_connected() is False

    def test_is_connected_true_for_dao_only_mode(self):
        """A long-lived DAO handle with no Access.Application is still a valid connection."""
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        # No Access.Application — this is the DAO-only branch.
        dispatcher._access_app = None
        dispatcher._current_db = MagicMock()  # DAO Database handle

        assert dispatcher.is_connected() is True

    def test_is_connected_true_for_access_mode(self):
        """Access/COM mode: both Access.Application and Database must be present.

        Backward-compat pin: this was the original behavior before
        slice 2 of dao-first-linked-tables-properties, and WinCom
        callers (wincom.py:237) depend on it.
        """
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher._access_app = MagicMock()
        dispatcher._current_db = MagicMock()

        assert dispatcher.is_connected() is True

    def test_is_connected_false_for_access_mode_with_missing_db(self):
        """Access mode requires both — if Database is gone, no connection."""
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher._access_app = MagicMock()
        dispatcher._current_db = None

        assert dispatcher.is_connected() is False

    def test_is_connected_false_after_dao_disconnect(self):
        """After close_dao_database clears the handle, is_connected() is False.

        This is the post-disconnect invariant the DaoAdapter relies on.
        """
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        dispatcher = ComDispatcher()
        dispatcher._access_app = None
        dispatcher._current_db = MagicMock()
        assert dispatcher.is_connected() is True

        dispatcher._current_db = None  # simulates close_dao_database
        assert dispatcher.is_connected() is False


# ===================================================================== #
# create-access-database-from-scratch — PR 1 (bootstrap core)
# ===================================================================== #
#
# ComDispatcher.create_dao_database() is the STA-thread entry point for
# blank .accdb creation. Contract (REQ-1 / REQ-2 / REQ-8):
#   * Primary: ``DAO.DBEngine.120.CreateDatabase(path, locale, version)``.
#   * Fallback: ``Access.Application.NewCurrentDatabase(path)``.
#   * Cleanup: every handle is released in ``finally`` (REQ-2, S-4 / S-5).
#   * Non-Windows: typed ``PlatformUnsupported`` error without win32 imports.
#   * Locale/version constants exported as module attributes (REFACTOR).


def _make_inline_dispatcher():
    """Build a dispatcher that runs ``call()`` synchronously.

    Mirrors ``_make_dispatcher_with_db`` from test_dao_adapter.py —
    bypass the "not started" gate and replace ``call`` with an inline
    runner so the inner _do closure executes on the test thread and
    the test can inspect its win32com imports and side effects.
    """
    from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

    dispatcher = ComDispatcher()
    dispatcher._started = True
    dispatcher._thread = True

    def _inline_call(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    dispatcher.call = _inline_call  # type: ignore[method-assign]
    return dispatcher


class TestComDispatcherCreateDaoDatabase:
    """ComDispatcher.create_dao_database() runs DAO CreateDatabase on the STA thread.

    REQ-1: DAO is primary; Access.Application is the fallback.
    REQ-2: every handle is released in finally.
    REQ-8: non-Windows returns ``PlatformUnsupported`` without win32 imports.
    """

    def test_create_dao_database_dispatches_dao_primary(self):
        """Primary: ``DAO.DBEngine.120.CreateDatabase(path, locale, version)``.

        REQ-1: ``dbLangGeneral`` and ``dbVersion120`` (128) are the
        default locale/version. REQ-2 / S-4: the returned Database
        handle is closed in finally.
        """
        from ms_access_mcp.adapters.com_dispatcher import (
            DEFAULT_DB_LOCALE,
            DEFAULT_DB_VERSION,
        )

        dispatcher = _make_inline_dispatcher()
        new_db = MagicMock()
        engine = MagicMock()
        engine.CreateDatabase.return_value = new_db
        win32_module = MagicMock()
        win32_module.client.Dispatch.return_value = engine

        with patch.dict(
            sys.modules, {"win32com": win32_module, "win32com.client": win32_module.client}
        ):
            dispatcher.create_dao_database(r"C:\new\new.accdb")

        # DAO primary path was hit with the canonical locale/version.
        engine.CreateDatabase.assert_called_once_with(
            r"C:\new\new.accdb", DEFAULT_DB_LOCALE, DEFAULT_DB_VERSION
        )
        # Returned Database handle was closed in the finally block.
        new_db.Close.assert_called_once()
        # Access.Application fallback was NOT used.
        assert win32_module.client.Dispatch.call_args_list == [call("DAO.DBEngine.120")]

    def test_create_dao_database_falls_back_to_access_application(self):
        """When DAO.CreateDatabase fails, fall back to Access.Application.

        REQ-1 (fallback): ``Access.Application.NewCurrentDatabase(path)``
        creates the file; ``CloseCurrentDatabase`` + ``Quit`` release
        the handle in finally (REQ-2).
        """
        dispatcher = _make_inline_dispatcher()
        application = MagicMock()

        def _dispatch(prog_id: str):
            if prog_id == "DAO.DBEngine.120":
                raise OSError("DAO not registered")
            return application

        win32_module = MagicMock()
        win32_module.client.Dispatch.side_effect = _dispatch

        with patch.dict(
            sys.modules, {"win32com": win32_module, "win32com.client": win32_module.client}
        ):
            dispatcher.create_dao_database(r"C:\new\new.accdb")

        application.NewCurrentDatabase.assert_called_once_with(r"C:\new\new.accdb")
        application.CloseCurrentDatabase.assert_called_once()
        application.Quit.assert_called_once()

    def test_create_dao_database_releases_handles_on_failure(self):
        """REQ-2 / S-5: Access.Application handle is released in
        ``finally`` even when the create itself raises.
        """
        dispatcher = _make_inline_dispatcher()
        application = MagicMock()
        application.NewCurrentDatabase.side_effect = RuntimeError("Access broken")

        def _dispatch(prog_id: str):
            if prog_id == "DAO.DBEngine.120":
                raise OSError("DAO not registered")
            return application

        win32_module = MagicMock()
        win32_module.client.Dispatch.side_effect = _dispatch

        with patch.dict(
            sys.modules, {"win32com": win32_module, "win32com.client": win32_module.client}
        ):
            with pytest.raises(RuntimeError, match="create_dao_database failed"):
                dispatcher.create_dao_database(r"C:\new\new.accdb")

        # Critical invariant: handle released even though create failed.
        application.CloseCurrentDatabase.assert_called_once()
        application.Quit.assert_called_once()

    def test_create_dao_database_rejects_non_windows(self, monkeypatch):
        """REQ-8: non-Windows hosts return ``PlatformUnsupported``
        without importing ``win32com``. ``sys.modules`` is poisoned
        so any import attempt would raise — reaching the assertion
        proves the short-circuit fired first.
        """
        from ms_access_mcp.adapters.com_dispatcher import ComDispatcher

        monkeypatch.setattr(sys, "platform", "linux")
        dispatcher = ComDispatcher()

        with patch.dict(
            sys.modules,
            {"win32com": None, "win32com.client": None, "pythoncom": None},
        ):
            with pytest.raises(RuntimeError, match="PlatformUnsupported"):
                dispatcher.create_dao_database(r"/tmp/x.accdb")


class TestComDispatcherDbLocaleConstants:
    """Pin the default locale/version constants — shared source of
    truth that the service layer re-exports (REFACTOR).
    """

    def test_default_db_locale_value(self):
        from ms_access_mcp.adapters.com_dispatcher import DEFAULT_DB_LOCALE

        assert DEFAULT_DB_LOCALE == ";LANGID=0x0409;CP=1252;COUNTRY=0"

    def test_default_db_version_value(self):
        from ms_access_mcp.adapters.com_dispatcher import DEFAULT_DB_VERSION

        # dbVersion120 == 128 (Access 2016+ .accdb format).
        assert DEFAULT_DB_VERSION == 128
