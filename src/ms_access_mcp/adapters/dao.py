"""DaoAdapter lifecycle + DaoSession helper + schema/property read surface
(slices 1—5 of dao-first-linked-tables-properties).

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
  helpers. Slice 5 adds the row CRUD and table/index DDL surface.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from types import TracebackType
from typing import Any

from .com_dispatcher import DAO_DB_FAIL_ON_ERROR, ComDispatcher
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
        # Slice 5: export strategies. Same registry as
        # ``OdbcAdapter`` / ``WinComAdapter`` so the strategy
        # pattern (csv / json / excel) is reusable across backends.
        from .export.strategies import ExportStrategySelector

        self._strategy_selector: ExportStrategySelector = ExportStrategySelector()

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

    # ------------------------------------------------------------------ #
    # SQL value formatting + WHERE sanitization
    # ------------------------------------------------------------------ #
    #
    # DAO's ``Database.Execute`` does not support ``?`` parameter
    # placeholders the way pyodbc does — values must be inlined into
    # the SQL string. The helpers below match the format used by
    # ``WinComAdapter`` (slice 3+) so DAO-emitted SQL is byte-identical
    # to COM-emitted SQL for the same input.
    #
    # The WHERE-string allowlist is the same one WinComAdapter uses,
    # kept here as a class attribute so tests can pin the contract.

    # Regex allowlist for raw WHERE strings in update_data/delete_data.
    # Permitted characters: alphanumeric, whitespace, SQL operators
    # (., = < > ( ) ' " - %).
    _WHERE_ALLOWLIST_RE = r"^[\w\s\.\,\=\<\>\(\)\'\"\-%]+$"
    # Dangerous DDL/DML keywords that have no legitimate use in a raw
    # WHERE clause. Mirrors the policy in WinComAdapter.
    _DANGEROUS_WHERE_PATTERNS = (
        r"--",  # SQL single-line comment
        r"/\*",  # SQL block comment start
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bTRUNCATE\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b",
        r"\bUNION\b",
        # Tautology patterns: OR followed by digit-comparison (OR 1=1).
        r"^\s*OR\s+\d+\s*=\s*\d+",
    )

    @staticmethod
    def _format_dao_value(val: object) -> str:
        """Format a Python value for inline use in DAO SQL.

        DAO.Execute does NOT support ``?`` parameter placeholders the way
        ADO does, so values are formatted as SQL literals:

        * ``None`` → ``NULL``
        * ``bool`` → ``-1`` (True) or ``0`` (False) — Access convention
        * ``int`` / ``float`` → ``str(val)``
        * ``datetime`` → ``#YYYY-MM-DD HH:MM:SS#`` (Access date literal)
        * ``str`` → single-quoted with internal ``'`` doubled
        """
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "-1" if val else "0"
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, datetime):
            return f"#{val.strftime('%Y-%m-%d %H:%M:%S')}#"
        # String — single-quote and escape internal quotes
        s = str(val).replace("'", "''")
        return f"'{s}'"

    @staticmethod
    def _sanitize_where_string(where_str: str) -> str | None:
        """Validate a raw WHERE string against the SQL injection allowlist.

        Returns the validated string if it passes, or ``None`` if it
        contains characters or keywords outside the policy. The caller
        is responsible for turning ``None`` into a structured error
        response.
        """
        if not re.match(DaoAdapter._WHERE_ALLOWLIST_RE, where_str):
            return None
        for pattern in DaoAdapter._DANGEROUS_WHERE_PATTERNS:
            if re.search(pattern, where_str, re.IGNORECASE):
                return None
        return where_str

    @staticmethod
    def _access_sql_type(access_type: str, size: int = 255) -> str:
        """Map an Access type name to its Jet SQL DDL string.

        Mirrors :meth:`WinComAdapter._access_sql_type` so DAO-emitted
        DDL is identical to COM-emitted DDL for the same input.
        """
        type_map = {
            "Text": f"VARCHAR({size})",
            "Long Integer": "INTEGER",
            "Integer": "SMALLINT",
            "Byte": "BYTE",
            "Currency": "MONEY",
            "Single": "SINGLE",
            "Double": "DOUBLE",
            "Date/Time": "DATETIME",
            "Memo": "MEMO",
            "Boolean": "BIT",
            "Binary": "BINARY",
            "GUID": "GUID",
            "Big Integer": "BIGINT",
            "Unsigned Byte": "BYTE",
            "Unsigned Integer": "INTEGER",
            "Unsigned Long Integer": "INTEGER",
            "Decimal": "DECIMAL",
            "Counter": "COUNTER",
            "AutoNumber": "COUNTER",
        }
        return type_map.get(access_type, "VARCHAR(255)")

    # ------------------------------------------------------------------ #
    # IDataAdapter (row CRUD + raw SQL) — slice 5
    # ------------------------------------------------------------------ #
    #
    # Spec §1 "CRUD via DAO": all IDataAdapter methods dispatch to DAO
    # on the shared ComDispatcher STA thread. Result shapes match
    # OdbcAdapter's existing contract so callers stay uniform across
    # backends (``{"success", "rows", "count", "columns"}`` for
    # queries, ``{"success", "affected"}`` for writes).

    def execute_query(self, sql: str, params: list | None = None) -> dict:
        """Execute a SQL ``SELECT`` via DAO ``OpenRecordset``.

        Args:
            sql: SELECT statement to execute.
            params: Not used for DAO — kept for protocol compatibility.

        Returns:
            dict with ``success``, ``rows`` (list[dict]),
            ``count`` (int), ``columns`` (list[str]), and on failure
            ``error`` (str). Shape matches :meth:`OdbcAdapter.execute_query`.
        """
        _ = params
        if not self._dispatcher.is_connected():
            return {
                "success": False,
                "rows": [],
                "count": 0,
                "columns": [],
                "error": "Not connected",
            }

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                rs = db.OpenRecordset(sql)
                if rs.EOF:
                    rs.Close()
                    return {"success": True, "rows": [], "count": 0, "columns": []}

                columns = []
                for i in range(rs.Fields.Count):
                    columns.append(rs.Fields(i).Name)

                results: list[dict] = []
                while not rs.EOF:
                    row: dict = {}
                    for i, col in enumerate(columns):
                        val = rs.Fields(i).Value
                        if val is not None and hasattr(val, "strftime"):
                            val = val.isoformat()
                        row[col] = val
                    results.append(row)
                    rs.MoveNext()

                rs.Close()
                return {
                    "success": True,
                    "rows": results,
                    "count": len(results),
                    "columns": columns,
                }
            except Exception as e:
                return {
                    "success": False,
                    "rows": [],
                    "count": 0,
                    "columns": [],
                    "error": str(e),
                }

        return self._dispatcher.call(_do)

    def insert_data(self, table_name: str, data: dict | list[dict]) -> dict:
        """Insert one or more rows via DAO ``Execute`` with inline values.

        Args:
            table_name: Name of the target table.
            data: A single dict for one row, or a list of dicts for
                multiple rows. Values are formatted as DAO SQL literals
                via :meth:`_format_dao_value` — DAO cannot bind ``?``
                placeholders.

        Returns:
            dict with ``success`` and ``affected`` (int), plus
            ``error`` on failure. Shape matches
            :meth:`OdbcAdapter.insert_data`.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected", "affected": 0}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                rows = data if isinstance(data, list) else [data]
                total_affected = 0
                for row in rows:
                    cols = ", ".join(f"[{c}]" for c in row.keys())
                    vals = ", ".join(self._format_dao_value(v) for v in row.values())
                    sql = f"INSERT INTO [{table_name}] ({cols}) VALUES ({vals})"
                    db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                    total_affected += db.RecordsAffected
                return {"success": True, "affected": total_affected}
            except Exception as e:
                return {"success": False, "error": str(e), "affected": 0}

        return self._dispatcher.call(_do)

    def update_data(
        self,
        table_name: str,
        set_dict: dict,
        where_dict: dict | str | None = None,
    ) -> dict:
        """Update rows via DAO ``Execute`` with inline values.

        Args:
            table_name: Name of the target table.
            set_dict: Column → new value pairs to set.
            where_dict: Dict of conditions (ANDed), a raw SQL WHERE
                string (validated against the allowlist), or ``None``
                to update all rows.

        Returns:
            dict with ``success`` and ``affected`` (int), plus
            ``error`` on failure.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected", "affected": 0}

        # Sanitize raw WHERE strings BEFORE entering the dispatcher —
        # injection rejection must never reach the DAO engine.
        if isinstance(where_dict, str):
            if self._sanitize_where_string(where_dict) is None:
                return {
                    "success": False,
                    "error": "where_dict contains disallowed characters — SQL injection blocked",
                    "affected": 0,
                }

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                set_clause = ", ".join(
                    f"[{c}] = {self._format_dao_value(v)}" for c, v in set_dict.items()
                )
                sql = f"UPDATE [{table_name}] SET {set_clause}"
                if where_dict is not None:
                    if isinstance(where_dict, str):
                        sql += f" WHERE {where_dict}"
                    else:
                        where_clause = " AND ".join(
                            f"[{c}] = {self._format_dao_value(v)}" for c, v in where_dict.items()
                        )
                        sql += f" WHERE {where_clause}"
                db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                return {"success": True, "affected": db.RecordsAffected}
            except Exception as e:
                return {"success": False, "error": str(e), "affected": 0}

        return self._dispatcher.call(_do)

    def delete_data(
        self,
        table_name: str,
        where_dict: dict | str | None = None,
    ) -> dict:
        """Delete rows via DAO ``Execute``.

        Args:
            table_name: Name of the target table.
            where_dict: Dict of conditions (ANDed), a raw SQL WHERE
                string (validated), or ``None`` to delete all rows.

        Returns:
            dict with ``success`` and ``affected`` (int), plus
            ``error`` on failure.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected", "affected": 0}

        if isinstance(where_dict, str):
            if self._sanitize_where_string(where_dict) is None:
                return {
                    "success": False,
                    "error": "where_dict contains disallowed characters — SQL injection blocked",
                    "affected": 0,
                }

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                sql = f"DELETE FROM [{table_name}]"
                if where_dict is not None:
                    if isinstance(where_dict, str):
                        sql += f" WHERE {where_dict}"
                    else:
                        where_clause = " AND ".join(
                            f"[{c}] = {self._format_dao_value(v)}" for c, v in where_dict.items()
                        )
                        sql += f" WHERE {where_clause}"
                db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                return {"success": True, "affected": db.RecordsAffected}
            except Exception as e:
                return {"success": False, "error": str(e), "affected": 0}

        return self._dispatcher.call(_do)

    def execute_raw_sql(self, sql: str) -> int:
        """Execute arbitrary SQL via DAO ``Execute``.

        Returns:
            int: Number of records affected. Raises ``RuntimeError``
            when not connected so callers can distinguish "no database"
            from "zero rows affected".
        """
        if not self._dispatcher.is_connected():
            raise RuntimeError("Not connected")

        def _do() -> int:
            db = self._dispatcher.current_db
            db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
            return db.RecordsAffected

        return self._dispatcher.call(_do)

    def _execute_raw(self, sql: str) -> int:
        """Strategy-pattern hook for ``ExportStrategy.execute_raw``.

        Bound into the export ``ExportContext`` so ``CsvStrategy`` /
        ``ExcelStrategy`` can issue IISAM ``INSERT INTO [Text;...]
        SELECT ...`` statements on the same long-lived DAO handle.
        """
        return self.execute_raw_sql(sql)

    def export_data(
        self,
        sql: str,
        file_path: str,
        format: str = "csv",
        **options: Any,
    ) -> dict:
        """Export the result of a SQL SELECT query to a file.

        Delegates to the same ``ExportStrategy`` registry used by
        :class:`OdbcAdapter` and :class:`WinComAdapter`. The strategy
        tries an Access-engine IISAM fast path first (for CSV and
        Excel) and falls back to a Python-side writer when the engine
        is unavailable or the format has no IISAM support (JSON).

        Args:
            sql: Raw ``SELECT`` query to execute.
            file_path: Destination file path.
            format: ``"csv"`` (default), ``"json"``, or ``"excel"``.
            **options: Format-specific options forwarded to the strategy.

        Returns:
            dict with ``success`` and ``rows_exported`` / ``error``.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        from .export.strategies import ExportContext

        try:
            strategy = self._strategy_selector.get(format)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        context = ExportContext(
            sql=sql,
            file_path=file_path,
            options=options,
            execute_query=self.execute_query,
            execute_raw=self._execute_raw,
        )
        return strategy.export(context)

    # ------------------------------------------------------------------ #
    # ISchemaAdapter (table/index DDL) — slice 5
    # ------------------------------------------------------------------ #
    #
    # Spec §1 "Schema, queries, indexes via DAO": the table DDL and
    # index DDL surfaces are implemented via DAO ``Execute`` for DDL
    # (``CREATE TABLE`` / ``DROP TABLE`` / ``CREATE INDEX`` /
    # ``DROP INDEX`` / ``ALTER TABLE``) and via DAO object model for
    # renames (``TableDef.Name``, ``Field.Name``). Relation cleanup
    # in ``delete_table`` matches ``WinComAdapter.delete_table`` —
    # inbound and outbound relations are removed first so a
    # foreign-key-referenced table can still be dropped.

    def create_table(self, table_name: str, columns: list[dict]) -> dict:
        """Create a new table via DAO ``Execute`` with Jet DDL.

        Args:
            table_name: Name of the table to create.
            columns: List of dicts with keys ``name`` (str), ``type``
                (Access type name), ``size`` (int, optional, default 255),
                ``required`` (bool, optional, default False),
                ``is_autoincrement`` (bool, optional, default False),
                ``primary_key`` (bool, optional, default False).

        Returns:
            dict with ``success`` or ``success=False`` + ``error``.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                col_defs: list[str] = []
                pk_col: str | None = None
                for col in columns:
                    col_name = col["name"]
                    col_type = col.get("type", "Text")
                    col_size = col.get("size", 255)
                    required = col.get("required", False)
                    is_autoincrement = col.get("is_autoincrement", False)
                    is_pk = col.get("primary_key", False)

                    type_sql = self._access_sql_type(col_type, col_size)
                    col_def = f"[{col_name}] {type_sql}"
                    if is_autoincrement or is_pk:
                        col_def += " NOT NULL"
                        if is_autoincrement:
                            pk_col = col_name
                    elif required:
                        col_def += " NOT NULL"
                    col_defs.append(col_def)

                if pk_col:
                    col_defs.append(f"PRIMARY KEY ([{pk_col}])")

                sql = f"CREATE TABLE [{table_name}] ({', '.join(col_defs)})"
                db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def delete_table(self, table_name: str) -> dict:
        """Drop a table via DAO ``Execute`` after removing referencing relations.

        Iterates ``db.Relations`` in reverse order and deletes any
        relation where the target table is either ``Table`` or
        ``ForeignTable``, then issues ``DROP TABLE``. Reverse-order
        iteration avoids index-shift bugs when an element is removed.

        Args:
            table_name: Name of the table to drop.

        Returns:
            dict with ``success`` or ``success=False`` + ``error``.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                # Walk Relations in reverse so deleting one doesn't
                # shift the indices of the rest.
                for i in range(db.Relations.Count - 1, -1, -1):
                    rel = db.Relations(i)
                    if rel.Table == table_name or rel.ForeignTable == table_name:
                        db.Relations.Delete(rel.Name)
                db.Execute(f"DROP TABLE [{table_name}]", DAO_DB_FAIL_ON_ERROR)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def create_index(
        self,
        table_name: str,
        index_name: str,
        columns: list[str],
        unique: bool = False,
        ignore_nulls: bool = False,
    ) -> dict:
        """Create an index via Jet DDL.

        Jet SQL: ``CREATE [UNIQUE] INDEX [name] ON [table] (col_list) [WITH IGNORE NULL]``.

        Args:
            table_name: Name of the table to index.
            index_name: Name for the new index.
            columns: List of column names to include.
            unique: If ``True``, creates a ``UNIQUE`` index.
            ignore_nulls: If ``True``, appends ``WITH IGNORE NULL``.

        Returns:
            dict with ``success`` or ``success=False`` + ``error``.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                col_list = ", ".join(f"[{col}]" for col in columns)
                sql = "CREATE "
                if unique:
                    sql += "UNIQUE "
                sql += f"INDEX [{index_name}] ON [{table_name}] ({col_list})"
                if ignore_nulls:
                    sql += " WITH IGNORE NULL"
                db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def drop_index(self, table_name: str, index_name: str) -> dict:
        """Drop an index via Jet DDL.

        Jet SQL: ``DROP INDEX [name] ON [table]``. The ``ON [table]``
        clause is **required** in Jet SQL — Access rejects the ODBC
        form.

        Args:
            table_name: Name of the table containing the index.
            index_name: Name of the index to drop.

        Returns:
            dict with ``success`` or ``success=False`` + ``error``.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                db.Execute(
                    f"DROP INDEX [{index_name}] ON [{table_name}]",
                    DAO_DB_FAIL_ON_ERROR,
                )
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def alter_table(self, table_name: str, operations: list[dict]) -> dict:
        """Apply a list of schema modifications to a table.

        Supports ``add_column`` / ``drop_column`` / ``modify_column``
        via Jet DDL, and ``rename_table`` / ``rename_column`` via the
        DAO object model (``TableDef.Name``, ``Field.Name``).
        Unknown actions are reported per-op; per-op failures do not
        abort the rest of the batch.

        Args:
            table_name: Target table name.
            operations: List of operation dicts, each with ``action``
                and ``params`` keys.

        Returns:
            dict with ``success`` (overall), ``operations`` (per-op
            results), and on connection failure ``error``.
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "operations": [], "error": "Not connected"}

        valid_actions = {
            "add_column",
            "drop_column",
            "modify_column",
            "rename_table",
            "rename_column",
        }
        results: list[dict] = []

        def _do() -> dict:
            for op in operations:
                action = op.get("action")
                params = op.get("params", {})

                if action not in valid_actions:
                    results.append(
                        {
                            "action": action,
                            "success": False,
                            "error": f"Unknown action: {action}",
                        }
                    )
                    continue

                try:
                    if action == "add_column":
                        result = self._alter_table_add_column(table_name, params)
                    elif action == "drop_column":
                        result = self._alter_table_drop_column(table_name, params)
                    elif action == "modify_column":
                        result = self._alter_table_modify_column(table_name, params)
                    elif action == "rename_table":
                        result = self._alter_table_rename_table(table_name, params)
                    elif action == "rename_column":
                        result = self._alter_table_rename_column(table_name, params)
                    else:
                        result = {"success": False, "error": f"Unhandled action: {action}"}
                    results.append({"action": action, **result})
                except Exception as e:
                    results.append({"action": action, "success": False, "error": str(e)})

            overall = all(r["success"] for r in results)
            return {"success": overall, "operations": results}

        return self._dispatcher.call(_do)

    def _alter_table_add_column(self, table_name: str, params: dict) -> dict:
        """Execute ``ALTER TABLE ADD COLUMN`` via DAO DDL."""
        name = params["name"]
        col_type = params.get("type", "Text")
        size = params.get("size", 255)
        nullable = params.get("nullable", True)

        type_sql = self._access_sql_type(col_type, size)
        col_def = f"[{name}] {type_sql}"
        if not nullable:
            col_def += " NOT NULL"
        else:
            col_def += " NULL"

        sql = f"ALTER TABLE [{table_name}] ADD COLUMN {col_def}"
        db = self._dispatcher.current_db
        db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
        return {"success": True}

    def _alter_table_drop_column(self, table_name: str, params: dict) -> dict:
        """Execute ``ALTER TABLE DROP COLUMN`` via DAO DDL."""
        name = params["name"]
        sql = f"ALTER TABLE [{table_name}] DROP COLUMN [{name}]"
        db = self._dispatcher.current_db
        db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
        return {"success": True}

    def _alter_table_modify_column(self, table_name: str, params: dict) -> dict:
        """Execute ``ALTER TABLE ALTER COLUMN`` via DAO DDL."""
        name = params["name"]
        col_type = params.get("type", "Text")
        size = params.get("size", 255)
        nullable = params.get("nullable", True)

        type_sql = self._access_sql_type(col_type, size)
        col_def = f"[{name}] {type_sql}"
        if not nullable:
            col_def += " NOT NULL"
        else:
            col_def += " NULL"

        sql = f"ALTER TABLE [{table_name}] ALTER COLUMN {col_def}"
        db = self._dispatcher.current_db
        db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
        return {"success": True}

    def _alter_table_rename_table(self, table_name: str, params: dict) -> dict:
        """Rename a table via ``TableDef.Name`` assignment."""
        new_name = params["new_name"]
        db = self._dispatcher.current_db
        tdef = db.TableDefs(table_name)
        tdef.Name = new_name
        return {"success": True}

    def _alter_table_rename_column(self, table_name: str, params: dict) -> dict:
        """Rename a column via ``Field.Name`` assignment."""
        old_name = params["name"]
        new_name = params["new_name"]
        db = self._dispatcher.current_db
        tdef = db.TableDefs(table_name)
        field = tdef.Fields(old_name)
        field.Name = new_name
        return {"success": True}
