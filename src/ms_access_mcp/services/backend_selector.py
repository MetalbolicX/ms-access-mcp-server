"""BackendSelector — centralized adapter selection service.

This module provides a stateless factory for selecting between ODBC, COM,
and DAO adapters based on explicit arguments, environment variables, and
requested capabilities.

REQ-1 through REQ-24 of the backend-selector SDD are implemented here.
DAO routing is added in slice 2 of ``dao-first-linked-tables-properties``
(see spec §1 / §3).
"""

from enum import Flag, auto
from typing import Literal, cast

import os
import sys

from ..logging import get_logger

_logger = get_logger(__name__)

# Warning is logged at most once per process so a chatty selector does
# not flood the logs when DAO is unavailable on the host.
_dao_fallback_warned: bool = False


class BackendCapabilities(Flag):
    """Flags describing what operations a backend must support.

    REQ-9: All 10 flags must be defined.
    """

    CAN_READ_DATA = auto()
    CAN_WRITE_DATA = auto()
    CAN_INTROSPECT_SCHEMA = auto()
    CAN_HANDLE_VBA = auto()
    CAN_HANDLE_FORMS = auto()
    CAN_HANDLE_REPORTS = auto()
    CAN_HANDLE_MACROS = auto()
    CAN_COMPACT = auto()
    CAN_CREATE_LINKED_TABLE = auto()
    CAN_IMPORT_EXPORT_TEXT = auto()


# REQ-10: Capability bundles used by call sites (migration.py, cli/main.py)
SCHEMA_CAPS = BackendCapabilities.CAN_INTROSPECT_SCHEMA
DATA_READ_CAPS = (
    BackendCapabilities.CAN_READ_DATA | BackendCapabilities.CAN_INTROSPECT_SCHEMA
)
DATA_WRITE_CAPS = (
    BackendCapabilities.CAN_READ_DATA
    | BackendCapabilities.CAN_WRITE_DATA
    | BackendCapabilities.CAN_INTROSPECT_SCHEMA
)
VBA_CAPS = BackendCapabilities.CAN_HANDLE_VBA | BackendCapabilities.CAN_INTROSPECT_SCHEMA


class BackendCapabilityMismatchError(Exception):
    """Raised when requested capabilities require a backend that is unavailable.

    REQ-3, REQ-23, REQ-24.
    """

    pass


class BackendUnavailableError(Exception):
    """Raised when a backend is explicitly requested but unavailable on the platform.

    REQ-6, REQ-19.
    """

    pass


# Valid ACCESS_MCP_BACKEND values (case-insensitive).
# "dao" was added in slice 2 of dao-first-linked-tables-properties — DAO is
# the new first-choice Windows backend for data, schema, and linked tables.
_VALID_BACKEND_VALUES = frozenset({"auto", "odbc", "com", "dao"})

# Capabilities that require the COM backend.
# CAN_CREATE_LINKED_TABLE was REMOVED in slice 2 of
# dao-first-linked-tables-properties — DAO now owns linked-table operations,
# so the capability is satisfiable on Windows via DAO before COM.
_COM_ONLY_CAPS = (
    BackendCapabilities.CAN_HANDLE_VBA
    | BackendCapabilities.CAN_HANDLE_FORMS
    | BackendCapabilities.CAN_HANDLE_REPORTS
    | BackendCapabilities.CAN_HANDLE_MACROS
    | BackendCapabilities.CAN_COMPACT
    | BackendCapabilities.CAN_IMPORT_EXPORT_TEXT
)


def _normalize_backend(value: str) -> str:
    """Normalize a backend string to lowercase and validate it.

    Raises ValueError if the value is not one of the valid options.
    """
    normalized = value.lower().strip()
    if normalized not in _VALID_BACKEND_VALUES:
        raise ValueError(
            f"Invalid ACCESS_MCP_BACKEND value: {value!r}. "
            f"Expected one of: {', '.join(sorted(_VALID_BACKEND_VALUES))}."
        )
    return normalized


