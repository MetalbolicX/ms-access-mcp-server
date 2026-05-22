from typing import Any
import sqlite3
from .base import TargetConnector

class SqliteConnector(TargetConnector):
    """SQLite connector for migration."""

    def __init__(self):
        self._conn: Any = None
        from ..services.schema_mapper import SchemaMapper
        self._schema_mapper = SchemaMapper()

    @property
    def target_type(self) -> str:
        return "sqlite"

    def connect(self, connection_string: str) -> bool:
        try:
            # SQLite connection_string is typically a file path
            self._conn = sqlite3.connect(connection_string)
            return True
        except Exception:
            self._conn = None
            return False

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def is_connected(self) -> bool:
        return self._conn is not None

    def create_table(self, schema: Any) -> bool:
        if not self.is_connected():
            return False
        try:
            ddl = self._schema_mapper.map_table_ddl(schema, "sqlite")
            with self._conn.cursor() as cur:
                cur.execute(ddl)
            self._conn.commit()
            return True
        except Exception:
            self._conn.rollback()
            return False

    def insert_rows(self, table: str, rows: list[dict]) -> int:
        if not self.is_connected() or not rows:
            return 0
        try:
            cols = list(rows[0].keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join([f'"{c}"' for c in cols])
            sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'
            with self._conn.cursor() as cur:
                for row in rows:
                    cur.execute(sql, list(row.values()))
            self._conn.commit()
            return len(rows)
        except Exception:
            self._conn.rollback()
            return 0

    def rollback_table(self, table: str) -> None:
        if not self.is_connected():
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute(f'DROP TABLE IF EXISTS "{table}"')
            self._conn.commit()
        except Exception:
            self._conn.rollback()

    def table_exists(self, table_name: str) -> bool:
        if not self.is_connected():
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
                    (table_name,)
                )
                return cur.fetchone() is not None
        except Exception:
            return False

    def generate_ddl(self, schema: Any) -> str:
        return self._schema_mapper.map_table_ddl(schema, "sqlite")