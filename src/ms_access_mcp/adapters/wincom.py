import os
import shutil
import sys
from datetime import datetime
from typing import Optional, Callable, Any
from .base import AccessAdapter
from .interfaces import IDataAdapter, ISchemaAdapter, IUiAdapter
from .com_dispatcher import ComDispatcher, DAO_DB_FAIL_ON_ERROR
from .vba_operations import VbaOperations
from .ui_operations import UiOperations
from .versioning_io import VersioningIo
from .schema_inspector import SchemaInspector
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


class WinComAdapter(IDataAdapter, ISchemaAdapter, IUiAdapter):
    """COM-based adapter using pywin32 for full Access automation.

    All COM operations are dispatched to a dedicated STA thread via ComDispatcher
    to avoid thread-affinity errors when the MCP server handles requests from
    different async workers.
    """

    def __init__(self, db_path: str | None = None, strategy_selector: Any | None = None) -> None:
        from .export.strategies import ExportStrategySelector

        self._db_path: str | None = db_path
        self._dispatcher = ComDispatcher()
        self._vba = VbaOperations(self._dispatcher)
        self._ui = UiOperations(self._dispatcher)
        self._schema = SchemaInspector(self._dispatcher)
        self._versioning = VersioningIo(
            dispatcher=self._dispatcher,
            save_text=self._ui._save_object_to_text,
            load_text=self._ui._load_object_from_text,
            get_tables_fn=self._schema.get_tables,
            get_relationships_fn=self._schema.get_relationships,
            get_system_tables_fn=self._schema.get_system_tables,
        )
        # Wire VbaOperations to UiOperations for shared _load_object_from_text (acModule=5 path)
        self._vba.set_load_text(self._ui._load_object_from_text)
        # State mirrors what dispatcher holds for query purposes
        self._ado_conn: Optional[Any] = None
        # Export strategy registry (injectable for testing)
        self._strategy_selector: ExportStrategySelector = strategy_selector or ExportStrategySelector()

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
                self._dispatcher._access_app = win32com.client.Dispatch("Access.Application")

                self._dispatcher._access_app.Visible = False

                # Open via DAO FIRST with readwrite so _current_db is writable.
                # Using Exclusive=False so external file copy (shutil, etc.) can
                # still access the database without triggering exclusive lock errors.
                # OpenCurrentDatabase on its own opens in read-only mode for COM automation.
                dbe = self._dispatcher._access_app.DBEngine
                self._dispatcher._current_db = dbe.OpenDatabase(db_path, False, False)

                # Now OpenCurrentDatabase — the underlying DAO handle is already writable,
                # so CurrentDb inherits the writable state.
                self._dispatcher._access_app.OpenCurrentDatabase(db_path, False)

                # Suppress Access dialogs after DB is open (VBA module naming, etc.)
                try:
                    self._dispatcher._access_app.DoCmd.SetWarnings(False)
                except Exception:
                    pass

                self._dispatcher._ado_conn = self._dispatcher._access_app.CurrentProject.Connection

                # Dismiss any Access dialog that appeared after OpenCurrentDatabase
                # (VBA module naming prompts, compile errors, etc.) — must be called
                # after CurrentProject.Connection because VBA loads async on first
                # property access and may trigger the dialog at that point.
                # Use a brief sleep first so the dialog has time to fully render.
                import time
                time.sleep(0.5)
                self._dispatcher._dismiss_access_dialogs()

                return True
            except Exception as _ex:
                self._dispatcher._release_com_safe()
                import sys
                print(f"[WinComAdapter] _do_connect FAILED: {_ex}", file=sys.stderr)
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

    def execute_query(self, sql: str, params: list | None = None) -> dict:
        """Execute SQL query via DAO and return results as dict.

        Args:
            sql: SQL query string (SELECT statements).
            params: Not used for DAO — kept for protocol compatibility.

        Returns:
            dict with success, rows (list[dict]), count, columns.
        """
        _ = params
        if not self.is_connected():
            return {"success": False, "rows": [], "count": 0, "columns": [], "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                rs = db.OpenRecordset(sql)
                if rs.EOF:
                    rs.Close()
                    return {"success": True, "rows": [], "count": 0, "columns": []}

                # Read column names
                columns = []
                for i in range(rs.Fields.Count):
                    columns.append(rs.Fields(i).Name)

                # Read all rows
                results = []
                while not rs.EOF:
                    row = {}
                    for i, col in enumerate(columns):
                        val = rs.Fields(i).Value
                        if val is not None and hasattr(val, 'strftime'):
                            val = val.isoformat()
                        row[col] = val
                    results.append(row)
                    rs.MoveNext()

                rs.Close()
                return {"success": True, "rows": results, "count": len(results), "columns": columns}

            except Exception as e:
                return {"success": False, "rows": [], "count": 0, "columns": [], "error": str(e)}

        return self._dispatcher.call(_do)

    def get_tables(self) -> list[TableInfo]:
        """Get all user tables from the connected database."""
        return self._schema.get_tables()

    @staticmethod
    def _access_type_name(access_type: int) -> str:
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

    def get_system_tables(self) -> list[TableInfo]:
        """Get system tables from the database."""
        return self._schema.get_system_tables()

    # ========================================================================
    # RELATIONSHIPS (Foreign Keys)
    # ========================================================================

    def _get_table_indexes(self, table_name: str) -> dict[str, list[str]]:
        """Return {index_name: [columns]} for indexes where Primary=True."""
        return self._schema._get_table_indexes(table_name)

    def _get_field_details(self, table_name: str) -> list[dict]:
        """Return list of {name, type, size, attributes, default_value} for each field."""
        return self._schema._get_field_details(table_name)

    def _get_relationship_columns(self) -> list[ForeignKeyInfo]:
        """Read Relations collection and build ForeignKeyInfo list."""
        return self._schema._get_relationship_columns()

    def get_queries(self) -> list[QueryInfo]:
        """Get all saved queries (QueryDefs) via SchemaInspector."""
        return self._schema.get_queries()

    def get_table_schema_plan(self) -> tuple[list[TableSchema], UnknownMetadata]:
        """Extract table schema fidelity metadata from Access DAO collections.

        Saved queries are intentionally excluded by using only table definitions.
        """
        return self._schema.get_table_schema_plan()

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get all foreign key relationships from DAO Relations collection."""
        return self._schema.get_relationships()

    def generate_sql(self, output_path: str) -> dict:
        """Generate Jet SQL DDL and write to output_path.

        Orchestrates reading schema (tables, indexes, field details, FKs),
        calls JetSqlGenerator.generate(), and writes to output_path.

        Returns:
            dict with success=True, path, statements (count), tables (list)
        """
        return self._schema.generate_sql(output_path)

    # ========================================================================
    # OBJECT METADATA
    # ========================================================================

    def get_object_metadata(self, object_name: str) -> dict:
        """Get metadata for a database object."""
        return self._schema.get_object_metadata(object_name)

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
    # DATA EXPORT (Strategy pattern — csv, json, excel)
    # ========================================================================

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
        return self._dispatcher.call(self._execute_raw_on_current_db, sql)

    def _execute_raw_on_current_db(self, sql: str) -> int:
        """Execute SQL against the current DAO database on the STA thread."""
        db = self._dispatcher.current_db
        db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
        return db.RecordsAffected

    def execute_raw_sql(self, sql: str) -> int:
        """Execute raw SQL statement via COM dispatcher. Returns rows affected.

        Args:
            sql: Raw SQL string to execute against the Access DAO engine.

        Returns:
            int: Number of records affected by the execution.
        """
        return self._dispatcher.call(self._execute_raw_on_current_db, sql)

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

            ado = self._dispatcher.ado_conn
            executed = 0
            for entry in parse["statements"]:
                try:
                    ado.Execute(entry["text"])
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

    # ========================================================================
    # DAO CRUD — Data Operations
    # ========================================================================

    def insert_data(self, table_name: str, data: dict | list[dict]) -> dict:
        """Insert one or more rows into a table via DAO SQL.

        Args:
            table_name: Name of the table
            data: A single dict for one row, or a list of dicts for multiple rows

        Returns:
            dict with success=True and affected=number of rows inserted
        """
        if not self.is_connected():
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

    def update_data(self, table_name: str, set_dict: dict, where_dict: dict | str | None = None) -> dict:
        """Update rows in a table via DAO SQL.

        Args:
            table_name: Name of the table
            set_dict: Dict of column=value pairs to set
            where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows

        Returns:
            dict with success=True and affected=number of rows updated
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected", "affected": 0}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                set_clause = ", ".join(f"[{c}] = {self._format_dao_value(v)}" for c, v in set_dict.items())
                sql = f"UPDATE [{table_name}] SET {set_clause}"
                if where_dict is not None:
                    if isinstance(where_dict, str):
                        sql += f" WHERE {where_dict}"
                    else:
                        where_clause = " AND ".join(f"[{c}] = {self._format_dao_value(v)}" for c, v in where_dict.items())
                        sql += f" WHERE {where_clause}"
                db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                return {"success": True, "affected": db.RecordsAffected}
            except Exception as e:
                return {"success": False, "error": str(e), "affected": 0}

        return self._dispatcher.call(_do)

    def delete_data(self, table_name: str, where_dict: dict | str | None = None) -> dict:
        """Delete rows from a table via DAO SQL.

        Args:
            table_name: Name of the table
            where_dict: Dict of conditions (ANDed), a raw SQL string, or None for all rows

        Returns:
            dict with success=True and affected=number of rows deleted
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected", "affected": 0}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                sql = f"DELETE FROM [{table_name}]"
                if where_dict is not None:
                    if isinstance(where_dict, str):
                        sql += f" WHERE {where_dict}"
                    else:
                        where_clause = " AND ".join(f"[{c}] = {self._format_dao_value(v)}" for c, v in where_dict.items())
                        sql += f" WHERE {where_clause}"
                db.Execute(sql, DAO_DB_FAIL_ON_ERROR)
                return {"success": True, "affected": db.RecordsAffected}
            except Exception as e:
                return {"success": False, "error": str(e), "affected": 0}

        return self._dispatcher.call(_do)

    # ========================================================================
    # DAO CRUD — Query Operations
    # ========================================================================

    def create_query(self, name: str, sql: str) -> dict:
        """Create a saved QueryDef via DAO.

        Args:
            name: Name of the query
            sql: SQL statement for the query

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                db.CreateQueryDef(name, sql)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def set_query_sql(self, name: str, sql: str) -> dict:
        """Update an existing QueryDef's SQL via DAO.

        Args:
            name: Name of the existing query
            sql: New SQL statement

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                qdef = db.QueryDefs(name)
                qdef.SQL = sql
                qdef.Close()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def delete_query(self, name: str) -> dict:
        """Delete a saved QueryDef via DAO.

        Args:
            name: Name of the query to delete

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                db.QueryDefs.Delete(name)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    # ========================================================================
    # DAO CRUD — Table Operations
    # ========================================================================

    def create_table(self, table_name: str, columns: list[dict]) -> dict:
        """Create a table via DAO DDL.

        Args:
            table_name: Name of the table to create
            columns: List of dicts with keys: name, type, size, required, is_autoincrement

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
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
        """Drop a table via DAO DDL.

        Deletes all DAO Relations involving the table before DROP,
        so tables referenced by foreign keys can be removed.

        Args:
            table_name: Name of the table to delete

        Returns:
            dict with success=True or success=False and error
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                for i in range(db.Relations.Count - 1, -1, -1):
                    rel = db.Relations(i)
                    if rel.Table == table_name or rel.ForeignTable == table_name:
                        db.Relations.Delete(rel.Name)
                db.Execute(f"DROP TABLE [{table_name}]", DAO_DB_FAIL_ON_ERROR)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    @staticmethod
    def _access_sql_type(access_type: str, size: int = 255) -> str:
        """Map Access type name to SQL type string.

        Args:
            access_type: Access type name (e.g. "Text", "Long Integer", "Currency")
            size: Size for VARCHAR types (default 255)

        Returns:
            SQL type string for DDL
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
        return type_map.get(access_type, f"VARCHAR({size})")

    # Delegated to VbaOperations
    def vba_list_procedures(self, module_name: str) -> list[dict]:
        return self._vba.vba_list_procedures(module_name)

    def vba_get_procedure(self, module_name: str, procedure_name: str) -> dict:
        return self._vba.vba_get_procedure(module_name, procedure_name)

    def vba_replace_procedure(self, module_name: str, procedure_name: str, new_code: str) -> bool:
        return self._vba.vba_replace_procedure(module_name, procedure_name, new_code)