def _requires_com(capabilities: BackendCapabilities | None) -> bool:
    """Return True if any flag in capabilities is COM-only."""
    if capabilities is None:
        return False
    return bool(capabilities & _COM_ONLY_CAPS)


def _com_only_cap_names(capabilities: BackendCapabilities) -> list[str]:
    """Return names of COM-only capability flags present in capabilities."""
    result: list[str] = []
    for flag in BackendCapabilities:
        if flag in capabilities & _COM_ONLY_CAPS:
            result.append(cast(str, flag.name))
    return result


def _is_dao_constructable() -> bool:
    """Return True if the DAO engine can be constructed on this host.

    The probe is intentionally cheap:
    * Non-Windows hosts can never construct DAO → False.
    * Windows hosts need ``win32com`` importable. The actual
      ``Dispatch("DAO.DBEngine.120")`` probe lives in the
      ``DaoAdapter.connect()`` failure path (slice 3+); the selector
      probe just gates on ``win32com`` importability so the selector
      does not point users at a backend that will crash on first call.

    Result is cached implicitly by Python's import cache — repeated
    calls are O(1) once ``win32com.client`` has been imported once.
    """
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # type: ignore[import-not-found]  # noqa: F401
    except Exception:
        return False
    return True


def backend_available(backend: str) -> bool:
    """Return True when the named backend can be used on this host.

    The check is platform-only (Windows / non-Windows). Runtime
    readiness (e.g. Access Runtime installed) is NOT checked here —
    the adapter's ``connect()`` will surface those failures.

    Raises:
        ValueError: if ``backend`` is not a recognised value. This is
            intentional — callers should handle unknown backends the
            same way they handle unknown env-var values.
    """
    normalized = _normalize_backend(backend)
    if normalized == "auto":
        # "auto" is a resolution mode, not a backend — always available.
        return True
    if normalized == "odbc":
        return True  # cross-platform
    if normalized == "com":
        return sys.platform == "win32"
    if normalized == "dao":
        return _is_dao_constructable()
    # _normalize_backend already raised for unknown values; defensive:
    raise ValueError(f"Unknown backend: {backend!r}")


