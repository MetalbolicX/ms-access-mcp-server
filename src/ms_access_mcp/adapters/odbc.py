import os
from typing import Any, Optional
import pyodbc
from .base import AccessAdapter
from .com_only_mixin import ComOnlyAdapterMixin
from ..models.database import (
    TableInfo,
    RelationshipInfo,
    QueryInfo,
    LinkedTableInfo,
)
from ..models.migration import TableSchema, ColumnSchema, UnknownMetadata


# Connection string templates for Access databases
ACCESS_DRIVER = "{Microsoft Access Driver (*.mdb, *.accdb)}"
ACE_OLEDB_12 = "Microsoft.ACE.OLEDB.12.0"
ACE_OLEDB_16 = "Microsoft.ACE.OLEDB.16.0"


class OdbcAdapter(ComOnlyAdapterMixin, AccessAdapter):
    """Data-only adapter using pyodbc for fast read-only access.

    Inherits ComOnlyAdapterMixin first so its NotImplementedError stubs
    take precedence over AccessAdapter protocol stubs for COM-only methods.
    Implements IDataAdapter + ISchemaAdapter (via AccessAdapter protocol).
    """

    # Default driver string — used when ACCESS_MCP_ODBC_DRIVER is not set
    DEFAULT_DRIVER = "{Microsoft Access Driver (*.mdb, *.accdb)}"

    def __init__(self, db_path: str | None = None, strategy_selector: Any | None = None) -> None:
        from .export.strategies import ExportStrategySelector

        self._conn: Optional[pyodbc.Connection] = None
        self._db_path: Optional[str] = db_path
        self._strategy_selector: ExportStrategySelector = strategy_selector or ExportStrategySelector()
        self._driver_name: str = (
            os.environ.get("ACCESS_MCP_ODBC_DRIVER", self.DEFAULT_DRIVER).strip()
            or self.DEFAULT_DRIVER
        )

    def connect(self, db_path: str) -> bool:
        """Connect to an Access database via ODBC."""
        if not os.path.exists(db_path):
            return False

        # Build connection string candidates: ACE_OLEDB_16 → ACE_OLEDB_12 → Driver
        ext = os.path.splitext(db_path)[1].lower()
        candidates: list[str] = []
        if ext == ".accdb":
            candidates = [
                f"Provider={ACE_OLEDB_16};Data Source={db_path};",
                f"Provider={ACE_OLEDB_12};Data Source={db_path};",
                f"Driver={self._driver_name};DBQ={db_path};",
            ]
        else:
            candidates = [
                f"Driver={self._driver_name};DBQ={db_path};",
                f"Provider={ACE_OLEDB_12};Data Source={db_path};",
                f"Provider={ACE_OLEDB_16};Data Source={db_path};",
            ]

        last_error: Exception | None = None
        for conn_str in candidates:
            try:
                self._conn = pyodbc.connect(conn_str, autocommit=True)
                self._db_path = db_path
                return True
            except Exception as e:
                last_error = e
                continue

        self._cleanup()
        return False

    def disconnect(self) -> None:
        """Disconnect from the Access database."""
        self._cleanup()

    def _cleanup(self) -> None:
        """Close the ODBC connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        self._db_path = None

    def is_connected(self) -> bool:
        """Check if connected to a database."""
        return self._conn is not None

    # ========================================================================
    # IDataAdapter — Data CRUD
    # ========================================================================

    def execute_query(self, sql: str, params: Optional[list] = None) -> dict:
        """Execute a SQL query and return results."""
        if not self.is_connected():
            return {"success": False, "rows": [], "count": 0, "columns": [], "error": "Not connected"}

        columns: list[str] = []
        results: list[dict] = []
        try:
            cursor = self._conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            columns = [column[0] for column in cursor.description] if cursor.description else []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            cursor.close()
            return {"success": True, "rows": results, "count": len(results), "columns": columns}
        except Exception as e:
            return {"success": False, "rows": [], "count": 0, "columns": [], "error": str(e)}

    def insert_data(self, table_name: str, data: dict | list[dict]) -> dict:
        """Insert one or more rows into a table.

        Args:
            table_name: Name of the table
            data: A single dict for one row, or a list of dicts for multiple rows

        Returns:
            dict with success=True and affected=number of rows inserted
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        if isinstance(data, dict):
            data = [data]

        try:
            cursor = self._conn.cursor()
            total_affected = 0
            for row in data:
                cols = ", ".join(f"[{c}]" for c in row.keys())
                vals = ", ".join("?" for _ in row.values())
                sql = f"INSERT INTO [{table_name}] ({cols}) VALUES ({vals})"
                cursor.execute(sql, tuple(row.values()))
                total_affected += cursor.rowcount
            cursor.close()
            return {"success": True, "affected": total_affected}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_data(self, table_name: str, set_dict: dict, where_dict: dict | str | None = None) -> dict:
        """Update rows in a table.

        Args:
            table_name: Name of the table
            set_dict: Dict of column=value pairs to set
            where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows

        Returns:
            dict with success=True and affected=number of rows updated
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        try:
            cursor = self._conn.cursor()
            set_clause = ", ".join(f"[{c}] = ?" for c in set_dict.keys())
            sql = f"UPDATE [{table_name}] SET {set_clause}"

            params = list(set_dict.values())

            if where_dict is not None:
                if isinstance(where_dict, str):
                    sql += f" WHERE {where_dict}"
                else:
                    where_clause = " AND ".join(f"[{c}] = ?" for c in where_dict.keys())
                    sql += f" WHERE {where_clause}"
                    params.extend(where_dict.values())

            cursor.execute(sql, tuple(params))
            affected = cursor.rowcount
            cursor.close()
            return {"success": True, "affected": affected}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_data(self, table_name: str, where_dict: dict | str | None = None) -> dict:
        """Delete rows from a table.

        Args:
            table_name: Name of the table
            where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows

        Returns:
            dict with success=True and affected=number of rows deleted
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        try:
            cursor = self._conn.cursor()
            sql = f"DELETE FROM [{table_name}]"

            params: list = []
            if where_dict is not None:
                if isinstance(where_dict, str):
                    sql += f" WHERE {where_dict}"
                else:
                    where_clause = " AND ".join(f"[{c}] = ?" for c in where_dict.keys())
                    sql += f" WHERE {where_clause}"
                    params.extend(where_dict.values())

            cursor.execute(sql, tuple(params))
            affected = cursor.rowcount
            cursor.close()
            return {"success": True, "affected": affected}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_data(self, sql: str, file_path: str, format: str = "csv", **options: Any) -> dict:
        """Export the result of a SQL SELECT query to a file.

        Delegates to the appropriate ``ExportStrategy`` registered in
        ``self._strategy_selector``.  The strategy tries an Access-engine
        IISAM fast path first (for CSV and Excel) and falls back to a
        Python-side writer when the engine is unavailable or the format
        has no IISAM support (JSON).

        Args:
            sql: Raw ``SELECT`` query to execute.
            file_path: Destination file path.
            format: Output format — ``"csv"`` (default), ``"json"``, or ``"excel"``.
            **options: Format-specific options forwarded to the strategy.
                Common options: ``delimiter``, ``header``, ``encoding``,
                ``pretty``, ``sheet_name``.

        Returns:
            dict with ``success=True``, ``rows_exported`` (int), ``file_path`` (str),
            or ``success=False``, ``error`` (str).
        """
        if not self.is_connected():
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

    def _execute_raw(self, sql: str) -> int:
        """Run arbitrary SQL through the Access engine (IISAM, DDL, etc.)."""
        cursor = self._conn.cursor()
        cursor.execute(sql)
        affected = cursor.rowcount if cursor.rowcount >= 0 else 0
        cursor.close()
        return affected

    # ========================================================================
    # ISchemaAdapter — Schema Introspection and DDL
    # ========================================================================

    def get_tables(self) -> list[TableInfo]:
        """Get all user tables from the connected database.

        Uses ODBC SQLTables (cursor.tables) instead of MSysObjects
        or information_schema, which are unreliable via the Access ODBC driver.
        """
        if not self.is_connected():
            return []

        tables: list[TableInfo] = []
        try:
            cursor = self._conn.cursor()

            # Enumerate user tables via ODBC SQLTables
            table_names: list[str] = []
            for row in cursor.tables():
                if row.table_type == 'TABLE' and not row.table_name.startswith('MSys'):
                    table_names.append(row.table_name)

            for name in table_names:
                fields = []
                record_count = 0

                try:
                    # Get column metadata via ODBC SQLColumns
                    for col in cursor.columns(name):
                        fields.append({
                            "name": col.column_name,
                            "type": self._pyodbc_type_name(col.type_name),
                            "size": col.column_size or 0,
                            "required": col.nullable == 0,  # SQL_NO_NULLS
                            "allow_zero_length": True,
                        })

                    # Get record count
                    cursor.execute(f"SELECT COUNT(*) FROM [{name}]")
                    count_row = cursor.fetchone()
                    if count_row:
                        record_count = count_row[0]
                except Exception:
                    pass

                tables.append(TableInfo(
                    name=name,
                    fields=fields,
                    record_count=record_count,
                ))

            cursor.close()
        except Exception:
            pass

        return tables

    def get_system_tables(self) -> list[TableInfo]:
        """Get system tables — limited via ODBC."""
        if not self.is_connected():
            return []
        # ODBC can't easily enumerate system tables
        return []

    def get_object_metadata(self, object_name: str) -> dict:
        """Get object metadata — not available via ODBC."""
        return {}

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get relationships — not available via ODBC."""
        return []

    def get_table_schema_plan(self) -> tuple[list[TableSchema], UnknownMetadata]:
        """Build a best-effort table schema plan from ODBC metadata.

        ODBC cannot reliably expose Access-only metadata (FK/index/default/autoincrement),
        so these are explicitly marked unknown.
        """
        tables = self.get_tables()
        schema_tables: list[TableSchema] = []
        for table in tables:
            columns = [
                ColumnSchema(
                    name=field.name,
                    source_type=field.type,
                    max_length=field.size if field.size > 0 else None,
                    allow_null=not field.required,
                    is_autoincrement=False,
                    default_value=None,
                )
                for field in table.fields
            ]
            schema_tables.append(TableSchema(name=table.name, columns=columns))

        return (
            schema_tables,
            UnknownMetadata(
                primary_keys=True,
                foreign_keys=True,
                defaults=True,
                indexes=True,
                autoincrement=True,
            ),
        )

    def generate_sql(self, output_path: str) -> dict:
        """Generate SQL DDL — not available via ODBC."""
        return {"success": False, "error": "Not available via ODBC"}

    def execute_sql_script(self, script_path: str) -> dict:
        """Execute SQL script — not available via ODBC."""
        raise NotImplementedError("execute_sql_script requires COM (WinComAdapter)")

    def execute_raw_sql(self, sql: str) -> int:
        """Execute raw SQL via pyodbc cursor. Returns rows affected."""
        if not self.is_connected():
            raise RuntimeError("Not connected")
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql)
            return cursor.rowcount if cursor.rowcount >= 0 else 0
        finally:
            cursor.close()

    # ========================================================================
    # Query CRUD (ISchemaAdapter)
    # ========================================================================

    def get_queries(self) -> list[QueryInfo]:
        """Get all saved queries (stored views) from the database."""
        if not self.is_connected():
            return []

        queries: list[QueryInfo] = []
        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT TABLE_NAME, VIEW_DEFINITION
                FROM INFORMATION_SCHEMA.VIEWS
                WHERE TABLE_SCHEMA = 'dbo'
                AND TABLE_NAME NOT LIKE '~%'
                ORDER BY TABLE_NAME
            """)
            for row in cursor.fetchall():
                queries.append(QueryInfo(
                    name=row[0],
                    sql=row[1],
                    type="select",  # Views are typically select queries
                ))
            cursor.close()
        except Exception:
            pass
        return queries

    def create_query(self, name: str, sql: str) -> dict:
        """Create a new stored query (Access querydef implemented as SQL view)."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        try:
            cursor = self._conn.cursor()
            cursor.execute(f"CREATE VIEW [{name}] AS {sql}")
            cursor.close()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_query_sql(self, name: str, sql: str) -> dict:
        """Update SQL of an existing query (recreate the view)."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        try:
            cursor = self._conn.cursor()
            # Drop existing view first
            cursor.execute(f"DROP VIEW [{name}]")
            # Create new view with updated SQL
            cursor.execute(f"CREATE VIEW [{name}] AS {sql}")
            cursor.close()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_query(self, name: str) -> dict:
        """Delete a stored query (drop the view)."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        try:
            cursor = self._conn.cursor()
            cursor.execute(f"DROP VIEW [{name}]")
            cursor.close()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Table CRUD (ISchemaAdapter)
    # ========================================================================

    def create_table(self, table_name: str, columns: list[dict]) -> dict:
        """Create a new table in the database.

        Args:
            table_name: Name of the table to create
            columns: List of dicts with keys: name (str), type (str),
                     size (int, optional), nullable (bool, optional)

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        ODBC_TYPE_MAP = {
            "Text": "VARCHAR",
            "Long Integer": "INT",
            "Integer": "SMALLINT",
            "Boolean": "BIT",
            "Date/Time": "DATETIME",
            "Currency": "MONEY",
            "Memo": "TEXT",
            "Double": "FLOAT",
            "Single": "REAL",
            "Binary": "VARBINARY",
        }

        col_defs = []
        for col in columns:
            name = col["name"]
            odbc_type = ODBC_TYPE_MAP.get(col["type"], "VARCHAR")
            size = col.get("size", 255) if col["type"] == "Text" else 0
            nullable = col.get("nullable", True)

            if size > 0 and col["type"] in ("Text",):
                col_def = f"[{name}] {odbc_type}({size})"
            elif odbc_type in ("VARCHAR",):
                col_def = f"[{name}] {odbc_type}({size or 255})"
            else:
                col_def = f"[{name}] {odbc_type}"

            if not nullable:
                col_def += " NOT NULL"
            else:
                col_def += " NULL"

            col_defs.append(col_def)

        ddl = f"CREATE TABLE [{table_name}] ({', '.join(col_defs)})"

        try:
            cursor = self._conn.cursor()
            cursor.execute(ddl)
            cursor.close()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_table(self, table_name: str) -> dict:
        """Delete a table from the database.

        Args:
            table_name: Name of the table to delete

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        try:
            cursor = self._conn.cursor()
            cursor.execute(f"DROP TABLE [{table_name}]")
            cursor.close()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Linked Tables (ISchemaAdapter)
    # ========================================================================

    def get_linked_tables(self) -> dict:
        """Get linked tables — not available via ODBC."""
        return {"success": False, "error": "Not available via ODBC"}

    def create_linked_table(self, name: str, source_table: str, connect_string: str) -> dict:
        """Create linked table — not available via ODBC."""
        return {"success": False, "error": "Not available via ODBC"}

    def refresh_linked_table(self, name: str) -> dict:
        """Refresh linked table — not available via ODBC."""
        return {"success": False, "error": "Not available via ODBC"}

    def unlink_table(self, name: str) -> dict:
        """Unlink table — not available via ODBC."""
        return {"success": False, "error": "Not available via ODBC"}

    # ========================================================================
    # Schema DDL Export (ISchemaAdapter)
    # ========================================================================

    def export_schema_ddl(self, output_dir: str) -> dict:
        """Export schema DDL using ODBC introspection."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}
        return self._export_schema_ddl(output_dir)

    def _export_schema_ddl(self, output_dir: str) -> dict:
        """Internal DDL export using ODBC introspection."""
        from pathlib import Path

        tables = self.get_tables()
        relationships = self.get_relationships()

        schema_dir = Path(output_dir) / "schema"
        schema_dir.mkdir(parents=True, exist_ok=True)

        ddl_tables_path = schema_dir / "ddl_tables.sql"
        ddl_rels_path = schema_dir / "ddl_relationships.sql"

        # Generate CREATE TABLE statements
        with open(ddl_tables_path, "w", encoding="utf-8") as f:
            f.write("-- Access Table DDL\n-- Generated by ms-access-mcp-server\n\n")
            for table in tables:
                f.write(f"CREATE TABLE [{table.name}] (\n")
                col_defs = []
                for field in table.fields:
                    col_def = f"  [{field.name}] {field.type}"
                    if field.required:
                        col_def += " NOT NULL"
                    else:
                        col_def += " NULL"
                    col_defs.append(col_def)
                f.write(",\n".join(col_defs))
                f.write("\n);\n\n")

        # Generate relationship constraints
        with open(ddl_rels_path, "w", encoding="utf-8") as f:
            f.write("-- Access Relationship DDL\n-- Generated by ms-access-mcp-server\n\n")
            for rel in relationships:
                f.write(f"-- Relationship: {rel.name}\n")
                f.write(f"-- Table: {rel.table}, Foreign Table: {rel.foreign_table}\n")
                f.write(f"-- Attributes: {rel.attributes}\n")
                f.write(f"ALTER TABLE [{rel.table}] ADD CONSTRAINT [{rel.name}] ")
                f.write(f"FOREIGN KEY REFERENCES [{rel.foreign_table}];\n")

        return {
            "success": True,
            "ddl_tables": str(ddl_tables_path),
            "ddl_relationships": str(ddl_rels_path),
            "tables_exported": len(tables),
            "relationships_exported": len(relationships),
        }

    # ========================================================================
    # Compact/repair and copy — special implementations (not from mixin)
    # ========================================================================

    def compact_repair(self, action: str, source_path: str, dest_path: str, keep_original: bool = True) -> dict:
        """Compact or repair database — not available via ODBC."""
        if action not in ("compact", "repair"):
            return {"success": False, "error": f"Invalid action '{action}'. Must be 'compact' or 'repair'."}
        return {"success": False, "error": "Not available via ODBC"}

    def copy_database(self, source: str, dest: str) -> bool:
        """Copy database file via file system copy (not COM)."""
        import shutil
        try:
            shutil.copy2(source, dest)
            return True
        except Exception:
            return False

    # ========================================================================
    # Internal helpers
    # ========================================================================

    def _pyodbc_type_name(self, sql_type: str) -> str:
        """Map SQL Server/Access type string to friendly name."""
        type_upper = sql_type.upper() if sql_type else ""
        type_map = {
            "VARCHAR": "Text",
            "CHAR": "Text",
            "TEXT": "Text",
            "MEMO": "Memo",
            "INTEGER": "Long Integer",
            "INT": "Long Integer",
            "BIGINT": "Big Integer",
            "SMALLINT": "Integer",
            "TINYINT": "Byte",
            "BIT": "Boolean",
            "DATETIME": "Date/Time",
            "DATE": "Date/Time",
            "TIME": "Date/Time",
            "TIMESTAMP": "Date/Time",
            "DECIMAL": "Decimal",
            "NUMERIC": "Decimal",
            "MONEY": "Currency",
            "CURRENCY": "Currency",
            "FLOAT": "Double",
            "REAL": "Single",
            "DOUBLE": "Double",
            "BINARY": "Binary",
            "VARBINARY": "Binary",
            "IMAGE": "Binary",
            "GUID": "GUID",
        }
        return type_map.get(type_upper, sql_type)