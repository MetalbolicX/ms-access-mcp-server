import os
from typing import Optional
import pyodbc
from .base import AccessAdapter
from ..models.database import (
    TableInfo,
    FormInfo,
    ReportInfo,
    MacroInfo,
    ModuleInfo,
    ControlInfo,
    RelationshipInfo,
)


# Connection string templates for Access databases
ACCESS_DRIVER = "{Microsoft Access Driver (*.mdb, *.accdb)}"
ACE_OLEDB_12 = "Microsoft.ACE.OLEDB.12.0"
ACE_OLEDB_16 = "Microsoft.ACE.OLEDB.16.0"


class OdbcAdapter(AccessAdapter):
    """Data-only adapter using pyodbc for fast read-only access."""

    def __init__(self) -> None:
        self._conn: Optional[pyodbc.Connection] = None
        self._db_path: Optional[str] = None

    def connect(self, db_path: str) -> bool:
        """Connect to an Access database via ODBC."""
        if not os.path.exists(db_path):
            return False

        try:
            # Try ACE OLEDB first (works for both .mdb and .accdb)
            ext = os.path.splitext(db_path)[1].lower()
            if ext == ".accdb":
                conn_str = f"Provider={ACE_OLEDB_16};Data Source={db_path};"
            else:
                conn_str = f"Driver={ACCESS_DRIVER};DBQ={db_path};"

            self._conn = pyodbc.connect(conn_str, autocommit=True)
            self._db_path = db_path
            return True
        except Exception:
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

    def _tables_query(self) -> str:
        """SQL to get user tables (excludes system tables)."""
        return """
            SELECT name
            FROM MSysObjects
            WHERE type = 1 AND flags = 0 AND name NOT LIKE '~*'
            ORDER BY name
        """

    def _columns_query(self, table_name: str) -> str:
        """SQL to get column metadata for a table."""
        # Escape brackets in table name for Access SQL safety
        safe_name = table_name.replace("]", "]")
        return f"""
            SELECT
                column_name AS name,
                data_type AS type,
                character_maximum_length AS size,
                is_nullable AS nullable
            FROM information_schema.columns
            WHERE table_name = '[{safe_name}]'
            ORDER BY ordinal_position
        """

    def get_tables(self) -> list[TableInfo]:
        """Get all user tables from the connected database."""
        if not self.is_connected():
            return []

        tables: list[TableInfo] = []
        try:
            cursor = self._conn.cursor()

            # Get table names using Access system tables
            cursor.execute(self._tables_query())
            table_names = [row[0] for row in cursor.fetchall()]

            for name in table_names:
                if name.startswith("MSys"):
                    continue

                fields = []
                record_count = 0

                try:
                    # Get column info
                    cursor.execute(self._columns_query(name))
                    for row in cursor.fetchall():
                        fields.append({
                            "name": row.name,
                            "type": self._pyodbc_type_name(row.type),
                            "size": row.size or 0,
                            "required": row.nullable == "NO",
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

    def execute_query(self, sql: str, params: Optional[list] = None) -> list[dict]:
        """Execute a SQL query and return results."""
        if not self.is_connected():
            return []

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
        except Exception:
            pass

        return results

    def launch_access(self, visible: bool = False) -> None:
        """Launch Access UI - not supported via ODBC."""
        raise NotImplementedError("OdbcAdapter cannot launch Access UI")

    def close_access(self) -> None:
        """Close Access UI - not supported via ODBC."""
        raise NotImplementedError("OdbcAdapter cannot close Access UI")

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Modify VBA code - not supported via ODBC."""
        raise NotImplementedError("OdbcAdapter cannot modify VBA")

    # ========================================================================
    # COM-only operations (not available via ODBC - return empty/false)
    # ========================================================================

    def get_forms(self) -> list[FormInfo]:
        """Get forms - not available via ODBC."""
        return []

    def get_reports(self) -> list[ReportInfo]:
        """Get reports - not available via ODBC."""
        return []

    def get_macros(self) -> list[MacroInfo]:
        """Get macros - not available via ODBC."""
        return []

    def get_modules(self) -> list[ModuleInfo]:
        """Get modules - not available via ODBC."""
        return []

    def get_vba_code(self, module_name: str) -> str:
        """Get VBA code - not available via ODBC."""
        return ""

    def get_system_tables(self) -> list[TableInfo]:
        """Get system tables - limited via ODBC."""
        if not self.is_connected():
            return []
        # ODBC can't easily enumerate system tables
        return []

    def form_exists(self, form_name: str) -> bool:
        """Form existence check - not available via ODBC."""
        return False

    def get_form_controls(self, form_name: str) -> list[ControlInfo]:
        """Get form controls - not available via ODBC."""
        return []

    def export_form_to_text(self, form_name: str) -> str:
        """Export form - not available via ODBC."""
        return ""

    def import_form_from_text(self, form_data: str) -> bool:
        """Import form - not available via ODBC."""
        return False

    def delete_form(self, form_name: str) -> bool:
        """Delete form - not available via ODBC."""
        return False

    def export_report_to_text(self, report_name: str) -> str:
        """Export report - not available via ODBC."""
        return ""

    def import_report_from_text(self, report_data: str) -> bool:
        """Import report - not available via ODBC."""
        return False

    def delete_report(self, report_name: str) -> bool:
        """Delete report - not available via ODBC."""
        return False

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        """Add VBA procedure - not available via ODBC."""
        return False

    def compile_vba(self) -> bool:
        """Compile VBA - not available via ODBC."""
        return False

    def get_object_metadata(self, object_name: str) -> dict:
        """Get object metadata - not available via ODBC."""
        return {}

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get relationships - not available via ODBC."""
        return []

    def execute_sql_script(self, script_path: str) -> dict:
        """Execute SQL script - not available via ODBC."""
        raise NotImplementedError("execute_sql_script requires COM (WinComAdapter)")

    def export_form_to_text(self, form_name: str) -> str:
        """Export form - not available via ODBC."""
        return ""

    def export_report_to_text(self, report_name: str) -> str:
        """Export report - not available via ODBC."""
        return ""

    def export_module_to_text(self, module_name: str) -> str:
        """Export module - not available via ODBC."""
        return ""

    def export_macro_to_text(self, macro_name: str) -> str:
        """Export macro - not available via ODBC."""
        return ""

    def export_all_versioning(self, output_dir: str) -> dict:
        """Export versioning - not available via ODBC."""
        raise NotImplementedError("export_all_versioning requires COM (WinComAdapter)")