"""Windows-only DAO reader — extracts foreign keys via DAO.DBEngine.120.

Mirrors the output shape of :class:`ms_access_mcp.adapters.odbc_schema_reader.OdbcSchemaReader`
and :meth:`ms_access_mcp.adapters.schema_inspector.SchemaInspector.get_relationships`
so the front-end ER diagram and ``mcp/schema.py`` get a uniform
``list[RelationshipInfo]`` regardless of which reader is active.

Why this exists:
    The ODBC ``MSysRelationships`` system table is hidden in many Jet/ACE
    builds or fails on machines without the ACE OLEDB provider. DAO exposes
    the same foreign-key metadata via ``Database.Relations`` and is typically
    available on any Windows host that has Microsoft Access or the Access
    runtime installed.

Resource lifecycle:
    Each ``get_relationships()`` call opens the DAO ``Database`` locally
    with ``Exclusive=False, ReadOnly=True`` so a concurrent ODBC read on
    the same ``.accdb`` file is NOT blocked, and ``db.Close()`` runs in
    a ``finally`` block to release the COM handle deterministically.
    Cheap for local Access files; avoids long-lived COM lock conflicts
    and STA apartment-affinity issues across async executor threads.

Failure modes:
    - Missing ``win32com`` / DAO not installed: raised on import / Dispatch.
      The reader catches ``Exception`` at the boundary and returns ``[]``,
      logging a WARNING.
    - ``OpenDatabase`` fails (file in use, bad password): caught and
      ``[]`` returned.
    - Iteration over ``db.Relations`` fails mid-way: DB still closed in
      ``finally``; ``[]`` returned.

Filtering:
    Relations whose name starts with ``~`` (Access temp objects) or
    ``MSys`` (Access system relations) are skipped — same filter as
    :class:`SchemaInspector`.
"""
from __future__ import annotations

import logging
from typing import Any

from ..models.database import RelationshipInfo


class DaoRelationshipReader:
    """Read MS Access relationships via DAO.DBEngine.120 (Windows + Office).

    Args:
        db_path: Absolute path to the ``.accdb`` or ``.mdb`` file.
        password: Optional database password. Appended as ``;PWD=...`` to
            the DAO ``OpenDatabase`` connect string when non-empty.
        logger: Logger for graceful-degradation warnings.
    """

    def __init__(
        self,
        db_path: str,
        password: str = "",
        logger: logging.Logger | None = None,
    ) -> None:
        self._db_path = db_path
        self._password = password
        self._logger = logger or logging.getLogger(__name__)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get all foreign-key relationships from the DAO ``Relations`` collection.

        Returns:
            list[RelationshipInfo]: One entry per FK, with multi-column
            FKs aggregated into a single ``RelationshipInfo``. System
            relations (``~`` and ``MSys`` prefixes) are filtered out.
            Returns ``[]`` on any DAO failure.
        """
        db: Any | None = None
        try:
            db = self._open_database()
            return self._read_relations(db)
        except Exception as e:
            # DAO is best-effort; if the file is locked, the password is
            # wrong, or the engine is missing, we degrade to empty list
            # — the ODBC reader is the canonical fallback.
            self._logger.warning(
                "DaoRelationshipReader.get_relationships failed: %s", e
            )
            return []
        finally:
            if db is not None:
                self._close(db)

    # ------------------------------------------------------------------ #
    # Implementation
    # ------------------------------------------------------------------ #

    def _open_database(self) -> Any:
        """Open the DAO database in read-only, non-exclusive mode.

        ``OpenDatabase(path, Exclusive=False, ReadOnly=True, connect_str)``
        — see https://learn.microsoft.com/en-us/office/client-developer/access/desktop-database-reference/database-opendatabase-method

        Returns the DAO ``Database`` COM object. Never returns ``None``;
        raises on failure.
        """
        # Lazy import — win32com is Windows-only and not installed by
        # default on Linux/macOS CI environments.
        import win32com.client  # type: ignore[import-not-found]

        engine = win32com.client.Dispatch("DAO.DBEngine.120")
        connect_str = f";PWD={self._password}" if self._password else ""
        return engine.OpenDatabase(self._db_path, False, True, connect_str)

    @staticmethod
    def _read_relations(db: Any) -> list[RelationshipInfo]:
        """Walk ``db.Relations`` and project to ``RelationshipInfo`` shape.

        Mirrors the filter (``~`` and ``MSys``) and output shape of
        :class:`SchemaInspector.get_relationships` and the
        ``OdbcSchemaReader`` fallback.
        """
        relationships: list[RelationshipInfo] = []
        rels = db.Relations
        for i in range(rels.Count):
            rel = rels(i)
            if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                continue
            child_cols: list[str] = []
            parent_cols: list[str] = []
            for j in range(rel.Fields.Count):
                f = rel.Fields(j)
                child_cols.append(f.Name)
                parent_cols.append(f.ForeignName)
            relationships.append(
                RelationshipInfo(
                    name=rel.Name,
                    table=rel.Table,
                    foreign_table=rel.ForeignTable,
                    attributes=str(rel.Attributes),
                    columns=child_cols,
                    foreign_columns=parent_cols,
                )
            )
        return relationships

    @staticmethod
    def _close(db: Any) -> None:
        """Close the DAO database. Swallows exceptions on teardown."""
        try:
            db.Close()
        except Exception:
            pass
