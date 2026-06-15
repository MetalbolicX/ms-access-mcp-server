"""Unit tests for the database_bootstrap service.

Pin REQ-1 (DAO create), REQ-2 (STA + finally cleanup), REQ-8 (non-Windows
platform guard) before the implementation lands. PR 1 of
``create-access-database-from-scratch`` — bootstrap core only.
"""

from __future__ import annotations

import sys
from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest

# ===================================================================== #
# DatabaseBootstrapResult dataclass shape
# ===================================================================== #


class TestDatabaseBootstrapResultDataclass:
    """``DatabaseBootstrapResult`` is the typed return shape of
    ``create_blank_database`` — three fields: ``success`` (bool),
    ``path`` (str), ``error`` (str | None, default None).
    """

    def test_fields(self):
        from ms_access_mcp.services.database_bootstrap import DatabaseBootstrapResult

        assert {f.name for f in fields(DatabaseBootstrapResult)} == {
            "success",
            "path",
            "error",
        }

    def test_default_and_failure_construction(self):
        from ms_access_mcp.services.database_bootstrap import DatabaseBootstrapResult

        ok = DatabaseBootstrapResult(success=True, path=r"C:\x.accdb")
        assert ok.success is True and ok.path == r"C:\x.accdb" and ok.error is None

        err = DatabaseBootstrapResult(success=False, path=r"C:\x.accdb", error="boom")
        assert err.success is False and err.error == "boom"


# ===================================================================== #
# REQ-8: non-Windows platform guard
# ===================================================================== #


@pytest.mark.parametrize("platform_name", ["linux", "darwin"])
def test_create_blank_database_non_windows_returns_platform_unsupported(monkeypatch, platform_name):
    """REQ-8: non-Windows hosts return ``PlatformUnsupported``."""
    from ms_access_mcp.services.database_bootstrap import create_blank_database

    monkeypatch.setattr(sys, "platform", platform_name)
    result = create_blank_database("/tmp/x.accdb")
    assert result.success is False
    assert result.path == "/tmp/x.accdb"
    assert result.error == "PlatformUnsupported"


def test_create_blank_database_does_not_import_pywin32_on_non_windows(monkeypatch):
    """The service must short-circuit before any ``win32com`` import.

    We poison ``sys.modules`` so any import attempt raises
    ``ImportError`` — reaching the assertion means the short-circuit
    fired before any win32 import was attempted.
    """
    monkeypatch.setattr(sys, "platform", "linux")
    with patch.dict(
        sys.modules,
        {"win32com": None, "win32com.client": None, "pythoncom": None},
    ):
        from ms_access_mcp.services.database_bootstrap import create_blank_database

        result = create_blank_database("/tmp/x.accdb")
    assert result.error == "PlatformUnsupported"


# ===================================================================== #
# Delegation to DaoAdapter.create_database
# ===================================================================== #


class TestCreateBlankDatabaseDelegation:
    """``create_blank_database`` delegates to ``DaoAdapter.create_database``
    and translates the result to ``DatabaseBootstrapResult``.
    """

    def test_delegates_to_dao_adapter_create_database(self, monkeypatch):
        from ms_access_mcp.services import database_bootstrap
        from ms_access_mcp.services.database_bootstrap import create_blank_database

        monkeypatch.setattr(sys, "platform", "win32")
        mock_adapter = MagicMock()
        mock_adapter.create_database.return_value = True
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        with patch.object(database_bootstrap, "DaoAdapter", mock_adapter_cls):
            result = create_blank_database(r"C:\fake\new.accdb")

        mock_adapter_cls.assert_called_once_with(db_path=r"C:\fake\new.accdb")
        mock_adapter.create_database.assert_called_once_with(r"C:\fake\new.accdb")
        assert result.success is True
        assert result.path == r"C:\fake\new.accdb"
        assert result.error is None

    def test_returns_failure_when_dao_returns_false(self, monkeypatch):
        from ms_access_mcp.services import database_bootstrap
        from ms_access_mcp.services.database_bootstrap import create_blank_database

        monkeypatch.setattr(sys, "platform", "win32")
        mock_adapter = MagicMock()
        mock_adapter.create_database.return_value = False

        with patch.object(database_bootstrap, "DaoAdapter", MagicMock(return_value=mock_adapter)):
            result = create_blank_database(r"C:\fake\new.accdb")

        assert result.success is False
        assert result.path == r"C:\fake\new.accdb"
        assert result.error is not None

    def test_returns_failure_when_dao_raises(self, monkeypatch):
        from ms_access_mcp.adapters.dao import DaoOperationError
        from ms_access_mcp.services import database_bootstrap
        from ms_access_mcp.services.database_bootstrap import create_blank_database

        monkeypatch.setattr(sys, "platform", "win32")
        mock_adapter = MagicMock()
        mock_adapter.create_database.side_effect = DaoOperationError("access denied")

        with patch.object(database_bootstrap, "DaoAdapter", MagicMock(return_value=mock_adapter)):
            result = create_blank_database(r"C:\fake\new.accdb")

        assert result.success is False
        assert isinstance(result.error, str)
        assert "access denied" in result.error


# ===================================================================== #
# REFACTOR — shared constants & typed error text
# ===================================================================== #


class TestDatabaseBootstrapConstants:
    """The service re-exports the dispatcher's locale/version constants
    and pins the typed error text. REFACTOR: one source of truth.
    """

    def test_platform_unsupported_error_constant(self):
        from ms_access_mcp.services.database_bootstrap import (
            PLATFORM_UNSUPPORTED_ERROR,
        )

        assert PLATFORM_UNSUPPORTED_ERROR == "PlatformUnsupported"

    def test_create_blank_database_uses_constant_in_result(self, monkeypatch):
        from ms_access_mcp.services.database_bootstrap import (
            PLATFORM_UNSUPPORTED_ERROR,
            create_blank_database,
        )

        monkeypatch.setattr(sys, "platform", "linux")
        result = create_blank_database("/tmp/x.accdb")
        assert result.error == PLATFORM_UNSUPPORTED_ERROR

    def test_locale_version_re_exported_from_dispatcher(self):
        from ms_access_mcp.adapters.com_dispatcher import (
            DEFAULT_DB_LOCALE as DISP_LOCALE,
        )
        from ms_access_mcp.adapters.com_dispatcher import (
            DEFAULT_DB_VERSION as DISP_VERSION,
        )
        from ms_access_mcp.services.database_bootstrap import (
            DEFAULT_DB_LOCALE,
            DEFAULT_DB_VERSION,
        )

        # Same object — single source of truth.
        assert DEFAULT_DB_LOCALE is DISP_LOCALE
        assert DEFAULT_DB_VERSION is DISP_VERSION
        # And the values themselves are the canonical DAO defaults.
        assert DEFAULT_DB_LOCALE == ";LANGID=0x0409;CP=1252;COUNTRY=0"
        assert DEFAULT_DB_VERSION == 128  # dbVersion120
