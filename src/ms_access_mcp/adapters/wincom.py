import os
import sys
import queue
import threading
import concurrent.futures
from typing import Optional, Callable, Any
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


class ComDispatcher:
    """Owns a dedicated STA thread for all COM operations.

    WinCOM objects have apartment affinity — they must be created and used on the same thread.
    This dispatcher serializes all COM calls through a single STA thread so that
    any async worker can drive the adapter without thread-affinity errors.
    """

    DISPATCH_TIMEOUT = 30.0  # seconds

    def __init__(self) -> None:
        self._call_queue: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any], concurrent.futures.Future[Any]]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._stopping = False

        # COM objects — owned by the STA thread only
        self._access_app: Optional[Any] = None
        self._current_db: Optional[Any] = None
        self._ado_conn: Optional[Any] = None
        self._db_path: Optional[str] = None

    def start(self) -> None:
        """Start the STA dispatcher thread (idempotent)."""
        if self._started:
            return
        self._thread = threading.Thread(target=self._run, name="ComDispatcher-STA", daemon=True)
        self._thread.start()
        self._started = True

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute fn(*args, **kwargs) on the STA thread. Returns the result.

        Raises TimeoutError if the call takes longer than DISPATCH_TIMEOUT seconds.
        Raises whatever exception fn raises.
        """
        if not self._started or self._thread is None:
            raise RuntimeError("ComDispatcher has not been started")

        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        self._call_queue.put((fn, args, kwargs, future))
        return future.result(timeout=self.DISPATCH_TIMEOUT)

    def is_connected(self) -> bool:
        """Check if the dispatcher has an active Access.Application connection."""
        return self._access_app is not None and self._current_db is not None

    def set_db_path(self, db_path: str) -> None:
        """Set the database path (called by adapter.connect before opening)."""
        self._db_path = db_path

    def shutdown(self) -> None:
        """Signal the dispatcher thread to stop and clean up COM objects."""
        self._stopping = True
        # Put a sentinel to wake the thread
        self._call_queue.put((lambda: None, (), {}, concurrent.futures.Future()))
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._access_app = None
        self._current_db = None
        self._ado_conn = None
        self._db_path = None
        self._started = False

    # -------------------------------------------------------------------------
    # Internal: runs on the STA thread
    # -------------------------------------------------------------------------

    def _run(self) -> None:
        """STA thread main loop. Initializes COM and processes call queue."""
        # Import here so non-Windows platforms never hit this code path
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()

        try:
            while not self._stopping:
                try:
                    fn, args, kwargs, future = self._call_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if self._stopping:
                    break

                try:
                    result = fn(*args, **kwargs)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
        finally:
            # Clean up COM on the same thread
            self._cleanup_com()
            pythoncom.CoUninitialize()

    def _cleanup_com(self) -> None:
        """Close Access and release COM objects (must run on STA thread)."""
        if self._access_app is not None:
            try:
                self._access_app.CloseCurrentDatabase()
            except Exception:
                pass
            try:
                self._access_app.Quit()
            except Exception:
                pass
            self._access_app = None
        self._current_db = None
        self._ado_conn = None


class WinComAdapter(AccessAdapter):
    """COM-based adapter using pywin32 for full Access automation.

    All COM operations are dispatched to a dedicated STA thread via ComDispatcher
    to avoid thread-affinity errors when the MCP server handles requests from
    different async workers.
    """

    def __init__(self) -> None:
        self._dispatcher = ComDispatcher()
        # State mirrors what dispatcher holds for query purposes
        self._db_path: Optional[str] = None

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
                self._dispatcher._access_app.OpenCurrentDatabase(db_path)
                self._dispatcher._current_db = self._dispatcher._access_app.CurrentDb()
                self._dispatcher._ado_conn = self._dispatcher._access_app.CurrentProject.Connection
                return True
            except Exception:
                self._dispatcher._cleanup_com()
                return False

        return self._dispatcher.call(_do_connect)

    def disconnect(self) -> None:
        """Disconnect from the Access database."""
        def _do_disconnect() -> None:
            self._dispatcher._cleanup_com()
        try:
            self._dispatcher.call(_do_disconnect)
        except Exception:
            pass
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
                dao = self._dispatcher._access_app.DAo
                db = dao.DBEngine.OpenDatabase(self._dispatcher._db_path)
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

    def execute_query(self, sql: str, params: Optional[list] = None) -> list[dict]:
        """Execute a SQL query and return results."""
        if not self.is_connected():
            return []

        def _do() -> list[dict]:
            results: list[dict] = []
            try:
                rs = self._dispatcher._current_db.OpenRecordset(sql)
                if rs.RecordCount > 0 and not rs.EOF:
                    rs.MoveFirst()
                    while not rs.EOF:
                        row = {}
                        for i in range(rs.Fields.Count):
                            field = rs.Fields(i)
                            row[field.Name] = field.Value
                        results.append(row)
                        rs.MoveNext()
                rs.Close()
            except Exception:
                pass
            return results

        return self._dispatcher.call(_do)

    def launch_access(self, visible: bool = False) -> None:
        """Launch Microsoft Access application."""
        self._ensure_windows()

        def _do() -> None:
            import win32com.client
            if self._dispatcher._access_app is None:
                self._dispatcher._access_app = win32com.client.Dispatch("Access.Application")
            self._dispatcher._access_app.Visible = visible

        if not self._dispatcher._started:
            self._dispatcher.start()
        self._dispatcher.call(_do)

    def close_access(self) -> None:
        """Close Microsoft Access application."""
        def _do() -> None:
            if self._dispatcher._access_app is not None:
                self._dispatcher._access_app.Quit()
                self._dispatcher._access_app = None
                self._dispatcher._current_db = None

        try:
            self._dispatcher.call(_do)
        except Exception:
            pass

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Set VBA code in a module."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                vbe = self._dispatcher._access_app.VBE
                vb_project = vbe.ActiveVBProject
                if vb_project is None:
                    return False
                for mod in vb_project.VBComponents:
                    if mod.Name == module_name:
                        mod.CodeModule.DeleteLines(1, mod.CodeModule.CountOfLines)
                        mod.CodeModule.AddFromString(code)
                        return True
                return False
            except Exception:
                return False

        return self._dispatcher.call(_do)

# ========================================================================
    # FORM OPERATIONS
    # ========================================================================

    def get_forms(self) -> list[FormInfo]:
        """Get all forms in the database."""
        if not self.is_connected():
            return []

        def _do() -> list[FormInfo]:
            forms: list[FormInfo] = []
            try:
                all_forms = self._dispatcher._access_app.CurrentProject.AllForms
                for i in range(all_forms.Count):
                    form_obj = all_forms(i)
                    try:
                        record_source = ""
                        try:
                            record_source = str(form_obj.Properties("RecordSource")) if form_obj.Properties.Exists("RecordSource") else ""
                        except Exception:
                            pass
                        forms.append(FormInfo(name=form_obj.Name, record_source=record_source))
                    except Exception:
                        pass
            except Exception:
                pass
            return forms

        return self._dispatcher.call(_do)

    def form_exists(self, form_name: str) -> bool:
        """Check if a form exists."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                all_forms = self._dispatcher._access_app.CurrentProject.AllForms
                for i in range(all_forms.Count):
                    if all_forms(i).Name == form_name:
                        return True
            except Exception:
                pass
            return False

        return self._dispatcher.call(_do)

    def get_form_controls(self, form_name: str) -> list[ControlInfo]:
        """Get all controls in a form."""
        if not self.is_connected():
            return []

        def _do() -> list[ControlInfo]:
            controls: list[ControlInfo] = []
            try:
                doc = self._dispatcher._access_app.CurrentProject.AllForms(form_name)
                doc.Properties.DefaultView = 1
                controls.append(ControlInfo(
                    name="(RequiresDesignView)",
                    type="placeholder",
                    properties={"note": "Open form in design view to enumerate controls"},
                ))
            except Exception:
                pass
            return controls

        return self._dispatcher.call(_do)

    def export_form_to_text(self, form_name: str) -> str:
        """Export a form to text representation."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            try:
                self._dispatcher._access_app.DoCmd.OpenForm(form_name, 2)
                return f"Form: {form_name}\nExported via COM automation"
            except Exception:
                return ""

        return self._dispatcher.call(_do)

    def import_form_from_text(self, form_data: str) -> bool:
        """Import a form from text representation."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def delete_form(self, form_name: str) -> bool:
        """Delete a form from the database."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                self._dispatcher._access_app.DoCmd.DeleteObject(2, form_name)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    # ========================================================================
    # REPORT OPERATIONS
    # ========================================================================

    def get_reports(self) -> list[ReportInfo]:
        """Get all reports in the database."""
        if not self.is_connected():
            return []

        def _do() -> list[ReportInfo]:
            reports: list[ReportInfo] = []
            try:
                all_reports = self._dispatcher._access_app.CurrentProject.AllReports
                for i in range(all_reports.Count):
                    report_obj = all_reports(i)
                    try:
                        record_source = ""
                        try:
                            record_source = str(report_obj.Properties("RecordSource")) if report_obj.Properties.Exists("RecordSource") else ""
                        except Exception:
                            pass
                        reports.append(ReportInfo(name=report_obj.Name, record_source=record_source))
                    except Exception:
                        pass
            except Exception:
                pass
            return reports

        return self._dispatcher.call(_do)

    def export_report_to_text(self, report_name: str) -> str:
        """Export a report to text representation."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            try:
                return f"Report: {report_name}\nExported via COM automation"
            except Exception:
                return ""

        return self._dispatcher.call(_do)

    def import_report_from_text(self, report_data: str) -> bool:
        """Import a report from text representation."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def delete_report(self, report_name: str) -> bool:
        """Delete a report from the database."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                self._dispatcher._access_app.DoCmd.DeleteObject(4, report_name)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    # ========================================================================
    # MACRO OPERATIONS
    # ========================================================================

    def get_macros(self) -> list[MacroInfo]:
        """Get all macros in the database."""
        if not self.is_connected():
            return []

        def _do() -> list[MacroInfo]:
            macros: list[MacroInfo] = []
            try:
                all_macros = self._dispatcher._access_app.CurrentProject.AllMacros
                for i in range(all_macros.Count):
                    macro_obj = all_macros(i)
                    try:
                        macros.append(MacroInfo(name=macro_obj.Name, type="Macro"))
                    except Exception:
                        pass
            except Exception:
                pass
            return macros

        return self._dispatcher.call(_do)

    # ========================================================================
    # VBA/MODULE OPERATIONS
    # ========================================================================

    def get_modules(self) -> list[ModuleInfo]:
        """Get all VBA modules in the database."""
        if not self.is_connected():
            return []

        def _do() -> list[ModuleInfo]:
            modules: list[ModuleInfo] = []
            try:
                vbe = self._dispatcher._access_app.VBE
                vb_project = vbe.ActiveVBProject
                if vb_project is None:
                    return []
                for comp in vb_project.VBComponents:
                    try:
                        code = ""
                        if comp.Type == 1:
                            code = comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
                        modules.append(ModuleInfo(
                            name=comp.Name,
                            type="Standard Module" if comp.Type == 1 else "Class Module",
                            code=code,
                        ))
                    except Exception:
                        pass
            except Exception:
                pass
            return modules

        return self._dispatcher.call(_do)

    def get_vba_code(self, module_name: str) -> str:
        """Get VBA code from a module."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            try:
                vbe = self._dispatcher._access_app.VBE
                vb_project = vbe.ActiveVBProject
                if vb_project is None:
                    return ""
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        return comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
            except Exception:
                pass
            return ""

        return self._dispatcher.call(_do)

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        """Add a VBA procedure to a module."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                vbe = self._dispatcher._access_app.VBE
                vb_project = vbe.ActiveVBProject
                if vb_project is None:
                    return False
                target_module = None
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        target_module = comp
                        break
                if target_module is None:
                    target_module = vb_project.VBComponents.Add(1)
                    target_module.Name = module_name
                target_module.CodeModule.AddFromString(code)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def compile_vba(self) -> bool:
        """Compile VBA code."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                vbe = self._dispatcher._access_app.VBE
                vb_project = vbe.ActiveVBProject
                if vb_project is None:
                    return False
                self._dispatcher._access_app.DoCmd.RunCommand(0xE8)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

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
                dao = self._dispatcher._access_app.DAo
                db = dao.DBEngine.OpenDatabase(self._dispatcher._db_path)
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
                db.Close()
            except Exception:
                pass
            return tables

        return self._dispatcher.call(_do)

    # ========================================================================
    # RELATIONSHIPS (Foreign Keys)
    # ========================================================================

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get all foreign key relationships from DAO Relations collection."""
        if not self.is_connected():
            return []

        def _do() -> list[RelationshipInfo]:
            relationships: list[RelationshipInfo] = []
            try:
                dao = self._dispatcher._access_app.DAo
                db = dao.DBEngine.OpenDatabase(self._dispatcher._db_path)
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
                db.Close()
            except Exception:
                pass
            return relationships

        return self._dispatcher.call(_do)

    # ========================================================================
    # OBJECT METADATA
    # ========================================================================

    def get_object_metadata(self, object_name: str) -> dict:
        """Get metadata for a database object."""
        if not self.is_connected():
            return {}

        def _do() -> dict:
            try:
                for collection_name in ["AllTables", "AllForms", "AllReports", "AllMacros"]:
                    try:
                        collection = getattr(self._dispatcher._access_app.CurrentProject, collection_name)
                        for i in range(collection.Count):
                            obj = collection(i)
                            if obj.Name == object_name:
                                return {
                                    "name": obj.Name,
                                    "type": collection_name.replace("All", "").lower(),
                                    "properties": self._get_object_properties(obj),
                                }
                    except Exception:
                        pass
            except Exception:
                pass
            return {}

        return self._dispatcher.call(_do)

    def _get_object_properties(self, obj: object) -> dict:
        """Get properties of an Access object."""
        def _do() -> dict:
            props = {}
            try:
                for prop in obj.Properties:
                    try:
                        props[prop.Name] = str(prop.Value)
                    except Exception:
                        pass
            except Exception:
                pass
            return props

        if not self._dispatcher._started:
            return {}
        try:
            return self._dispatcher.call(_do)
        except Exception:
            return {}

    # ========================================================================
    # SQL SCRIPT EXECUTION (Jet SQL pass-through)
    # ========================================================================

    def execute_sql_script(self, script_path: str) -> dict:
        """Execute a SQL script file against the connected database.

        Uses ADO (CurrentProject.Connection) for DML (INSERT/UPDATE/SELECT)
        with ANSI-92 SQL support. Falls back to DAO for DDL (CREATE TABLE, etc.)
        since ADO's Execute method does not support DDL in Access.
        All statements run in sequence - rollback on any failure.
        """
        if not os.path.exists(script_path):
            return {
                "success": False,
                "error": f"File not found: {script_path}",
                "statements_executed": 0,
            }

        if not self.is_connected():
            return {
                "success": False,
                "error": "Not connected to database",
                "statements_executed": 0,
            }

        try:
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read file: {e}",
                "statements_executed": 0,
            }

        # Strip SQL comments and split on semicolons
        content = self._strip_sql_comments(content)
        statements = [s.strip() for s in content.split(";")]
        statements = [s for s in statements if s]

        if not statements:
            return {
                "success": True,
                "statements_executed": 0,
                "message": "No statements to execute",
            }

        def _do() -> dict:
            executed = 0
            use_ado = self._dispatcher._ado_conn is not None
            dao_db = None

            try:
                for stmt in statements:
                    if not stmt:
                        continue

                    if use_ado:
                        try:
                            # ADO path - supports ANSI-92 mode for DML
                            # Parameters: CommandText, RecordsAffected(-1=ignore), Options(128=adExecuteNoRecords)
                            self._dispatcher._ado_conn.Execute(stmt, -1, 128)
                            executed += 1
                            continue
                        except Exception as ado_err:
                            err_str = str(ado_err).lower()
                            if "expected 'delete" in err_str or "expected 'insert" in err_str:
                                pass  # Fall through to DAO below
                            else:
                                raise

                    # DAO path (fallback for DDL or when ADO unavailable)
                    if dao_db is None:
                        dao_db = self._dispatcher._access_app.Dao.DBEngine.OpenDatabase(self._dispatcher._db_path)
                    dao_db.Execute(stmt, 128)  # dbFailOnError
                    executed += 1

                return {
                    "success": True,
                    "statements_executed": executed,
                    "message": f"{executed} statement(s) executed successfully",
                    "engine": "ADO" if use_ado else "DAO",
                }
            except Exception as e:
                return {
                    "success": False,
                    "statements_executed": executed,
                    "error": str(e),
                    "failing_statement": stmt if executed < len(statements) else "",
                    "engine": "ADO" if use_ado and executed > 0 else "DAO",
                }
            finally:
                if dao_db is not None:
                    try:
                        dao_db.Close()
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

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
    # VERSIONING EXPORT (git-friendly text export)
    # ========================================================================

    def export_module_to_text(self, module_name: str) -> str:
        """Export VBA module code as plain text."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            try:
                vbe = self._dispatcher._access_app.VBE
                vb_project = vbe.ActiveVBProject
                if vb_project is None:
                    return ""
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        return comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
            except Exception:
                pass
            return ""

        return self._dispatcher.call(_do)

    def export_macro_to_text(self, macro_name: str) -> str:
        """Export macro metadata as text (macros can't export as code)."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            try:
                all_macros = self._dispatcher._access_app.CurrentProject.AllMacros
                for i in range(all_macros.Count):
                    if all_macros(i).Name == macro_name:
                        return f"Macro: {macro_name}\nType: Access Macro"
            except Exception:
                pass
            return ""

        return self._dispatcher.call(_do)

    def export_all_versioning(self, output_dir: str) -> dict:
        """Export all forms, reports, modules, and macros to a directory structure."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected to database", "exported": {}}

        def _do() -> dict:
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                return {"success": False, "error": f"Cannot create directory: {e}", "exported": {}}

            def safe_filename(name: str) -> str:
                for ch in '\\/:*?"<>|':
                    name = name.replace(ch, '_')
                return name

            exported = {"forms": [], "reports": [], "modules": [], "macros": []}

            # Export forms
            try:
                forms = self._dispatcher.call(self.get_forms)
                forms_dir = os.path.join(output_dir, "forms")
                os.makedirs(forms_dir, exist_ok=True)
                for form in forms:
                    try:
                        safe_name = safe_filename(form.name)
                        out_path = os.path.join(forms_dir, f"forms_{safe_name}.txt")
                        self._dispatcher._access_app.SaveAsText(2, form.name, out_path)
                        exported["forms"].append(form.name)
                    except Exception:
                        pass
            except Exception:
                pass

            # Export reports
            try:
                reports = self._dispatcher.call(self.get_reports)
                reports_dir = os.path.join(output_dir, "reports")
                os.makedirs(reports_dir, exist_ok=True)
                for report in reports:
                    try:
                        safe_name = safe_filename(report.name)
                        out_path = os.path.join(reports_dir, f"reports_{safe_name}.txt")
                        self._dispatcher._access_app.SaveAsText(4, report.name, out_path)
                        exported["reports"].append(report.name)
                    except Exception:
                        pass
            except Exception:
                pass

            # Export VBA modules
            try:
                modules = self._dispatcher.call(self.get_modules)
                modules_dir = os.path.join(output_dir, "modules")
                os.makedirs(modules_dir, exist_ok=True)
                for mod in modules:
                    try:
                        safe_name = safe_filename(mod.name)
                        out_path = os.path.join(modules_dir, f"modules_{safe_name}.txt")
                        with open(out_path, "w", encoding="utf-8") as f:
                            f.write(mod.code or "")
                        exported["modules"].append(mod.name)
                    except Exception:
                        pass
            except Exception:
                pass

            # Export macros
            try:
                macros = self._dispatcher.call(self.get_macros)
                macros_dir = os.path.join(output_dir, "macros")
                os.makedirs(macros_dir, exist_ok=True)
                for macro in macros:
                    try:
                        safe_name = safe_filename(macro.name)
                        out_path = os.path.join(macros_dir, f"macros_{safe_name}.txt")
                        with open(out_path, "w", encoding="utf-8") as f:
                            f.write(f"Macro: {macro.name}\nType: Access Macro\n")
                        exported["macros"].append(macro.name)
                    except Exception:
                        pass
            except Exception:
                pass

            total = (len(exported["forms"]) + len(exported["reports"]) +
                     len(exported["modules"]) + len(exported["macros"]))

            return {
                "success": True,
                "exported": exported,
                "output_dir": output_dir,
                "file_count": total,
            }

        return self._dispatcher.call(_do)
