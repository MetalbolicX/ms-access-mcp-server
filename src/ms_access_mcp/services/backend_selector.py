"""BackendSelector — centralized adapter selection service.

This module provides a stateless factory for selecting between ODBC and COM
adapters based on explicit arguments, environment variables, and requested
capabilities.

REQ-1 through REQ-24 of the backend-selector SDD are implemented here.
"""

from enum import Flag, auto
from typing import Literal, cast

import os
import sys


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


# Valid ACCESS_MCP_BACKEND values (case-insensitive)
_VALID_BACKEND_VALUES = frozenset({"auto", "odbc", "com"})

# Capabilities that require the COM backend
_COM_ONLY_CAPS = (
    BackendCapabilities.CAN_HANDLE_VBA
    | BackendCapabilities.CAN_HANDLE_FORMS
    | BackendCapabilities.CAN_HANDLE_REPORTS
    | BackendCapabilities.CAN_HANDLE_MACROS
    | BackendCapabilities.CAN_COMPACT
    | BackendCapabilities.CAN_CREATE_LINKED_TABLE
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


class BackendSelector:
    """Stateless factory for selecting and constructing adapter instances.

    REQ-16, REQ-18: This class maintains no internal state. Every call to
    get_adapter() evaluates env vars fresh, so changes between calls are respected.
    """

    @staticmethod
    def get_adapter(
        db_path: str,
        backend: Literal["odbc", "com", "auto"] | None = None,
        capabilities: BackendCapabilities | None = None,
    ):
        """Resolve the backend and return the appropriate adapter instance.

        Resolution order (REQ-2, REQ-5):
        1. Explicit ``backend`` argument takes highest precedence.
        2. ``ACCESS_MCP_BACKEND`` environment variable (read at call time).
        3. ``"auto"`` as default.

        With ``backend="auto"`` (REQ-21):
        - If any capability flag is COM-only → resolve to ``"com"``
        - Otherwise → resolve to ``"odbc"``

        Raises (REQ-3, REQ-6, REQ-19):
        - ``BackendCapabilityMismatchError`` when ODBC is forced but a
          COM-only capability is requested.
        - ``BackendUnavailableError`` when COM is requested on a non-Windows
          platform.

        REQ-16: Returns a new adapter instance on every call. No caching.
        """
        # Resolve backend: explicit arg → env var → "auto"
        if backend is not None:
            resolved = _normalize_backend(backend)
        else:
            env_value = os.environ.get("ACCESS_MCP_BACKEND", "auto")
            resolved = _normalize_backend(env_value)

        # Determine if any capability requires COM
        requires_com_flag = _requires_com(capabilities)

        # Auto-resolution: choose based on capability requirements
        if resolved == "auto":
            resolved = "com" if requires_com_flag else "odbc"

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

        # ODBC path
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        return OdbcAdapter(db_path=db_path)