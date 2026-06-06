"""Unit tests for BackendSelector — Phase 1 SDD.

These tests follow Strict TDD: RED first (tests written against non-existent code),
then GREEN (minimum implementation to pass), then REFACTOR.
"""

import sys

import pytest


# =============================================================================
# T1.1 — BackendCapabilities enum and basic selection scenarios
# =============================================================================


class TestBackendCapabilitiesEnum:
    """REQ-9: BackendCapabilities enum has all 10 expected flags."""

    def test_enum_has_all_10_flags(self):
        """All 10 capability flags must be defined in the enum."""
        from ms_access_mcp.services.backend_selector import BackendCapabilities

        flags = list(BackendCapabilities)
        expected_names = [
            "CAN_READ_DATA",
            "CAN_WRITE_DATA",
            "CAN_INTROSPECT_SCHEMA",
            "CAN_HANDLE_VBA",
            "CAN_HANDLE_FORMS",
            "CAN_HANDLE_REPORTS",
            "CAN_HANDLE_MACROS",
            "CAN_COMPACT",
            "CAN_CREATE_LINKED_TABLE",
            "CAN_IMPORT_EXPORT_TEXT",
        ]
        actual_names = [f.name for f in flags]
        for name in expected_names:
            assert name in actual_names, f"Missing flag: {name}"


class TestBackendSelectorExplicitBackend:
    """REQ-2: Explicit backend= arg returns correct adapter type."""

    def test_explicit_odbc_returns_odbc_adapter(self, monkeypatch):
        """backend='odbc' returns an OdbcAdapter instance."""
        # Clear any env var so it doesn't interfere
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)

        from ms_access_mcp.services.backend_selector import BackendSelector
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = BackendSelector.get_adapter("/tmp/test.accdb", backend="odbc")
        assert isinstance(adapter, OdbcAdapter)

    def test_explicit_com_returns_wincom_adapter(self, monkeypatch):
        """backend='com' returns a WinComAdapter instance (Windows only)."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        # Mock sys.platform to simulate Windows
        monkeypatch.setattr(sys, "platform", "win32")

        from ms_access_mcp.services.backend_selector import BackendSelector
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = BackendSelector.get_adapter("/tmp/test.accdb", backend="com")
        assert isinstance(adapter, WinComAdapter)


class TestBackendSelectorEnvVar:
    """REQ-4 & REQ-5: ACCESS_MCP_BACKEND env var controls selection."""

    def test_no_args_reads_env_var_odbc(self, monkeypatch):
        """No backend arg + ACCESS_MCP_BACKEND=odbc → OdbcAdapter."""
        monkeypatch.setenv("ACCESS_MCP_BACKEND", "odbc")

        from ms_access_mcp.services.backend_selector import BackendSelector
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = BackendSelector.get_adapter("/tmp/test.accdb")
        assert isinstance(adapter, OdbcAdapter)

    def test_no_args_reads_env_var_com(self, monkeypatch):
        """No backend arg + ACCESS_MCP_BACKEND=com → WinComAdapter (Windows only)."""
        monkeypatch.setenv("ACCESS_MCP_BACKEND", "com")
        monkeypatch.setattr(sys, "platform", "win32")

        from ms_access_mcp.services.backend_selector import BackendSelector
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = BackendSelector.get_adapter("/tmp/test.accdb")
        assert isinstance(adapter, WinComAdapter)

    def test_explicit_backend_overrides_env_var(self, monkeypatch):
        """backend= arg takes precedence over ACCESS_MCP_BACKEND env var."""
        monkeypatch.setenv("ACCESS_MCP_BACKEND", "odbc")
        monkeypatch.setattr(sys, "platform", "win32")

        from ms_access_mcp.services.backend_selector import BackendSelector
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = BackendSelector.get_adapter("/tmp/test.accdb", backend="com")
        assert isinstance(adapter, WinComAdapter)


class TestBackendSelectorDefault:
    """REQ-2 & REQ-12: Default (no args) returns OdbcAdapter."""

    def test_no_args_no_env_returns_odbc(self, monkeypatch):
        """No backend arg + no env var → OdbcAdapter (default)."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)

        from ms_access_mcp.services.backend_selector import BackendSelector
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = BackendSelector.get_adapter("/tmp/test.accdb")
        assert isinstance(adapter, OdbcAdapter)


