"""DaoAdapter lifecycle + DaoSession helper + schema/property read surface
(slices 1—4 of dao-first-linked-tables-properties).

* :class:`DaoSession` — reusable DAO open/close context manager,
  extracted from :class:`DaoRelationshipReader`. Used for short-lived,
  read-only metadata handles.
* :class:`DaoOperationError` — canonical DAO failure surface.
* :class:`DaoAdapter` — Windows-only DAO backend owning a long-lived
  ``DAO.DBEngine.120`` handle on the shared ``ComDispatcher`` STA
  thread. Slice 2 adds the ``connect()`` / ``disconnect()`` /
  ``is_connected()`` lifecycle. Slice 4 adds the schema/property read
  surface: it composes :class:`SchemaInspector` and
  :class:`DbOperations` over its dispatcher and delegates each
  ``ISchemaAdapter`` / ``IDatabasePropertiesAdapter`` method to those
  helpers. CRUD and linked-table surfaces land in slice 5+.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any

from .com_dispatcher import ComDispatcher
from .db_operations import DbOperations
from .schema_inspector import SchemaInspector

logger = logging.getLogger(__name__)

# ===================================================================== #
# DaoSession — context manager
# ===================================================================== #


class DaoSession:
    """Context manager for a short-lived DAO ``Database`` handle.

    Args:
        db_path: Absolute path to the ``.accdb`` or ``.mdb`` file.
        password: Optional database password; appended as ``;PWD=...``.
        read_only: ``True`` (default) opens with ``ReadOnly=True`` so
            concurrent ODBC readers are not blocked.

    The caller drives ``DaoSession`` from inside ``dispatcher.call(...)``
    so the open/close happens on the STA thread.
    """

    def __init__(
        self,
        db_path: str,
        password: str = "",
        read_only: bool = True,
    ) -> None:
        self.path: str = db_path
        self._password: str = password
        self.read_only: bool = read_only
        self.db: Any | None = None

    def __enter__(self) -> DaoSession:
        self.db = self._open_database()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # Returning None → do not suppress body exceptions. The close
        # is the finally-equivalent guarantee.
        self._close()

    def close(self) -> None:
        """Close the DAO database if open. Idempotent."""
        self._close()

    def _open_database(self) -> Any:
        import win32com.client  # type: ignore[import-not-found]

        engine = win32com.client.Dispatch("DAO.DBEngine.120")
        connect_str = f";PWD={self._password}" if self._password else ""
        return engine.OpenDatabase(self.path, False, self.read_only, connect_str)

    def _close(self) -> None:
        if self.db is None:
            return
        try:
            self.db.Close()
        except Exception:
            pass
        finally:
            self.db = None


# ===================================================================== #
# DaoOperationError + DaoAdapter
# ===================================================================== #


class DaoOperationError(Exception):
    """Raised by DaoAdapter for any DAO operation failure.

    Carries ``message`` and the original ``cause`` exception so callers
    can log, mark the adapter unhealthy, and fall back to ODBC.
    """

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.cause: BaseException | None = cause


class DaoAdapter:
    """Windows-only DAO backend with a long-lived ``Database`` handle.

    The adapter owns no thread of its own — it drives the shared
    :class:`ComDispatcher` STA thread via ``open_dao_database`` /
    ``close_dao_database`` so the handle is reused across all
    operations. Per-call ``OpenDatabase`` is forbidden by contract.

    Args:
        db_path: Absolute path to the ``.accdb`` or ``.mdb`` file. Used
            as the default for :meth:`connect` if no override is given.
        dispatcher: Optional :class:`ComDispatcher`. When ``None``
            (default) the adapter owns its own. Slice 5 will inject
            ``WinComAdapter``'s dispatcher to share the STA thread.

    Lifecycle:
        A fresh adapter is **not** connected. Call :meth:`connect` to
        open the long-lived handle, :meth:`disconnect` to close it.
        :meth:`is_connected` reflects the adapter's view of the
        dispatcher's handle state.
    """

    def __init__(
        self,
        db_path: str,
        dispatcher: ComDispatcher | None = None,
    ) -> None:
        self._db_path: str = db_path
        self._dispatcher: ComDispatcher = dispatcher or ComDispatcher()
        # Slice 2: connection lifecycle state. The adapter is the
        # source of truth for "is this instance connected" — the
        # dispatcher may be shared with other adapters in slice 5,
        # so we cannot rely solely on dispatcher._current_db.
        self._connected: bool = False
        # Slice 4: schema/property read surface. Both helpers run on
        # the shared ComDispatcher STA thread; their inner _do()
        # closures read ``self._dispatcher.current_db``, which the
        # adapter populates in :meth:`connect`. Composition over
        # inheritance: we keep SchemaInspector's DAO logic intact
        # and only route the public methods through this class so
        # ``DaoAdapter`` satisfies ``ISchemaAdapter`` and
        # ``IDatabasePropertiesAdapter`` from a single entry point.
        self._schema: SchemaInspector = SchemaInspector(self._dispatcher)
        self._db_ops: DbOperations = DbOperations(self._dispatcher)

    # ------------------------------------------------------------------ #
    # Connection lifecycle (slice 2 of dao-first-linked-tables-properties)
    # ------------------------------------------------------------------ #

    def connect(
        self,
        db_path: str | None = None,
        password: str = "",
    ) -> None:
        """Open a long-lived DAO ``Database`` handle on the STA thread.

        Args:
            db_path: Defaults to the path passed to ``__init__`` if not
                given. When provided, rebinds the adapter to ``db_path``
                (matches spec §1 scenario "Reconnect rebinds").
            password: Optional database password; appended as
                ``;PWD=<password>`` to the DAO connect string only when
                non-empty. The password is **not** persisted on the
                adapter — callers that reconnect must pass it again.

        Raises:
            DaoOperationError: If the open fails (engine missing, file
                in use, bad password, dispatcher not constructable).
                The adapter's connection state is left ``False`` and
                the dispatcher is marked unhealthy so callers can
                detect the failure via :meth:`is_connected`.

        The handle is reused across all subsequent operations; per-call
        ``OpenDatabase`` is forbidden. Calling ``connect()`` on an
        already-connected adapter rebinds via
        :meth:`ComDispatcher.open_dao_database`, which closes the
        existing handle first.
        """
        target_path = db_path if db_path is not None else self._db_path
        # The dispatcher must be running before we can drive the
        # DAO open on its STA thread. ``start()`` is idempotent.
        self._dispatcher.start()
        try:
            self._dispatcher.open_dao_database(
                target_path,
                password=password,
                read_only=False,  # spec §1: Exclusive=False, ReadOnly=False
            )
        except Exception as e:
            # Per spec §1 "Degradation and error surface": on a
            # transient failure the connection is marked unhealthy
            # and is_connected() returns False until disconnect()+connect().
            self._dispatcher.mark_unhealthy()
            self._connected = False
            raise DaoOperationError(
                f"DAO connect failed for {target_path}: {e}",
                cause=e,
            ) from e
        # open_dao_database resets the healthy flag on success
        self._connected = True
        if db_path is not None:
            self._db_path = db_path

    def disconnect(self) -> None:
        """Close the long-lived DAO ``Database`` handle. Idempotent.

        Safe to call on a fresh adapter or on one that has already
        been disconnected. The dispatcher's STA thread is reused for
        the close so apartment affinity is preserved.

        Unlike :meth:`connect`, a clean ``disconnect()`` does **not**
        mark the dispatcher unhealthy — the next successful
        :meth:`connect` will reset health on its own.
        """
        try:
            self._dispatcher.close_dao_database()
        except Exception as e:
            # Close can fail if the COM handle was torn down by
            # another path. Log and still flip our state — the
            # caller asked us to disconnect, so we honor that.
            logger.warning("DaoAdapter.disconnect close_dao_database failed: %s", e)
        finally:
            self._connected = False

    def is_connected(self) -> bool:
        """Return ``True`` if this adapter holds an open DAO handle.

        Reflects the adapter's last-known connection state. A
        successful :meth:`connect` flips this to ``True``; a
        :meth:`connect` failure leaves it ``False``; a
        :meth:`disconnect` always clears it.
        """
        return self._connected

    # ------------------------------------------------------------------ #
    # Schema / property read surface (slice 4 of dao-first-linked-tables-properties)
    # ------------------------------------------------------------------ #
    #
    # Each method below is a thin delegation to either
    # :class:`SchemaInspector` or :class:`DbOperations`. The helpers
    # already gate on the dispatcher's connection state, so a
    # not-connected call returns the spec-mandated empty/zero value
    # (empty list for reads, ``False`` for ``set_database_property``)
    # without raising. This matches the
    # ``ISchemaAdapter``/``IDatabasePropertiesAdapter`` contract for
    # the OdbcAdapter fallback path.
    #
    # Spec coverage:
    #   * §1 Schema/queries/indexes/relationships — read methods below.
    #   * §1 Database properties via DAO — ``get_database_properties``
    #     and ``set_database_property`` delegate to ``DbOperations``,
    #     preserving the four-bucket shape (``startup``, ``app``,
    #     ``project``, ``all``) and the auto-detect type behaviour.
    #   * §1 Spec scenario "Query round-trip" — ``create_query`` →
    #     ``set_query_sql`` → ``get_queries`` round-trips through the
    #     same DAO ``QueryDefs`` collection via the shared dispatcher.

    # --- ISchemaAdapter (read) ----------------------------------------- #

    def get_tables(self) -> list:
        """Return user tables (filtered: no ``MSys`` / ``~`` / linked)."""
        return self._schema.get_tables()

    def get_system_tables(self) -> list:
        """Return system tables (``MSys`` prefix)."""
        return self._schema.get_system_tables()

    def get_queries(self) -> list:
        """Return saved queries, excluding system queries."""
        return self._schema.get_queries()

    def get_indexes(self, table_name: str) -> list:
        """Return all indexes (primary + secondary) for ``table_name``."""
        return self._schema.get_indexes(table_name)

    def get_relationships(self) -> list:
        """Return foreign-key relationships, excluding system relations."""
        return self._schema.get_relationships()

    def get_object_metadata(self, object_name: str) -> dict:
        """Return metadata for a database object (table / form / etc.)."""
        return self._schema.get_object_metadata(object_name)

    def get_table_schema_plan(self) -> tuple:
        """Return ``(list[TableSchema], UnknownMetadata)`` for migration."""
        return self._schema.get_table_schema_plan()

    def generate_sql(self, output_path: str) -> dict:
        """Generate Jet SQL DDL and write to ``output_path``."""
        return self._schema.generate_sql(output_path)

    def get_database_statistics(self) -> dict:
        """Return O(1) database statistics — counts, file info, version."""
        return self._schema.get_database_statistics()

    # --- ISchemaAdapter (write, slice 4 minimum) ----------------------- #

    def create_query(self, name: str, sql: str) -> dict:
        """Create a saved query (QueryDef) on the current database."""
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                qdef = db.CreateQueryDef(name, sql)
                db.QueryDefs.Append(qdef)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def set_query_sql(self, name: str, sql: str) -> dict:
        """Update the SQL of an existing saved query."""
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                qdef = self._dispatcher.current_db.QueryDefs(name)
                qdef.SQL = sql
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def delete_query(self, name: str) -> dict:
        """Delete a saved query from the current database."""
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                self._dispatcher.current_db.QueryDefs.Delete(name)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def create_relationship(
        self,
        table_name: str,
        relationship_name: str,
        columns: list[str],
        foreign_table: str,
        foreign_columns: list[str],
    ) -> dict:
        """Create a foreign-key relationship via DAO Relations."""
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}
        if len(columns) != len(foreign_columns):
            return {
                "success": False,
                "error": "columns and foreign_columns must have same length",
            }
        return self._schema.create_relationship(
            table_name,
            relationship_name,
            columns,
            foreign_table,
            foreign_columns,
        )

    def delete_relationship(self, table_name: str, relationship_name: str) -> dict:
        """Delete a foreign-key relationship via DAO Relations."""
        return self._schema.delete_relationship(table_name, relationship_name)

    # --- IDatabasePropertiesAdapter ------------------------------------ #

    def get_database_properties(self, names: list[str] | None = None) -> dict:
        """Return the four-bucket database properties shape.

        Delegates to :class:`DbOperations` so the
        ``startup``/``app``/``project``/``all`` categorisation and the
        name-filter behaviour match the existing ``DbOperations``
        contract used by :class:`WinComAdapter`.
        """
        return self._db_ops.get_database_properties(names)

    def set_database_property(self, name: str, value: str, type: str | None = None) -> bool:
        """Create or update a database property on the current DB.

        Type is auto-detected (``Boolean`` → ``Long`` → ``Double`` →
        ``Text``) when ``type`` is ``None``.
        """
        return self._db_ops.set_database_property(name, value, type)
