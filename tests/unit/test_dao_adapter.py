"""Unit tests for DaoAdapter scaffold + DaoOperationError.

Slice 1 of dao-first-linked-tables-properties: pins the contracts that
must hold from day one so subsequent slices (PR 2+) can build on a
stable shape.
"""

from __future__ import annotations

import pytest

from ms_access_mcp.adapters.com_dispatcher import ComDispatcher
from ms_access_mcp.adapters.dao import DaoAdapter, DaoOperationError


class TestDaoOperationError:
    """DaoOperationError is the canonical DAO failure surface."""

    def test_is_exception_subclass(self):
        assert issubclass(DaoOperationError, Exception)

    def test_message_only_constructor(self):
        err = DaoOperationError("open failed")
        assert err.message == "open failed"
        assert "open failed" in str(err)

    def test_cause_preserved(self):
        cause = RuntimeError("file in use")
        err = DaoOperationError("open failed", cause=cause)
        assert err.cause is cause

    def test_raise_and_catch_round_trip(self):
        with pytest.raises(DaoOperationError) as exc_info:
            raise DaoOperationError("boom")
        assert exc_info.value.message == "boom"


class TestDaoAdapterConstruction:
    """DaoAdapter ctor must accept db_path and optional dispatcher."""

    def test_construction_with_db_path_only(self):
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb")
        assert adapter._db_path == r"C:\fake\db.accdb"
        assert isinstance(adapter._dispatcher, ComDispatcher)

    def test_construction_with_injected_dispatcher(self):
        dispatcher = ComDispatcher()
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)
        assert adapter._dispatcher is dispatcher

    def test_is_connected_false_at_construction(self):
        """A fresh adapter is not connected — connect() is a later-slice concern."""
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb")
        assert adapter.is_connected() is False
