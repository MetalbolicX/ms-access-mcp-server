import os
import shutil
import subprocess
import sys
import queue
import tempfile
import threading
import concurrent.futures
from datetime import datetime
from typing import Optional, Callable, Any
from .base import AccessAdapter

# DAO DBEngine.Execute option flags
DAO_DB_FAIL_ON_ERROR = 128  # dbFailOnError — raises exception if record operation fails
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


class ComDispatcher:
    """Owns a dedicated STA thread for all COM operations.

    WinCOM objects have apartment affinity — they must be created and used on the same thread.
    This dispatcher serializes all COM calls through a single STA thread so that
    any async worker can drive the adapter without thread-affinity errors.
    """

    DISPATCH_TIMEOUT = 120.0  # seconds (cold Access start + large DB open can take 60s+)

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
            self._thread.join(timeout=15.0)
        # Ensure release even if thread already dead
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
            self._release_com_safe()
            pythoncom.CoUninitialize()

    def _release_com_safe(self) -> None:
        """Release all COM objects in order: ADO -> DAO -> Access Application.

        Uses a watchdog thread to avoid hanging on Access.Quit().
        Falls back to taskkill /F if graceful shutdown fails on Windows.
        """
        errors: list[str] = []

        # 1. Close ADO connection explicitly
        if self._ado_conn is not None:
            try:
                self._ado_conn.Close()
            except Exception as e:
                errors.append(f"ADO Close: {e}")
            self._ado_conn = None

        # 2. Close DAO database explicitly
        if self._current_db is not None:
            try:
                self._current_db.Close()
            except Exception as e:
                errors.append(f"DAO Close: {e}")
            self._current_db = None

        # 3. Close and quit Access Application via COM
        if self._access_app is not None:
            try:
                self._access_app.CloseCurrentDatabase()
            except Exception as e:
                errors.append(f"CloseCurrentDatabase: {e}")

            # 4. Quit() with 5s watchdog
            app = self._access_app
            quit_ok = False
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(lambda: app.Quit())
                    fut.result(timeout=5.0)
                    quit_ok = True
            except concurrent.futures.TimeoutError:
                errors.append("Access.Quit() timed out after 5s")
            except Exception as e:
                errors.append(f"Access.Quit(): {e}")

            self._access_app = None

            # 5. Force-kill fallback (Windows only)
            if not quit_ok and sys.platform == 'win32':
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "MSACCESS.EXE"],
                        capture_output=True, text=True, timeout=10
                    )
                except Exception as e:
                    errors.append(f"taskkill: {e}")

        if errors:
            print(f"[ComDispatcher] Cleanup completed with {len(errors)} warning(s): {'; '.join(errors)}")

    def _cleanup_com(self) -> None:
        """Legacy wrapper — delegates to _release_com_safe()."""
        self._release_com_safe()


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
                self._dispatcher._access_app = win32com.client.Dispatch("Access.Application")

                # Open via DAO FIRST with exclusive+readwrite so _current_db is writable.
                # OpenCurrentDatabase on its own opens in read-only mode for COM automation.
                dbe = self._dispatcher._access_app.DBEngine
                self._dispatcher._current_db = dbe.OpenDatabase(db_path, True, False)

                # Now OpenCurrentDatabase — the underlying DAO handle is already writable,
                # so CurrentDb inherits the writable state.
                self._dispatcher._access_app.OpenCurrentDatabase(db_path, True)

                self._dispatcher._ado_conn = self._dispatcher._access_app.CurrentProject.Connection
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
                db = self._dispatcher._access_app.DBEngine.OpenDatabase(self._dispatcher._db_path)
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
        """Get the first VBA project via VBProjects enumeration.

        COM VBProjects collection uses 1-based indexing.
        More reliable than ActiveVBProject in COM automation, which depends
        on which project is active/focused and may return None.
        """
        try:
            vbe = self._dispatcher._access_app.VBE
            # VBProjects is 1-based COM collection
            for i in range(1, vbe.VBProjects.Count + 1):
                return vbe.VBProjects(i)
        except Exception:
            pass
        return None

    def _save_object_to_text(self, object_type: int, object_name: str) -> str:
        """Export an Access object to text using SaveAsText.

        Returns the text content or empty string on failure.
        object_type: acForm=2, acReport=4, acModule=5, acMacro=8
        """
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_exp_")
            os.close(fd)
            self._dispatcher._access_app.SaveAsText(object_type, object_name, temp_path)
            with open(temp_path, "rb") as f:
                raw = f.read()
            # SaveAsText outputs UTF-16-LE with BOM; decode accordingly
            content = raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")
            return content
        except Exception:
            return ""
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    def _load_object_from_text(self, object_type: int, object_name: str, text_data: str) -> bool:
        """Import an Access object from text data using LoadFromText.

        object_type: acForm=2, acReport=4, acModule=5, acMacro=8
        """
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_imp_")
            os.close(fd)
            with open(temp_path, "wb") as f:
                # Write as UTF-16-LE with BOM (what Access expects)
                f.write(b"\xff\xfe")
                f.write(text_data.encode("utf-16-le"))
            self._dispatcher._access_app.LoadFromText(object_type, object_name, temp_path)
            return True
        except Exception:
            return False
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

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
                rs = self._dispatcher._current_db.OpenRecordset(sql)
                if rs.RecordCount > 0 and not rs.EOF:
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
                            row[field.Name] = field.Value
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
                db = self._dispatcher._current_db
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
                db = self._dispatcher._current_db

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
                db = self._dispatcher._current_db
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
                db = self._dispatcher._current_db
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
                self._dispatcher._current_db.CreateQueryDef(name, sql)
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
                qdef = self._dispatcher._current_db.QueryDefs(name)
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
                self._dispatcher._current_db.QueryDefs.Delete(name)
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
                db = self._dispatcher._current_db
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
                self._dispatcher._current_db.TableDefs.Delete(table_name)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    def launch_access(self, visible: bool = False) -> None:
        """Launch Microsoft Access application."""
        self._ensure_windows()

        def _do() -> None:
            import win32com.client
            if self._dispatcher._access_app is None:
                self._dispatcher._access_app = win32com.client.Dispatch("Access.Application")
            try:
                self._dispatcher._access_app.Visible = visible
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
            if self._dispatcher._access_app is not None:
                app = self._dispatcher._access_app
                # Save all VBA modules before quitting
                try:
                    vb_project = app.VBE.VBProjects(1)
                    for comp in vb_project.VBComponents:
                        if comp.Type == 1:  # vbext_ct_StdModule
                            app.DoCmd.Save(5, comp.Name)  # 5 = acModule
                except Exception:
                    pass
                self._dispatcher._release_com_safe()

        try:
            self._dispatcher.call(_do)
        except Exception as e:
            print(f"Cleanup warning: close_access failed: {e}", file=sys.stderr)

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Set VBA code in a module."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return False
            try:
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
        """Get all controls in a form by opening it in design view."""
        if not self.is_connected():
            return []

        def _do() -> list[ControlInfo]:
            controls: list[ControlInfo] = []
            opened = False
            try:
                # Open in design view (acDesign). Numeric value 1 avoids triggering events.
                self._dispatcher._access_app.DoCmd.OpenForm(form_name, 1)
                opened = True

                # Get the form via Screen.ActiveForm (most reliable after OpenForm).
                # Fallback: try the Forms collection.
                try:
                    form = self._dispatcher._access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher._access_app.Forms(form_name)

                if form is not None:
                    for i in range(form.Controls.Count):
                        try:
                            ctrl = form.Controls(i)
                            ctrl_name = ctrl.Name
                            ctrl_type_code = ctrl.ControlType
                            ctrl_type = self._access_control_type_name(ctrl_type_code)

                            # Collect key readability properties individually
                            # (bulk iteration of Properties is slow and exception-prone).
                            props: dict[str, str] = {}
                            for prop_name in ("Visible", "Enabled", "Left", "Top",
                                              "Width", "Height", "Caption",
                                              "ControlSource", "TabIndex"):
                                try:
                                    val = ctrl.Properties(prop_name).Value
                                    if val is not None:
                                        props[prop_name] = str(val)
                                except Exception:
                                    pass

                            controls.append(ControlInfo(
                                name=ctrl_name, type=ctrl_type, properties=props,
                            ))
                        except Exception:
                            pass
            except Exception:
                pass
            finally:
                if opened:
                    try:
                        # Close form without saving (acForm=2, acSaveNo=2)
                        self._dispatcher._access_app.DoCmd.Close(2, form_name, 2)
                    except Exception:
                        pass
            return controls

        return self._dispatcher.call(_do)

    def export_form_to_text(self, form_name: str) -> str:
        """Export a form to text representation via SaveAsText."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            return self._save_object_to_text(2, form_name)

        return self._dispatcher.call(_do)

    def import_form_from_text(self, form_name: str, form_data: str) -> bool:
        """Import a form from text data via LoadFromText."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            return self._load_object_from_text(2, form_name, form_data)

        return self._dispatcher.call(_do)

    def open_form(self, form_name: str) -> bool:
        """Open a form in Access (appears on the server desktop)."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                self._dispatcher._access_app.DoCmd.OpenForm(form_name)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def close_form(self, form_name: str) -> bool:
        """Close an open form without saving."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            try:
                self._dispatcher._access_app.DoCmd.Close(2, form_name, 2)  # acForm=2, acSaveNo=2
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def get_control_properties(self, form_name: str, control_name: str) -> dict:
        """Get all properties of a specific control by opening the form in design view."""
        if not self.is_connected():
            return {}

        def _do() -> dict:
            opened = False
            try:
                self._dispatcher._access_app.DoCmd.OpenForm(form_name, 1)
                opened = True

                try:
                    form = self._dispatcher._access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher._access_app.Forms(form_name)

                if form is not None:
                    for i in range(form.Controls.Count):
                        try:
                            ctrl = form.Controls(i)
                            if ctrl.Name == control_name:
                                props: dict[str, str] = {}
                                for prop in ctrl.Properties:
                                    try:
                                        props[prop.Name] = str(prop.Value)
                                    except Exception:
                                        pass
                                return props
                        except Exception:
                            pass
                return {}
            except Exception:
                return {}
            finally:
                if opened:
                    try:
                        self._dispatcher._access_app.DoCmd.Close(2, form_name, 2)
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def set_control_property(self, form_name: str, control_name: str, property_name: str, value: str) -> bool:
        """Set a property of a control by opening the form in design view.

        Opens the form in design view, sets the property, and saves the form.
        Returns True if the property was set successfully.
        """
        if not self.is_connected():
            return False

        def _do() -> bool:
            opened = False
            try:
                self._dispatcher._access_app.DoCmd.OpenForm(form_name, 1)
                opened = True

                try:
                    form = self._dispatcher._access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher._access_app.Forms(form_name)

                if form is not None:
                    for i in range(form.Controls.Count):
                        try:
                            ctrl = form.Controls(i)
                            if ctrl.Name == control_name:
                                ctrl.Properties(property_name).Value = value
                                return True
                        except Exception:
                            pass
                return False
            except Exception:
                return False
            finally:
                if opened:
                    try:
                        self._dispatcher._access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes
                    except Exception:
                        pass

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
        """Export a report to text representation via SaveAsText."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            return self._save_object_to_text(4, report_name)

        return self._dispatcher.call(_do)

    def import_report_from_text(self, report_name: str, report_data: str) -> bool:
        """Import a report from text data via LoadFromText."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            return self._load_object_from_text(4, report_name, report_data)

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

    def get_vba_project_name(self) -> str:
        """Get the VBA project name from COM."""
        if not self.is_connected():
            return ""
        def _do() -> str:
            vb_project = self._get_vb_project()
            return vb_project.Name if vb_project else ""
        try:
            return self._dispatcher.call(_do)
        except Exception:
            return ""

    def get_modules(self) -> list[ModuleInfo]:
        """Get all VBA modules in the database."""
        if not self.is_connected():
            return []

        def _do() -> list[ModuleInfo]:
            modules: list[ModuleInfo] = []
            vb_project = self._get_vb_project()
            if vb_project is None:
                return []
            try:
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
            vb_project = self._get_vb_project()
            if vb_project is None:
                return ""
            try:
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        lines = comp.CodeModule.CountOfLines
                        if lines > 0:
                            return comp.CodeModule.Lines(1, lines)
                        return ""
            except Exception:
                pass
            return ""

        return self._dispatcher.call(_do)

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        """Add a VBA procedure to a module."""
        if not self.is_connected():
            return False

        def _do() -> bool:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return False
            try:
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

    def delete_module(self, module_name: str) -> bool:
        """Delete a VBA module from the database.

        Args:
            module_name: Name of the module to delete

        Returns:
            True if deleted, False if not found or error
        """
        if not self.is_connected():
            return False

        def _do() -> bool:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return False
            try:
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        vb_project.VBComponents.Remove(comp)
                        return True
                return False
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def save_database(self) -> dict:
        """Save all VBA modules and database changes.

        Uses DoCmd.Save to persist each standard module.
        Returns structured result with success/error.

        Returns:
            dict with success=True on success, error message on failure
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return {"success": False, "error": "No VBA project"}
            app = self._dispatcher._access_app
            saved = 0
            errors = []
            try:
                for comp in vb_project.VBComponents:
                    if comp.Type == 1:  # vbext_ct_StdModule
                        try:
                            app.DoCmd.Save(5, comp.Name)  # 5 = acModule
                            saved += 1
                        except Exception as e:
                            errors.append(f"{comp.Name}: {e}")
            except Exception as e:
                return {"success": False, "error": str(e)}
            return {
                "success": True,
                "saved_modules": saved,
                "errors": errors,
            }

        return self._dispatcher.call(_do)

    def compile_vba(self) -> dict:
        """Compile VBA code.

        Tries known DoCmd.RunCommand constants for VBA compilation.
        The correct command ID varies by Access version:
        - 301: Access 16.0 (Office 365 / 2021) — confirmed working
        - 206: acCmdCompileAllModules (older versions)
        - 317: acCmdCompileAndSaveAllModules (older versions)
        - 232: 0xE8 — commonly documented online

        Returns:
            dict with success=True on success
            dict with success=False and error message on failure
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        # Compile command IDs by Access version (most likely first)
        _COMPILE_CMD_IDS = [301, 206, 317, 232]

        def _do() -> dict:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return {"success": False, "error": "No VBA project"}
            app = self._dispatcher._access_app
            for cmd_id in _COMPILE_CMD_IDS:
                try:
                    app.DoCmd.RunCommand(cmd_id)
                    return {"success": True}
                except Exception:
                    continue
            return {
                "success": False,
                "error": "Could not find working compile command for this Access version",
            }

        try:
            return self._dispatcher.call(_do)
        except Exception as e:
            return {"success": False, "error": str(e)}

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
                db = self._dispatcher._current_db
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
                db = self._dispatcher._current_db
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
                db = self._dispatcher._current_db
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
                db = self._dispatcher._current_db
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
                db = self._dispatcher._current_db

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
                db = self._dispatcher._current_db
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
                # 1. Get tables (already dispatches internally)
                base_tables = self.get_tables()
                if not base_tables:
                    return {"success": True, "path": output_path, "statements": 0, "tables": []}

                # 2. Enrich each table with field details and primary keys
                tables: list[TableInfo] = []
                for base_table in base_tables:
                    table_name = base_table.name

                    # Get field details (attributes, default_value) via direct dispatch
                    field_details = self._dispatcher.call(self._get_field_details, table_name)

                    # Get primary key columns for this table via direct dispatch
                    indexes = self._dispatcher.call(self._get_table_indexes, table_name)
                    pk_columns: list[str] = []
                    for idx_name, idx_fields in indexes.items():
                        if idx_name.startswith("~"):
                            continue
                        pk_columns = idx_fields
                        break

                    # Merge field details into FieldInfo objects
                    enriched_fields: list[FieldInfo] = []
                    field_detail_map = {fd["name"]: fd for fd in field_details}

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

                # 3. Get relationships and foreign keys
                relationships = self.get_relationships()
                foreign_keys = self._dispatcher.call(self._get_relationship_columns)

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
                    collection = getattr(self._dispatcher._access_app.CurrentProject, collection_name)
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
                db = self._dispatcher._current_db
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
                db = self._dispatcher._current_db
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
                tdef = self._dispatcher._current_db.TableDefs(name)
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
                self._dispatcher._current_db.TableDefs.Delete(name)
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

                    dbe = self._dispatcher._access_app.DBEngine
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

                        dbe = self._dispatcher._access_app.DBEngine
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

    def export_table_csv(self, table_or_query: str, file_path: str, delimiter: str = ",", header: bool = True) -> dict:
        """Export a table or query to a CSV file.

        Args:
            table_or_query: Name of the table or query to export
            file_path: Path to the output CSV file
            delimiter: Field delimiter (default ',')
            header: Whether to write header row (default True)

        Returns:
            dict with success=True, rows_exported=N, file_path
        """
        import csv
        from pathlib import Path

        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        result = self.execute_query(f"SELECT * FROM [{table_or_query}]")
        if not result.get("success"):
            return {"success": False, "error": result.get("error", "Query failed")}

        rows = result.get("rows", [])
        columns = result.get("columns", [])

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns, delimiter=delimiter)
                if header:
                    writer.writeheader()
                writer.writerows(rows)

            return {"success": True, "rows_exported": len(rows), "file_path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
    # VERSIONING EXPORT (git-friendly text export)
    # ========================================================================

    def export_module_to_text(self, module_name: str) -> str:
        """Export VBA module code as plain text."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return ""
            try:
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        lines = comp.CodeModule.CountOfLines
                        if lines > 0:
                            return comp.CodeModule.Lines(1, lines)
                        return ""
            except Exception:
                pass
            return ""

        return self._dispatcher.call(_do)

    def export_macro_to_text(self, macro_name: str) -> str:
        """Export a macro to text representation via SaveAsText."""
        if not self.is_connected():
            return ""

        def _do() -> str:
            return self._save_object_to_text(8, macro_name)

        return self._dispatcher.call(_do)

    def export_all_versioning(self, output_dir: str) -> dict:
        """Export all forms, reports, modules, and macros to a directory structure."""
        if not self.is_connected():
            return {"success": False, "error": "Not connected to database", "exported": {}}

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
            forms = self.get_forms()
            forms_dir = os.path.join(output_dir, "forms")
            os.makedirs(forms_dir, exist_ok=True)
            for form in forms:
                try:
                    safe_name = safe_filename(form.name)
                    out_path = os.path.join(forms_dir, f"forms_{safe_name}.txt")
                    self._dispatcher.call(lambda p=out_path, n=form.name: self._dispatcher._access_app.SaveAsText(2, n, p))
                    exported["forms"].append(form.name)
                except Exception:
                    pass
        except Exception:
            pass

        # Export reports
        try:
            reports = self.get_reports()
            reports_dir = os.path.join(output_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            for report in reports:
                try:
                    safe_name = safe_filename(report.name)
                    out_path = os.path.join(reports_dir, f"reports_{safe_name}.txt")
                    self._dispatcher.call(lambda p=out_path, n=report.name: self._dispatcher._access_app.SaveAsText(4, n, p))
                    exported["reports"].append(report.name)
                except Exception:
                    pass
        except Exception:
            pass

        # Export VBA modules (no COM needed — data is already in mod.code)
        try:
            modules = self.get_modules()
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

        # Export macros (no COM needed — static text)
        try:
            macros = self.get_macros()
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

    # ========================================================================
    # SQL SCRIPT EXECUTION
    # ========================================================================

    def execute_sql_script(self, script_path: str) -> dict:
        """Execute a SQL script from a file path.

        Reads the file, strips SQL comments, splits by semicolons,
        and executes each statement via DAO.

        Args:
            script_path: Absolute path to the .sql file

        Returns:
            dict with success=True, statements_executed=N
            or success=False, error="...", statements_executed=N
        """
        if not os.path.exists(script_path):
            return {
                "success": False,
                "statements_executed": 0,
                "error": f"File not found: {script_path}",
            }

        if not self.is_connected():
            return {
                "success": False,
                "statements_executed": 0,
                "error": "Not connected",
            }

        def _do() -> dict:
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    raw_sql = f.read()
            except Exception as e:
                return {"success": False, "statements_executed": 0, "error": str(e)}

            sql = self._strip_sql_comments(raw_sql).strip()
            if not sql:
                return {"success": True, "statements_executed": 0}

            # Split by semicolons and filter empty statements
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            db = self._dispatcher._current_db
            executed = 0
            for stmt in statements:
                try:
                    db.Execute(stmt, DAO_DB_FAIL_ON_ERROR)
                    executed += 1
                except Exception as e:
                    return {
                        "success": False,
                        "statements_executed": executed,
                        "error": f"Error at statement {executed + 1}: {e}",
                    }

            return {"success": True, "statements_executed": executed}

        try:
            return self._dispatcher.call(_do)
        except Exception as e:
            return {"success": False, "statements_executed": 0, "error": str(e)}

    # ========================================================================
    # DATABASE FILE COPY
    # ========================================================================

    def copy_database(self, source: str, dest: str) -> bool:
        """Copy a database file using shutil.copy2.

        Args:
            source: Path to source .accdb/.mdb file
            dest: Path to destination file

        Returns:
            True if copy succeeded, False otherwise
        """
        try:
            shutil.copy2(source, dest)
            return True
        except Exception:
            return False
