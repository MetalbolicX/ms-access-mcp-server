"""Unit tests for DaoAdapter lifecycle + DaoOperationError.

Slices 1—2 of dao-first-linked-tables-properties: pins the
construction contract (slice 1) and the connect / disconnect /
is_connected lifecycle (slice 2). Schema, CRUD, and linked-table
surfaces land in slices 3+.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

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
        """A fresh adapter is not connected — connect() is the next step."""
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb")
        assert adapter.is_connected() is False


# ===================================================================== #
# Slice 2 — connection lifecycle
# ===================================================================== #


def _make_adapter_with_mock_dispatcher() -> tuple[DaoAdapter, MagicMock]:
    """Build a DaoAdapter with a MagicMock dispatcher for lifecycle tests.

    The MagicMock stands in for ComDispatcher.start /
    open_dao_database / close_dao_database / mark_unhealthy without
    needing the real STA thread.
    """
    dispatcher = MagicMock(spec=ComDispatcher)
    adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)
    return adapter, dispatcher


class TestDaoAdapterConnect:
    """DaoAdapter.connect() opens the long-lived DAO handle on the STA thread."""

    def test_connect_starts_dispatcher_and_opens_with_defaults(self):
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()

        adapter.connect()

        # Spec §1: Exclusive=False, ReadOnly=False, password empty.
        dispatcher.start.assert_called_once()
        dispatcher.open_dao_database.assert_called_once_with(
            r"C:\fake\db.accdb",
            password="",
            read_only=False,
        )
        # mark_unhealthy must NOT be called on a clean open.
        dispatcher.mark_unhealthy.assert_not_called()
        assert adapter.is_connected() is True

    def test_connect_with_password_passes_through(self):
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()

        adapter.connect(password="secret")

        dispatcher.open_dao_database.assert_called_once_with(
            r"C:\fake\db.accdb",
            password="secret",
            read_only=False,
        )
        # Password is not stored on the adapter — we never persist it.
        assert not hasattr(adapter, "_password") or getattr(adapter, "_password", None) != "secret"

    def test_connect_with_explicit_path_rebinds(self):
        """Spec §1: Reconnect rebinds — operations target the new path only."""
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()

        adapter.connect(db_path=r"C:\other\b.accdb")

        assert adapter._db_path == r"C:\other\b.accdb"
        dispatcher.open_dao_database.assert_called_once_with(
            r"C:\other\b.accdb",
            password="",
            read_only=False,
        )

    def test_connect_failure_wraps_in_dao_operation_error(self):
        """Spec §1 "Degradation and error surface": failure → DaoOperationError."""
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()
        cause = OSError("file in use")
        dispatcher.open_dao_database.side_effect = cause

        with pytest.raises(DaoOperationError) as exc_info:
            adapter.connect()

        assert exc_info.value.cause is cause
        assert "DAO connect failed" in exc_info.value.message
        assert "file in use" in exc_info.value.message

    def test_connect_failure_marks_dispatcher_unhealthy(self):
        """On failure, the dispatcher is marked unhealthy and is_connected() is False."""
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()
        dispatcher.open_dao_database.side_effect = OSError("boom")

        with pytest.raises(DaoOperationError):
            adapter.connect()

        dispatcher.mark_unhealthy.assert_called_once()
        assert adapter.is_connected() is False

    def test_connect_failure_leaves_internal_state_unconnected(self):
        """After a failed connect, the adapter reports False even if a prior connect succeeded."""
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()

        # First connect succeeds → True
        adapter.connect()
        assert adapter.is_connected() is True

        # Second connect fails → False
        dispatcher.open_dao_database.side_effect = OSError("nope")
        with pytest.raises(DaoOperationError):
            adapter.connect()
        assert adapter.is_connected() is False

    def test_connect_idempotent_rebinds_via_dispatcher(self):
        """Calling connect() twice rebinds the dispatcher's handle.

        The dispatcher's ``open_dao_database`` already closes the
        existing handle before opening a new one, so the adapter just
        delegates the rebind.
        """
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()

        adapter.connect()
        adapter.connect()

        assert dispatcher.open_dao_database.call_count == 2
        assert adapter.is_connected() is True


class TestDaoAdapterDisconnect:
    """DaoAdapter.disconnect() closes the long-lived handle. Idempotent."""

    def test_disconnect_calls_dispatcher_close(self):
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()
        adapter.connect()
        assert adapter.is_connected() is True

        adapter.disconnect()

        dispatcher.close_dao_database.assert_called_once()
        assert adapter.is_connected() is False

    def test_disconnect_is_safe_when_not_connected(self):
        """A fresh adapter can be disconnected without raising."""
        adapter, _dispatcher = _make_adapter_with_mock_dispatcher()

        # No connect() called first.
        adapter.disconnect()

        # close_dao_database is still invoked (dispatcher is a no-op
        # when no handle is open), but the adapter state is consistent.
        assert adapter.is_connected() is False

    def test_disconnect_does_not_mark_unhealthy(self):
        """A clean disconnect is not a failure — health is reset on next connect."""
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()
        adapter.connect()
        dispatcher.reset_mock()  # ignore the connect() side effects

        adapter.disconnect()

        dispatcher.mark_unhealthy.assert_not_called()
        assert adapter.is_connected() is False

    def test_disconnect_swallows_close_errors(self):
        """If close_dao_database raises, disconnect still clears the adapter state."""
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()
        adapter.connect()
        dispatcher.close_dao_database.side_effect = RuntimeError("COM already torn down")

        # Must not raise.
        adapter.disconnect()

        assert adapter.is_connected() is False

    def test_disconnect_idempotent(self):
        """Multiple disconnects in a row are all safe."""
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()
        adapter.connect()

        adapter.disconnect()
        adapter.disconnect()
        adapter.disconnect()

        assert dispatcher.close_dao_database.call_count == 3
        assert adapter.is_connected() is False


class TestDaoAdapterIsConnected:
    """is_connected() reflects the adapter's view of the connection state."""

    def test_is_connected_false_at_construction(self):
        adapter, _ = _make_adapter_with_mock_dispatcher()
        assert adapter.is_connected() is False

    def test_is_connected_true_after_successful_connect(self):
        adapter, _ = _make_adapter_with_mock_dispatcher()
        adapter.connect()
        assert adapter.is_connected() is True

    def test_is_connected_false_after_disconnect(self):
        adapter, _ = _make_adapter_with_mock_dispatcher()
        adapter.connect()
        adapter.disconnect()
        assert adapter.is_connected() is False

    def test_is_connected_false_after_failed_connect(self):
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()
        dispatcher.open_dao_database.side_effect = OSError("nope")

        with pytest.raises(DaoOperationError):
            adapter.connect()
        assert adapter.is_connected() is False

    def test_is_connected_reflects_only_this_adapters_state(self):
        """The dispatcher is shared; the adapter tracks its own state.

        Slice 5 will inject WinComAdapter's dispatcher. Until then, this
        test pins that disconnecting one adapter does not affect
        another adapter that shares the same dispatcher mock.
        """
        dispatcher = MagicMock(spec=ComDispatcher)
        a = DaoAdapter(db_path=r"C:\a.accdb", dispatcher=dispatcher)
        b = DaoAdapter(db_path=r"C:\b.accdb", dispatcher=dispatcher)

        a.connect()
        b.connect()
        assert a.is_connected() and b.is_connected()

        a.disconnect()
        assert a.is_connected() is False
        assert b.is_connected() is True  # unaffected by a's disconnect


class TestDaoAdapterReconnectScenario:
    """Spec §1: Reconnect rebinds — disconnect + connect to a new path."""

    def test_disconnect_then_connect_rebinds_path(self):
        """Spec scenario: connected to a.accdb, disconnect+connect(b.accdb)
        → operations target b.accdb only, prior handle closed.
        """
        adapter, dispatcher = _make_adapter_with_mock_dispatcher()

        # Initial connect to a.accdb (via constructor default).
        adapter.connect()
        first_path = adapter._db_path
        assert first_path == r"C:\fake\db.accdb"

        # Reconnect to b.accdb — the spec scenario.
        adapter.disconnect()
        adapter.connect(db_path=r"C:\new\b.accdb")

        assert adapter._db_path == r"C:\new\b.accdb"
        assert adapter.is_connected() is True
        # close_dao_database was called once during disconnect.
        assert dispatcher.close_dao_database.call_count == 1
        # open_dao_database was called twice — once for each path.
        assert dispatcher.open_dao_database.call_count == 2
        # And the second call targets b.accdb.
        second_call = dispatcher.open_dao_database.call_args_list[1]
        assert second_call == call(
            r"C:\new\b.accdb",
            password="",
            read_only=False,
        )
