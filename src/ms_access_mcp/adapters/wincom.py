import os
from typing import Optional
from .base import AccessAdapter
from ..models.database import TableInfo


class WinComAdapter(AccessAdapter):
    """COM-based adapter using pywin32 for full Access automation."""

    def __init__(self) -> None:
        self._access_app: Optional[object] = None
        self._current_db: Optional[object] = None
        self._db_path: Optional[str] = None

    def connect(self, db_path: str) -> bool:
        """Connect to an Access database via COM automation."""
        import win32com.client

        if not os.path.exists(db_path):
            return False

        try:
            self._access_app = win32com.client.Dispatch("Access.Application")
            self._access_app.OpenCurrentDatabase(db_path)
            self._current_db = self._access_app.CurrentDb()
            self._db_path = db_path
            return True
        except Exception:
            self._cleanup()
            return False

    def disconnect(self) -> None:
        """Disconnect from the Access database."""
        self._cleanup()

    def _cleanup(self) -> None:
        """Release COM objects."""
        if self._current_db is not None:
            self._current_db = None
        if self._access_app is not None:
            try:
                self._access_app.CloseCurrentDatabase()
            except Exception:
                pass
            self._access_app.Quit()
            self._access_app = None
        self._db_path = None

    def is_connected(self) -> bool:
        """Check if connected to a database."""
        return self._access_app is not None and self._current_db is not None

    def get_tables(self) -> list[TableInfo]:
        """Get all user tables from the connected database."""
        if not self.is_connected():
            return []

        tables: list[TableInfo] = []
        try:
            dao = self._access_app.DAo
            db = dao.DBEngine.OpenDatabase(self._db_path)
            for i in range(db.TableDefs.Count):
                tdef = db.TableDefs(i)
                # Skip system tables and temp tables
                if tdef.Name.startswith("MSys") or tdef.Name.startswith("~"):
                    continue
                # Skip linked tables and system objects
                if tdef.Attributes & 0x80000000:  # dbHiddenObject
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

                # Get record count if possible
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

        results: list[dict] = []
        try:
            rs = self._current_db.OpenRecordset(sql)
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

    def launch_access(self, visible: bool = False) -> None:
        """Launch Microsoft Access application."""
        import win32com.client

        if self._access_app is None:
            self._access_app = win32com.client.Dispatch("Access.Application")
        self._access_app.Visible = visible

    def close_access(self) -> None:
        """Close Microsoft Access application."""
        if self._access_app is not None:
            self._access_app.Quit()
            self._access_app = None
            self._current_db = None

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Set VBA code in a module."""
        if not self.is_connected():
            return False

        try:
            vbe = self._access_app.VBE
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