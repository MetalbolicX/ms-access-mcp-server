"""Unit tests for DaoAdapter lifecycle + DaoOperationError + schema/property surface.

Slices 1—7 of dao-first-linked-tables-properties: pins the
construction contract (slice 1), the connect / disconnect /
is_connected lifecycle (slice 2), the schema/property read
surface (slice 4), the row CRUD + table/index DDL surface (slice 5),
the linked-table surface (slice 6), and the short-lived relationship
reader (``DaoAdapter.read_relationships_short_lived``) that replaces
the deleted ``DaoRelationshipReader`` helper (slice 7). DAO backend
wiring and selector cutover landed in earlier slices.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from ms_access_mcp.adapters.com_dispatcher import ComDispatcher
from ms_access_mcp.adapters.dao import DaoAdapter, DaoOperationError, DaoSession
from ms_access_mcp.models.database import (
    IndexInfo,
    QueryInfo,
    RelationshipInfo,
    TableInfo,
)


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


# ===================================================================== #
# Slice 4 — DAO schema + property read surface
# ===================================================================== #
#
# DaoAdapter delegates to SchemaInspector and DbOperations via the
# shared ComDispatcher. Each test sets up a mock dispatcher with a
# realistic current_db (mocked DAO objects) and verifies that the
# DaoAdapter method returns the expected shape.
#
# Why not mock SchemaInspector/DbOperations directly? Two reasons:
# 1) The spec says output shapes must match the existing
#    TableInfo / QueryInfo / IndexInfo / RelationshipInfo models —
#    testing the end-to-end delegation confirms the shape is
#    preserved without inventing fake "what the helper would return"
#    expectations.
# 2) The SchemaInspector and DbOperations implementations already
#    have their own unit tests. Mocking them here would only verify
#    that DaoAdapter calls the right helper, which is trivial — the
#    real value is in verifying the integration through the dispatcher.


def _make_connected_adapter() -> tuple[DaoAdapter, MagicMock]:
    """Build a DaoAdapter that reports ``is_connected() == True``.

    Returns the adapter and its mock dispatcher. The dispatcher is
    configured so the SchemaInspector / DbOperations methods can be
    called inline (no real STA thread).
    """
    # Use a plain MagicMock (no spec=) so we can freely set private
    # attributes like ``_started`` that DbOperations / SchemaInspector
    # check but that ``spec=ComDispatcher`` would block.
    dispatcher = MagicMock()
    # SchemaInspector and DbOperations gate on dispatcher.is_connected();
    # also some helpers (DbOperations.get_database_properties) gate on
    # dispatcher._started. Make both return True so the helpers execute.
    dispatcher.is_connected.return_value = True
    dispatcher._started = True
    return DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher), dispatcher


def _make_disconnected_adapter() -> tuple[DaoAdapter, MagicMock]:
    """Build a DaoAdapter whose dispatcher reports is_connected=False.

    Used for tests that verify the spec contract: a not-connected
    adapter returns the empty/zero result instead of raising.
    """
    dispatcher = MagicMock()
    dispatcher.is_connected.return_value = False
    dispatcher._started = False
    return DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher), dispatcher


def _make_dispatcher_with_db(db: Any) -> MagicMock:
    """Build a mock dispatcher with a known current_db.

    SchemaInspector / DbOperations reach into ``dispatcher.current_db``
    and call functions via ``dispatcher.call(fn)``. We wire ``call``
    to execute the function inline so the helpers' inner _do()
    closures run on the test thread.
    """
    dispatcher = MagicMock()
    dispatcher.is_connected.return_value = True
    dispatcher._started = True
    dispatcher.current_db = db
    dispatcher.call.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    return dispatcher


def _make_db_with_table_defs(table_defs: list[Any]) -> MagicMock:
    """Build a mock DAO Database that walks TableDefs by index AND iteration.

    SchemaInspector.get_table_schema_plan uses ``for tdef in db.TableDefs``
    (iteration) while get_tables uses ``for i in range(db.TableDefs.Count)``
    (index). Both must work.
    """
    db = MagicMock()
    db.TableDefs.Count = len(table_defs)
    db.TableDefs.__iter__.return_value = iter(table_defs)

    def _tdef_getter(i: int) -> Any:
        return table_defs[i]

    db.TableDefs.side_effect = _tdef_getter
    return db


class _MockDaoTableDefs:
    """DAO TableDefs collection — supports index iteration AND name lookup.

    DAO's ``TableDefs`` is both an iterable collection (used by
    ``for tdef in db.TableDefs``) and a name-keyed accessor
    (``db.TableDefs("Customers")``). MagicMock doesn't handle both
    cleanly out of the box, so this helper provides the same
    interface as a real DAO binding.
    """

    def __init__(self, table_defs: list[Any]) -> None:
        self._tdefs = list(table_defs)
        self.Count = len(self._tdefs)
        # Append/Delete are surfaced as instance attributes so tests
        # can attach ``side_effect`` to them in the same way as a
        # plain MagicMock.
        self.Append = MagicMock()
        self.Delete = MagicMock()

    def __call__(self, key: int | str) -> Any:
        if isinstance(key, str):
            for t in self._tdefs:
                if t.Name == key:
                    return t
            raise KeyError(f"Table {key!r} not found")
        if isinstance(key, int):
            return self._tdefs[key]
        raise TypeError(f"Invalid key type: {type(key)}")

    def __iter__(self):
        return iter(self._tdefs)


def _make_db_with_named_tables(table_defs: list[Any]) -> MagicMock:
    """Build a mock DAO Database that supports name-keyed TableDefs lookup."""
    db = MagicMock()
    db.TableDefs = _MockDaoTableDefs(table_defs)
    return db


class _MockDaoIndexes:
    """DAO Indexes collection — supports iteration over its items."""

    def __init__(self, indexes: list[Any]) -> None:
        self._idxs = list(indexes)
        self.Count = len(self._idxs)

    def __iter__(self):
        return iter(self._idxs)


def _make_tdef(
    name: str,
    fields: list[tuple[str, int]] | None = None,
    attributes: int = 0,
    indexes: list[Any] | None = None,
) -> MagicMock:
    """Build a mock DAO TableDef with optional fields/indexes."""
    tdef = MagicMock()
    tdef.Name = name
    tdef.Attributes = attributes
    field_list = fields or []
    field_mocks: list[MagicMock] = []
    for fname, ftype in field_list:
        f = MagicMock()
        f.Name = fname
        f.Type = ftype
        f.Size = 0
        f.Required = False
        f.AllowZeroLength = True
        f.Attributes = 0
        f.DefaultValue = None
        field_mocks.append(f)
    tdef.Fields.Count = len(field_mocks)
    tdef.Fields.side_effect = lambda i: field_mocks[i]
    # Indexes needs to be iterable (SchemaInspector walks via ``for idx in
    # tdef.Indexes``) AND have a Count attribute.
    idx_mocks = indexes or []
    tdef.Indexes = _MockDaoIndexes(idx_mocks)
    return tdef


def _make_index(name: str, cols: list[str], **flags: bool) -> MagicMock:
    """Build a mock DAO Index with optional primary/unique/ignore_nulls."""
    idx = MagicMock()
    idx.Name = name
    idx.Primary = flags.get("primary", False)
    idx.Unique = flags.get("unique", False)
    idx.IgnoreNulls = flags.get("ignore_nulls", False)
    field_mocks: list[MagicMock] = []
    for c in cols:
        f = MagicMock()
        f.Name = c
        field_mocks.append(f)
    idx.Fields = field_mocks
    return idx


# --------------------------------------------------------------------- #
# Schema read methods — get_tables / get_system_tables / get_queries /
# get_indexes / get_object_metadata / get_table_schema_plan
# --------------------------------------------------------------------- #


class TestDaoAdapterGetTables:
    """DaoAdapter.get_tables() returns user tables via the SchemaInspector."""

    def test_get_tables_returns_user_tables_only(self):
        """2 user + 1 MSys + 1 ~ scratch table → 2 user entries."""
        tdef_user1 = _make_tdef("Customers", fields=[("ID", 4), ("Name", 10)])
        tdef_user2 = _make_tdef("Orders", fields=[("ID", 4), ("Total", 7)])
        tdef_sys = _make_tdef("MSysObjects", fields=[("Id", 4)])
        tdef_tmp = _make_tdef("~tmp", fields=[("X", 4)])
        db = _make_db_with_table_defs([tdef_user1, tdef_user2, tdef_sys, tdef_tmp])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)
        # SchemaInspector and DbOperations wrap a try/except in get_tables
        # so missing record_count falls back to 0 — that's fine for this
        # test since the OpenRecordset call is caught and ignored.
        for t in (tdef_user1, tdef_user2, tdef_sys, tdef_tmp):
            t.OpenRecordset.return_value.EOF = True

        result = adapter.get_tables()

        assert isinstance(result, list)
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"Customers", "Orders"}
        for t in result:
            assert isinstance(t, TableInfo)

    def test_get_tables_empty_when_not_connected(self):
        """Not connected → empty list (does not raise)."""
        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_tables()

        assert result == []

    def test_get_tables_returns_table_info_shape(self):
        """Each entry is a TableInfo with name, fields, record_count."""
        tdef = _make_tdef("Products", fields=[("SKU", 10), ("Price", 7)])
        tdef.OpenRecordset.return_value.EOF = True
        db = _make_db_with_table_defs([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_tables()

        assert len(result) == 1
        t = result[0]
        assert t.name == "Products"
        assert len(t.fields) == 2
        assert {f.name for f in t.fields} == {"SKU", "Price"}


class TestDaoAdapterGetSystemTables:
    """DaoAdapter.get_system_tables() returns system tables via SchemaInspector."""

    def test_get_system_tables_returns_msys_tables(self):
        """2 user + 2 MSys tables → 2 MSys entries."""
        t_user1 = _make_tdef("Users")
        t_user2 = _make_tdef("Orders")
        t_sys1 = _make_tdef("MSysObjects", fields=[("Id", 4)])
        t_sys2 = _make_tdef("MSysQueries", fields=[("Id", 4)])
        db = _make_db_with_table_defs([t_user1, t_user2, t_sys1, t_sys2])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_system_tables()

        assert isinstance(result, list)
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"MSysObjects", "MSysQueries"}

    def test_get_system_tables_empty_when_not_connected(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_system_tables()

        assert result == []


class TestDaoAdapterGetQueries:
    """DaoAdapter.get_queries() returns saved queries via SchemaInspector."""

    def test_get_queries_returns_user_queries(self):
        """2 user + 1 system (~) query → 2 user entries with name/sql/type."""
        q_user1 = MagicMock()
        q_user1.Name = "ActiveOrders"
        q_user1.SQL = "SELECT * FROM Orders WHERE Active = True"
        q_user1.Type = 0  # select
        q_user2 = MagicMock()
        q_user2.Name = "AllCustomers"
        q_user2.SQL = "SELECT * FROM Customers"
        q_user2.Type = 0
        q_sys = MagicMock()
        q_sys.Name = "~TMPCache"
        q_sys.SQL = "SELECT 1"
        q_sys.Type = 0

        db = MagicMock()
        db.QueryDefs.Count = 3
        db.QueryDefs.side_effect = lambda i: [q_user1, q_user2, q_sys][i]
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_queries()

        assert isinstance(result, list)
        assert len(result) == 2
        names = {q.name for q in result}
        assert names == {"ActiveOrders", "AllCustomers"}
        for q in result:
            assert isinstance(q, QueryInfo)
            assert q.sql  # non-empty
        # Spec round-trip scenario: query SQL must round-trip cleanly
        active = next(q for q in result if q.name == "ActiveOrders")
        assert active.sql == "SELECT * FROM Orders WHERE Active = True"

    def test_get_queries_empty_when_not_connected(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_queries()

        assert result == []


class TestDaoAdapterGetIndexes:
    """DaoAdapter.get_indexes() returns all indexes (primary + secondary)."""

    def test_get_indexes_returns_primary_and_secondary(self):
        """PK + 2 secondary indexes → 3 IndexInfo entries."""
        tdef = _make_tdef(
            "Orders",
            indexes=[
                _make_index("PK_Orders", ["OrderID"], primary=True, unique=True),
                _make_index("IX_OrderDate", ["OrderDate"]),
                _make_index("IX_CustomerID", ["CustomerID"]),
            ],
        )
        db = _make_db_with_named_tables([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_indexes("Orders")

        assert isinstance(result, list)
        assert len(result) == 3
        names = {idx.name for idx in result}
        assert names == {"PK_Orders", "IX_OrderDate", "IX_CustomerID"}
        for idx in result:
            assert isinstance(idx, IndexInfo)
        pk = next(idx for idx in result if idx.name == "PK_Orders")
        assert pk.is_primary is True
        assert pk.is_unique is True

    def test_get_indexes_empty_when_not_connected(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_indexes("Orders")

        assert result == []


class TestDaoAdapterGetRelationships:
    """DaoAdapter.get_relationships() filters MSys/~ and returns RelationshipInfo."""

    def test_get_relationships_filters_system_relations(self):
        """Spec scenario: 3 user + 1 system FK → 3 entries; no ~/MSys names."""
        rel_user1 = MagicMock()
        rel_user1.Name = "FK_Orders_Customers"
        rel_user1.Table = "Orders"
        rel_user1.ForeignTable = "Customers"
        rel_user1.Attributes = 256
        f1 = MagicMock()
        f1.Name = "CustomerID"
        f1.ForeignName = "ID"
        rel_user1.Fields.Count = 1
        rel_user1.Fields.side_effect = lambda i: [f1][i]

        rel_user2 = MagicMock()
        rel_user2.Name = "FK_OrderItems_Orders"
        rel_user2.Table = "OrderItems"
        rel_user2.ForeignTable = "Orders"
        rel_user2.Attributes = 0
        f2a = MagicMock()
        f2a.Name = "OrderID"
        f2a.ForeignName = "ID"
        f2b = MagicMock()
        f2b.Name = "LineNo"
        f2b.ForeignName = "LineNo"
        rel_user2.Fields.Count = 2
        rel_user2.Fields.side_effect = lambda i: [f2a, f2b][i]

        rel_user3 = MagicMock()
        rel_user3.Name = "FK_Invoices_Customers"
        rel_user3.Table = "Invoices"
        rel_user3.ForeignTable = "Customers"
        rel_user3.Attributes = 0
        f3 = MagicMock()
        f3.Name = "CustomerID"
        f3.ForeignName = "ID"
        rel_user3.Fields.Count = 1
        rel_user3.Fields.side_effect = lambda i: [f3][i]

        rel_sys = MagicMock()
        rel_sys.Name = "~TMPCache"
        rel_sys.Table = "Whatever"
        rel_sys.ForeignTable = "X"
        rel_sys.Attributes = 0
        rel_sys.Fields.Count = 0

        rel_msys = MagicMock()
        rel_msys.Name = "MSysRelZZZ"
        rel_msys.Table = "Whatever"
        rel_msys.ForeignTable = "Y"
        rel_msys.Attributes = 0
        rel_msys.Fields.Count = 0

        db = MagicMock()
        db.Relations.Count = 5
        db.Relations.side_effect = lambda i: [rel_user1, rel_user2, rel_user3, rel_sys, rel_msys][i]
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_relationships()

        assert isinstance(result, list)
        assert len(result) == 3
        for r in result:
            assert isinstance(r, RelationshipInfo)
            assert not r.name.startswith("~")
            assert not r.name.startswith("MSys")
        names = {r.name for r in result}
        assert names == {
            "FK_Orders_Customers",
            "FK_OrderItems_Orders",
            "FK_Invoices_Customers",
        }

    def test_get_relationships_empty_when_not_connected(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_relationships()

        assert result == []


class TestDaoAdapterGetObjectMetadata:
    """DaoAdapter.get_object_metadata() returns metadata for a named object."""

    def test_get_object_metadata_returns_table_metadata(self):
        """Object named in get_tables() → table metadata dict."""
        tdef = _make_tdef("Customers", fields=[("ID", 4), ("Name", 10)])
        tdef.OpenRecordset.return_value.EOF = True
        db = _make_db_with_table_defs([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_object_metadata("Customers")

        assert result.get("name") == "Customers"
        assert result.get("type") == "table"
        # record_count surfaces in properties (str-cast by SchemaInspector)
        assert "record_count" in result.get("properties", {})

    def test_get_object_metadata_empty_when_not_connected(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_object_metadata("Anything")

        assert result == {}


class TestDaoAdapterGetTableSchemaPlan:
    """DaoAdapter.get_table_schema_plan() returns (tables, unknown) tuple."""

    def test_get_table_schema_plan_returns_tuple(self):
        """Returns a tuple of (list[TableSchema], UnknownMetadata)."""
        from ms_access_mcp.models.migration import UnknownMetadata

        tdef = _make_tdef("Customers", fields=[("ID", 4), ("Name", 10)])
        tdef.OpenRecordset.return_value.EOF = True
        db = _make_db_with_table_defs([tdef])
        # No relations
        db.Relations = MagicMock()
        db.Relations.Count = 0
        # No indexes for the index extraction
        tdef.Indexes.Count = 0
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_table_schema_plan()

        assert isinstance(result, tuple)
        assert len(result) == 2
        tables, unknown = result
        assert isinstance(tables, list)
        assert isinstance(unknown, UnknownMetadata)
        assert len(tables) == 1
        assert tables[0].name == "Customers"

    def test_get_table_schema_plan_empty_when_not_connected(self):
        from ms_access_mcp.models.migration import UnknownMetadata

        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_table_schema_plan()

        assert result == ([], UnknownMetadata())


# --------------------------------------------------------------------- #
# Database property methods
# --------------------------------------------------------------------- #


class TestDaoAdapterGetDatabaseProperties:
    """DaoAdapter.get_database_properties() returns the four-bucket shape."""

    def test_get_database_properties_returns_four_buckets(self):
        """Even when not connected, returns the four-bucket shape (no raise)."""
        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_database_properties()

        assert isinstance(result, dict)
        assert set(result.keys()) == {"startup", "app", "project", "all"}
        for bucket in result.values():
            assert isinstance(bucket, dict)

    def test_get_database_properties_filter_by_name(self):
        """Spec scenario: filter by name → only that property is returned."""
        prop_apptitle = MagicMock()
        prop_apptitle.Name = "AppTitle"
        prop_apptitle.Value = "MyApp"
        prop_author = MagicMock()
        prop_author.Name = "Author"
        prop_author.Value = "Jane"
        # Iteration by index — DbOperations walks db.Properties(i)
        props = [prop_apptitle, prop_author]
        db = MagicMock()
        db.Properties.Count = len(props)
        db.Properties.side_effect = lambda i: props[i]
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_database_properties(names=["AppTitle"])

        assert "AppTitle" in result["all"]
        assert "Author" not in result["all"]
        # AppTitle is in the startup bucket (per DbOperations classification)
        assert "AppTitle" in result["startup"]
        # Author is in the app bucket
        assert result["app"] == {}  # Author is in app bucket below

    def test_get_database_properties_all_properties_when_no_filter(self):
        """No names filter → both AppTitle and Author appear in 'all'."""
        prop_apptitle = MagicMock()
        prop_apptitle.Name = "AppTitle"
        prop_apptitle.Value = "MyApp"
        prop_author = MagicMock()
        prop_author.Name = "Author"
        prop_author.Value = "Jane"
        props = [prop_apptitle, prop_author]
        db = MagicMock()
        db.Properties.Count = len(props)
        db.Properties.side_effect = lambda i: props[i]
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_database_properties()

        assert "AppTitle" in result["all"]
        assert "Author" in result["all"]


class TestDaoAdapterSetDatabaseProperty:
    """DaoAdapter.set_database_property() creates/updates a property."""

    def test_set_database_property_creates_new_property(self):
        """Spec scenario: DB without MyFlag → set returns True; read returns Boolean."""
        db = MagicMock()
        # No existing properties
        db.Properties.Count = 0
        # Track the created property
        created = MagicMock()
        db.CreateProperty.return_value = created
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.set_database_property("MyFlag", "true")

        assert result is True
        db.CreateProperty.assert_called_once()
        db.Properties.Append.assert_called_once_with(created)

    def test_set_database_property_updates_existing(self):
        """If property already exists, update its value in place."""
        existing = MagicMock()
        existing.Name = "MyFlag"
        existing.Type = 1  # Boolean
        db = MagicMock()
        db.Properties.Count = 1
        db.Properties.side_effect = lambda i: existing
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.set_database_property("MyFlag", "false")

        assert result is True
        # Did not call CreateProperty (existing found)
        db.CreateProperty.assert_not_called()
        # Updated value on the existing object
        assert existing.Value is False  # "false" → False (boolean coerce)

    def test_set_database_property_returns_false_on_failure(self):
        """A COM failure → False (not raising)."""
        db = MagicMock()
        # Force CreateProperty to raise
        db.Properties.Count = 0
        db.CreateProperty.side_effect = RuntimeError("COM boom")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.set_database_property("X", "1")

        assert result is False

    def test_set_database_property_returns_false_when_not_connected(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.set_database_property("X", "1")

        assert result is False


# --------------------------------------------------------------------- #
# Query CRUD — create_query, set_query_sql, delete_query
# --------------------------------------------------------------------- #


class TestDaoAdapterQueryCrud:
    """create_query / set_query_sql / delete_query cover the spec round-trip scenario."""

    def test_create_query_persists_a_new_querydef(self):
        """create_query("Q", "SELECT 1") → success=True and QueryDefs.Append is called."""
        db = MagicMock()
        # No existing queries
        db.QueryDefs.Count = 0
        created = MagicMock()
        db.CreateQueryDef.return_value = created
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_query("Q", "SELECT 1")

        assert result == {"success": True}
        db.CreateQueryDef.assert_called_once_with("Q", "SELECT 1")
        db.QueryDefs.Append.assert_called_once_with(created)

    def test_set_query_sql_updates_existing_querydef(self):
        """set_query_sql("Q", "SELECT 2") sets SQL on the existing QueryDef."""
        existing = MagicMock()
        existing.Name = "Q"
        db = MagicMock()
        db.QueryDefs.Count = 1
        db.QueryDefs.side_effect = lambda key: (
            existing if key == "Q" else (_ for _ in ()).throw(KeyError(key))
        )
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.set_query_sql("Q", "SELECT 2")

        assert result == {"success": True}
        assert existing.SQL == "SELECT 2"

    def test_delete_query_removes_querydef(self):
        """delete_query("Q") → success=True and QueryDefs.Delete is called."""
        db = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_query("Q")

        assert result == {"success": True}
        db.QueryDefs.Delete.assert_called_once_with("Q")


# --------------------------------------------------------------------- #
# Relationship CRUD — create_relationship, delete_relationship
# --------------------------------------------------------------------- #


class TestDaoAdapterRelationshipCrud:
    """create_relationship / delete_relationship cover FK management."""

    def test_create_relationship_appends_relation(self):
        """create_relationship creates a Relation with the right fields and appends."""
        db = MagicMock()
        created = MagicMock()
        db.CreateRelation.return_value = created
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_relationship(
            table_name="Orders",
            relationship_name="FK_Orders_Customers",
            columns=["CustomerID"],
            foreign_table="Customers",
            foreign_columns=["ID"],
        )

        assert result == {"success": True}
        db.CreateRelation.assert_called_once_with("FK_Orders_Customers", "Orders", "Customers")
        created.CreateField.assert_called_once_with("CustomerID")
        # Append called on both the relation's fields and the db's relations
        created.Fields.Append.assert_called_once()
        db.Relations.Append.assert_called_once_with(created)

    def test_create_relationship_rejects_mismatched_column_lengths(self):
        """columns and foreign_columns must be the same length."""
        adapter, _ = _make_connected_adapter()

        result = adapter.create_relationship(
            table_name="A",
            relationship_name="FK_A_B",
            columns=["x", "y"],
            foreign_table="B",
            foreign_columns=["x"],  # length mismatch
        )

        assert result["success"] is False
        assert "same length" in result["error"]

    def test_create_relationship_returns_error_when_not_connected(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.create_relationship(
            table_name="A",
            relationship_name="FK_A_B",
            columns=["x"],
            foreign_table="B",
            foreign_columns=["x"],
        )

        assert result["success"] is False
        assert result["error"] == "Not connected"

    def test_delete_relationship_removes_relation(self):
        """delete_relationship → success=True and Relations.Delete called."""
        db = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_relationship("Orders", "FK_Orders_Customers")

        assert result == {"success": True}
        db.Relations.Delete.assert_called_once_with("FK_Orders_Customers")

    def test_delete_relationship_returns_error_when_not_connected(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.delete_relationship("A", "FK")

        assert result["success"] is False
        assert "Not connected" in result["error"]


# ===================================================================== #
# Slice 5 — DAO CRUD + DDL (write) surface
# ===================================================================== #
#
# DaoAdapter implements the IDataAdapter row CRUD methods (execute_query,
# insert_data, update_data, delete_data, execute_raw_sql, export_data)
# and the ISchemaAdapter table/index DDL methods (create_table,
# delete_table, create_index, drop_index, alter_table) using DAO on the
# shared ComDispatcher STA thread.
#
# The contract mirrors OdbcAdapter: result shapes use ``affected`` for
# writes and ``rows``/``count``/``columns`` for queries. WHERE strings
# pass the same allowlist sanitization as WinComAdapter (slice 3+) and
# inline value formatting follows the same SQL-literal pattern.


# --------------------------------------------------------------------- #
# execute_query
# --------------------------------------------------------------------- #


class TestDaoAdapterExecuteQuery:
    """DaoAdapter.execute_query() returns DAO OpenRecordset results."""

    def test_execute_query_returns_rows(self):
        """Spec: SELECT returns success=True with rows/columns/count."""
        from datetime import datetime

        rs = MagicMock()
        rs.EOF = False
        rs.Fields.Count = 3
        f_id = MagicMock()
        f_id.Name = "ID"
        f_name = MagicMock()
        f_name.Name = "Name"
        f_dt = MagicMock()
        f_dt.Name = "Created"
        rs.Fields.side_effect = lambda i: [f_id, f_name, f_dt][i]
        # First row
        f_id.Value = 1
        f_name.Value = "Alice"
        f_dt.Value = datetime(2024, 1, 1, 12, 0, 0)

        # MoveNext is a no-op until we flip EOF
        def _move_next() -> None:
            rs.EOF = True

        rs.MoveNext.side_effect = _move_next

        db = MagicMock()
        db.OpenRecordset.return_value = rs
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.execute_query("SELECT ID, Name, Created FROM Customers")

        assert result["success"] is True
        assert result["rows"] == [{"ID": 1, "Name": "Alice", "Created": "2024-01-01T12:00:00"}]
        assert result["count"] == 1
        assert result["columns"] == ["ID", "Name", "Created"]

    def test_execute_query_empty_result(self):
        """No rows → empty list, count=0, columns still extracted."""
        rs = MagicMock()
        rs.EOF = True
        db = MagicMock()
        db.OpenRecordset.return_value = rs
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.execute_query("SELECT * FROM Empty")

        assert result == {
            "success": True,
            "rows": [],
            "count": 0,
            "columns": [],
        }

    def test_execute_query_ignores_params(self):
        """DAO cannot bind ? params; the arg is accepted but ignored."""
        rs = MagicMock()
        rs.EOF = True
        db = MagicMock()
        db.OpenRecordset.return_value = rs
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        # Should not raise even though DAO cannot bind params
        result = adapter.execute_query("SELECT * FROM T WHERE ID = ?", params=[1])

        assert result["success"] is True
        db.OpenRecordset.assert_called_once_with("SELECT * FROM T WHERE ID = ?")

    def test_execute_query_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.execute_query("SELECT 1")

        assert result["success"] is False
        assert "Not connected" in result["error"]
        assert result["rows"] == []
        assert result["count"] == 0
        assert result["columns"] == []

    def test_execute_query_dao_error_returns_error(self):
        db = MagicMock()
        db.OpenRecordset.side_effect = RuntimeError("DAO boom")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.execute_query("SELECT bogus")

        assert result["success"] is False
        assert "DAO boom" in result["error"]
        assert result["rows"] == []


# --------------------------------------------------------------------- #
# insert_data
# --------------------------------------------------------------------- #


class TestDaoAdapterInsertData:
    """DaoAdapter.insert_data() inserts rows via DAO Execute with inline values."""

    def test_insert_data_single_row(self):
        db = MagicMock()
        db.RecordsAffected = 1
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.insert_data("Customers", {"Name": "Alice", "Email": "alice@example.com"})

        assert result["success"] is True
        assert result["affected"] == 1
        db.Execute.assert_called_once()
        sql = db.Execute.call_args[0][0]
        assert "INSERT INTO [Customers]" in sql
        assert "[Name]" in sql
        assert "[Email]" in sql
        assert "'Alice'" in sql
        assert "'alice@example.com'" in sql

    def test_insert_data_multiple_rows(self):
        db = MagicMock()
        db.RecordsAffected = 1
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.insert_data(
            "Customers",
            [
                {"Name": "Alice", "Email": "alice@example.com"},
                {"Name": "Bob", "Email": "bob@example.com"},
            ],
        )

        assert result["success"] is True
        assert result["affected"] == 2
        assert db.Execute.call_count == 2

    def test_insert_data_formats_inline_values(self):
        """Bool/None/int/str are formatted as DAO SQL literals (no ? placeholders)."""
        db = MagicMock()
        db.RecordsAffected = 1
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        adapter.insert_data(
            "T",
            {
                "n": 42,
                "b": True,
                "s": "O'Reilly",
                "z": None,
            },
        )

        sql = db.Execute.call_args[0][0]
        assert "?" not in sql
        assert "42" in sql
        assert "-1" in sql  # True → -1
        assert "'O''Reilly'" in sql  # single-quote escape
        assert "NULL" in sql

    def test_insert_data_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.insert_data("T", {"x": 1})

        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_insert_data_dao_error_returns_error(self):
        db = MagicMock()
        db.Execute.side_effect = RuntimeError("constraint violation")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.insert_data("T", {"x": 1})

        assert result["success"] is False
        assert "constraint violation" in result["error"]


# --------------------------------------------------------------------- #
# update_data
# --------------------------------------------------------------------- #


class TestDaoAdapterUpdateData:
    """DaoAdapter.update_data() updates rows via DAO Execute with inline values."""

    def test_update_data_with_where_dict(self):
        db = MagicMock()
        db.RecordsAffected = 3
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.update_data("Customers", {"Name": "Alice"}, {"ID": 1})

        assert result["success"] is True
        assert result["affected"] == 3
        db.Execute.assert_called_once()
        sql = db.Execute.call_args[0][0]
        assert "UPDATE [Customers] SET" in sql
        assert "[Name] = 'Alice'" in sql
        assert "WHERE [ID] = 1" in sql

    def test_update_data_with_where_string(self):
        db = MagicMock()
        db.RecordsAffected = 2
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.update_data(
            "Customers",
            {"Name": "Alice"},
            "ID = 1 AND Status = 'Active'",
        )

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "UPDATE [Customers] SET" in sql
        assert "ID = 1 AND Status = 'Active'" in sql

    def test_update_data_no_where_updates_all_rows(self):
        db = MagicMock()
        db.RecordsAffected = 100
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.update_data("Customers", {"Status": "Inactive"})

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "WHERE" not in sql

    def test_update_data_rejects_dangerous_where_string(self):
        """WHERE strings with --, ;, DROP, etc. are blocked before execution."""
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.update_data("T", {"x": 1}, "1=1; DROP TABLE Users--")

        assert result["success"] is False
        assert "disallowed" in result["error"].lower() or "injection" in result["error"].lower()
        # No Execute call — sanitization runs before dispatch
        db.Execute.assert_not_called()

    def test_update_data_rejects_tautology_or_1_eq_1(self):
        """``OR 1=1`` style tautology at the start of the WHERE is blocked."""
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.update_data("T", {"x": 1}, "OR 1=1")

        assert result["success"] is False
        db.Execute.assert_not_called()

    def test_update_data_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.update_data("T", {"x": 1}, {"ID": 1})

        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_update_data_dao_error_returns_error(self):
        db = MagicMock()
        db.Execute.side_effect = RuntimeError("type mismatch")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.update_data("T", {"x": 1}, {"ID": 1})

        assert result["success"] is False
        assert "type mismatch" in result["error"]


# --------------------------------------------------------------------- #
# delete_data
# --------------------------------------------------------------------- #


class TestDaoAdapterDeleteData:
    """DaoAdapter.delete_data() deletes rows via DAO Execute."""

    def test_delete_data_with_where_dict(self):
        db = MagicMock()
        db.RecordsAffected = 2
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_data("Customers", {"ID": 1, "Status": "Inactive"})

        assert result["success"] is True
        assert result["affected"] == 2
        sql = db.Execute.call_args[0][0]
        assert "DELETE FROM [Customers]" in sql
        assert "[ID] = 1" in sql
        assert "[Status] = 'Inactive'" in sql

    def test_delete_data_with_where_string(self):
        db = MagicMock()
        db.RecordsAffected = 1
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_data("Customers", "ID = 1 AND Status = 'Spam'")

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "ID = 1 AND Status = 'Spam'" in sql

    def test_delete_data_no_where_deletes_all(self):
        db = MagicMock()
        db.RecordsAffected = 10
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_data("Customers")

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "DELETE FROM [Customers]" in sql
        assert "WHERE" not in sql

    def test_delete_data_rejects_dangerous_where_string(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_data("T", "1=1 OR 1=1; DROP TABLE Users--")

        assert result["success"] is False
        db.Execute.assert_not_called()

    def test_delete_data_rejects_dangerous_keyword(self):
        """WHERE strings containing DROP/DELETE/INSERT etc. are blocked."""
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_data("T", "ID = 1; DROP TABLE Users")

        assert result["success"] is False
        db.Execute.assert_not_called()

    def test_delete_data_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.delete_data("T", {"ID": 1})

        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_delete_data_dao_error_returns_error(self):
        db = MagicMock()
        db.Execute.side_effect = RuntimeError("locked")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_data("T", {"ID": 1})

        assert result["success"] is False
        assert "locked" in result["error"]


# --------------------------------------------------------------------- #
# execute_raw_sql
# --------------------------------------------------------------------- #


class TestDaoAdapterExecuteRawSql:
    """DaoAdapter.execute_raw_sql() runs arbitrary SQL via DAO.Execute."""

    def test_execute_raw_sql_returns_records_affected(self):
        db = MagicMock()
        db.RecordsAffected = 5
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.execute_raw_sql("DELETE FROM Logs")

        assert result == 5
        db.Execute.assert_called_once()
        # DAO_DB_FAIL_ON_ERROR = 128
        assert db.Execute.call_args[0][1] == 128

    def test_execute_raw_sql_not_connected_raises(self):
        adapter, _ = _make_disconnected_adapter()

        with pytest.raises(RuntimeError, match="Not connected"):
            adapter.execute_raw_sql("SELECT 1")

    def test_execute_raw_sql_propagates_dao_error(self):
        db = MagicMock()
        db.Execute.side_effect = RuntimeError("syntax error")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        with pytest.raises(RuntimeError, match="syntax error"):
            adapter.execute_raw_sql("SELEKT 1")


# --------------------------------------------------------------------- #
# export_data
# --------------------------------------------------------------------- #


class TestDaoAdapterExportData:
    """DaoAdapter.export_data() delegates to the export strategy selector."""

    def test_export_data_uses_strategy_selector(self):
        adapter, _dispatcher = _make_adapter_with_mock_dispatcher()
        # Stub the strategy selector on the adapter
        from ms_access_mcp.adapters.export.strategies import (
            CsvStrategy,
            ExportStrategySelector,
        )

        adapter._strategy_selector = ExportStrategySelector()
        adapter._strategy_selector.register(CsvStrategy())
        # Provide execute_query and execute_raw so the strategy can call them
        adapter.execute_query = MagicMock(
            return_value={"success": True, "rows": [], "columns": [], "count": 0}
        )
        adapter._execute_raw = MagicMock(return_value=0)

        result = adapter.export_data("SELECT 1", "out.csv", format="csv")

        # CSV fast path returns success; details depend on whether the IISAM
        # path was available — but result is always a dict.
        assert isinstance(result, dict)
        assert "success" in result

    def test_export_data_unsupported_format_returns_error(self):
        adapter, _ = _make_adapter_with_mock_dispatcher()
        from ms_access_mcp.adapters.export.strategies import ExportStrategySelector

        adapter._strategy_selector = ExportStrategySelector()

        result = adapter.export_data("SELECT 1", "out.xyz", format="xyz")

        assert result["success"] is False
        assert "Unsupported" in result["error"] or "format" in result["error"].lower()

    def test_export_data_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.export_data("SELECT 1", "out.csv", format="csv")

        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_export_data_forwards_options(self):
        """Format-specific options (delimiter/encoding) reach the strategy."""
        adapter, _ = _make_adapter_with_mock_dispatcher()
        from ms_access_mcp.adapters.export.strategies import (
            CsvStrategy,
            ExportStrategySelector,
        )

        # Capture the ExportContext the strategy receives
        captured: dict = {}

        class _SpyStrategy(CsvStrategy):
            def export(self, context):  # type: ignore[override]
                captured["context"] = context
                return {"success": True, "rows_exported": 0, "file_path": context.file_path}

        adapter._strategy_selector = ExportStrategySelector()
        adapter._strategy_selector.register(_SpyStrategy())
        adapter.execute_query = MagicMock(
            return_value={"success": True, "rows": [], "columns": [], "count": 0}
        )
        adapter._execute_raw = MagicMock(return_value=0)

        adapter.export_data("SELECT 1", "out.csv", format="csv", delimiter="|", encoding="utf-8")

        ctx = captured["context"]
        assert ctx.options.get("delimiter") == "|"
        assert ctx.options.get("encoding") == "utf-8"


# --------------------------------------------------------------------- #
# create_table
# --------------------------------------------------------------------- #


class TestDaoAdapterCreateTable:
    """DaoAdapter.create_table() runs CREATE TABLE via DAO.Execute."""

    def test_create_table_basic(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_table(
            "T",
            [
                {"name": "ID", "type": "Long Integer", "is_autoincrement": True},
                {"name": "Name", "type": "Text", "size": 100, "required": True},
            ],
        )

        assert result["success"] is True
        db.Execute.assert_called_once()
        sql = db.Execute.call_args[0][0]
        assert "CREATE TABLE [T]" in sql
        assert "[ID] INTEGER NOT NULL" in sql
        assert "[Name] VARCHAR(100) NOT NULL" in sql
        assert "PRIMARY KEY ([ID])" in sql

    def test_create_table_without_pk(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_table(
            "T", [{"name": "Name", "type": "Text", "size": 50, "required": False}]
        )

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "PRIMARY KEY" not in sql
        # DAO default for non-required columns is NULL (implicit).
        # The DDL omits the NULL keyword in that case — matching
        # WinComAdapter.create_table.
        assert "[Name] VARCHAR(50)" in sql
        assert "NOT NULL" not in sql

    def test_create_table_with_dao_error_returns_error(self):
        db = MagicMock()
        db.Execute.side_effect = RuntimeError("table exists")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_table("T", [{"name": "X", "type": "Text"}])

        assert result["success"] is False
        assert "table exists" in result["error"]

    def test_create_table_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.create_table("T", [{"name": "X", "type": "Text"}])

        assert result["success"] is False
        assert "Not connected" in result["error"]


# --------------------------------------------------------------------- #
# delete_table
# --------------------------------------------------------------------- #


class TestDaoAdapterDeleteTable:
    """DaoAdapter.delete_table() drops a table and cleans up inbound/outbound relations."""

    def test_delete_table_basic(self):
        db = MagicMock()
        db.Execute = MagicMock()
        # No relations referencing the table
        db.Relations.Count = 0
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_table("T")

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "DROP TABLE [T]" in sql

    def test_delete_table_removes_referencing_relations(self):
        """If a relation references the table, it must be removed before DROP."""
        db = MagicMock()
        db.Execute = MagicMock()
        # Two relations: one references the table as Table, one as ForeignTable,
        # one unrelated.
        rel_target_as_table = MagicMock()
        rel_target_as_table.Name = "FK_X_T"
        rel_target_as_table.Table = "T"
        rel_target_as_table.ForeignTable = "X"
        rel_target_as_foreign = MagicMock()
        rel_target_as_foreign.Name = "FK_T_Y"
        rel_target_as_foreign.Table = "Y"
        rel_target_as_foreign.ForeignTable = "T"
        rel_unrelated = MagicMock()
        rel_unrelated.Name = "FK_A_B"
        rel_unrelated.Table = "A"
        rel_unrelated.ForeignTable = "B"

        db.Relations.Count = 3
        # Iterate in reverse order to avoid index shifts
        db.Relations.side_effect = lambda i: [
            rel_target_as_table,
            rel_target_as_foreign,
            rel_unrelated,
        ][2 - i]
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.delete_table("T")

        assert result["success"] is True
        # Both referencing relations were removed
        assert db.Relations.Delete.call_count == 2
        deleted_names = {c.args[0] for c in db.Relations.Delete.call_args_list}
        assert deleted_names == {"FK_X_T", "FK_T_Y"}
        db.Execute.assert_called_once_with("DROP TABLE [T]", 128)

    def test_delete_table_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.delete_table("T")

        assert result["success"] is False
        assert "Not connected" in result["error"]


# --------------------------------------------------------------------- #
# create_index
# --------------------------------------------------------------------- #


class TestDaoAdapterCreateIndex:
    """DaoAdapter.create_index() runs CREATE INDEX via DAO.Execute."""

    def test_create_index_basic(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_index("Orders", "IX_OrderDate", ["OrderDate", "CustomerID"])

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "CREATE INDEX [IX_OrderDate] ON [Orders] ([OrderDate], [CustomerID])" in sql
        assert "UNIQUE" not in sql
        assert "IGNORE NULL" not in sql

    def test_create_index_unique(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_index("T", "UX_Email", ["Email"], unique=True)

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "CREATE UNIQUE INDEX" in sql

    def test_create_index_with_ignore_nulls(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_index("T", "IX_X", ["X"], ignore_nulls=True)

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "WITH IGNORE NULL" in sql

    def test_create_index_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.create_index("T", "IX_X", ["X"])

        assert result["success"] is False
        assert "Not connected" in result["error"]


# --------------------------------------------------------------------- #
# drop_index
# --------------------------------------------------------------------- #


class TestDaoAdapterDropIndex:
    """DaoAdapter.drop_index() runs DROP INDEX via DAO.Execute."""

    def test_drop_index_basic(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.drop_index("Orders", "IX_OrderDate")

        assert result["success"] is True
        db.Execute.assert_called_once()
        sql = db.Execute.call_args[0][0]
        assert "DROP INDEX [IX_OrderDate] ON [Orders]" in sql

    def test_drop_index_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.drop_index("T", "IX_X")

        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_drop_index_dao_error_returns_error(self):
        db = MagicMock()
        db.Execute.side_effect = RuntimeError("index not found")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.drop_index("T", "IX_X")

        assert result["success"] is False
        assert "index not found" in result["error"]


# --------------------------------------------------------------------- #
# alter_table
# --------------------------------------------------------------------- #


class TestDaoAdapterAlterTable:
    """DaoAdapter.alter_table() applies a list of DDL operations to a table."""

    def test_alter_table_add_column(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.alter_table(
            "T",
            [{"action": "add_column", "params": {"name": "X", "type": "Text", "size": 50}}],
        )

        assert result["success"] is True
        assert len(result["operations"]) == 1
        assert result["operations"][0]["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "ALTER TABLE [T] ADD COLUMN [X] VARCHAR(50) NULL" in sql

    def test_alter_table_drop_column(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.alter_table("T", [{"action": "drop_column", "params": {"name": "X"}}])

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "ALTER TABLE [T] DROP COLUMN [X]" in sql

    def test_alter_table_modify_column(self):
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.alter_table(
            "T",
            [
                {
                    "action": "modify_column",
                    "params": {"name": "X", "type": "Long Integer", "nullable": False},
                }
            ],
        )

        assert result["success"] is True
        sql = db.Execute.call_args[0][0]
        assert "ALTER TABLE [T] ALTER COLUMN [X] INTEGER NOT NULL" in sql

    def test_alter_table_rename_table(self):
        """Rename uses DAO TableDef.Name assignment, not DDL."""
        tdef = MagicMock()
        tdef.Name = "OldName"
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.alter_table(
            "OldName",
            [{"action": "rename_table", "params": {"new_name": "NewName"}}],
        )

        assert result["success"] is True
        # Renamed in place
        assert tdef.Name == "NewName"

    def test_alter_table_rename_column(self):
        """Rename column uses DAO Field.Name assignment, not DDL."""
        old_field = MagicMock()
        old_field.Name = "OldCol"
        tdef = MagicMock()
        tdef.Name = "T"  # explicit so _MockDaoTableDefs can look it up
        # Use a Fields mock that returns our field by name OR index
        tdef.Fields.Count = 1
        tdef.Fields.side_effect = lambda key: (
            old_field
            if (isinstance(key, int) and key == 0) or key == "OldCol"
            else (_ for _ in ()).throw(KeyError(key))
        )
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.alter_table(
            "T",
            [
                {
                    "action": "rename_column",
                    "params": {"name": "OldCol", "new_name": "NewCol"},
                }
            ],
        )

        assert result["success"] is True
        assert old_field.Name == "NewCol"

    def test_alter_table_unknown_action_recorded_as_failure(self):
        """Unknown actions are reported per-op; overall success is False."""
        db = MagicMock()
        db.Execute = MagicMock()
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.alter_table("T", [{"action": "nonsense", "params": {}}])

        assert result["success"] is False
        assert result["operations"][0]["success"] is False
        assert "Unknown action" in result["operations"][0]["error"]

    def test_alter_table_per_op_failure_does_not_abort(self):
        """A failed op is reported; subsequent ops still execute."""
        db = MagicMock()
        # First Execute call (drop column) raises; second (add column) succeeds
        db.Execute.side_effect = [RuntimeError("col missing"), None]
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.alter_table(
            "T",
            [
                {"action": "drop_column", "params": {"name": "X"}},
                {"action": "add_column", "params": {"name": "Y", "type": "Text"}},
            ],
        )

        assert result["success"] is False  # overall: at least one failure
        assert result["operations"][0]["success"] is False
        assert result["operations"][1]["success"] is True

    def test_alter_table_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.alter_table("T", [{"action": "add_column", "params": {"name": "X"}}])

        assert result["success"] is False
        assert "Not connected" in result["error"]


# ===================================================================== #
# Slice 6 — DAO linked-table surface
# ===================================================================== #
#
# DaoAdapter owns the five linked-table methods that WinComAdapter used
# to expose. The DAO port preserves three behaviours from
# WinComAdapter:
#   1) get_linked_tables filters to Attributes & 0x80000000 (the
#      dbLinkAttachedTable flag) and classifies the connect string as
#      ODBC / Access / Excel from its prefix.
#   2) create / refresh / recreate strip PWD= from the persisted
#      connect string after the link is established.
#   3) recreate_linked_table captures the original Attributes (which
#      may include dbHiddenObject = 1) and restores them on the new
#      tdef so hidden linked tables stay hidden across a rebuild.
#
# The mock TableDefs collection needs both index iteration (for
# get_linked_tables) and name-keyed lookup (for refresh/recreate/
# unlink). The existing _MockDaoTableDefs already provides both.


# DAO attribute flag constants (mirroring the access constants used in
# WinComAdapter). Exposed at module level so tests can reference them
# without importing pywin32.
DB_ATTACHED_TABLE = 0x80000000  # dbLinkAttachedTable — marks linked tdefs
DB_HIDDEN_OBJECT = 0x1  # dbHiddenObject — the spec's hidden-preservation flag


def _make_linked_tdef(
    name: str,
    source_table: str,
    connect_string: str,
    attributes: int = DB_ATTACHED_TABLE,
) -> MagicMock:
    """Build a mock DAO TableDef representing a linked (attached) table.

    Defaults to ``dbLinkAttachedTable`` but accepts a custom
    ``attributes`` so tests can simulate a hidden linked table
    (``DB_ATTACHED_TABLE | DB_HIDDEN_OBJECT``).
    """
    tdef = MagicMock()
    tdef.Name = name
    tdef.SourceTableName = source_table
    tdef.Connect = connect_string
    tdef.Attributes = attributes
    return tdef


def _make_local_tdef(name: str) -> MagicMock:
    """Build a mock DAO TableDef representing a non-linked (local) table."""
    tdef = MagicMock()
    tdef.Name = name
    tdef.SourceTableName = name
    tdef.Connect = ""  # local tables have no connect string
    tdef.Attributes = 0  # no dbLinkAttachedTable flag
    return tdef


class _FakeTdef:
    """Plain Python stand-in for a DAO TableDef.

    Unlike :class:`MagicMock`, every attribute is a real attribute —
    so tests that need to read or assign ``Connect`` or ``Attributes``
    can do so without the MagicMock ``__getattr__`` indirection. Used
    by linked-table tests that need to capture the post-Append
    ``Connect`` value (which the adapter writes via
    ``tdef.Connect = self._strip_password(...)``).
    """

    def __init__(
        self,
        name: str = "",
        source_table: str = "",
        connect_string: str = "",
        attributes: int = 0,
    ) -> None:
        self.Name = name
        self.SourceTableName = source_table
        self.Connect = connect_string
        self.Attributes = attributes

    def RefreshLink(self) -> None:
        """No-op by default; tests can monkey-patch or set side_effects."""


# --------------------------------------------------------------------- #
# get_linked_tables
# --------------------------------------------------------------------- #


class TestDaoAdapterGetLinkedTables:
    """DaoAdapter.get_linked_tables() returns the linked (attached) tables only."""

    def test_get_linked_tables_returns_attached_only(self):
        """Spec scenario: 2 linked + 3 local tables → 2 linked entries."""
        linked_odbc = _make_linked_tdef(
            "Orders", "dbo.Orders", "ODBC;DSN=MyDSN;PWD=secret", DB_ATTACHED_TABLE
        )
        linked_access = _make_linked_tdef(
            "Customers", "Customers", "Access;DATABASE=C:\\other.accdb", DB_ATTACHED_TABLE
        )
        local_a = _make_local_tdef("Products")
        local_b = _make_local_tdef("Categories")
        local_c = _make_local_tdef("Suppliers")

        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([linked_odbc, local_a, linked_access, local_b, local_c])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_linked_tables()

        assert result["success"] is True
        assert len(result["linked_tables"]) == 2
        names = {t["name"] for t in result["linked_tables"]}
        assert names == {"Orders", "Customers"}

    def test_get_linked_tables_classifies_type_from_connect_prefix(self):
        """Type field is "ODBC" / "Access" / "Excel" based on the Connect prefix."""
        linked_odbc = _make_linked_tdef("A", "srcA", "ODBC;DSN=X")
        linked_access = _make_linked_tdef("B", "srcB", "Access;DATABASE=Y")
        linked_excel = _make_linked_tdef("C", "srcC", "Excel 12.0;HDR=YES")
        local = _make_local_tdef("D")

        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([linked_odbc, linked_access, linked_excel, local])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_linked_tables()

        type_by_name = {t["name"]: t["type"] for t in result["linked_tables"]}
        assert type_by_name == {"A": "ODBC", "B": "Access", "C": "Excel"}

    def test_get_linked_tables_includes_name_source_and_attributes(self):
        """Each entry carries name, source_table, connect_string, type, attributes."""
        linked = _make_linked_tdef(
            "Orders",
            "dbo.Orders",
            "ODBC;DSN=MyDSN;PWD=secret",
            DB_ATTACHED_TABLE,
        )
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([linked])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_linked_tables()

        assert len(result["linked_tables"]) == 1
        entry = result["linked_tables"][0]
        assert entry["name"] == "Orders"
        assert entry["source_table"] == "dbo.Orders"
        assert entry["connect_string"] == "ODBC;DSN=MyDSN;PWD=secret"
        assert entry["type"] == "ODBC"
        assert entry["attributes"] == DB_ATTACHED_TABLE

    def test_get_linked_tables_empty_when_no_links(self):
        """A database with only local tables returns an empty list."""
        local_a = _make_local_tdef("A")
        local_b = _make_local_tdef("B")
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([local_a, local_b])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_linked_tables()

        assert result == {"success": True, "linked_tables": []}

    def test_get_linked_tables_default_type_is_odbc_for_unknown_prefix(self):
        """Unknown Connect prefixes fall back to 'ODBC' (matches WinComAdapter)."""
        linked_unknown = _make_linked_tdef("Z", "srcZ", "WeirdProvider;FOO=bar")
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([linked_unknown])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.get_linked_tables()

        assert result["linked_tables"][0]["type"] == "ODBC"

    def test_get_linked_tables_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.get_linked_tables()

        assert result["success"] is False
        assert "Not connected" in result["error"]


# --------------------------------------------------------------------- #
# create_linked_table
# --------------------------------------------------------------------- #


class TestDaoAdapterCreateLinkedTable:
    """DaoAdapter.create_linked_table() creates an attached tdef and strips PWD."""

    def test_create_linked_table_appends_attached_tdef(self):
        """A new linked tdef is created with Attributes=dbLinkAttachedTable."""
        db = MagicMock()
        created = _FakeTdef(name="L")
        # Start as un-flagged; the adapter must set dbLinkAttachedTable.
        created.Attributes = 0
        db.CreateTableDef.return_value = created
        db.TableDefs = _MockDaoTableDefs([])  # no existing tables
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_linked_table("L", "srcL", "ODBC;DSN=X;PWD=s")

        assert result["success"] is True
        # CreateTableDef called with the local name
        db.CreateTableDef.assert_called_once_with("L")
        # SourceTableName set on the tdef
        assert created.SourceTableName == "srcL"
        # Append was called once
        db.TableDefs.Append.assert_called_once_with(created)
        # Attributes set to dbLinkAttachedTable during the call
        assert created.Attributes == DB_ATTACHED_TABLE
        # After the call, the Connect string has been stripped of PWD=
        assert "PWD" not in created.Connect
        assert "DSN=X" in created.Connect

    def test_create_linked_table_persists_without_pwd(self):
        """Spec scenario: connect_string with PWD= → stored Connect has no PWD=."""
        db = MagicMock()
        created = _FakeTdef(name="L")
        db.CreateTableDef.return_value = created
        db.TableDefs = _MockDaoTableDefs([])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        adapter.create_linked_table("L", "RemoteR", "ODBC;DSN=X;PWD=secret")

        # The final connect_string value written must not contain PWD=
        final = created.Connect
        assert "PWD" not in final
        assert "secret" not in final
        # DSN survives the strip
        assert "DSN=X" in final

    def test_create_linked_table_keeps_pwd_less_string_intact(self):
        """A connect string without PWD= is preserved verbatim."""
        db = MagicMock()
        created = _FakeTdef(name="L")
        db.CreateTableDef.return_value = created
        db.TableDefs = _MockDaoTableDefs([])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_linked_table("L", "srcL", "ODBC;DSN=X")

        assert result["success"] is True
        # No PWD= → sanitized output equals the input verbatim
        assert created.Connect == "ODBC;DSN=X"

    def test_create_linked_table_dao_error_returns_error(self):
        """CreateTableDef failure → success=False with the DAO error message."""
        db = MagicMock()
        db.CreateTableDef.side_effect = RuntimeError("name in use")
        db.TableDefs = _MockDaoTableDefs([])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.create_linked_table("L", "src", "ODBC;DSN=X")

        assert result["success"] is False
        assert "name in use" in result["error"]

    def test_create_linked_table_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.create_linked_table("L", "src", "ODBC;DSN=X")

        assert result["success"] is False
        assert "Not connected" in result["error"]


# --------------------------------------------------------------------- #
# refresh_linked_table
# --------------------------------------------------------------------- #


class TestDaoAdapterRefreshLinkedTable:
    """DaoAdapter.refresh_linked_table() re-auths and strips the new password."""

    def test_refresh_linked_table_re_auths_with_new_connect_string(self):
        """Spec scenario: stale creds → RefreshLink invoked with the new connect string."""
        tdef = _FakeTdef(name="L", connect_string="ODBC;DSN=X;PWD=old")
        refresh_calls = {"n": 0}

        def _refresh() -> None:
            refresh_calls["n"] += 1

        tdef.RefreshLink = _refresh
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.refresh_linked_table("L", "ODBC;DSN=X;PWD=new")

        assert result["success"] is True
        # RefreshLink was called
        assert refresh_calls["n"] == 1
        # The post-refresh Connect was stripped of PWD=
        assert "PWD" not in tdef.Connect
        assert "new" not in tdef.Connect

    def test_refresh_linked_table_without_connect_string_keeps_existing(self):
        """When no connect_string is passed, RefreshLink is called and the
        existing (already-stored, presumably sanitized) connect string
        is preserved — no PWD to strip because it was never persisted.
        """
        tdef = _FakeTdef(name="L", connect_string="ODBC;DSN=X")
        refresh_calls = {"n": 0}

        def _refresh() -> None:
            refresh_calls["n"] += 1

        tdef.RefreshLink = _refresh
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.refresh_linked_table("L")

        assert result["success"] is True
        assert refresh_calls["n"] == 1
        # Connect string was sanitized (unchanged because no PWD=)
        assert tdef.Connect == "ODBC;DSN=X"

    def test_refresh_linked_table_dao_error_returns_error(self):
        """RefreshLink failure → success=False with the DAO error message."""
        tdef = _FakeTdef(name="L", connect_string="ODBC;DSN=X")

        def _refresh_boom() -> None:
            raise RuntimeError("link not found")

        tdef.RefreshLink = _refresh_boom
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.refresh_linked_table("L")

        assert result["success"] is False
        assert "link not found" in result["error"]

    def test_refresh_linked_table_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.refresh_linked_table("L", "ODBC;DSN=X")

        assert result["success"] is False
        assert "Not connected" in result["error"]


# --------------------------------------------------------------------- #
# recreate_linked_table
# --------------------------------------------------------------------- #


class TestDaoAdapterRecreateLinkedTable:
    """DaoAdapter.recreate_linked_table() rebuilds a tdef and preserves hidden."""

    def test_recreate_linked_table_preserves_hidden_attributes(self):
        """Spec scenario: hidden linked 'L' → recreated 'L' has the same Attributes.

        dbHiddenObject is 0x1. The dbLinkAttachedTable flag (0x80000000)
        was already on the original tdef; the recreate path must keep
        BOTH bits on the rebuilt tdef so a hidden linked table stays
        hidden across the rebuild.
        """
        original_attrs = DB_ATTACHED_TABLE | DB_HIDDEN_OBJECT
        old_tdef = _FakeTdef(name="L", attributes=original_attrs)
        new_tdef = _FakeTdef(name="L")

        db = _make_recreate_db(
            existing={"L": old_tdef},
            new_tdef=new_tdef,
        )
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.recreate_linked_table("L", "srcL", "ODBC;DSN=X;PWD=secret")

        assert result["success"] is True
        # The recreated tdef's Attributes retains the original bits.
        assert new_tdef.Attributes == original_attrs
        # The Connect was stripped after Append.
        assert "PWD" not in new_tdef.Connect
        assert "secret" not in new_tdef.Connect

    def test_recreate_linked_table_uses_provided_attributes(self):
        """When attributes is supplied, it overrides the captured ones."""
        old_tdef = _FakeTdef(name="L", attributes=DB_ATTACHED_TABLE)  # not hidden
        new_tdef = _FakeTdef(name="L")

        db = _make_recreate_db(
            existing={"L": old_tdef},
            new_tdef=new_tdef,
        )
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        # Caller passes an explicit (non-hidden) attribute set.
        result = adapter.recreate_linked_table(
            "L", "srcL", "ODBC;DSN=X", attributes=DB_ATTACHED_TABLE
        )

        assert result["success"] is True
        # Provider's value wins over the captured one.
        assert new_tdef.Attributes == DB_ATTACHED_TABLE

    def test_recreate_linked_table_defaults_attrs_when_old_missing(self):
        """If the old tdef cannot be read (already gone), use dbLinkAttachedTable."""
        new_tdef = _FakeTdef(name="L")

        db = _make_recreate_db(
            existing={},  # nothing pre-existing — name lookup will raise
            new_tdef=new_tdef,
        )
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.recreate_linked_table("L", "srcL", "ODBC;DSN=X")

        assert result["success"] is True
        assert new_tdef.Attributes == DB_ATTACHED_TABLE

    def test_recreate_linked_table_dao_error_returns_error(self):
        """A failure during delete or create → success=False with the error."""
        old_tdef = _FakeTdef(name="L", attributes=DB_ATTACHED_TABLE)
        new_tdef = _FakeTdef(name="L")

        db = _make_recreate_db(
            existing={"L": old_tdef},
            new_tdef=new_tdef,
            delete_error="cannot drop in use",
        )
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.recreate_linked_table("L", "src", "ODBC;DSN=X")

        assert result["success"] is False
        assert "cannot drop in use" in result["error"]

    def test_recreate_linked_table_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.recreate_linked_table("L", "src", "ODBC;DSN=X")

        assert result["success"] is False
        assert "Not connected" in result["error"]


def _make_recreate_db(
    existing: dict[str, _FakeTdef],
    new_tdef: _FakeTdef,
    delete_error: str | None = None,
) -> MagicMock:
    """Build a mock DAO Database for the recreate path.

    The recreate path needs:
      * ``db.CreateTableDef(name)`` → returns ``new_tdef``
      * ``db.TableDefs(name)`` → looks up by name in ``existing``
      * ``db.TableDefs.Delete(name)`` → removes from ``existing`` (or
        raises ``delete_error`` if provided)
      * ``db.TableDefs.Append(tdef)`` → adds to ``existing``

    Returns a :class:`MagicMock` with the four slots wired up. The
    helper exists so the four recreate tests share a single, focused
    mock recipe — they only differ in their input data.
    """

    def _create_tdef(name: str) -> _FakeTdef:
        new_tdef.Name = name
        return new_tdef

    def _delete(name: str) -> None:
        if delete_error is not None:
            raise RuntimeError(delete_error)
        existing.pop(name, None)

    def _append(tdef: _FakeTdef) -> None:
        existing[tdef.Name] = tdef

    db = MagicMock()
    db.CreateTableDef.side_effect = _create_tdef
    # db.TableDefs is a regular MagicMock so the call ``db.TableDefs(name)``
    # returns whatever ``side_effect`` produces — that lets us model
    # both the in-collection name lookup and the post-Delete KeyError
    # with a single, transparent helper.
    table_defs_mock = MagicMock()

    def _name_lookup(name: str) -> _FakeTdef:
        if name in existing:
            return existing[name]
        raise KeyError(name)

    table_defs_mock.side_effect = _name_lookup
    table_defs_mock.Delete.side_effect = _delete
    table_defs_mock.Append.side_effect = _append
    db.TableDefs = table_defs_mock
    return db


# --------------------------------------------------------------------- #
# unlink_table
# --------------------------------------------------------------------- #


class TestDaoAdapterUnlinkTable:
    """DaoAdapter.unlink_table() deletes the linked tdef from TableDefs."""

    def test_unlink_table_deletes_tabledef(self):
        """Spec scenario: linked 'L' → success=True and Delete is called."""
        tdef = _FakeTdef(name="L")
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([tdef])
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.unlink_table("L")

        assert result == {"success": True}
        db.TableDefs.Delete.assert_called_once_with("L")

    def test_unlink_table_missing_returns_error(self):
        """Trying to unlink a name that doesn't exist → success=False."""
        db = MagicMock()
        db.TableDefs = _MockDaoTableDefs([])  # empty
        # The empty _MockDaoTableDefs' Delete mock is permissive by
        # default; force it to raise so the adapter's exception path
        # is exercised the way DAO would on a real missing name.
        db.TableDefs.Delete.side_effect = KeyError("Table 'Ghost' not found")
        dispatcher = _make_dispatcher_with_db(db)
        adapter = DaoAdapter(db_path=r"C:\fake\db.accdb", dispatcher=dispatcher)

        result = adapter.unlink_table("Ghost")

        assert result["success"] is False
        assert result["error"]  # non-empty error string

    def test_unlink_table_not_connected_returns_error(self):
        adapter, _ = _make_disconnected_adapter()

        result = adapter.unlink_table("L")

        assert result["success"] is False
        assert "Not connected" in result["error"]