class BackendSelector:
    """Stateless factory for selecting and constructing adapter instances.

    REQ-16, REQ-18: This class maintains no internal state. Every call to
    get_adapter() evaluates env vars fresh, so changes between calls are respected.
    """

    @staticmethod
    def get_adapter(
        db_path: str,
        backend: Literal["odbc", "com", "dao", "auto"] | None = None,
        capabilities: BackendCapabilities | None = None,
    ):
        """Resolve the backend and return the appropriate adapter instance.

        Resolution order (REQ-2, REQ-5):
        1. Explicit ``backend`` argument takes highest precedence.
        2. ``ACCESS_MCP_BACKEND`` environment variable (read at call time).
        3. ``"auto"`` as default.

        With ``backend="auto"``:
        - If any capability flag is COM-only → resolve to ``"com"``.
        - Else if DAO is constructable on this host → resolve to ``"dao"``
          (added in slice 2 of dao-first-linked-tables-properties).
        - Else → resolve to ``"odbc"``.

        Raises (REQ-3, REQ-6, REQ-19):
        - ``BackendCapabilityMismatchError`` when ODBC is forced but a
          COM-only capability is requested.
        - ``BackendUnavailableError`` when COM or DAO is requested on a
          non-Windows platform.

        REQ-16: Returns a new adapter instance on every call. No caching.
        """
        # Resolve backend: explicit arg → env var → "auto"
        # Track the env-var-vs-default origin so the dao/com branches can
        # distinguish "user asked for X" from "auto resolved to X".
        env_value = os.environ.get("ACCESS_MCP_BACKEND", "auto")
        env_explicit = "ACCESS_MCP_BACKEND" in os.environ
        if backend is not None:
            resolved = _normalize_backend(backend)
        else:
            resolved = _normalize_backend(env_value)

        # Determine if any capability requires COM
        requires_com_flag = _requires_com(capabilities)

        # Auto-resolution: prefer COM (for COM-only caps) over DAO over ODBC.
        if resolved == "auto":
            if requires_com_flag:
                resolved = "com"
            elif _is_dao_constructable():
                resolved = "dao"
            else:
                resolved = "odbc"

        # Validate: ODBC backend cannot satisfy COM-only capabilities
        if resolved == "odbc" and requires_com_flag:
            # capabilities is verified non-None here by the requires_com_flag check
            assert capabilities is not None
            cap_names = _com_only_cap_names(capabilities)
            cap_list = [f.name for f in BackendCapabilities if f in capabilities]
            raise BackendCapabilityMismatchError(
                f"ACCESS_MCP_BACKEND=odbc conflicts with capability "
                f"{cap_names[0]} which requires COM. "
                f"(Requested capabilities: {cap_list})"
            )

        # DAO path — Windows-only; falls back to ODBC if engine is missing.
        if resolved == "dao":
            if sys.platform != "win32":
                # DAO requires Windows. If the user asked for dao
                # explicitly (via arg or env var) on a non-Windows
                # platform, surface a BackendUnavailableError. This
                # matches the spec scenario "Explicit dao on Linux →
                # BackendUnavailableError" and the
                # "ACCESS_MCP_BACKEND=dao on Linux MUST raise" rule.
                if backend is not None or env_explicit:
                    raise BackendUnavailableError(
                        "DAO backend is not available on non-Windows platforms. "
                        "Use backend='odbc' or ACCESS_MCP_BACKEND=odbc."
                    )
                # Defensive: should be unreachable because the auto branch
                # only resolves to "dao" when _is_dao_constructable() is True,
                # which already excludes non-Windows. But keep the safety net
                # so a future platform refactor cannot silently regress.
                resolved = "odbc"
            elif not _is_dao_constructable():
                # Windows host, win32com missing → fall back to ODBC.
                # Spec: log WARNING once.
                global _dao_fallback_warned
                if not _dao_fallback_warned:
                    _logger.warning(
                        "DAO backend requested but win32com is not importable. "
                        "Falling back to OdbcAdapter. Install Microsoft Access or "
                        "the Access Runtime to enable DAO."
                    )
                    _dao_fallback_warned = True
                resolved = "odbc"
            else:
                from ms_access_mcp.adapters.dao import DaoAdapter

                return DaoAdapter(db_path=db_path)

        # Validate: COM is Windows-only
        if resolved == "com":
            if sys.platform != "win32":
                # REQ-20: auto mode with COM-only capability on Linux → mismatch (capability unsatisfiable)
                # REQ-6/REQ-19: explicit backend="com" on Linux → unavailable (user made wrong choice)
                # We distinguish by whether the user explicitly chose "com" or auto-resolved to it.
                explicit_com = backend is not None
                if explicit_com:
                    raise BackendUnavailableError(
                        "COM automation is not available on Linux. "
                        "Use backend='odbc' or ACCESS_MCP_BACKEND=odbc."
                    )
                else:
                    # capabilities must be non-None: we only reach this branch
                    # because auto mode resolved to com due to COM-only capabilities
                    assert capabilities is not None
                    cap_names = _com_only_cap_names(capabilities)
                    raise BackendCapabilityMismatchError(
                        f"Capabilities require COM backend ({cap_names[0]}), "
                        f"but COM automation is not available on Linux. "
                        f"Use ACCESS_MCP_BACKEND=odbc or remove the COM-only capability."
                    )
            from ms_access_mcp.adapters.wincom import WinComAdapter

            return WinComAdapter(db_path=db_path)  # type: ignore[reportAbstractUsage]

        # ODBC path (also reached when DAO fell back)
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        return OdbcAdapter(db_path=db_path)
