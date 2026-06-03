import os
import shutil
import sys
from datetime import datetime
from typing import Optional, Callable, Any
from ..config import ServerConfig
from .base import AccessAdapter
from .com_dispatcher import ComDispatcher, DAO_DB_FAIL_ON_ERROR
from .vba_operations import VbaOperations
from .ui_operations import UiOperations
from .versioning_io import VersioningIo
from ..models.database import (
    TableInfo,
    FormInfo,
    ReportInfo,
    MacroInfo,
    ModuleInfo,
    ControlInfo,
    RelationshipInfo,
    QueryInfo,
    LinkedTableInfo,
    ForeignKeyInfo,
    FieldInfo,
)
from ..models.migration import (
    TableSchema,
    ColumnSchema,
    ForeignKeySchema,
    IndexSchema,
    UnknownMetadata,
)


class WinComAdapter(AccessAdapter):
    """COM-based adapter using pywin32 for full Access automation.

    All COM operations are dispatched to a dedicated STA thread via ComDispatcher
    to avoid thread-affinity errors when the MCP server handles requests from
    different async workers.
    """

    def __init__(self) -> None:
        self._dispatcher = ComDispatcher()
        self._vba = VbaOperations(self._dispatcher)
        self._ui = UiOperations(self._dispatcher)
        self._versioning = VersioningIo(
            dispatcher=self._dispatcher,
            save_text=self._ui._save_object_to_text,
            load_text=self._ui._load_object_from_text,
            get_tables_fn=self.get_tables,
            get_relationships_fn=self.get_relationships,
            get_system_tables_fn=self.get_system_tables,
        )
        # Wire VbaOperations to UiOperations for shared _load_object_from_text (acModule=5 path)
        self._vba.set_load_text(self._ui._load_object_from_text)
        # State mirrors what dispatcher holds for query purposes
        self._db_path: Optional[str] = None
        self._ado_conn: Optional[Any] = None

    def _ensure_windows(self) -> None:
        """Raise RuntimeError if not on Windows. Called before first COM operation."""
        if sys.platform != 'win32':
            raise RuntimeError("WinComAdapter requires Windows (COM automation)")

    def connect(self, db_path: str) -> bool:
        """Connect to an Access database via COM automation."""
        if not os.path.exists(db_path):
            return False

        self._ensure_windows()
        self._dispatcher.start()
        self._db_path = db_path
        self._dispatcher.set_db_path(db_path)

        def _do_connect() -> bool:
            import win32com.client
            try:
                self._dispatcher.access_app = win32com.client.Dispatch("Access.Application")

                self._dispatcher.access_app.Visible = False

                # Open via DAO FIRST with readwrite so _current_db is writable.
                # Using Exclusive=False so external file copy (shutil, etc.) can
                # still access the database without triggering exclusive lock errors.
                # OpenCurrentDatabase on its own opens in read-only mode for COM automation.
                dbe = self._dispatcher.access_app.DBEngine
                self._dispatcher.current_db = dbe.OpenDatabase(db_path, False, False)

                # Now OpenCurrentDatabase — the underlying DAO handle is already writable,
                # so CurrentDb inherits the writable state.
                self._dispatcher.access_app.OpenCurrentDatabase(db_path, False)

                # Suppress Access dialogs after DB is open (VBA module naming, etc.)
                try:
                    self._dispatcher.access_app.DoCmd.SetWarnings(False)
                except Exception:
                    pass

                self._dispatcher.ado_conn = self._dispatcher.access_app.CurrentProject.Connection

                # Dismiss any Access dialog that appeared after OpenCurrentDatabase
                # (VBA module naming prompts, compile errors, etc.) — must be called
                # after CurrentProject.Connection because VBA loads async on first
                # property access and may trigger the dialog at that point.
                # Use a brief sleep first so the dialog has time to fully render.
                import time
                time.sleep(0.5)
                self._dispatcher._dismiss_access_dialogs()

                return True
            except Exception:
                self._dispatcher._release_com_safe()
                return False

        return self._dispatcher.call(_do_connect)

    def disconnect(self) -> None:
        """Disconnect from the Access database."""
        def _do_disconnect() -> None:
            self._dispatcher._release_com_safe()
        try:
            self._dispatcher.call(_do_disconnect)
        except Exception as e:
            print(f"Cleanup warning: disconnect failed: {e}", file=sys.stderr)
        self._dispatcher.shutdown()
        self._db_path = None

    def is_connected(self) -> bool:
        """Check if connected to a database."""
        if not self._dispatcher._started:
            return False
        try:
            return self._dispatcher.call(lambda: self._dispatcher.is_connected())
        except Exception:
            return False

    def get_tables(self) -> list[TableInfo]:
        """Get all user tables from the connected database."""
        if not self.is_connected():
            return []

        def _do() -> list[TableInfo]:
            tables: list[TableInfo] = []
            try:
                db = self._dispatcher.access_app.DBEngine.OpenDatabase(self._dispatcher.db_path)
                for i in range(db.TableDefs.Count):
                    tdef = db.TableDefs(i)
                    if tdef.Name.startswith("MSys") or tdef.Name.startswith("~"):
                        continue
                    if tdef.Attributes & 0x80000000:
                        continue

                    fields = []
                    for j in range(tdef.Fields.Count):
                        fld = tdef.Fields(j)
                        fields.append({
                            "name": fld.Name,
                            "type": self._access_type_name(fld.Type),
                            "size": fld.Size,
                            "required": bool(fld.Required),
                            "allow_zero_length": bool(fld.AllowZeroLength),
                        })

                    record_count = 0
                    try:
                        rs = db.OpenRecordset(f"SELECT COUNT(*) FROM [{tdef.Name}]")
                        if not rs.EOF:
                            record_count = rs.Fields(0).Value
                        rs.Close()
                    except Exception:
                        pass

                    tables.append(TableInfo(
                        name=tdef.Name,
                        fields=fields,
                        record_count=record_count,
                    ))
                db.Close()
            except Exception:
                pass
            return tables

        return self._dispatcher.call(_do)

    def _access_type_name(self, access_type: int) -> str:
        """Map Access data type integer to string name."""
        type_map = {
            1: "Boolean",
            2: "Byte",
            3: "Integer",
            4: "Long Integer",
            5: "Currency",
            6: "Single",
            7: "Double",
            8: "Date/Time",
            10: "Text",
            11: "Binary",
            12: "Memo",
            15: "GUID",
            16: "Big Integer",
            17: "Unsigned Byte",
            18: "Unsigned Integer",
            19: "Unsigned Long Integer",
            20: "Decimal",
        }
        return type_map.get(access_type, f"Unknown({access_type})")

    @staticmethod
    def _format_dao_value(val: object) -> str:
        """Format a Python value for inline use in DAO SQL.

        DAO.Execute does NOT support ? parameter placeholders like ADO,
        so values must be formatted inline with proper escaping.
        """
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "-1" if val else "0"
        if isinstance(val, int):
            return str(val)
        if isinstance(val, float):
            return str(val)
        if isinstance(val, datetime):
            return f"#{val.strftime('%Y-%m-%d %H:%M:%S')}#"
        # String — single-quote and escape
        s = str(val).replace("'", "''")
        return f"'{s}'"

    @staticmethod
    def _access_control_type_name(ctrl_type: int) -> str:
        """Map Access AcControlType integer to readable name."""
        type_map = {
            100: "TextBox",
            101: "Label",
            102: "CommandButton",
            103: "OptionButton",
            104: "ComboBox",
            105: "ListBox",
            106: "SubForm",
            107: "ToggleButton",
            108: "CheckBox",
            109: "OptionGroup",
            110: "TabControl",
            111: "Page",
            112: "Image",
            114: "BoundObjectFrame",
            115: "ObjectFrame",
            118: "Line",
            119: "Rectangle",
            120: "PageBreak",
            122: "Attachment",
            123: "NavigationButton",
            124: "NavigationControl",
            126: "WebBrowserControl",
            128: "EmptyCell",
        }
        return type_map.get(ctrl_type, f"Control({ctrl_type})")

    def _get_vb_project(self):
        return self._vba._get_vb_project()

    # Delegated to VersioningIo
    def export_module_to_text(self, module_name: str) -> str:
        return self._versioning.export_module_to_text(module_name)

    def export_macro_to_text(self, macro_name: str) -> str:
        return self._versioning.export_macro_to_text(macro_name)

    def import_macro_from_text(self, macro_name: str, macro_data: str) -> bool:
        return self._versioning.import_macro_from_text(macro_name, macro_data)

    def export_all_versioning(self, output_dir: str, *, dedup: bool = True, module_ext: str = ".bas") -> dict:
        return self._versioning.export_all_versioning(
            output_dir,
            dedup=dedup,
            module_ext=module_ext,
            get_forms_fn=self.get_forms,
            get_reports_fn=self.get_reports,
            get_modules_fn=self.get_modules,
            get_macros_fn=self.get_macros,
            get_queries_fn=self.get_queries,
            export_form_to_text_fn=self._ui.export_form_to_text,
            export_report_to_text_fn=self._ui.export_report_to_text,
        )

    def export_query_to_text(self, query_name: str) -> str:
        return self._versioning.export_query_to_text(query_name)

    def import_query_from_text(self, query_name: str, query_data: str) -> bool:
        return self._versioning.import_query_from_text(query_name, query_data)

    def compare_versioning(self, export_dir: str) -> dict:
        return self._versioning.compare_versioning(
            export_dir,
            get_forms_fn=self.get_forms,
            get_reports_fn=self.get_reports,
            get_modules_fn=self.get_modules,
            get_macros_fn=self.get_macros,
            get_queries_fn=self.get_queries,
            export_form_to_text_fn=self._ui.export_form_to_text,
            export_report_to_text_fn=self._ui.export_report_to_text,
            export_macro_to_text_fn=self.export_macro_to_text,
            export_query_to_text_fn=self.export_query_to_text,
            export_module_to_text_fn=self.export_module_to_text,
        )

    def import_all_versioning(self, input_dir: str) -> dict:
        return self._versioning.import_all_versioning(
            input_dir,
            get_modules_fn=self.get_modules,
            set_vba_code_fn=self.set_vba_code,
            compile_vba_fn=self.compile_vba,
            import_form_from_text_fn=self._ui.import_form_from_text,
            import_report_from_text_fn=self._ui.import_report_from_text,
            import_macro_from_text_fn=self.import_macro_from_text,
            import_query_from_text_fn=self.import_query_from_text,
        )

    def export_schema_ddl(self, output_dir: str) -> dict:
        return self._versioning.export_schema_ddl(output_dir)

    # Delegated to VbaOperations

    # ========================================================================
    # FORM OPERATIONS
    # ========================================================================

    def get_forms(self) -> list[FormInfo]:
        return self._ui.get_forms()

    def form_exists(self, form_name: str) -> bool:
        return self._ui.form_exists(form_name)

    def get_form_controls(self, form_name: str) -> list[ControlInfo]:
        return self._ui.get_form_controls(form_name)

    def open_form(self, form_name: str) -> bool:
        return self._ui.open_form(form_name)

    def close_form(self, form_name: str) -> bool:
        return self._ui.close_form(form_name)

    def delete_form(self, form_name: str) -> bool:
        return self._ui.delete_form(form_name)

    def export_form_to_text(self, form_name: str) -> str:
        return self._ui.export_form_to_text(form_name)

    def import_form_from_text(self, form_name: str, form_data: str) -> bool:
        return self._ui.import_form_from_text(form_name, form_data)

    # ========================================================================
    # CONTROL OPERATIONS
    # ========================================================================

    def get_control_properties(self, form_name: str, control_name: str) -> dict:
        return self._ui.get_control_properties(form_name, control_name)

    def set_control_property(self, form_name: str, control_name: str, property_name: str, value: str) -> bool:
        return self._ui.set_control_property(form_name, control_name, property_name, value)

    def set_control_properties(self, form_name: str, control_name: str, properties: dict[str, Any]) -> dict[str, bool]:
        return self._ui.set_control_properties(form_name, control_name, properties)

    def get_control_event_procedures(self, form_name: str, control_name: str) -> list[dict]:
        return self._ui.get_control_event_procedures(form_name, control_name)

    # ========================================================================
    # REPORT OPERATIONS
    # ========================================================================

    def get_reports(self) -> list[ReportInfo]:
        return self._ui.get_reports()

    def report_exists(self, report_name: str) -> bool:
        return self._ui.report_exists(report_name)

    def delete_report(self, report_name: str) -> bool:
        return self._ui.delete_report(report_name)

    def export_report_to_text(self, report_name: str) -> str:
        return self._ui.export_report_to_text(report_name)

    def import_report_from_text(self, report_name: str, report_data: str) -> bool:
        return self._ui.import_report_from_text(report_name, report_data)

    # ========================================================================
    # MACRO OPERATIONS
    # ========================================================================

    def get_macros(self) -> list[MacroInfo]:
        return self._ui.get_macros()

    # Delegated to VbaOperations
    def get_vba_project_name(self) -> str:
        return self._vba.get_vba_project_name()

    def get_modules(self) -> list[ModuleInfo]:
        return self._vba.get_modules()

    def get_vba_code(self, module_name: str) -> str:
        return self._vba.get_vba_code(module_name)

    def set_vba_code(self, module_name: str, code: str) -> bool:
        return self._vba.set_vba_code(module_name, code)

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        return self._vba.add_vba_procedure(module_name, procedure_name, code)

    def delete_module(self, module_name: str) -> bool:
        return self._vba.delete_module(module_name)

    def save_database(self) -> dict:
        return self._vba.save_database()

    def compile_vba(self) -> dict:
        return self._vba.compile_vba()

    @staticmethod
    def _normalize_dao_value(value: Any) -> Any:
        """Convert DAO-specific types to JSON/sqlite3-compatible Python types.

        DAO returns datetime objects, COM variant types, etc. that cannot be
        serialized by most connectors. Normalise them here so all downstream
        consumers (insert_rows, JSON serialization) receive clean values.
        """
        if value is None:
            return None
        # pywintypes.datetime → ISO string (sqlite3 cannot handle datetime objects)
        if hasattr(value, "isoformat") and callable(value.isoformat):
            return value.isoformat()
        return value

    def execute_query(self, sql: str, params: Optional[list] = None) -> dict:
        """Execute a SQL query and return results.

        Note: params is not supported in WinComAdapter (DAO OpenRecordset does not
        support parameterized queries). SQL must be sanitized before calling.
        """
        if not self.is_connected():
            return {"success": False, "rows": [], "count": 0, "columns": [], "error": "Not connected"}

        def _do() -> dict:
            results: list[dict] = []
            columns: list[str] = []
            try:
                rs = self._dispatcher.current_db.OpenRecordset(sql)
                if not rs.EOF:
                    rs.MoveFirst()
                    # Collect column names first
                    for i in range(rs.Fields.Count):
                        columns.append(rs.Fields(i).Name)
                    # Then collect rows
                    rs.MoveFirst()
                    while not rs.EOF:
                        row = {}
                        for i in range(rs.Fields.Count):
                            field = rs.Fields(i)
                            row[field.Name] = self._normalize_dao_value(field.Value)
                        results.append(row)
                        rs.MoveNext()
                rs.Close()
                return {"success": True, "rows": results, "count": len(results), "columns": columns}
            except Exception as e:
                return {"success": False, "rows": [], "count": 0, "columns": [], "error": str(e)}

        return self._dispatcher.call(_do)

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

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                for row in data:
                    cols = ", ".join(f"[{c}]" for c in row.keys())
                    vals = ", ".join(self._format_dao_value(v) for v in row.values())
                    sql = f"INSERT INTO [{table_name}] ({cols}) VALUES ({vals})"
                    db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                return {"success": True, "affected": len(data)}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

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

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db

                # Build SET clause with inline-formatted values (DAO doesn't support ? params)
                set_parts = []
                for col, val in set_dict.items():
                    set_parts.append(f"[{col}] = {self._format_dao_value(val)}")
                set_clause = ", ".join(set_parts)
                sql = f"UPDATE [{table_name}] SET {set_clause}"

                if where_dict is not None:
                    if isinstance(where_dict, str):
                        sql += f" WHERE {where_dict}"
                    else:
                        where_parts = []
                        for col, val in where_dict.items():
                            where_parts.append(f"[{col}] = {self._format_dao_value(val)}")
                        sql += " WHERE " + " AND ".join(where_parts)

                db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                affected = db.RecordsAffected
                return {"success": True, "affected": affected}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

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

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                sql = f"DELETE FROM [{table_name}]"

                if where_dict is not None:
                    if isinstance(where_dict, str):
                        sql += f" WHERE {where_dict}"
                    else:
                        where_parts = []
                        for col, val in where_dict.items():
                            where_parts.append(f"[{col}] = {self._format_dao_value(val)}")
                        sql += " WHERE " + " AND ".join(where_parts)

                db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                affected = db.RecordsAffected
                return {"success": True, "affected": affected}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    # ========================================================================
    # QUERY CRUD OPERATIONS
    # ========================================================================

    def get_queries(self) -> list[QueryInfo]:
        """Get all saved queries from the database."""
        if not self.is_connected():
            return []

        def _do() -> list[QueryInfo]:
            queries: list[QueryInfo] = []
            try:
                db = self._dispatcher.current_db
                for i in range(db.QueryDefs.Count):
                    qdef = db.QueryDefs(i)
                    if qdef.Name.startswith("~"):
                        continue  # Skip system queries
                    queries.append(QueryInfo(
                        name=qdef.Name,
                        sql=qdef.sql,
                        type=self._query_type_name(qdef.Type),
                    ))
            except Exception:
                pass
            return queries

        return self._dispatcher.call(_do)

    def _query_type_name(self, query_type: int) -> str:
        """Map DAO QueryDef Type integer to readable name."""
        type_map = {
            0: "select",
            1: "action",
            2: "crosstab",
            4: "update",
            5: "append",
            6: "delete",
            7: "make-table",
            8: "data-definition",
        }
        return type_map.get(query_type, f"unknown({query_type})")

    def create_query(self, name: str, sql: str) -> dict:
        """Create a new stored query."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                # CreateQueryDef with a non-empty name auto-appends to QueryDefs collection.
                # Explicit Append is not needed and causes "Invalid operation" on writeable DAO.
                self._dispatcher.current_db.CreateQueryDef(name, sql)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def set_query_sql(self, name: str, sql: str) -> dict:
        """Update SQL of an existing query."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                qdef = self._dispatcher.current_db.QueryDefs(name)
                qdef.sql = sql
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def delete_query(self, name: str) -> dict:
        """Delete a stored query."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                self._dispatcher.current_db.QueryDefs.Delete(name)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

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

        DAO_TYPE_MAP = {
            "Text": 10,
            "Long Integer": 4,
            "Integer": 3,
            "Boolean": 1,
            "Date/Time": 8,
            "Currency": 5,
            "Memo": 12,
            "Double": 7,
            "Single": 6,
            "Binary": 9,
            "GUID": 15,
            "Byte": 2,
        }

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                tdef = db.CreateTableDef(table_name)

                for col in columns:
                    name = col["name"]
                    field_type = DAO_TYPE_MAP.get(col["type"], 10)
                    size = col.get("size", 0)
                    fld = tdef.CreateField(name, field_type, size)
                    fld.Required = not col.get("nullable", True)
                    tdef.Fields.Append(fld)

                db.TableDefs.Append(tdef)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def delete_table(self, table_name: str) -> dict:
        """Delete a table from the database.

        Args:
            table_name: Name of the table to delete

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                self._dispatcher.current_db.TableDefs.Delete(table_name)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def launch_access(self, visible: bool = False) -> None:
        """Launch Microsoft Access application."""
        self._ensure_windows()

        def _do() -> None:
            import win32com.client
            if self._dispatcher.access_app is None:
                self._dispatcher.access_app = win32com.client.Dispatch("Access.Application")
            try:
                self._dispatcher.access_app.Visible = visible
            except AttributeError:
                # Some Access versions/configs don't allow setting Visible
                # via COM dispatch. Not critical — Access opens regardless.
                pass

        if not self._dispatcher._started:
            self._dispatcher.start()
        self._dispatcher.call(_do)

    def close_access(self) -> None:
        """Close Microsoft Access application.

        Saves VBA modules before quitting to prevent loss of in-memory changes.
        """
        def _do() -> None:
            if self._dispatcher.access_app is not None:
                app = self._dispatcher.access_app
                # Modules created via LoadFromText are auto-saved by Access.
                # Named standard modules don't need pre-save here; changes are
                # persisted on quit or remain in-memory as designed.
                self._dispatcher._release_com_safe()

        try:
            self._dispatcher.call(_do)
        except Exception as e:
            print(f"Cleanup warning: close_access failed: {e}", file=sys.stderr)

    def set_vba_code(self, module_name: str, code: str) -> bool:
        return self._vba.set_vba_code(module_name, code)

    # ========================================================================
    # VBA/MODULE OPERATIONS
    # ========================================================================

    def get_vba_project_name(self) -> str:
        return self._vba.get_vba_project_name()

    def get_modules(self) -> list[ModuleInfo]:
        return self._vba.get_modules()

    def get_vba_code(self, module_name: str) -> str:
        return self._vba.get_vba_code(module_name)

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        return self._vba.add_vba_procedure(module_name, procedure_name, code)

    def delete_module(self, module_name: str) -> bool:
        return self._vba.delete_module(module_name)

    def save_database(self) -> dict:
        return self._vba.save_database()

    def compile_vba(self) -> dict:
        return self._vba.compile_vba()

    # ========================================================================
    # TRUSTED LOCATIONS (Pre/Post Hook for VBA Operations)
    # ========================================================================

    def _capture_trusted_locations(self) -> list[dict]:
        """Capture current Trusted Locations from Windows registry.

        Uses PowerShell to read HKLM and HKCU Trusted Locations registry keys.
        Returns list of dicts: [{"path": "...", "description": "..."}] or empty list.

        Returns:
            List of Trusted Location dicts, or empty list on non-Windows or error.
        """
        if sys.platform != "win32":
            return []

        try:
            import winreg
        except ImportError:
            print("[WinComAdapter] winreg not available, skipping Trusted Locations capture", file=sys.stderr)
            return []

        locations: list[dict] = []

        def read_key(hkey, subkey_path: str) -> None:
            """Read Trusted Locations from a specific registry key."""
            try:
                key = winreg.OpenKey(hkey, subkey_path, 0, winreg.KEY_READ)
                try:
                    i = 0
                    while True:
                        try:
                            loc_name = winreg.EnumKey(key, i)
                            loc_path_key = winreg.OpenKey(key, loc_name, 0, winreg.KEY_READ)
                            try:
                                path_val, _ = winreg.QueryValueEx(loc_path_key, "Path")
                                desc_val, _ = winreg.QueryValueEx(loc_path_key, "Description")
                                locations.append({
                                    "path": path_val,
                                    "description": desc_val if desc_val else "",
                                })
                            except FileNotFoundError:
                                # Path not found, skip silently
                                pass
                            except Exception:
                                # Skip entries we can't read
                                pass
                            finally:
                                winreg.CloseKey(loc_path_key)
                            i += 1
                        except OSError:
                            break
                finally:
                    winreg.CloseKey(key)
            except FileNotFoundError:
                # Key doesn't exist, nothing to capture
                pass
            except Exception:
                pass

        try:
            read_key(winreg.HKEY_LOCAL_MACHINE,
                     r"SOFTWARE\Microsoft\Office\16.0\Access\Security\Trusted Locations")
            read_key(winreg.HKEY_CURRENT_USER,
                     r"SOFTWARE\Microsoft\Office\16.0\Access\Security\Trusted Locations")
        except Exception:
            pass

        return locations

    def _restore_trusted_locations(self, locations: list[dict]) -> bool:
        """Restore Trusted Locations to Windows registry.

        Args:
            locations: List of dicts with "path" and "description" keys.

        Returns:
            True on success, False on failure.
        """
        if sys.platform != "win32":
            return False

        if not locations:
            return True

        try:
            import winreg
        except ImportError:
            print("[WinComAdapter] winreg not available, skipping Trusted Locations restore", file=sys.stderr)
            return False

        def write_location(hkey, subkey_path: str, locations: list[dict]) -> None:
            """Write Trusted Locations to a specific registry key."""
            try:
                key = winreg.CreateKey(hkey, subkey_path)
                for idx, loc in enumerate(locations):
                    loc_name = f"Location{idx + 1}"
                    loc_key = winreg.CreateKey(key, loc_name)
                    try:
                        winreg.SetValueEx(loc_key, "Path", 0, winreg.REG_SZ, loc.get("path", ""))
                        desc = loc.get("description", "")
                        if desc:
                            winreg.SetValueEx(loc_key, "Description", 0, winreg.REG_SZ, desc)
                    finally:
                        winreg.CloseKey(loc_key)
                winreg.CloseKey(key)
            except Exception:
                pass

        try:
            hklm_path = r"SOFTWARE\Microsoft\Office\16.0\Access\Security\Trusted Locations"
            hkcu_path = r"SOFTWARE\Microsoft\Office\16.0\Access\Security\Trusted Locations"
            write_location(winreg.HKEY_LOCAL_MACHINE, hklm_path, locations)
            write_location(winreg.HKEY_CURRENT_USER, hkcu_path, locations)
            return True
        except Exception as e:
            print(f"[WinComAdapter] Failed to restore Trusted Locations: {e}", file=sys.stderr)
            return False

    def _trusted_locations_wrap(self, func, *args, **kwargs):
        """Execute func(*args, **kwargs) with Trusted Locations preservation if enabled.

        Captures Trusted Locations before the call and restores them after,
        controlled by config.preserve_trusted_locations.
        """
        try:
            config = ServerConfig()
            preserve = config.preserve_trusted_locations
        except Exception:
            preserve = False

        if not preserve:
            return func(*args, **kwargs)

        captured = self._capture_trusted_locations()
        try:
            return func(*args, **kwargs)
        finally:
            if captured:
                self._restore_trusted_locations(captured)

    # ========================================================================
    # SYSTEM TABLES
    # ========================================================================

    def get_system_tables(self) -> list[TableInfo]:
        """Get system tables from the database."""
        if not self.is_connected():
            return []

        def _do() -> list[TableInfo]:
            tables: list[TableInfo] = []
            try:
                db = self._dispatcher.current_db
                for i in range(db.TableDefs.Count):
                    tdef = db.TableDefs(i)
                    if tdef.Name.startswith("MSys"):
                        fields = []
                        for j in range(tdef.Fields.Count):
                            fld = tdef.Fields(j)
                            fields.append({
                                "name": fld.Name,
                                "type": self._access_type_name(fld.Type),
                                "size": fld.Size,
                                "required": bool(fld.Required),
                                "allow_zero_length": bool(fld.AllowZeroLength),
                            })
                        tables.append(TableInfo(name=tdef.Name, fields=fields, record_count=0))
            except Exception:
                pass
            return tables

        return self._dispatcher.call(_do)

    # ========================================================================
    # RELATIONSHIPS (Foreign Keys)
    # ========================================================================

    def _get_table_indexes(self, table_name: str) -> dict[str, list[str]]:
        """Return {index_name: [columns]} for indexes where Primary=True."""
        if not self.is_connected():
            return {}

        def _do() -> dict[str, list[str]]:
            indexes: dict[str, list[str]] = {}
            try:
                db = self._dispatcher.current_db
                tdef = db.TableDefs(table_name)
                for idx in tdef.Indexes:
                    if idx.Primary:
                        indexes[idx.Name] = [f.Name for f in idx.Fields]
            except Exception:
                pass
            return indexes

        return self._dispatcher.call(_do)

    def _get_field_details(self, table_name: str) -> list[dict]:
        """Return list of {name, type, size, attributes, default_value} for each field."""
        if not self.is_connected():
            return []

        def _do() -> list[dict]:
            fields: list[dict] = []
            try:
                db = self._dispatcher.current_db
                tdef = db.TableDefs(table_name)
                for fld in tdef.Fields:
                    default = None
                    try:
                        default = str(fld.DefaultValue) if fld.DefaultValue is not None else None
                    except Exception:
                        default = None
                    fields.append({
                        "name": fld.Name,
                        "type": fld.Type,
                        "size": fld.Size,
                        "attributes": fld.Attributes,
                        "default_value": default,
                    })
            except Exception:
                pass
            return fields

        return self._dispatcher.call(_do)

    def _get_relationship_columns(self) -> list[ForeignKeyInfo]:
        """Read Relations collection and build ForeignKeyInfo list."""
        if not self.is_connected():
            return []

        def _do() -> list[ForeignKeyInfo]:
            from ..models.database import ForeignKeyInfo
            fks: list[ForeignKeyInfo] = []
            try:
                db = self._dispatcher.current_db
                for rel in db.Relations:
                    if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                        continue
                    cols = [f.Name for f in rel.Fields]
                    fks.append(ForeignKeyInfo(
                        name=rel.Name,
                        columns=cols,
                        foreign_table=rel.ForeignTable,
                        foreign_columns=cols,
                    ))
            except Exception:
                pass
            return fks

        return self._dispatcher.call(_do)

    def get_table_schema_plan(self) -> tuple[list[TableSchema], UnknownMetadata]:
        """Extract table schema fidelity metadata from Access DAO collections.

        Saved queries are intentionally excluded by using only table definitions.
        """
        if not self.is_connected():
            return ([], UnknownMetadata())

        def _do() -> tuple[list[TableSchema], UnknownMetadata]:
            schema_tables: list[TableSchema] = []
            unknown = UnknownMetadata()

            try:
                db = self._dispatcher.current_db

                relationships_by_table: dict[str, list[ForeignKeySchema]] = {}
                try:
                    for rel in db.Relations:
                        if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                            continue

                        child_columns: list[str] = []
                        parent_columns: list[str] = []
                        for rel_field in rel.Fields:
                            child_columns.append(rel_field.Name)
                            parent_name = getattr(rel_field, "ForeignName", rel_field.Name)
                            parent_columns.append(parent_name)

                        fk = ForeignKeySchema(
                            name=rel.Name,
                            columns=child_columns,
                            referenced_table=rel.ForeignTable,
                            referenced_columns=parent_columns,
                        )
                        relationships_by_table.setdefault(rel.Table, []).append(fk)
                except Exception:
                    unknown.foreign_keys = True

                for tdef in db.TableDefs:
                    table_name = tdef.Name
                    if table_name.startswith("MSys") or table_name.startswith("~"):
                        continue
                    if tdef.Attributes & 0x80000000:
                        # Linked tables are not source schema objects for migration plans.
                        continue

                    columns: list[ColumnSchema] = []
                    primary_key: list[str] = []
                    indexes: list[IndexSchema] = []

                    for fld in tdef.Fields:
                        default_value = None
                        try:
                            raw_default = fld.DefaultValue
                            default_value = str(raw_default) if raw_default is not None else None
                        except Exception:
                            unknown.defaults = True

                        attributes = int(getattr(fld, "Attributes", 0) or 0)
                        is_autoincrement = bool(attributes & 0x10)

                        columns.append(
                            ColumnSchema(
                                name=fld.Name,
                                source_type=self._access_type_name(fld.Type),
                                max_length=fld.Size if fld.Size and fld.Size > 0 else None,
                                allow_null=not bool(getattr(fld, "Required", False)),
                                is_autoincrement=is_autoincrement,
                                default_value=default_value,
                            )
                        )

                    try:
                        for idx in tdef.Indexes:
                            idx_fields = [idx_field.Name for idx_field in idx.Fields]
                            if not idx_fields:
                                continue
                            if bool(getattr(idx, "Primary", False)):
                                primary_key = idx_fields
                                continue
                            indexes.append(
                                IndexSchema(
                                    name=idx.Name,
                                    columns=idx_fields,
                                    is_unique=bool(getattr(idx, "Unique", False)),
                                )
                            )
                    except Exception:
                        unknown.indexes = True
                        unknown.primary_keys = True

                    if not primary_key:
                        unknown.primary_keys = True

                    if any(col.is_autoincrement for col in columns) and not primary_key:
                        unknown.autoincrement = True

                    schema_tables.append(
                        TableSchema(
                            name=table_name,
                            columns=columns,
                            primary_key=primary_key,
                            foreign_keys=relationships_by_table.get(table_name, []),
                            indexes=indexes,
                        )
                    )
            except Exception:
                unknown.primary_keys = True
                unknown.foreign_keys = True
                unknown.defaults = True
                unknown.indexes = True
                unknown.autoincrement = True
                return ([], unknown)

            return (schema_tables, unknown)

        return self._dispatcher.call(_do)

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get all foreign key relationships from DAO Relations collection."""
        if not self.is_connected():
            return []

        def _do() -> list[RelationshipInfo]:
            relationships: list[RelationshipInfo] = []
            try:
                db = self._dispatcher.current_db
                for i in range(db.Relations.Count):
                    rel = db.Relations(i)
                    if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                        continue
                    relationships.append(RelationshipInfo(
                        name=rel.Name,
                        table=rel.Table,
                        foreign_table=rel.ForeignTable,
                        attributes=str(rel.Attributes),
                    ))
            except Exception:
                pass
            return relationships

        return self._dispatcher.call(_do)

    def generate_sql(self, output_path: str) -> dict:
        """Generate Jet SQL DDL and write to output_path.

        Orchestrates reading schema (tables, indexes, field details, FKs),
        calls JetSqlGenerator.generate(), and writes to output_path.

        Returns:
            dict with success=True, path, statements (count), tables (list)
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        from ..services.sql_generator import JetSqlGenerator

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                access_app = self._dispatcher.access_app

                # 1. Read tables directly from DAO (avoid nested dispatch deadlock).
                #    get_tables() internally dispatches, so we replicate the logic
                #    here to stay on the STA thread within this single dispatch.
                base_tables: list[TableInfo] = []
                for i in range(db.TableDefs.Count):
                    tdef = db.TableDefs(i)
                    if tdef.Name.startswith("MSys") or tdef.Name.startswith("~"):
                        continue
                    if tdef.Attributes & 0x80000000:
                        continue
                    fields = []
                    for j in range(tdef.Fields.Count):
                        fld = tdef.Fields(j)
                        fields.append({
                            "name": fld.Name,
                            "type": self._access_type_name(fld.Type),
                            "size": fld.Size,
                            "required": bool(fld.Required),
                            "allow_zero_length": bool(fld.AllowZeroLength),
                        })
                    record_count = 0
                    try:
                        rs = db.OpenRecordset(f"SELECT COUNT(*) FROM [{tdef.Name}]")
                        if not rs.EOF:
                            record_count = rs.Fields(0).Value
                        rs.Close()
                    except Exception:
                        pass
                    base_tables.append(TableInfo(
                        name=tdef.Name,
                        fields=fields,
                        record_count=record_count,
                    ))

                if not base_tables:
                    return {"success": True, "path": output_path, "statements": 0, "tables": []}

                # 2. Enrich each table with field details and primary keys
                tables: list[TableInfo] = []
                for base_table in base_tables:
                    table_name = base_table.name

                    # Get field details via direct DAO access (no dispatch needed)
                    field_details: list[dict] = []
                    field_detail_map: dict[str, dict] = {}
                    try:
                        tdef = db.TableDefs(table_name)
                        for fld in tdef.Fields:
                            default = None
                            try:
                                default = str(fld.DefaultValue) if fld.DefaultValue is not None else None
                            except Exception:
                                default = None
                            detail = {
                                "name": fld.Name,
                                "type": fld.Type,
                                "size": fld.Size,
                                "attributes": fld.Attributes,
                                "default_value": default,
                            }
                            field_details.append(detail)
                            field_detail_map[fld.Name] = detail
                    except Exception:
                        pass

                    # Get primary key columns via direct DAO access
                    pk_columns: list[str] = []
                    try:
                        tdef = db.TableDefs(table_name)
                        for idx in tdef.Indexes:
                            if idx.Primary:
                                pk_columns = [f.Name for f in idx.Fields]
                                break
                    except Exception:
                        pass

                    # Merge field details into FieldInfo objects
                    enriched_fields: list[FieldInfo] = []
                    for fld in base_table.fields:
                        detail = field_detail_map.get(fld.name, {})
                        attrs = detail.get("attributes", 0)
                        is_auto = bool(attrs & 0x10) if attrs else False
                        default_val = detail.get("default_value")

                        enriched_fields.append(FieldInfo(
                            name=fld.name,
                            type=fld.type,
                            size=fld.size,
                            required=fld.required,
                            allow_zero_length=fld.allow_zero_length,
                            is_autoincrement=is_auto,
                            default_value=default_val,
                        ))

                    enriched_table = TableInfo(
                        name=table_name,
                        fields=enriched_fields,
                        record_count=base_table.record_count,
                        primary_key=pk_columns,
                    )
                    tables.append(enriched_table)

                # 3. Get relationships via direct DAO access
                relationships: list[RelationshipInfo] = []
                try:
                    for i in range(db.Relations.Count):
                        rel = db.Relations(i)
                        if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                            continue
                        relationships.append(RelationshipInfo(
                            name=rel.Name,
                            table=rel.Table,
                            foreign_table=rel.ForeignTable,
                            attributes=str(rel.Attributes),
                        ))
                except Exception:
                    pass

                foreign_keys: list[ForeignKeyInfo] = []
                try:
                    for rel in db.Relations:
                        if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                            continue
                        child_columns: list[str] = []
                        parent_columns: list[str] = []
                        for rel_field in rel.Fields:
                            child_columns.append(rel_field.Name)
                            parent_name = getattr(rel_field, "ForeignName", rel_field.Name)
                            parent_columns.append(parent_name)
                        foreign_keys.append(ForeignKeyInfo(
                            name=rel.Name,
                            columns=child_columns,
                            foreign_table=rel.ForeignTable,
                            foreign_columns=parent_columns,
                        ))
                except Exception:
                    pass

                # 4. Instantiate JetSqlGenerator and generate
                generator = JetSqlGenerator(tables, relationships, foreign_keys)
                statements = generator.generate()

                # 5. Write to output_path
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(statements))
                    if statements:
                        f.write("\n")

                return {
                    "success": True,
                    "path": output_path,
                    "statements": len(statements),
                    "tables": [t.name for t in tables],
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    # ========================================================================
    # OBJECT METADATA
    # ========================================================================

    def get_object_metadata(self, object_name: str) -> dict:
        """Get metadata for a database object."""
        if not self.is_connected():
            return {}

        # Check tables via get_tables() (dispatches internally, no nesting issue)
        try:
            for table in self.get_tables():
                if table.name == object_name:
                    return {
                        "name": table.name,
                        "type": "table",
                        "properties": {"record_count": str(table.record_count)},
                    }
        except Exception:
            pass

        # Check forms, reports, macros via COM dispatch
        def _do() -> dict:
            for collection_name in ["AllForms", "AllReports", "AllMacros"]:
                try:
                    collection = getattr(self._dispatcher.access_app.CurrentProject, collection_name)
                    for i in range(collection.Count):
                        obj = collection(i)
                        if obj.Name == object_name:
                            props = {}
                            try:
                                props = self._get_object_properties(obj)
                            except Exception:
                                pass
                            return {
                                "name": obj.Name,
                                "type": collection_name.replace("All", "").lower(),
                                "properties": props,
                            }
                except Exception:
                    pass
            return {}

        return self._dispatcher.call(_do)

    # ========================================================================
    # LINKED TABLES (DAO TableDefs)
    # ========================================================================

    def get_linked_tables(self) -> dict:
        """Get all linked tables from the database.

        Linked tables are identified by the dbLinkAttachedTable attribute (0x80000000).
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            linked_tables: list[dict] = []
            try:
                db = self._dispatcher.current_db
                for i in range(db.TableDefs.Count):
                    tdef = db.TableDefs(i)
                    if tdef.Attributes & 0x80000000:
                        connect_str = tdef.Connect or ""
                        if connect_str.startswith("ODBC"):
                            table_type = "ODBC"
                        elif connect_str.startswith("Access"):
                            table_type = "Access"
                        elif connect_str.startswith("Excel"):
                            table_type = "Excel"
                        else:
                            table_type = "ODBC"
                        linked_tables.append({
                            "name": tdef.Name,
                            "source_table": tdef.SourceTableName,
                            "connect_string": connect_str,
                            "type": table_type,
                        })
            except Exception as e:
                return {"success": False, "error": str(e)}
            return {"success": True, "linked_tables": linked_tables}

        return self._dispatcher.call(_do)

    def create_linked_table(self, name: str, source_table: str, connect_string: str) -> dict:
        """Create a linked table definition.

        Args:
            name: Name for the linked table in the Access database
            source_table: Name of the remote table
            connect_string: ODBC or other connection string

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                tdef = db.CreateTableDef(name)
                tdef.SourceTableName = source_table
                tdef.Connect = connect_string
                tdef.Attributes = 0x80000000  # dbLinkAttachedTable
                db.TableDefs.Append(tdef)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def refresh_linked_table(self, name: str) -> dict:
        """Refresh the link for a linked table.

        Args:
            name: Name of the linked table

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                tdef = self._dispatcher.current_db.TableDefs(name)
                tdef.RefreshLink()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def unlink_table(self, name: str) -> dict:
        """Unlink (delete) a linked table definition.

        Args:
            name: Name of the linked table to unlink

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                self._dispatcher.current_db.TableDefs.Delete(name)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    # ========================================================================
    # COMPACT/REPAIR (DAO DBEngine)
    # ========================================================================

    def compact_repair(self, action: str, source_path: str, dest_path: str, keep_original: bool = True) -> dict:
        """Compact or repair an Access database file.

        Args:
            action: "compact" or "repair"
            source_path: Path to the source .accdb file
            dest_path: Path for the output file (for compact) or same as source (for repair)
            keep_original: If True, keep original as .bak before compacting

        Returns:
            dict with success=True, output_path, stats (original_size, compacted_size)
            or success=False and error message
        """
        if action not in ("compact", "repair"):
            return {"success": False, "error": f"Invalid action '{action}'. Must be 'compact' or 'repair'."}

        if not os.path.exists(source_path):
            return {"success": False, "error": f"Source file not found: {source_path}"}

        def _do() -> dict:
            import shutil
            try:
                original_size = os.path.getsize(source_path)

                if action == "compact":
                    if keep_original:
                        backup_path = source_path + ".bak"
                        if os.path.exists(backup_path):
                            os.unlink(backup_path)
                        shutil.copy2(source_path, backup_path)

                    dbe = self._dispatcher.access_app.DBEngine
                    dbe.CompactDatabase(source_path, dest_path)
                    compacted_size = os.path.getsize(dest_path)

                    return {
                        "success": True,
                        "output_path": dest_path,
                        "stats": {
                            "original_size": original_size,
                            "compacted_size": compacted_size,
                        },
                    }

                else:  # repair
                    temp_path = source_path + ".repair_tmp"
                    try:
                        if keep_original:
                            backup_path = source_path + ".bak"
                            if os.path.exists(backup_path):
                                os.unlink(backup_path)
                            shutil.copy2(source_path, backup_path)

                        dbe = self._dispatcher.access_app.DBEngine
                        dbe.CompactDatabase(source_path, temp_path)
                        os.replace(temp_path, source_path)
                        repaired_size = os.path.getsize(source_path)

                        return {
                            "success": True,
                            "output_path": source_path,
                            "stats": {
                                "original_size": original_size,
                                "compacted_size": repaired_size,
                            },
                        }
                    except Exception:
                        if os.path.exists(temp_path):
                            try:
                                os.unlink(temp_path)
                            except Exception:
                                pass
                        raise

            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    # ========================================================================
    # DATA EXPORT (CSV/JSON)
    # ========================================================================

    _CODEPAGE_MAP = {
        "utf-8": 65001,
        "utf-16": 1200,
        "latin-1": 28591,
        "windows-1252": 1252,
        "cp1252": 1252,
        "shift-jis": 932,
    }

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
            self.db.Execute(insert_sql, DAO_DB_FAIL_ON_ERROR)
            return {"success": True, "rows_exported": self.db.RecordsAffected, "file_path": file_path}
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

    @staticmethod
    def _strip_sql_comments(sql: str) -> str:
        """Remove SQL comments (-- and /* */) from a script."""
        import re
        # Remove single-line comments (-- until end of line)
        sql = re.sub(r'(?m)^\s*--.*$', '', sql)
        # Remove block comments /* ... */
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        # Collapse multiple blank lines into one
        sql = re.sub(r'\n\s*\n', '\n', sql)
        return sql

    # ========================================================================
    # VERSIONING (delegated to VersioningIo)
    # ========================================================================

    # Delegated to VbaOperations

    # ------------------------------------------------------------------- #
    #  SQL Script Execution
    # ------------------------------------------------------------------- #

    def execute_sql_script(self, script_path: str) -> dict:
        """Execute a SQL script from a file path.

        Reads the file, strips SQL comments, splits by semicolons,
        and executes each statement via DAO. On error, returns structured
        info matching the access-sql-script-executor spec.

        Args:
            script_path: Absolute path to the .sql file

        Returns:
            dict with:
              success, statements_executed, error (always present)
              failing_statement, failing_line, access_error_code,
              access_error_message (on execution failure)
        """
        if not os.path.exists(script_path):
            return {
                "success": False,
                "statements_executed": 0,
                "error": f"File not found: {script_path}",
                "failing_statement": None,
                "failing_line": None,
                "access_error_code": None,
                "access_error_message": None,
            }

        if not self.is_connected():
            return {
                "success": False,
                "statements_executed": 0,
                "error": "Not connected",
                "failing_statement": None,
                "failing_line": None,
                "access_error_code": None,
                "access_error_message": None,
            }

        def _do() -> dict:
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    raw_sql = f.read()
            except Exception as e:
                err = self._extract_com_error(e)
                return {
                    "success": False,
                    "statements_executed": 0,
                    "error": err["error"],
                    "failing_statement": None,
                    "failing_line": None,
                    "access_error_code": err["code"],
                    "access_error_message": err["message"],
                }

            # Parse statements with original line number tracking
            parse = self._parse_script_lines(raw_sql)
            if not parse["statements"]:
                return {
                    "success": True,
                    "statements_executed": 0,
                    "failing_statement": None,
                    "failing_line": None,
                    "access_error_code": None,
                    "access_error_message": None,
                }

            db = self._dispatcher.current_db
            executed = 0
            for entry in parse["statements"]:
                try:
                    db.Execute(entry["text"], DAO_DB_FAIL_ON_ERROR)
                    executed += 1
                except Exception as e:
                    err = self._extract_com_error(e)
                    return {
                        "success": False,
                        "statements_executed": executed,
                        "error": err["error"],
                        "failing_statement": entry["text"],
                        "failing_line": entry["line"],
                        "access_error_code": err["code"],
                        "access_error_message": err["message"],
                    }

            return {
                "success": True,
                "statements_executed": executed,
                "failing_statement": None,
                "failing_line": None,
                "access_error_code": None,
                "access_error_message": None,
            }

        try:
            return self._dispatcher.call(_do)
        except Exception as e:
            err = self._extract_com_error(e)
            return {
                "success": False,
                "statements_executed": 0,
                "error": err["error"],
                "failing_statement": None,
                "failing_line": None,
                "access_error_code": err["code"],
                "access_error_message": err["message"],
            }

    def _parse_script_lines(self, raw_sql: str) -> dict:
        """Parse raw SQL into executable statements with original line numbers.

        Returns dict with 'statements' list of {text, line} or empty list.
        Comments are stripped per-statement for safe execution.
        Line numbers are 1-based and refer to the original file.
        """
        if not raw_sql.strip():
            return {"statements": []}

        statements: list[dict] = []
        pos = 0
        remaining = raw_sql

        while remaining:
            semi_idx = remaining.find(";")
            if semi_idx >= 0:
                raw_chunk = remaining[:semi_idx]
                remaining = remaining[semi_idx + 1:]
            else:
                raw_chunk = remaining
                remaining = ""

            raw_stripped = raw_chunk.strip()
            if not raw_stripped:
                pos += len(raw_chunk) + (1 if semi_idx >= 0 else 0)
                continue

            # Find where actual SQL content starts (skip leading whitespace)
            # so line numbers point to the statement, not to whitespace before it
            first_content = len(raw_chunk) - len(raw_chunk.lstrip())
            stmt_pos = pos + first_content

            # Strip comments from the chunk — this is safe per-statement
            clean = self._strip_sql_comments(raw_stripped).strip()
            if not clean:
                pos += len(raw_chunk) + (1 if semi_idx >= 0 else 0)
                continue

            # Original line number (1-based) of the statement in the file
            line = raw_sql[:stmt_pos].count("\n") + 1

            statements.append({"text": clean, "line": line})
            pos += len(raw_chunk) + (1 if semi_idx >= 0 else 0)

        return {"statements": statements}


    # ========================================================================
    #  COM Error Extractor (static helper)
    # ========================================================================

    @staticmethod
    def _extract_com_error(e: Exception) -> dict:
        """Extract structured error info from a COM or non-COM exception.

        Returns dict with 'error' (clean message), 'code', 'message'.
        For pywin32 COM errors, extracts the DAO error code and description.
        For standard Python exceptions, falls back to str(e).
        """
        error_str = str(e)
        code = None
        message = None

        # pywin32 com_error: args = (hresult, msg, excepinfo, arg)
        excepinfo = getattr(e, "args", None)
        if isinstance(excepinfo, tuple) and len(excepinfo) >= 3:
            info = excepinfo[2]
            if isinstance(info, tuple) and len(info) >= 6:
                description = info[2]  # Clean DAO error message
                scode = info[5]       # DAO error code (negative)
                if description:
                    error_str = description
                    message = description
                    code = scode
                if scode:
                    code = scode

        if code is None and hasattr(e, "winerror"):
            code = e.winerror  # type: ignore[union-attr]

        return {"error": error_str, "code": code, "message": message}

    # ========================================================================
    # DATABASE FILE COPY
    # ========================================================================

    def copy_database(self, source: str, dest: str) -> bool:
        """Copy a database file using shutil.copy2.

        Works even while connected because the DAO handle is opened with
        Exclusive=False (shared mode), so the file is not locked exclusively.

        Args:
            source: Path to source .accdb/.mdb file
            dest: Path to destination file

        Returns:
            True if copy succeeded, False otherwise
        """
        try:
            import shutil
            shutil.copy2(source, dest)
            return True
        except Exception:
            return False

    # Delegated to VbaOperations
    def vba_list_procedures(self, module_name: str) -> list[dict]:
        return self._vba.vba_list_procedures(module_name)

    def vba_get_procedure(self, module_name: str, procedure_name: str) -> dict:
        return self._vba.vba_get_procedure(module_name, procedure_name)

    def vba_replace_procedure(self, module_name: str, procedure_name: str, new_code: str) -> bool:
        return self._vba.vba_replace_procedure(module_name, procedure_name, new_code)
