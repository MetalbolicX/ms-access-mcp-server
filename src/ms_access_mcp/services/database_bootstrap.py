"""Database bootstrap service — creates blank ``.accdb`` files via DAO.

Implements REQ-1 (DAO create), REQ-2 (STA + finally cleanup), and
REQ-8 (non-Windows platform guard) of the
``create-access-database-from-scratch`` spec. The service is a thin
typed-envelope translation layer over :class:`DaoAdapter.create_database`;
the actual COM work lives in the adapter and dispatcher.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

from ..adapters.com_dispatcher import DEFAULT_DB_LOCALE, DEFAULT_DB_VERSION
from ..adapters.dao import DaoAdapter, DaoOperationError

# Re-export the locale/version constants from the dispatcher so callers
# can import them from one place. The dispatcher owns the value; the
# service is a thin façade.
__all__ = [
    "DEFAULT_DB_LOCALE",
    "DEFAULT_DB_VERSION",
    "PLATFORM_UNSUPPORTED_ERROR",
    "DatabaseBootstrapResult",
    "create_blank_database",
]

logger = logging.getLogger(__name__)

# Typed error string returned in :class:`DatabaseBootstrapResult.error`
# when the host is not Windows. Pinned so callers/tests can match on
# the exact value rather than parsing exception text.
PLATFORM_UNSUPPORTED_ERROR = "PlatformUnsupported"


@dataclass
class DatabaseBootstrapResult:
    """Typed return value of :func:`create_blank_database`.

    Attributes:
        success: ``True`` iff the ``.accdb`` was created on disk.
        path: Absolute path the caller asked to create (echoed back).
        error: ``None`` on success; a human-readable string on failure.
            ``PLATFORM_UNSUPPORTED_ERROR`` when the host is non-Windows.
    """

    success: bool
    path: str
    error: str | None = None


def create_blank_database(path: str) -> DatabaseBootstrapResult:
    """Create a blank ``.accdb`` at ``path`` on Windows via DAO.

    Returns :class:`DatabaseBootstrapResult` with ``success=True`` on
    success, or ``success=False`` plus a typed ``error`` on failure —
    including non-Windows hosts (``error=PLATFORM_UNSUPPORTED_ERROR``).

    The caller is responsible for PathGuard validation; this service
    does not re-validate the path (REQ-3 lives in the MCP tool layer,
    PR 2).
    """
    # REQ-8: short-circuit on non-Windows BEFORE we touch the adapter.
    # The adapter module is pure-Python at import time (no win32 calls),
    # so importing it on non-Windows is safe; we still avoid the
    # DaoAdapter ctor because the platform check is the spec's
    # authoritative "no pywin32 import on non-Windows" gate.
    if sys.platform != "win32":
        return DatabaseBootstrapResult(
            success=False,
            path=path,
            error=PLATFORM_UNSUPPORTED_ERROR,
        )

    adapter: DaoAdapter = DaoAdapter(db_path=path)
    try:
        created = adapter.create_database(path)
    except DaoOperationError as e:
        logger.error("Database bootstrap failed for %s: %s", path, e.message)
        return DatabaseBootstrapResult(success=False, path=path, error=e.message)
    except Exception as e:  # last-resort safety net for the service
        # Anything the adapter failed to wrap surfaces as a typed
        # failure rather than an unhandled exception.
        logger.exception("Database bootstrap crashed for %s", path)
        return DatabaseBootstrapResult(success=False, path=path, error=str(e))

    if not created:
        return DatabaseBootstrapResult(
            success=False,
            path=path,
            error="DAO create_database returned False",
        )

    return DatabaseBootstrapResult(success=True, path=path)
