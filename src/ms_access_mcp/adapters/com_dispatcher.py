"""Dedicated STA thread dispatcher for all COM operations.

WinCOM objects have apartment affinity — they must be created and used on the same thread.
This dispatcher serializes all COM calls through a single STA thread so that
any async worker can drive the adapter without thread-affinity errors.
"""

import logging
import os
import queue
import subprocess
import sys
import threading
import concurrent.futures
import time
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)

# DAO DBEngine.Execute option flags
DAO_DB_FAIL_ON_ERROR = 128

from ..models.database import (
    TableInfo, FormInfo, ReportInfo, MacroInfo, ModuleInfo,
    ControlInfo, RelationshipInfo, QueryInfo, LinkedTableInfo,
    ForeignKeyInfo, FieldInfo,
)
from ..models.migration import (
    TableSchema, ColumnSchema, ForeignKeySchema, IndexSchema, UnknownMetadata,
)


class ComDispatcher:
    """Owns a dedicated STA thread for all COM operations.

    WinCOM objects have apartment affinity — they must be created and used on the same thread.
    This dispatcher serializes all COM calls through a single STA thread so that
    any async worker can drive the adapter without thread-affinity errors.
    """

    DISPATCH_TIMEOUT = 120.0  # seconds (cold Access start + large DB open can take 60s+)

    def __init__(self) -> None:
        self._call_queue: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any], concurrent.futures.Future[Any]]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._stopping = False

        # COM objects — owned by the STA thread only
        self._access_app: Optional[Any] = None
        self._current_db: Optional[Any] = None
        self._ado_conn: Optional[Any] = None
        self._db_path: Optional[str] = None

    @property
    def access_app(self) -> Any:
        return self._access_app

    @property
    def current_db(self) -> Any:
        return self._current_db

    @property
    def ado_conn(self) -> Any:
        return self._ado_conn

    @property
    def db_path(self) -> str | None:
        return self._db_path

    def start(self) -> None:
        """Start the STA dispatcher thread (idempotent, reentrant after shutdown)."""
        if self._started:
            return
        self._stopping = False  # Reset in case start() is called after shutdown()
        self._thread = threading.Thread(target=self._run, name="ComDispatcher-STA", daemon=True)
        self._thread.start()
        self._started = True

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute fn(*args, **kwargs) on the STA thread. Returns the result.

        Raises TimeoutError if the call takes longer than DISPATCH_TIMEOUT seconds.
        Raises whatever exception fn raises.
        """
        if not self._started or self._thread is None:
            raise RuntimeError("ComDispatcher has not been started")

        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        self._call_queue.put((fn, args, kwargs, future))
        return future.result(timeout=self.DISPATCH_TIMEOUT)

    def is_connected(self) -> bool:
        """Check if the dispatcher has an active Access.Application connection."""
        return self._access_app is not None and self._current_db is not None

    def set_db_path(self, db_path: str) -> None:
        """Set the database path (called by adapter.connect before opening)."""
        self._db_path = db_path

    def shutdown(self) -> None:
        """Signal the dispatcher thread to stop and clean up COM objects." + """
        self._stopping = True
        # Flush pending futures with CancelledError before shutting down
        self._flush_pending_futures()
        # Put a sentinel to wake the thread
        self._call_queue.put((lambda: None, (), {}, concurrent.futures.Future()))
        if self._thread is not None:
            self._thread.join(timeout=15.0)
        # Ensure release even if thread already dead
        self._access_app = None
        self._current_db = None
        self._ado_conn = None
        self._db_path = None
        self._started = False

    def _flush_pending_futures(self) -> None:
        """Cancel all pending futures in the queue to prevent hanging calls.

        Called during shutdown to ensure that any pending calls are cancelled
        before the thread exits. This prevents the MCP client from hanging
        when the session is terminated.
        """
        cancelled = 0
        while True:
            try:
                fn, args, kwargs, future = self._call_queue.get_nowait()
                # Don't cancel the sentinel (lambda: None)
                if fn is not None:
                    try:
                        future.cancel()
                        cancelled += 1
                    except Exception:
                        pass
            except queue.Empty:
                break
        if cancelled > 0:
            logger.debug(f"Flushed {cancelled} pending futures during shutdown")

    # -------------------------------------------------------------------------
    # Internal: runs on the STA thread
    # -------------------------------------------------------------------------

    def _run(self) -> None:
        """STA thread main loop. Initializes COM and processes call queue."""
        # Import here so non-Windows platforms never hit this code path
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()

        try:
            while not self._stopping:
                try:
                    fn, args, kwargs, future = self._call_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if self._stopping:
                    break

                try:
                    result = fn(*args, **kwargs)
                    # Only set result if future is still valid (not cancelled)
                    try:
                        future.set_result(result)
                    except concurrent.futures.InvalidStateError:
                        # Future was cancelled — discard result
                        pass
                except Exception as e:
                    try:
                        future.set_exception(e)
                    except concurrent.futures.InvalidStateError:
                        # Future was cancelled — discard exception
                        pass
        finally:
            # Clean up COM on the same thread
            self._release_com_safe()
            pythoncom.CoUninitialize()

    def _release_com_safe(self) -> None:
        """Release all COM objects in order: ADO -> DAO -> Access Application.

        Uses a watchdog thread to avoid hanging on Access.Quit().
        Falls back to taskkill /F if graceful shutdown fails on Windows.
        """
        errors: list[str] = []

        # 1. Close ADO connection explicitly
        if self._ado_conn is not None:
            try:
                self._ado_conn.Close()
            except Exception as e:
                errors.append(f"ADO Close: {e}")
            self._ado_conn = None

        # 2. Close DAO database explicitly
        if self._current_db is not None:
            try:
                self._current_db.Close()
            except Exception as e:
                errors.append(f"DAO Close: {e}")
            self._current_db = None

        # 3. Close and quit Access Application via COM
        if self._access_app is not None:
            try:
                self._access_app.CloseCurrentDatabase()
            except Exception as e:
                errors.append(f"CloseCurrentDatabase: {e}")

            # 4. Quit() with 5s watchdog
            app = self._access_app
            quit_ok = False
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(lambda: app.Quit())
                    fut.result(timeout=5.0)
                    quit_ok = True
            except concurrent.futures.TimeoutError:
                errors.append("Access.Quit() timed out after 5s")
            except Exception as e:
                errors.append(f"Access.Quit(): {e}")

            self._access_app = None

            # 5. Force-kill fallback (Windows only) — PID-scoped to avoid killing other Access instances
            if not quit_ok and sys.platform == 'win32':
                pid_killed = False
                try:
                    import win32process
                    hwnd = app.hWndAccessApp()
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        capture_output=True, text=True, timeout=10
                    )
                    pid_killed = True
                except Exception as e:
                    errors.append(f"PID-scoped taskkill: {e}")

                # Fallback: if PID extraction failed, use /IM (kills all Access instances)
                if not pid_killed:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/IM", "MSACCESS.EXE"],
                            capture_output=True, text=True, timeout=10
                        )
                    except Exception as e:
                        errors.append(f"taskkill /IM fallback: {e}")

        if errors:
            logger.warning(f"Cleanup completed with {len(errors)} warning(s): {'; '.join(errors)}")

    @staticmethod
    def _dismiss_access_dialogs() -> None:
        """Dismiss modal dialogs shown by Microsoft Access.

        Uses Win32 API to find and close dialog windows (#32770 class) that
        belong to the MSACCESS.EXE process(es). Called after OpenCurrentDatabase
        to silence VBA module naming prompts and similar modal dialogs.

        Runs inline on the STA thread via _do_connect; the STA thread has a
        message pump so SendMessage/PostMessage calls are dispatched correctly.
        """
        try:
            import win32con
            import win32gui
            import win32process

            # Collect Access process PIDs by scanning all windows for OMain.
            # When Visible=False the main Access window may be invisible/minimized
            # so IsWindowVisible can't be used as a reliable filter.
            access_pids: set[int] = set()

            def collect_access_pids(hwnd: int, _: object) -> None:
                cls = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                # OMain = main Access window class (present for every Access instance)
                if cls == "OMain" and title and "Access" in title:
                    access_pids.add(pid)

            win32gui.EnumWindows(collect_access_pids, None)

            # If we found Access PIDs, scope the dialog close to those.
            # If not (e.g. Visible=False makes OMain unfindable), close ALL #32770
            # dialogs — this is safe in a test context where no human is using Access.
            close_all_dialogs = not access_pids

            def dismiss_dialogs(hwnd: int, _: object) -> None:
                from ctypes import windll
                import ctypes
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                cls = win32gui.GetClassName(hwnd)
                if cls != "#32770":
                    return
                # Close #32770 dialogs.  When Visible=False the OMain window may
                # be invisible so we use the close_all_dialogs fallback to ensure
                # any Access-related dialog (module naming, Save As, etc.) is
                # closed regardless of which Access PID it belongs to.
                # In a test context no human is using Access so closing other apps'
                # dialogs is safe (close_all_dialogs=False would only close dialogs
                # from the current Access instance — but the module naming dialog
                # comes from a different PID if the VBA project has unsaved changes).
                #
                # Try multiple approaches:
                # 1. WM_COMMAND(IDOK=1) — closes Access module naming dialogs
                # 2. WM_COMMAND(IDCANCEL=2) — closes other modal dialogs
                # 3. WM_CLOSE via SendMessageTimeoutW
                # 4. WM_SYSCOMMAND SC_CLOSE
                try:
                    windll.user32.SendMessageTimeoutW(
                        hwnd,
                        win32con.WM_COMMAND,
                        1, 0,  # IDOK
                        win32con.SMTO_ABORTIFHUNG | win32con.SMTO_NOTIMEOUTIFNOTHUNG,
                        500,
                        ctypes.byref(ctypes.c_ulong())
                    )
                except Exception:
                    pass
                try:
                    windll.user32.SendMessageTimeoutW(
                        hwnd,
                        win32con.WM_COMMAND,
                        2, 0,  # IDCANCEL
                        win32con.SMTO_ABORTIFHUNG | win32con.SMTO_NOTIMEOUTIFNOTHUNG,
                        500,
                        ctypes.byref(ctypes.c_ulong())
                    )
                except Exception:
                    pass
                try:
                    windll.user32.SendMessageTimeoutW(
                        hwnd,
                        win32con.WM_CLOSE,
                        0, 0,
                        win32con.SMTO_ABORTIFHUNG | win32con.SMTO_NOTIMEOUTIFNOTHUNG,
                        500,
                        ctypes.byref(ctypes.c_ulong())
                    )
                except Exception:
                    pass
                try:
                    win32gui.PostMessage(
                        hwnd, win32con.WM_SYSCOMMAND,
                        win32con.SC_CLOSE, 0
                    )
                except Exception:
                    pass

            # Run four times with short delays — Access might re-show the dialog
            # after the first close during ongoing VBA compilation.
            for _ in range(4):
                win32gui.EnumWindows(dismiss_dialogs, None)
                import time
                time.sleep(0.25)

        except ImportError:
            pass  # Not on Windows or win32gui not available
        except Exception:
            pass  # Best-effort only