# ===================================================================== #
# Slice 7 — DaoSession contract + DaoAdapter.read_relationships_short_lived
# ===================================================================== #
#
# Slice 7 of the dao-first-linked-tables-properties change deletes the
# standalone ``dao_relationship_reader.py`` helper and exposes the same
# capability as ``DaoAdapter.read_relationships_short_lived``. The tests
# that previously lived in ``tests/unit/test_dao_relationship_reader.py``
# are migrated here because the behavior now lives in
# ``ms_access_mcp.adapters.dao``. ``DaoSession`` itself is also covered
# here because the reader is its primary caller.


def _make_relation_mock(
    name: str,
    table: str,
    foreign_table: str,
    fields: list[tuple[str, str]],
    attributes: int = 0,
) -> MagicMock:
    """Build a MagicMock that mimics a DAO ``Relation`` object."""
    rel = MagicMock()
    rel.Name = name
    rel.Table = table
    rel.ForeignTable = foreign_table
    rel.Attributes = attributes

    field_mocks: list[MagicMock] = []
    for child_col, parent_col in fields:
        f = MagicMock()
        f.Name = child_col
        f.ForeignName = parent_col
        field_mocks.append(f)
    rel.Fields.Count = len(field_mocks)

    def _fields_getter(i):
        return field_mocks[i]

    rel.Fields.side_effect = _fields_getter
    rel.Fields.Item.side_effect = _fields_getter
    return rel


