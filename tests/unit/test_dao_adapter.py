"""Unit tests for DaoAdapter lifecycle + DaoOperationError + schema/property surface.

Slices 1—4 of dao-first-linked-tables-properties: pins the
construction contract (slice 1), the connect / disconnect /
is_connected lifecycle (slice 2), and the schema/property read
surface (slice 4). CRUD and linked-table surfaces land in slices 5+.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

import pytest

from ms_access_mcp.adapters.com_dispatcher import ComDispatcher
from ms_access_mcp.adapters.dao import DaoAdapter, DaoOperationError
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
