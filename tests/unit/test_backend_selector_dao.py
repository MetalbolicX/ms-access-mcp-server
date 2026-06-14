"""Tests for BackendSelector DAO routing (slice 2 of dao-first).

Covers spec scenarios §1/§3 of sdd/dao-first-linked-tables-properties:
* `backend="dao"` on Windows returns a ``DaoAdapter``; on non-Windows raises.
* `auto` on Windows with data caps picks DAO before ODBC.
* `backend_available("dao")` returns False on non-Windows.
* `CAN_CREATE_LINKED_TABLE` is no longer COM-only.
"""

from __future__ import annotations

import sys

import pytest


def _win(mp):
    mp.setattr(sys, "platform", "win32")


def _lnx(mp):
    mp.setattr(sys, "platform", "linux")


class TestValidBackendValues:
    def test_dao_in_frozenset(self):
        from ms_access_mcp.services import backend_selector
        for v in ("auto", "odbc", "com", "dao"):
            assert v in backend_selector._VALID_BACKEND_VALUES

    def test_normalize_dao_case_insensitive(self, monkeypatch):
        _win(monkeypatch)
        from ms_access_mcp.services.backend_selector import _normalize_backend
        assert _normalize_backend("dao") == "dao"
        assert _normalize_backend("DAO") == "dao"


class TestBackendAvailable:
    @pytest.mark.parametrize(
        "backend,platform,expected",
        [
            ("odbc", "linux", True),
            ("odbc", "win32", True),
            ("com", "win32", True),
            ("com", "linux", False),
            ("dao", "win32", True),
            ("dao", "linux", False),  # spec: Linux reports dao unavailable
            ("auto", "linux", True),  # auto is a mode, not a backend
        ],
    )
    def test_platform_availability(self, monkeypatch, backend, platform, expected):
        monkeypatch.setattr(sys, "platform", platform)
        from ms_access_mcp.services.backend_selector import backend_available
        assert backend_available(backend) is expected

    def test_garbage_raises_value_error(self):
        from ms_access_mcp.services.backend_selector import backend_available
        with pytest.raises(ValueError):
            backend_available("garbage")


class TestExplicitDaoBackend:
    def test_explicit_dao_on_windows_returns_dao_adapter(self, monkeypatch):
        _win(monkeypatch)
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        from ms_access_mcp.adapters.dao import DaoAdapter
        from ms_access_mcp.services.backend_selector import BackendSelector

        adapter = BackendSelector.get_adapter("/tmp/test.accdb", backend="dao")
        assert isinstance(adapter, DaoAdapter)
        assert adapter._db_path == "/tmp/test.accdb"

    @pytest.mark.parametrize("via", ["arg", "env"])
    def test_dao_on_linux_raises_unavailable(self, monkeypatch, via):
        _lnx(monkeypatch)
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        from ms_access_mcp.services.backend_selector import (
            BackendSelector,
            BackendUnavailableError,
        )

        if via == "arg":
            kwargs = {"backend": "dao"}
        else:
            monkeypatch.setenv("ACCESS_MCP_BACKEND", "dao")
            kwargs = {}

        with pytest.raises(BackendUnavailableError):
            BackendSelector.get_adapter("/tmp/test.accdb", **kwargs)


class TestAutoModeDaoOnWindows:
    @pytest.mark.parametrize(
        "caps_name",
        ["DATA_WRITE_CAPS", "DATA_READ_CAPS"],
    )
    def test_auto_windows_picks_dao(self, monkeypatch, caps_name):
        _win(monkeypatch)
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        from ms_access_mcp.adapters.dao import DaoAdapter
        from ms_access_mcp.services import backend_selector
        from ms_access_mcp.services.backend_selector import BackendSelector

        caps = getattr(backend_selector, caps_name)
        adapter = BackendSelector.get_adapter("/tmp/test.accdb", capabilities=caps)
        assert isinstance(adapter, DaoAdapter)

    def test_auto_linux_data_caps_picks_odbc(self, monkeypatch):
        _lnx(monkeypatch)
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        from ms_access_mcp.adapters.odbc import OdbcAdapter
        from ms_access_mcp.services.backend_selector import (
            DATA_WRITE_CAPS,
            BackendSelector,
        )

        adapter = BackendSelector.get_adapter(
            "/tmp/test.accdb", capabilities=DATA_WRITE_CAPS
        )
        assert isinstance(adapter, OdbcAdapter)


class TestCreateLinkedTableNotComOnly:
    def test_capability_only_resolves_to_dao(self, monkeypatch):
        _win(monkeypatch)
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        from ms_access_mcp.adapters.dao import DaoAdapter
        from ms_access_mcp.services.backend_selector import (
            BackendCapabilities,
            BackendSelector,
        )

        adapter = BackendSelector.get_adapter(
            "/tmp/test.accdb",
            capabilities=BackendCapabilities.CAN_CREATE_LINKED_TABLE,
        )
        assert isinstance(adapter, DaoAdapter)

    def test_odbc_with_capability_does_not_raise_mismatch(self, monkeypatch):
        _win(monkeypatch)
        monkeypatch.delenv("ACCESS_MCP_BACKEND", raising=False)
        from ms_access_mcp.adapters.odbc import OdbcAdapter
        from ms_access_mcp.services.backend_selector import (
            BackendCapabilities,
            BackendSelector,
        )

        adapter = BackendSelector.get_adapter(
            "/tmp/test.accdb",
            backend="odbc",
            capabilities=BackendCapabilities.CAN_CREATE_LINKED_TABLE,
        )
        assert isinstance(adapter, OdbcAdapter)

    def test_capability_removed_from_com_only_set(self):
        from ms_access_mcp.services import backend_selector
        from ms_access_mcp.services.backend_selector import BackendCapabilities

        flag = BackendCapabilities.CAN_CREATE_LINKED_TABLE
        assert flag not in backend_selector._COM_ONLY_CAPS

    @pytest.mark.parametrize(
        "cap",
        [
            "CAN_HANDLE_VBA",
            "CAN_HANDLE_FORMS",
            "CAN_HANDLE_REPORTS",
            "CAN_HANDLE_MACROS",
            "CAN_COMPACT",
            "CAN_IMPORT_EXPORT_TEXT",
        ],
    )
    def test_other_com_only_caps_unchanged(self, cap):
        from ms_access_mcp.services import backend_selector
        from ms_access_mcp.services.backend_selector import BackendCapabilities

        flag = getattr(BackendCapabilities, cap)
        assert flag in backend_selector._COM_ONLY_CAPS