def _make_db_mock(relations: list[MagicMock]) -> MagicMock:
    """Build a MagicMock that mimics a DAO ``Database`` object."""
    db = MagicMock()
    db.Relations.Count = len(relations)

    def _rel_getter(i):
        return relations[i]

    db.Relations.side_effect = _rel_getter
    db.Relations.Item.side_effect = _rel_getter
    return db


class TestDaoSession:
    """DaoSession is the reusable open/close context manager for short-lived
    read-only DAO handles. It was extracted from DaoRelationshipReader in
    slice 1 of dao-first-linked-tables-properties and is now used by
    DaoAdapter.read_relationships_short_lived (slice 7).
    """

    @patch("win32com.client.Dispatch")
    def test_session_passes_password_in_connect_string(self, mock_dispatch):
        """When a password is provided, the DAO connect string includes ``;PWD=...``."""
        engine = MagicMock()
        engine.OpenDatabase.return_value = MagicMock()
        mock_dispatch.return_value = engine

        with DaoSession(r"C:\fake\db.accdb", password="secret"):
            pass
        assert engine.OpenDatabase.call_args[0][3] == ";PWD=secret"

    @patch("win32com.client.Dispatch")
    def test_session_no_password_uses_empty_connect_string(self, mock_dispatch):
        """When no password is provided, the connect string arg is empty."""
        engine = MagicMock()
        engine.OpenDatabase.return_value = MagicMock()
        mock_dispatch.return_value = engine

        with DaoSession(r"C:\fake\db.accdb"):
            pass
        # 4th positional arg is the connect string
        assert engine.OpenDatabase.call_args[0][3] == ""

    @patch("win32com.client.Dispatch")
    def test_session_opens_read_only_by_default(self, mock_dispatch):
        """Default read_only=True means OpenDatabase is called with read-only=True."""
        engine = MagicMock()
        engine.OpenDatabase.return_value = MagicMock()
        mock_dispatch.return_value = engine

        with DaoSession(r"C:\fake\db.accdb"):
            pass
        # Signature: OpenDatabase(name, exclusive, read_only, connect)
        # positional args: [name, exclusive, read_only, connect]
        assert engine.OpenDatabase.call_args[0][2] is True

    @patch("win32com.client.Dispatch")
    def test_session_close_closes_db(self, mock_dispatch):
        """Exiting the context manager calls db.Close()."""
        engine = MagicMock()
        db = MagicMock()
        engine.OpenDatabase.return_value = db
        mock_dispatch.return_value = engine

        with DaoSession(r"C:\fake\db.accdb"):
            pass
        db.Close.assert_called_once()


