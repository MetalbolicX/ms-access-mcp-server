"""DaoAdapter scaffold + DaoSession helper (slice 1 of dao-first-linked-tables-properties).

* :class:`DaoSession` — reusable DAO open/close context manager,
  extracted from :class:`DaoRelationshipReader`.
* :class:`DaoOperationError` — canonical DAO failure surface.
* :class:`DaoAdapter` — Windows-only DAO backend. Slice 1 only
  establishes the ctor + the dispatcher seam; ``connect()`` lives in
  slice 2.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

from .com_dispatcher import ComDispatcher

# ===================================================================== #
# DaoSession — context manager
# ===================================================================== #


class DaoSession:
    """Context manager for a short-lived DAO ``Database`` handle.

    Args:
        db_path: Absolute path to the ``.accdb`` or ``.mdb`` file.
        password: Optional database password; appended as ``;PWD=...``.
        read_only: ``True`` (default) opens with ``ReadOnly=True`` so
            concurrent ODBC readers are not blocked.

    The caller drives ``DaoSession`` from inside ``dispatcher.call(...)``
    so the open/close happens on the STA thread.
    """

    def __init__(
        self,
        db_path: str,
        password: str = "",
        read_only: bool = True,
    ) -> None:
        self.path: str = db_path
        self._password: str = password
        self.read_only: bool = read_only
        self.db: Any | None = None

    def __enter__(self) -> DaoSession:
        self.db = self._open_database()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # Returning None → do not suppress body exceptions. The close
        # is the finally-equivalent guarantee.
        self._close()

    def close(self) -> None:
        """Close the DAO database if open. Idempotent."""
        self._close()

    def _open_database(self) -> Any:
        import win32com.client  # type: ignore[import-not-found]

        engine = win32com.client.Dispatch("DAO.DBEngine.120")
        connect_str = f";PWD={self._password}" if self._password else ""
        return engine.OpenDatabase(self.path, False, self.read_only, connect_str)

    def _close(self) -> None:
        if self.db is None:
            return
        try:
            self.db.Close()
        except Exception:
            pass
        finally:
            self.db = None


# ===================================================================== #
# DaoOperationError + DaoAdapter
# ===================================================================== #


class DaoOperationError(Exception):
    """Raised by DaoAdapter for any DAO operation failure.

    Carries ``message`` and the original ``cause`` exception so callers
    can log, mark the adapter unhealthy, and fall back to ODBC.
    """

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.cause: BaseException | None = cause


class DaoAdapter:
    """Windows-only DAO backend, scaffolded in slice 1.

    Slice 1 only establishes the ctor + the dispatcher seam;
    ``connect()`` and the data/schema/linked-tables surface land in
    slices 2+ so each PR stays under the 400-line review budget.

    Args:
        db_path: Absolute path to the ``.accdb`` or ``.mdb`` file.
        dispatcher: Optional :class:`ComDispatcher`. When ``None``
            (default) the adapter owns its own. Slice 5 will inject
            ``WinComAdapter``'s dispatcher to share the STA thread.
    """

    def __init__(
        self,
        db_path: str,
        dispatcher: ComDispatcher | None = None,
    ) -> None:
        self._db_path: str = db_path
        self._dispatcher: ComDispatcher = dispatcher or ComDispatcher()

    def is_connected(self) -> bool:
        """Return ``False`` in slice 1 — the adapter is not yet connectable.

        Slice 2 will open a long-lived DAO ``Database`` in ``connect()``
        and flip this to ``True`` based on the dispatcher's handle state.
        """
        return False
