from typing import Any
import os
import psycopg2
from .base import TargetConnector, ConnectorCapabilities
from ..services.schema_mapper import SchemaMapper

class PostgresConnector(TargetConnector):
    """PostgreSQL connector for migration."""

    def __init__(self):
        self._conn: Any = None
        self._schema_mapper = SchemaMapper()

    @property
    def target_type(self) -> str:
        return "postgres"

    def connect(self, connection_string: str) -> bool:
        try:
            self._conn = psycopg2.connect(connection_string)
            self._connection_string = connection_string
            return True
        except Exception:
            self._conn = None
            self._connection_string = None
            return False

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.closed

    def create_table(self, schema: Any) -> bool:
        if not self.is_connected():
            return False
        try:
            ddl = self._schema_mapper.map_table_ddl(schema, "postgres")
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
            placeholders = ", ".join(["%s"] * len(cols))
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
                    "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                    (table_name,)
                )
                return cur.fetchone() is not None
        except Exception:
            return False

    def generate_ddl(self, schema: Any) -> str:
        return self._schema_mapper.map_table_ddl(schema, "postgres")

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            supports_linked_insert_select=False,
            supports_passthrough_insert_select=True,
            supports_checksum=True,
            supports_sampling=True,
            preferred_batch_size=1000,
        )

    def get_odbc_connection_string(self) -> str:
        """Convert libpq DSN (host=... port=... dbname=... user=... password=...) to ODBC format.

        Returns:
            ODBC connection string: DRIVER={PostgreSQL Unicode};SERVER=host;PORT=port;DATABASE=dbname;UID=user;PWD=pass
        """
        if not hasattr(self, "_connection_string") or not self._connection_string:
            raise RuntimeError("PostgresConnector not connected or connection string not available")

        dsn = self._connection_string
        parts = self._parse_dsn(dsn)

        host = parts.get("host", "localhost")
        port = parts.get("port", "5432")
        dbname = parts.get("dbname", parts.get("database", ""))
        user = parts.get("user", "")
        password = parts.get("password", "")

        # Try environment variable for password if not in DSN
        if not password:
            password = os.environ.get("PGPASSWORD", "")

        odbc_parts = [
            "DRIVER={PostgreSQL Unicode}",
            f"SERVER={host}",
            f"PORT={port}",
            f"DATABASE={dbname}",
        ]
        if user:
            odbc_parts.append(f"UID={user}")
        if password:
            odbc_parts.append(f"PWD={password}")

        return ";".join(odbc_parts)

    def _parse_dsn(self, dsn: str) -> dict[str, str]:
        """Parse libpq DSN string into component key-value pairs.

        Supports both space-separated (key=value key2=value2) and
        URL-style (host=localhost port=5432) formats.
        """
        result: dict[str, str] = {}
        # Split on spaces, then parse each key=value pair
        tokens = dsn.split()
        for token in tokens:
            if "=" in token:
                key, val = token.split("=", 1)
                result[key.strip()] = val.strip()
        return result

    def get_row_count(self, table: str) -> int:
        if not self.is_connected():
            return 0
        try:
            with self._conn.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                row = cur.fetchone()
                return int(row[0]) if row else 0
        except Exception:
            return 0

    def get_checksum(self, table: str, columns: list[str]) -> str | None:
        if not self.is_connected() or not columns:
            return None
        try:
            quoted_columns = [f'"{column}"' for column in columns]
            order_by_clause = ", ".join(quoted_columns)
            value_expr = " || '|' || ".join([f"COALESCE({column}::text, '<NULL>')" for column in quoted_columns])
            sql = (
                f"SELECT md5(COALESCE(string_agg({value_expr}, '|' ORDER BY {order_by_clause}), '')) "
                f'FROM "{table}"'
            )
            with self._conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                return str(row[0]) if row and row[0] is not None else None
        except Exception:
            return None

    def sample_rows(self, table: str, columns: list[str], limit: int, offset: int = 0) -> list[dict]:
        if not self.is_connected() or not columns or limit <= 0:
            return []
        try:
            quoted_columns = [f'"{column}"' for column in columns]
            select_clause = ", ".join(quoted_columns)
            order_by_clause = ", ".join(quoted_columns)
            sql = (
                f"SELECT {select_clause} "
                f'FROM "{table}" '
                f"ORDER BY {order_by_clause} LIMIT %s OFFSET %s"
            )
            with self._conn.cursor() as cur:
                cur.execute(sql, (limit, offset))
                rows = cur.fetchall()
                return [dict(zip(columns, row, strict=False)) for row in rows]
        except Exception:
            return []

    def linked_transfer(self, source_adapter: Any, source_table: str, target_table: str) -> int:
        raise NotImplementedError("Linked transfer is adapter-specific and not available in this connector")