class TestDaoAdapterReadRelationshipsShortLived:
    """Tests for the slice-7 short-lived DAO relationship reader.

    Migrated from ``tests/unit/test_dao_relationship_reader.py`` after
    the standalone ``DaoRelationshipReader`` class was deleted. The
    function lives on :class:`DaoAdapter` and uses
    :class:`DaoSession` for the short-lived read-only handle.
    """

    def setup_method(self):
        self.db_path = r"C:\fake\db.accdb"
        self.password = ""
        self.logger = MagicMock()

    # ------------------------------------------------------------------ #
    # Happy path
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_single_fk_returns_one_relationship(self, mock_dispatch):
        """1 relation, 1 column → 1 RelationshipInfo with all fields populated."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock(
            [
                _make_relation_mock(
                    "FK_Orders_Customers",
                    "Orders",
                    "Customers",
                    [("CustomerID", "ID")],
                    attributes=256,
                )
            ]
        )
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        assert len(result) == 1
        rel = result[0]
        assert rel.name == "FK_Orders_Customers"
        assert rel.table == "Orders"
        assert rel.foreign_table == "Customers"
        assert rel.columns == ["CustomerID"]
        assert rel.foreign_columns == ["ID"]
        # attributes must be the string form of DAO Attributes
        assert rel.attributes == "256"
        # OpenDatabase was called once
        mock_engine.OpenDatabase.assert_called_once()
        # DB was closed in the finally
        mock_db.Close.assert_called_once()

    # ------------------------------------------------------------------ #
    # Multi-column composite FK
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_multi_column_fk_merged_into_one_relationship(self, mock_dispatch):
        """2 columns for same (child, parent) → 1 RelationshipInfo with both columns."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock(
            [
                _make_relation_mock(
                    "FK_OrderDetails_Orders",
                    "OrderDetails",
                    "Orders",
                    [("OrderID", "ID"), ("LineNo", "LineNo")],
                    attributes=0,
                )
            ]
        )
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        assert len(result) == 1
        rel = result[0]
        assert rel.name == "FK_OrderDetails_Orders"
        assert rel.table == "OrderDetails"
        assert rel.foreign_table == "Orders"
        assert rel.columns == ["OrderID", "LineNo"]
        assert rel.foreign_columns == ["ID", "LineNo"]

    # ------------------------------------------------------------------ #
    # Multiple independent FKs
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_multiple_independent_fks_returned_separately(self, mock_dispatch):
        """2 unrelated FKs → 2 RelationshipInfo entries."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock(
            [
                _make_relation_mock(
                    "FK_Orders_Customers",
                    "Orders",
                    "Customers",
                    [("CustomerID", "ID")],
                ),
                _make_relation_mock(
                    "FK_Orders_Employees",
                    "Orders",
                    "Employees",
                    [("EmployeeID", "ID")],
                ),
            ]
        )
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        assert len(result) == 2
        names = {r.name for r in result}
        assert "FK_Orders_Customers" in names
        assert "FK_Orders_Employees" in names

    # ------------------------------------------------------------------ #
    # System relations filtered
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_system_relations_filtered(self, mock_dispatch):
        """Relations whose name starts with `~` or `MSys` are skipped."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock(
            [
                _make_relation_mock(
                    "FK_Orders_Customers",
                    "Orders",
                    "Customers",
                    [("CustomerID", "ID")],
                ),
                _make_relation_mock(
                    "~TMPCache",
                    "Orders",
                    "Whatever",
                    [("X", "Y")],
                ),
                _make_relation_mock(
                    "MSysRelZZZ",
                    "Orders",
                    "Whatever2",
                    [("A", "B")],
                ),
            ]
        )
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        assert len(result) == 1
        assert result[0].name == "FK_Orders_Customers"
        for r in result:
            assert not r.name.startswith("~")
            assert not r.name.startswith("MSys")

    # ------------------------------------------------------------------ #
    # Empty result
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_empty_relations_returns_empty_list(self, mock_dispatch):
        """``Relations.Count == 0`` → [] and Close() still called."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock([])
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        assert result == []
        # Close still happens for an empty DB
        mock_db.Close.assert_called_once()

    # ------------------------------------------------------------------ #
    # Close is called even on exception
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_close_called_even_on_exception(self, mock_dispatch):
        """If iteration raises, db.Close() runs in the finally block."""
        mock_engine = MagicMock()
        mock_db = MagicMock()
        # db.Relations access itself raises
        type(mock_db.Relations).Count = property(
            lambda self_: (_ for _ in ()).throw(RuntimeError("relations boom"))
        )
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        # No exception escapes; reader returns [] on internal error
        assert result == []
        # Critical invariant: Close() was called even though the iteration failed
        mock_db.Close.assert_called_once()

    # ------------------------------------------------------------------ #
    # OpenDatabase raises — returns [] and logs WARNING
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_open_database_raises_returns_empty_with_warning(self, mock_dispatch):
        """OpenDatabase failure → [] and WARNING logged, no exception."""
        mock_engine = MagicMock()
        mock_engine.OpenDatabase.side_effect = RuntimeError(
            "Cannot open database — file in use"
        )
        mock_dispatch.return_value = mock_engine

        result = DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        assert result == []
        # WARNING was logged
        self.logger.warning.assert_called()

    # ------------------------------------------------------------------ #
    # OpenDatabase OK, db.Relations access raises — Close in finally
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_open_ok_relations_access_raises_returns_empty_close_in_finally(
        self, mock_dispatch
    ):
        """db.Relations raises after a successful open → [] and Close() still called."""
        mock_engine = MagicMock()
        mock_db = MagicMock()
        rels = mock_db.Relations
        type(rels).Count = property(
            lambda self_: (_ for _ in ()).throw(RuntimeError("Relations access boom"))
        )
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        result = DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        assert result == []
        mock_db.Close.assert_called_once()

    # ------------------------------------------------------------------ #
    # Password is forwarded to the connect string
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_password_forwarded_to_open_database(self, mock_dispatch):
        """When password is provided, OpenDatabase gets ``;PWD=<pw>`` in connect str."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock([])
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        DaoAdapter.read_relationships_short_lived(
            self.db_path, "secret", self.logger
        )

        # 4th positional arg of OpenDatabase(name, exclusive, read_only, connect)
        connect_str = mock_engine.OpenDatabase.call_args[0][3]
        assert connect_str == ";PWD=secret"

    # ------------------------------------------------------------------ #
    # Read-only flag is True (so concurrent ODBC reads are not blocked)
    # ------------------------------------------------------------------ #

    @patch("win32com.client.Dispatch")
    def test_opens_with_read_only_true(self, mock_dispatch):
        """The short-lived handle must be opened ReadOnly=True."""
        mock_engine = MagicMock()
        mock_db = _make_db_mock([])
        mock_engine.OpenDatabase.return_value = mock_db
        mock_dispatch.return_value = mock_engine

        DaoAdapter.read_relationships_short_lived(
            self.db_path, self.password, self.logger
        )

        # 3rd positional arg is read_only
        assert mock_engine.OpenDatabase.call_args[0][2] is True

    # ------------------------------------------------------------------ #
    # Static method — callable on the class without an instance
    # ------------------------------------------------------------------ #

    def test_callable_as_static_method(self):
        """read_relationships_short_lived is a static method — callable on the class."""
        # Smoke-test the descriptor: it's reachable without an instance
        assert callable(DaoAdapter.read_relationships_short_lived)
        # And the static helper used by the long-lived path too
        assert callable(DaoAdapter._read_relations_from_db)