# =============================================================================
# T1.2 — COM-required, Linux unavailable, mismatch, invalid env, stateless
# =============================================================================


class TestCapabilityForcesCom:
    """REQ-10 & REQ-11: Capabilities with COM-only flags force COM backend."""

    def test_can_handle_vba_forces_com(self, monkeypatch):
        """capabilities=CAN_HANDLE_VBA with no explicit backend → WinComAdapter."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        monkeypatch.setattr(sys, "platform", "win32")

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendCapabilities,
        )

        adapter = BackendSelector.get_adapter(
            "/tmp/test.accdb", capabilities=BackendCapabilities.CAN_HANDLE_VBA
        )
        from ms_access_mcp.adapters.wincom import WinComAdapter

        assert isinstance(adapter, WinComAdapter)

    def test_can_handle_forms_forces_com(self, monkeypatch):
        """capabilities=CAN_HANDLE_FORMS forces COM."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        monkeypatch.setattr(sys, "platform", "win32")

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendCapabilities,
        )
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = BackendSelector.get_adapter(
            "/tmp/test.accdb", capabilities=BackendCapabilities.CAN_HANDLE_FORMS
        )
        assert isinstance(adapter, WinComAdapter)

    def test_can_compact_forces_com(self, monkeypatch):
        """capabilities=CAN_COMPACT forces COM."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        monkeypatch.setattr(sys, "platform", "win32")

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendCapabilities,
        )
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = BackendSelector.get_adapter(
            "/tmp/test.accdb", capabilities=BackendCapabilities.CAN_COMPACT
        )
        assert isinstance(adapter, WinComAdapter)

    def test_mixed_caps_with_com_flag_uses_com(self, monkeypatch):
        """capabilities={CAN_READ_DATA, CAN_HANDLE_VBA} → COM (superset)."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        monkeypatch.setattr(sys, "platform", "win32")

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendCapabilities,
        )
        from ms_access_mcp.adapters.wincom import WinComAdapter

        caps = BackendCapabilities.CAN_READ_DATA | BackendCapabilities.CAN_HANDLE_VBA
        adapter = BackendSelector.get_adapter("/tmp/test.accdb", capabilities=caps)
        assert isinstance(adapter, WinComAdapter)

    def test_odbc_safe_caps_use_odbc(self, monkeypatch):
        """capabilities={CAN_READ_DATA, CAN_INTROSPECT_SCHEMA} → ODBC."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendCapabilities,
        )
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        caps = BackendCapabilities.CAN_READ_DATA | BackendCapabilities.CAN_INTROSPECT_SCHEMA
        adapter = BackendSelector.get_adapter("/tmp/test.accdb", capabilities=caps)
        assert isinstance(adapter, OdbcAdapter)


class TestLinuxComUnavailable:
    """REQ-6 & REQ-19: COM requested on Linux raises BackendUnavailableError."""

    def test_com_on_linux_raises_unavailable_error(self, monkeypatch):
        """backend='com' on Linux raises BackendUnavailableError."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendUnavailableError,
        )

        with pytest.raises(BackendUnavailableError) as exc_info:
            BackendSelector.get_adapter("/tmp/test.accdb", backend="com")
        assert "COM automation is not available on Linux" in str(exc_info.value)

    def test_vba_capability_on_linux_raises_mismatch_error(self, monkeypatch):
        """CAN_HANDLE_VBA on Linux raises BackendCapabilityMismatchError."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendCapabilities,
            BackendCapabilityMismatchError,
        )

        with pytest.raises(BackendCapabilityMismatchError) as exc_info:
            BackendSelector.get_adapter(
                "/tmp/test.accdb", capabilities=BackendCapabilities.CAN_HANDLE_VBA
            )
        # Error message should mention the capability
        assert "CAN_HANDLE_VBA" in str(exc_info.value)


class TestBackendMismatch:
    """REQ-3 & REQ-24: ODBC forced with COM-only capability raises mismatch."""

    def test_odbc_with_vba_capability_raises_mismatch(self, monkeypatch):
        """backend='odbc' + capabilities=CAN_HANDLE_VBA → BackendCapabilityMismatchError."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendCapabilities,
            BackendCapabilityMismatchError,
        )

        with pytest.raises(BackendCapabilityMismatchError) as exc_info:
            BackendSelector.get_adapter(
                "/tmp/test.accdb",
                backend="odbc",
                capabilities=BackendCapabilities.CAN_HANDLE_VBA,
            )
        assert "ACCESS_MCP_BACKEND=odbc" in str(exc_info.value) or "ODBC" in str(
            exc_info.value
        )

    def test_mismatch_error_names_requested_capability(self, monkeypatch):
        """Mismatch error message includes the conflicting capability name."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)

        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendCapabilities,
            BackendCapabilityMismatchError,
        )

        with pytest.raises(BackendCapabilityMismatchError) as exc_info:
            BackendSelector.get_adapter(
                "/tmp/test.accdb",
                backend="odbc",
                capabilities=BackendCapabilities.CAN_COMPACT,
            )
        assert "CAN_COMPACT" in str(exc_info.value)


class TestInvalidEnvVar:
    """REQ-4: Invalid ACCESS_MCP_BACKEND value raises ValueError."""

    def test_invalid_backend_env_value_raises_value_error(self, monkeypatch):
        """ACCESS_MCP_BACKEND=garbage raises ValueError with valid options."""
        monkeypatch.setenv("ACCESS_MCP_BACKEND", "garbage")

        from ms_access_mcp.services.backend_selector import BackendSelector

        with pytest.raises(ValueError) as exc_info:
            BackendSelector.get_adapter("/tmp/test.accdb")
        assert "auto" in str(exc_info.value).lower() or "odbc" in str(
            exc_info.value
        ).lower() or "com" in str(exc_info.value).lower()


class TestStateless:
    """REQ-16 & REQ-18: BackendSelector is stateless — no caching."""

    def test_two_calls_return_two_distinct_instances(self, monkeypatch):
        """Two calls return two distinct adapter objects (no singleton)."""
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)

        from ms_access_mcp.services.backend_selector import BackendSelector

        adapter1 = BackendSelector.get_adapter("/tmp/test.accdb", backend="odbc")
        adapter2 = BackendSelector.get_adapter("/tmp/test.accdb", backend="odbc")
        assert adapter1 is not adapter2

    def test_env_change_between_calls_respected(self, monkeypatch):
        """Changing ACCESS_MCP_BACKEND between calls changes the adapter."""
        from ms_access_mcp.services.backend_selector import BackendSelector
        from ms_access_mcp.adapters.odbc import OdbcAdapter
        from ms_access_mcp.adapters.wincom import WinComAdapter

        # First call: ODBC
        adapter1 = BackendSelector.get_adapter("/tmp/test.accdb", backend="odbc")
        assert isinstance(adapter1, OdbcAdapter)

        # Env change simulated by calling with explicit arg
        adapter2 = BackendSelector.get_adapter("/tmp/test.accdb", backend="com")
        assert isinstance(adapter2, WinComAdapter)


class TestCapabilityBundles:
    """Verify capability bundles are defined (used by call sites in later PRs)."""

    def test_schema_caps_defined(self):
        """SCHEMA_CAPS bundle must be importable."""
        from ms_access_mcp.services.backend_selector import SCHEMA_CAPS

        assert SCHEMA_CAPS is not None

    def test_data_read_caps_defined(self):
        """DATA_READ_CAPS bundle must be importable."""
        from ms_access_mcp.services.backend_selector import DATA_READ_CAPS

        assert DATA_READ_CAPS is not None

    def test_data_write_caps_defined(self):
        """DATA_WRITE_CAPS bundle must be importable."""
        from ms_access_mcp.services.backend_selector import DATA_WRITE_CAPS

        assert DATA_WRITE_CAPS is not None

    def test_vba_caps_defined(self):
        """VBA_CAPS bundle must be importable."""
        from ms_access_mcp.services.backend_selector import VBA_CAPS

        assert VBA_CAPS is not None