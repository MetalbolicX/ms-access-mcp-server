import os
from typing import Any, Optional
import pyodbc
from .base import AccessAdapter
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


class OdbcAdapter(AccessAdapter):
    """Data-only adapter using pyodbc for fast read-only access.

    Implements IDataAdapter + ISchemaAdapter.
    COM-only operations raise NotImplementedError.
    """

    def __init__(self) -> None:
        self._conn: Optional[pyodbc.Connection] = None
        self._db_path: Optional[str] = None

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
                f"Driver={ACCESS_DRIVER};DBQ={db_path};",
            ]
        else:
            candidates = [
                f"Driver={ACCESS_DRIVER};DBQ={db_path};",
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

    def export_table_csv(self, sql: str, file_path: str, delimiter: str = ",", header: bool = True, encoding: str = "utf-8") -> dict:
        """Export the result of a SQL query to a CSV file.

        Uses the ACE/Jet Text IISAM (INSERT INTO [Text;...]) as the primary path
        for performance. Falls back to csv.DictWriter when delimiter != "," or
        the encoding is not supported by the Text IISAM code page map.

        Args:
            sql: SQL SELECT query, or a table/query name (backwards compatible)
            file_path: Path to the output CSV file
            delimiter: Field delimiter (default ',')
            header: Whether to write header row (default True)
            encoding: Output file encoding (default 'utf-8')

        Returns:
            dict with success=True, rows_exported=N, file_path
        """
        import csv
        import re
        from pathlib import Path

        # Backwards compat: bare table/query name → SELECT * FROM [name]
        if not re.match(r'^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|EXEC|EXECUTE|WITH)\s', sql, re.IGNORECASE):
            sql = f"SELECT * FROM [{sql}]"

        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _fallback():
            result = self.execute_query(sql)
            if not result.get("success"):
                return {"success": False, "error": result.get("error", "Query failed")}
            rows = result.get("rows", [])
            columns = result.get("columns", [])
            try:
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w", newline="", encoding=encoding) as f:
                    writer = csv.DictWriter(f, fieldnames=columns, delimiter=delimiter)
                    if header:
                        writer.writeheader()
                    writer.writerows(rows)
                return {"success": True, "rows_exported": len(rows), "file_path": file_path}
            except Exception as e:
                return {"success": False, "error": str(e)}

        codepage = self._CODEPAGE_MAP.get(encoding)
        if delimiter != "," or codepage is None:
            return _fallback()

        try:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            conn_str = (
                f"Text;FMT=Delimited;HDR={'YES' if header else 'NO'};"
                f"CharacterSet={codepage};DATABASE={p.parent.absolute()}"
            )
            insert_sql = f"INSERT INTO [{conn_str}].[{p.name}] {sql}"
            cursor = self._conn.cursor()
            cursor.execute(insert_sql)
            rows_affected = cursor.rowcount
            cursor.close()
            return {"success": True, "rows_exported": rows_affected, "file_path": file_path}
        except Exception as e:
            return _fallback()

    def export_query_json(self, query_name: str, file_path: str, pretty: bool = False) -> dict:
        """Export a query to a JSON file.

        Args:
            query_name: Name of the query to export
            file_path: Path to the output JSON file
            pretty: Whether to format JSON with indentation (default False)

        Returns:
            dict with success=True, rows_exported=N, file_path
        """
        import json
        from pathlib import Path

        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        result = self.execute_query(f"SELECT * FROM [{query_name}]")
        if not result.get("success"):
            return {"success": False, "error": result.get("error", "Query failed")}

        rows = result.get("rows", [])

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2 if pretty else None)

            return {"success": True, "rows_exported": len(rows), "file_path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
    # COM-only operations — raise NotImplementedError
    # ========================================================================

    def launch_access(self, visible: bool = False) -> None:
        """Launch Access UI — not supported via ODBC."""
        raise NotImplementedError("OdbcAdapter cannot launch Access UI")

    def close_access(self) -> None:
        """Close Access UI — not supported via ODBC."""
        raise NotImplementedError("OdbcAdapter cannot close Access UI")

    def get_forms(self) -> list:
        """Get forms — not available via ODBC."""
        raise NotImplementedError("get_forms requires COM (WinComAdapter)")

    def get_reports(self) -> list:
        """Get reports — not available via ODBC."""
        raise NotImplementedError("get_reports requires COM (WinComAdapter)")

    def get_macros(self) -> list:
        """Get macros — not available via ODBC."""
        raise NotImplementedError("get_macros requires COM (WinComAdapter)")

    def get_modules(self) -> list:
        """Get modules — not available via ODBC."""
        raise NotImplementedError("get_modules requires COM (WinComAdapter)")

    def form_exists(self, form_name: str) -> bool:
        """Form existence check — not available via ODBC."""
        raise NotImplementedError("form_exists requires COM (WinComAdapter)")

    def report_exists(self, report_name: str) -> bool:
        """Report existence check — not available via ODBC."""
        raise NotImplementedError("report_exists requires COM (WinComAdapter)")

    def get_form_controls(self, form_name: str) -> list:
        """Get form controls — not available via ODBC."""
        raise NotImplementedError("get_form_controls requires COM (WinComAdapter)")

    def open_form(self, form_name: str) -> bool:
        """Open form — not available via ODBC."""
        raise NotImplementedError("open_form requires COM (WinComAdapter)")

    def close_form(self, form_name: str) -> bool:
        """Close form — not available via ODBC."""
        raise NotImplementedError("close_form requires COM (WinComAdapter)")

    def delete_form(self, form_name: str) -> bool:
        """Delete form — not available via ODBC."""
        raise NotImplementedError("delete_form requires COM (WinComAdapter)")

    def delete_report(self, report_name: str) -> bool:
        """Delete report — not available via ODBC."""
        raise NotImplementedError("delete_report requires COM (WinComAdapter)")

    def get_control_properties(self, form_name: str, control_name: str) -> dict:
        """Get control properties — not available via ODBC."""
        raise NotImplementedError("get_control_properties requires COM (WinComAdapter)")

    def set_control_property(self, form_name: str, control_name: str, property_name: str, value: str) -> bool:
        """Set control property — not available via ODBC."""
        raise NotImplementedError("set_control_property requires COM (WinComAdapter)")

    def set_control_properties(self, form_name: str, control_name: str, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple properties at once — not available via ODBC."""
        raise NotImplementedError("set_control_properties requires COM (WinComAdapter)")

    def get_control_event_procedures(self, form_name: str, control_name: str) -> list[dict]:
        """List event procedures for a control — not available via ODBC."""
        raise NotImplementedError("get_control_event_procedures requires COM (WinComAdapter)")

    def get_vba_code(self, module_name: str) -> str:
        """Get VBA code — not available via ODBC."""
        raise NotImplementedError("get_vba_code requires COM (WinComAdapter)")

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Modify VBA code — not available via ODBC."""
        raise NotImplementedError("set_vba_code requires COM (WinComAdapter)")

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        """Add VBA procedure — not available via ODBC."""
        raise NotImplementedError("add_vba_procedure requires COM (WinComAdapter)")

    def compile_vba(self) -> dict:
        """Compile VBA — not available via ODBC."""
        raise NotImplementedError("compile_vba requires COM (WinComAdapter)")

    def save_database(self) -> dict:
        """Save VBA modules — not available via ODBC."""
        raise NotImplementedError("save_database requires COM (WinComAdapter)")

    def delete_module(self, module_name: str) -> bool:
        """Delete module — not available via ODBC."""
        raise NotImplementedError("delete_module requires COM (WinComAdapter)")

    def vba_list_procedures(self, module_name: str) -> list[dict]:
        """List procedures in a module — not available via ODBC."""
        raise NotImplementedError("vba_list_procedures requires COM (WinComAdapter)")

    def vba_get_procedure(self, module_name: str, procedure_name: str) -> dict:
        """Get procedure source — not available via ODBC."""
        raise NotImplementedError("vba_get_procedure requires COM (WinComAdapter)")

    def vba_replace_procedure(self, module_name: str, procedure_name: str, new_code: str) -> bool:
        """Replace procedure body — not available via ODBC."""
        raise NotImplementedError("vba_replace_procedure requires COM (WinComAdapter)")

    def export_form_to_text(self, form_name: str) -> str:
        """Export form — not available via ODBC."""
        raise NotImplementedError("export_form_to_text requires COM (WinComAdapter)")

    def import_form_from_text(self, form_name: str, form_data: str) -> bool:
        """Import form — not available via ODBC."""
        raise NotImplementedError("import_form_from_text requires COM (WinComAdapter)")

    def export_report_to_text(self, report_name: str) -> str:
        """Export report — not available via ODBC."""
        raise NotImplementedError("export_report_to_text requires COM (WinComAdapter)")

    def import_report_from_text(self, report_name: str, report_data: str) -> bool:
        """Import report — not available via ODBC."""
        raise NotImplementedError("import_report_from_text requires COM (WinComAdapter)")

    def export_module_to_text(self, module_name: str) -> str:
        """Export module — not available via ODBC."""
        raise NotImplementedError("export_module_to_text requires COM (WinComAdapter)")

    def export_macro_to_text(self, macro_name: str) -> str:
        """Export macro — not available via ODBC."""
        raise NotImplementedError("export_macro_to_text requires COM (WinComAdapter)")

    def export_all_versioning(self, output_dir: str) -> dict:
        """Export versioning — not available via ODBC."""
        raise NotImplementedError("export_all_versioning requires COM (WinComAdapter)")

    def export_query_to_text(self, query_name: str) -> str:
        """Export query text — not available via ODBC."""
        raise NotImplementedError("export_query_to_text requires COM (WinComAdapter)")

    def import_query_from_text(self, query_name: str, query_data: str) -> bool:
        """Import query — not available via ODBC."""
        raise NotImplementedError("import_query_from_text requires COM (WinComAdapter)")

    def import_all_versioning(self, input_dir: str) -> dict:
        """Import versioning — not available via ODBC."""
        raise NotImplementedError("import_all_versioning requires COM (WinComAdapter)")

    def compare_versioning(self, export_dir: str) -> dict:
        """Compare versioning — not available via ODBC."""
        raise NotImplementedError("compare_versioning requires COM (WinComAdapter)")

    def compact_repair(self, action: str, source_path: str, dest_path: str, keep_original: bool = True) -> dict:
        """Compact or repair database — not available via ODBC."""
        if action not in ("compact", "repair"):
            return {"success": False, "error": f"Invalid action '{action}'. Must be 'compact' or 'repair'."}
        return {"success": False, "error": "Not available via ODBC"}

    def copy_database(self, source: str, dest: str) -> bool:
        """Copy database file — available via ODBC."""
        import shutil
        try:
            shutil.copy2(source, dest)
            return True
        except Exception:
            return False

    # ========================================================================
    # Internal helpers
    # ========================================================================

    _CODEPAGE_MAP = {
        "utf-8": 65001,
        "utf-16": 1200,
        "latin-1": 28591,
        "windows-1252": 1252,
        "cp1252": 1252,
        "shift-jis": 932,
    }

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