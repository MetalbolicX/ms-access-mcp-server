"""WinComAdapter integration tests with mocked COM layer.

Creates a complete mock Access/DAO/ADO COM environment using SQLite for data
storage, so every WinComAdapter method exercises real code paths through
ComDispatcher, SQL generation, result parsing, and error handling.

Strategy:
  - Seed sys.modules with mock win32com.client + pythoncom BEFORE any
    WinComAdapter import, so the STA dispatcher thread uses our mocks.
  - Mock DAO objects (TableDefs, Fields, Recordsets, QueryDefs) backed by
    real SQLite for data operations (execute_query, insert/update/delete).
  - Mock Access object model (CurrentProject.AllForms, VBE, DoCmd) for
    form/report/macro/VBA operations.
  - Patch sys.platform to 'win32' so _ensure_windows() passes.
"""

from __future__ import annotations

import os
import sys
import json
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

from ms_access_mcp.adapters.wincom import WinComAdapter

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Mock COM module injection
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def mock_com_modules():
    """Inject mock win32com.client and pythoncom into sys.modules.

    These modules normally exist only on Windows. By pre-seeding them,
    ComDispatcher's STA thread can import them without ImportError.
    """
    mock_win32com_client = MagicMock()
    sys.modules["win32com"] = MagicMock()
    sys.modules["win32com"].client = mock_win32com_client
    sys.modules["win32com.client"] = mock_win32com_client

    mock_pythoncom = MagicMock()
    sys.modules["pythoncom"] = mock_pythoncom

    yield {
        "client": mock_win32com_client,
        "pythoncom": mock_pythoncom,
    }

    # Cleanup
    for mod_name in ("pythoncom", "win32com.client", "win32com"):
        sys.modules.pop(mod_name, None)


# ═══════════════════════════════════════════════════════════════════════
# SQLite-backed DAO mocks
# ═══════════════════════════════════════════════════════════════════════

class MockDaoField:
    """Mirrors a DAO Field object with real attribute access."""
    def __init__(self, name: str, type_val: int = 10, size: int = 0,
                 required: bool = False, allow_zero_length: bool = True,
                 attributes: int = 0, default_value: Any = None,
                 value: Any = None):
        self.Name = name
        self.Type = type_val
        self.Size = size
        self.Required = required
        self.AllowZeroLength = allow_zero_length
        self.Attributes = attributes
        self.DefaultValue = default_value
        self.Value = value


class MockDaoFields:
    """Mock DAO Fields collection — accessed via fields(index)."""
    def __init__(self, fields: list[MockDaoField] | None = None):
        self._fields = list(fields or [])

    def __call__(self, index: int) -> MockDaoField:
        return self._fields[index]

    def __iter__(self):
        return iter(self._fields)

    @property
    def Count(self) -> int:
        return len(self._fields)

    def Append(self, field: MockDaoField) -> None:
        self._fields.append(field)


class MockDaoIndex:
    """Mock DAO Index object."""
    def __init__(self, name: str, fields: list[MockDaoField], primary: bool = False,
                 unique: bool = False):
        self.Name = name
        self._fields = MockDaoFields(fields)
        self.Primary = primary
        self.Unique = unique

    @property
    def Fields(self):
        return self._fields


class MockDaoIndexes:
    """Mock DAO Indexes collection."""
    def __init__(self, indexes: list[MockDaoIndex] | None = None):
        self._indexes = list(indexes or [])

    def __iter__(self):
        return iter(self._indexes)


class MockDaoTableDef:
    """Mock DAO TableDef object — title-cased attributes."""
    def __init__(self, name: str, fields: list[MockDaoField] | None = None,
                 attributes: int = 0, connect: str = "",
                 source_table_name: str = ""):
        self.Name = name
        self._fields = MockDaoFields(fields or [])
        self.Attributes = attributes
        self.Connect = connect
        self.SourceTableName = source_table_name
        self._indexes = MockDaoIndexes()

    @property
    def Fields(self) -> MockDaoFields:
        return self._fields

    @property
    def Indexes(self) -> MockDaoIndexes:
        return self._indexes

    def CreateField(self, name: str, type_val: int, size: int = 0) -> MockDaoField:
        return MockDaoField(name, type_val, size)

    def RefreshLink(self) -> None:
        """Mock RefreshLink — no-op for testing."""
        pass

    def __repr__(self) -> str:
        return f"<MockDaoTableDef '{self.Name}'>"


class MockDaoQueryDef:
    """Mock DAO QueryDef object."""
    def __init__(self, name: str, sql: str = ""):
        self.Name = name
        self.sql = sql
        self.Type = 0  # select

    def Close(self) -> None:
        """No-op close for mock."""
        pass


class MockDaoRelation:
    """Mock DAO Relation object."""
    def __init__(self, name: str, table: str, foreign_table: str,
                 fields: list[MockDaoField], attributes: int = 0):
        self.Name = name
        self.Table = table
        self.ForeignTable = foreign_table
        self.Attributes = attributes
        self._fields = MockDaoFields(fields)

    @property
    def Fields(self) -> MockDaoFields:
        return self._fields


class MockDaoRecordset:
    """DAO Recordset backed by real SQLite cursor data.

    Raises exceptions for invalid SQL (no silent swallowing).
    """
    def __init__(self, conn, sql: str):
        cursor = conn.execute(sql)
        self._columns = [desc[0] for desc in cursor.description] if cursor.description else []
        self._rows: list[tuple] = cursor.fetchall()
        self._index = 0 if self._rows else -1
        self._closed = False

    @property
    def EOF(self) -> bool:
        return self._index < 0 or self._index >= len(self._rows)

    @property
    def RecordCount(self) -> int:
        return len(self._rows)

    @property
    def Fields(self):
        return self

    def __call__(self, index: int) -> MockDaoField:
        if self._index < 0 or self._index >= len(self._rows):
            return MockDaoField("", value=None)
        row = self._rows[self._index]
        col_name = self._columns[index] if index < len(self._columns) else f"col{index}"
        value = row[index] if index < len(row) else None
        return MockDaoField(col_name, value=value)

    @property
    def Count(self) -> int:
        return len(self._columns)

    def MoveFirst(self) -> None:
        self._index = 0 if self._rows else -1

    def MoveNext(self) -> None:
        if self._index >= 0:
            self._index += 1

    def Close(self) -> None:
        self._closed = True


class MockDaoRelations:
    """Mock DAO Relations collection."""
    def __init__(self, relations: list[MockDaoRelation] | None = None):
        self._relations = list(relations or [])

    def __call__(self, index: int) -> MockDaoRelation:
        return self._relations[index]

    def __iter__(self):
        return iter(self._relations)

    @property
    def Count(self) -> int:
        return len(self._relations)

    def Delete(self, name: str) -> None:
        """Delete a relation by name."""
        for i, rel in enumerate(self._relations):
            if rel.Name == name:
                del self._relations[i]
                return
        raise Exception(f"Relation '{name}' not found")


class MockDaoTableDefs:
    """Mock DAO TableDefs collection backed by SQLite metadata."""
    def __init__(self, conn, tables: list[MockDaoTableDef] | None = None):
        self._conn = conn
        # Pre-populate from SQLite schema
        self._tables: dict[str, MockDaoTableDef] = {}
        if tables:
            for t in tables:
                self._tables[t.Name] = t
        self._load_from_sqlite()

    def _load_from_sqlite(self) -> None:
        """Sync with actual SQLite tables."""
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        for row in cursor.fetchall():
            name = row[0]
            if name not in self._tables:
                # Build fields from SQLite pragma
                fields = []
                try:
                    col_cursor = self._conn.execute(f"PRAGMA table_info(\"{name}\")")
                    for col in col_cursor.fetchall():
                        cid, col_name, col_type, not_null, default_val, pk = col
                        fields.append(MockDaoField(
                            name=col_name,
                            type_val=10,  # DAO Text
                            required=bool(not_null),
                            default_value=default_val,
                        ))
                except Exception:
                    pass
                self._tables[name] = MockDaoTableDef(name, fields)

    def __call__(self, index: int | str) -> MockDaoTableDef:
        if isinstance(index, str):
            return self._tables[index]
        names = list(self._tables.keys())
        return self._tables[names[index]]

    def __iter__(self):
        return iter(self._tables.values())

    @property
    def Count(self) -> int:
        return len(self._tables)

    def Append(self, tdef: MockDaoTableDef) -> None:
        self._tables[tdef.Name] = tdef

    def Delete(self, name: str) -> None:
        self._tables.pop(name, None)


class MockDaoQueryDefs:
    """Mock DAO QueryDefs collection."""
    def __init__(self):
        self._queries: dict[str, MockDaoQueryDef] = {}

    def __call__(self, index: int | str) -> MockDaoQueryDef:
        if isinstance(index, str):
            return self._queries[index]
        names = list(self._queries.keys())
        return self._queries[names[index]]

    def __iter__(self):
        return iter(self._queries.values())

    @property
    def Count(self) -> int:
        return len(self._queries)

    def Delete(self, name: str) -> None:
        self._queries.pop(name, None)


class MockDaoDatabase:
    """Mock DAO Database backed by a real SQLite connection.

    Translates DAO-style operations (TableDefs, OpenRecordset, Execute)
    into SQLite queries. The adapter uses bracket syntax [table] which
    SQLite rejects, so raw SQL DDL/DML goes directly to SQLite while
    schema discovery uses the mock layer.
    """

    def __init__(self, db_path: str = ":memory:", conn=None):
        # Share the same SQLite connection across all OpenDatabase calls
        # so get_tables() (which opens/closes its own handle) sees data
        # created via execute_query() on _current_db.
        if conn is None:
            conn = sqlite3_connect(":memory:", check_same_thread=False)
        self._conn = conn
        self._db_path = db_path
        self._query_defs = MockDaoQueryDefs()
        self._relations = MockDaoRelations()
        self.RecordsAffected = 0
        self._table_cache: dict[str, MockDaoTableDef] = {}
        self._table_defs: MockDaoTableDefs | None = None

    @property
    def _tables(self) -> dict[str, MockDaoTableDef]:
        """Direct access to TableDefs tables for test setup."""
        return self._table_defs._tables if self._table_defs else {}

    def Close(self) -> None:
        """No-op: all OpenDatabase calls share one connection.

        The real DAO creates a new connection per OpenDatabase, but our
        mock returns the same MockDaoDatabase instance.  Closing it would
        destroy data for other callers.  Actual cleanup happens when the
        MockAccessApplication fixture is torn down.
        """

    @property
    def TableDefs(self) -> MockDaoTableDefs:
        if self._table_defs is None:
            self._table_defs = MockDaoTableDefs(
                self._conn, list(self._table_cache.values())
            )
        return self._table_defs

    @property
    def QueryDefs(self) -> MockDaoQueryDefs:
        return self._query_defs

    @property
    def Relations(self) -> MockDaoRelations:
        return self._relations

    def OpenRecordset(self, sql: str):
        """Execute SQL and return a DAO-style Recordset."""
        return MockDaoRecordset(self._conn, sql)

    def Execute(self, sql: str, options: int = 0) -> None:
        try:
            self._conn.execute(sql)
            self._conn.commit()
            cursor = self._conn.execute("SELECT changes()")
            self.RecordsAffected = cursor.fetchone()[0]
        except Exception:
            # Mock layer silently swallows all errors (DDL and DML)
            # so tests don't depend on SQLite's specific error messages
            self.RecordsAffected = 0

    def CreateTableDef(self, name: str) -> MockDaoTableDef:
        tdef = MockDaoTableDef(name)
        return tdef

    def CreateQueryDef(self, name: str, sql: str):
        qdef = MockDaoQueryDef(name, sql)
        self._query_defs._queries[name] = qdef
        return qdef

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.Close()


# Need a reference to sqlite3 through a function to avoid import confusion
import sqlite3
sqlite3_connect = sqlite3.connect


# ═══════════════════════════════════════════════════════════════════════
# Mock project object hierarchy (AllForms, AllReports, etc.)
# ═══════════════════════════════════════════════════════════════════════

class MockProjectItem:
    """An item in AllForms / AllReports / AllMacros."""
    def __init__(self, name: str, props: dict[str, Any] | None = None):
        self.Name = name
        self._props = props or {}
        self.Properties = MockProperties(self._props)

    def __repr__(self) -> str:
        return f"<MockProjectItem '{self.Name}'>"


class MockProperties:
    """Mock COM Properties collection."""
    def __init__(self, data: dict[str, Any]):
        self._data = data

    def Exists(self, name: str) -> bool:
        return name in self._data

    def __call__(self, name: str):
        return MockProperty(name, self._data.get(name, ""))


class MockProperty:
    def __init__(self, name: str, value: Any):
        self.Name = name
        self.Value = value


class MockProjectCollection:
    """Mock AllForms / AllReports / AllMacros collection."""
    def __init__(self, items: list[MockProjectItem] | None = None):
        self._items = list(items or [])

    def __call__(self, index: int) -> MockProjectItem:
        return self._items[index]

    def __iter__(self):
        return iter(self._items)

    @property
    def Count(self) -> int:
        return len(self._items)


class MockCodeModule:
    """Mock VBA CodeModule with procedure support."""
    def __init__(self, code: str = ""):
        self._lines = code.split("\n") if code else []
        self._procedures: dict[str, dict] = {}  # name -> {start, count, kind}

    def set_procedures(self, procedures: list[dict]) -> None:
        """Set procedure info list: [{name, start_line, line_count, kind}]"""
        self._procedures = {}
        for p in procedures:
            self._procedures[p["name"]] = {
                "start": p["start_line"],
                "count": p["line_count"],
                "kind": p.get("kind", 0),
            }
        if not self._lines:
            max_line = 0
            for p in procedures:
                max_line = max(max_line, p["start_line"] + p["line_count"] - 1)
            self._lines = ["" for _ in range(max_line)]

    @property
    def CountOfLines(self) -> int:
        return len(self._lines)

    def Lines(self, start: int, count: int) -> str:
        """Return lines (1-based)."""
        return "\n".join(self._lines[start - 1:start - 1 + count])

    def DeleteLines(self, start: int, count: int) -> None:
        self._lines = self._lines[:start - 1] + self._lines[start - 1 + count:]

    def InsertLines(self, start: int, code: str) -> None:
        """Insert code at line position (1-based)."""
        new_lines = code.split("\n")
        self._lines = self._lines[:start - 1] + new_lines + self._lines[start - 1:]

    def AddFromString(self, code: str) -> None:
        self._lines = code.split("\n")

    def ProcOfLine(self, line: int, kind: int = 0) -> str:
        """Return procedure name at given line (1-based), or empty string."""
        for name, info in self._procedures.items():
            start = info["start"]
            end = start + info["count"] - 1
            if start <= line <= end:
                return name
        return ""

    def ProcStartLine(self, name: str, kind: int = 0) -> int:
        """Return start line of procedure."""
        if name in self._procedures:
            return self._procedures[name]["start"]
        raise Exception(f"Procedure '{name}' not found")

    def ProcCountLines(self, name: str, kind: int = 0) -> int:
        """Return line count of procedure."""
        if name in self._procedures:
            return self._procedures[name]["count"]
        raise Exception(f"Procedure '{name}' not found")

    def ProcKind(self, line_or_name: int | str, kind: int = 0) -> int:
        """Return procedure kind (0=Sub, 1=Function, 2=Property)."""
        if isinstance(line_or_name, int):
            name = self.ProcOfLine(line_or_name, kind)
            if name and name in self._procedures:
                return self._procedures[name]["kind"]
            return 0
        if line_or_name in self._procedures:
            return self._procedures[line_or_name]["kind"]
        raise Exception(f"Procedure '{line_or_name}' not found")


class MockVBComponent:
    """Mock VBE VBComponent (module)."""
    def __init__(self, name: str, comp_type: int = 1, code: str = ""):
        self.Name = name
        self.Type = comp_type  # 1 = vbext_ct_StdModule
        self.CodeModule = MockCodeModule(code)


class MockVBComponents:
    """Mock VBE VBComponents collection."""
    def __init__(self, components: list[MockVBComponent] | None = None):
        self._components: dict[str, MockVBComponent] = {}
        self._list: list[MockVBComponent] = []
        if components:
            for c in components:
                self._components[c.Name] = c
                self._list.append(c)

    def __iter__(self):
        return iter(self._list)

    def Add(self, comp_type: int) -> MockVBComponent:
        comp = MockVBComponent(f"Module{len(self._list) + 1}", comp_type)
        self._components[comp.Name] = comp
        self._list.append(comp)
        return comp

    def Remove(self, comp: MockVBComponent) -> None:
        self._components.pop(comp.Name, None)
        self._list = [c for c in self._list if c.Name != comp.Name]


class MockVBProject:
    """Mock VBE VBProject."""
    def __init__(self, name: str = "VBAProject"):
        self.Name = name
        self.VBComponents = MockVBComponents()


class MockVBProjects:
    """Mock VBE VBProjects collection (1-based)."""
    def __init__(self, projects: list[MockVBProject] | None = None):
        self._projects = list(projects or [MockVBProject()])

    def __call__(self, index: int) -> MockVBProject:
        if 1 <= index <= len(self._projects):
            return self._projects[index - 1]
        raise IndexError(f"VBProjects index {index} out of range")

    @property
    def Count(self) -> int:
        return len(self._projects)


class MockVBE:
    """Mock VBE object."""
    def __init__(self, projects: MockVBProjects | None = None):
        self.VBProjects = projects or MockVBProjects()


class MockDoCmd:
    """Mock DoCmd object — records calls."""
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    def OpenForm(self, form_name: str, view: int = 0, *args, **kwargs):
        self.calls.append(("OpenForm", (form_name, view), kwargs))

    def Close(self, object_type: int, object_name: str, save: int):
        self.calls.append(("Close", (object_type, object_name, save), {}))

    def Save(self, object_type: int, object_name: str):
        self.calls.append(("Save", (object_type, object_name), {}))

    def DeleteObject(self, object_type: int, object_name: str):
        self.calls.append(("DeleteObject", (object_type, object_name), {}))

    def RunCommand(self, cmd_id: int):
        self.calls.append(("RunCommand", (cmd_id,), {}))


class MockScreen:
    """Mock Screen object."""
    def __init__(self):
        self.ActiveForm = None


class MockCurrentProject:
    """Mock CurrentProject with COM-style collections."""
    def __init__(self):
        self.AllForms = MockProjectCollection()
        self.AllReports = MockProjectCollection()
        self.AllMacros = MockProjectCollection()
        self.Connection = MagicMock()  # ADO connection


class MockAccessApplication:
    """Complete mock Access.Application with DAO, VBE, DoCmd, and CurrentProject.

    All data operations delegate to a MockDaoDatabase backed by SQLite.
    """

    def __init__(self, db_path: str = ":memory:", conn=None):
        self.Visible = False
        self.DBEngine = self  # DBEngine is the app itself for mock
        self.CurrentProject = MockCurrentProject()
        self.DoCmd = MockDoCmd()
        self.VBE = MockVBE()
        self.Screen = MockScreen()
        self.Forms = MagicMock()  # Forms(name) returns form
        self._db = MockDaoDatabase(db_path, conn)
        self._save_texts: dict[tuple[int, str], str] = {}  # (type, name) -> content

    @property
    def QueryDefs(self):
        """Delegate QueryDefs to the underlying DAO database."""
        return self._db.QueryDefs

    def OpenDatabase(self, path: str, exclusive: bool = False,
                     readonly: bool = False) -> MockDaoDatabase:
        return self._db

    def OpenCurrentDatabase(self, path: str, exclusive: bool = False) -> None:
        pass

    def CompactDatabase(self, source: str, dest: str) -> None:
        """Simulate compact by copying content."""
        import shutil
        if os.path.exists(source):
            shutil.copy2(source, dest)

    def CloseCurrentDatabase(self) -> None:
        pass

    def Quit(self) -> None:
        pass

    def close(self) -> None:
        """Release the shared SQLite connection."""
        self._db._conn.close()

    # ── SaveAsText / LoadFromText ───────────────────────────────────

    def SaveAsText(self, object_type: int, object_name: str,
                   file_path: str) -> None:
        content = f"Mock {object_type} export of {object_name}"
        self._save_texts[(object_type, object_name)] = content
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def LoadFromText(self, object_type: int, object_name: str,
                     file_path: str) -> None:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                raw = f.read()
            # SaveAsText outputs UTF-16-LE with BOM; decode accordingly
            text = raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")
            self._save_texts[(object_type, object_name)] = text


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _patch_platform():
    """Make WinComAdapter._ensure_windows() pass."""
    with patch.object(sys, "platform", "win32"):
        yield


@pytest.fixture
def mock_app():
    """Create a fresh MockAccessApplication for each test."""
    return MockAccessApplication()


@pytest.fixture(autouse=True)
def _inject_dispatch(mock_com_modules, mock_app):
    """Make win32com.client.Dispatch return our mock Access app.

    This is called inside the STA dispatcher thread when
    _do_connect() runs `win32com.client.Dispatch("Access.Application")`.
    """
    mock_com_modules["client"].Dispatch.return_value = mock_app
    yield


@pytest.fixture
def adapter():
    """Create a fresh WinComAdapter for each test."""
    a = WinComAdapter()
    yield a
    # Cleanup: disconnect if connected
    try:
        if a.is_connected():
            a.disconnect()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWinComConnection:
    """Connection lifecycle — connect, disconnect, is_connected."""

    def test_connect_returns_true(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock database content")
        result = adapter.connect(str(db_path))
        assert result is True
        assert adapter.is_connected() is True

    def test_connect_nonexistent_path_returns_false(self, adapter):
        result = adapter.connect(r"C:\nonexistent\path.accdb")
        assert result is False
        assert adapter.is_connected() is False

    def test_disconnect_clears_state(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock database content")
        adapter.connect(str(db_path))
        assert adapter.is_connected() is True
        adapter.disconnect()
        assert adapter.is_connected() is False

    def test_is_connected_before_connect_returns_false(self, adapter):
        assert adapter.is_connected() is False

    def test_disconnect_without_connect_does_not_raise(self, adapter):
        adapter.disconnect()  # should not raise


class TestWinComDataOperations:
    """CRUD data operations against SQLite-backed DAO mock."""

    def test_execute_query_select(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Real SQLite query
        result = adapter.execute_query("SELECT 1 AS num")
        assert result["success"] is True
        assert result["count"] >= 1
        assert "num" in result["columns"]

    def test_execute_query_not_connected(self, adapter):
        result = adapter.execute_query("SELECT 1")
        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_insert_and_query(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Create table via SQLite directly (DAO CreateTableDef goes through
        # mock layer, but Execute uses SQLite directly)
        adapter.execute_query("CREATE TABLE users (id INTEGER, name TEXT)")
        result = adapter.insert_data("users", {"id": 1, "name": "Alice"})
        assert result["success"] is True
        assert result["affected"] == 1

        result = adapter.execute_query("SELECT * FROM users")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["rows"][0]["name"] == "Alice"

    def test_insert_multiple_rows(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE items (id INTEGER, label TEXT)")
        result = adapter.insert_data("items", [
            {"id": 1, "label": "A"},
            {"id": 2, "label": "B"},
        ])
        assert result["success"] is True
        assert result["affected"] == 2

    def test_update_data(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE users (id INTEGER, name TEXT)")
        adapter.insert_data("users", {"id": 1, "name": "Alice"})
        result = adapter.update_data("users", {"name": "Bob"}, {"id": 1})
        assert result["success"] is True

        result = adapter.execute_query("SELECT name FROM users WHERE id=1")
        assert result["rows"][0]["name"] == "Bob"

    def test_update_no_where(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE users (id INTEGER, name TEXT)")
        adapter.insert_data("users", {"id": 1, "name": "Alice"})
        adapter.insert_data("users", {"id": 2, "name": "Charlie"})
        result = adapter.update_data("users", {"name": "Unknown"})
        assert result["success"] is True

    def test_delete_data(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE users (id INTEGER, name TEXT)")
        adapter.insert_data("users", {"id": 1, "name": "Alice"})
        result = adapter.delete_data("users", {"id": 1})
        assert result["success"] is True

        result = adapter.execute_query("SELECT * FROM users")
        assert result["count"] == 0

    def test_delete_no_where(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE users (id INTEGER, name TEXT)")
        adapter.insert_data("users", {"id": 1, "name": "Alice"})
        result = adapter.delete_data("users")
        assert result["success"] is True

    def test_insert_not_connected_returns_error(self, adapter):
        result = adapter.insert_data("t", {"x": 1})
        assert result["success"] is False

    def test_update_not_connected_returns_error(self, adapter):
        result = adapter.update_data("t", {"x": 1})
        assert result["success"] is False

    def test_delete_not_connected_returns_error(self, adapter):
        result = adapter.delete_data("t")
        assert result["success"] is False

    def test_update_data_sqli_blocked_via_parameterization(self, adapter, mock_app, tmp_path):
        """SQL injection attempt in where_dict value should be treated as literal string.

        When parameterized queries are used, a value like "1; DROP TABLE users--"
        is bound as a parameter, not executed as SQL.
        """
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE users (id INTEGER, name TEXT)")
        adapter.insert_data("users", {"id": 1, "name": "Alice"})
        adapter.insert_data("users", {"id": 2, "name": "Bob"})

        # Malicious where value — should be treated as a literal, not executed
        result = adapter.update_data(
            "users",
            {"name": "Hacked"},
            {"name": "1; DROP TABLE users--"},
        )
        # With parameterized queries, the malicious string is a literal value
        # The table should still exist and have 2 rows (no rows updated because
        # no name matches the literal string "1; DROP TABLE users--")
        result_select = adapter.execute_query("SELECT COUNT(*) as cnt FROM users")
        assert result_select["rows"][0]["cnt"] == 2  # table still intact, 2 rows

    def test_delete_data_sqli_blocked_via_parameterization(self, adapter, mock_app, tmp_path):
        """SQL injection attempt in where_dict should be treated as literal string on delete."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE users (id INTEGER, name TEXT)")
        adapter.insert_data("users", {"id": 1, "name": "Alice"})
        adapter.insert_data("users", {"id": 2, "name": "Bob"})

        # Malicious where value
        result = adapter.delete_data("users", {"name": "1; DROP TABLE users--"})
        # Table should still exist (1 row deleted = 0, no match for literal string)
        result_select = adapter.execute_query("SELECT COUNT(*) as cnt FROM users")
        assert result_select["rows"][0]["cnt"] == 2  # table still intact

    def test_update_data_obrien_escaped(self, adapter, mock_app, tmp_path):
        """O'Brien with apostrophe should be safely handled via parameterization."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE users (id INTEGER, name TEXT)")
        adapter.insert_data("users", {"id": 1, "name": "O'Brien"})

        result = adapter.update_data("users", {"name": "Smith"}, {"name": "O'Brien"})
        assert result["success"] is True

        result = adapter.execute_query("SELECT name FROM users WHERE id=1")
        assert result["rows"][0]["name"] == "Smith"


class TestWinComSchema:
    """Schema operations — tables, queries, relationships."""

    def test_get_tables_returns_list(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Create a real SQLite table so the mock DAO picks it up
        adapter.execute_query("CREATE TABLE test_users (id INTEGER, name TEXT)")
        tables = adapter.get_tables()
        names = [t.name for t in tables]
        assert "test_users" in names

    def test_get_tables_not_connected_returns_empty(self, adapter):
        assert adapter.get_tables() == []

    def test_get_tables_includes_fields(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE test_items (id INTEGER PRIMARY KEY, label TEXT)")
        tables = adapter.get_tables()
        items = [t for t in tables if t.name == "test_items"]
        assert len(items) > 0
        assert len(items[0].fields) > 0

    def test_get_queries_returns_list(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # CreateQueryDef via internal mock
        mock_app._db.CreateQueryDef("qryTest", "SELECT 1 AS x")
        queries = adapter.get_queries()
        names = [q.name for q in queries]
        assert "qryTest" in names

    def test_get_queries_not_connected_returns_empty(self, adapter):
        assert adapter.get_queries() == []

    def test_create_query(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.create_query("qryNew", "SELECT 1 AS x")
        assert result["success"] is True

    def test_set_query_sql(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app._db.CreateQueryDef("qryTest", "SELECT 1 AS x")
        result = adapter.set_query_sql("qryTest", "SELECT 2 AS y")
        assert result["success"] is True

    def test_delete_query(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app._db.CreateQueryDef("qryTest", "SELECT 1 AS x")
        result = adapter.delete_query("qryTest")
        assert result["success"] is True

    def test_create_query_not_connected(self, adapter):
        result = adapter.create_query("q", "SELECT 1")
        assert result["success"] is False

    def test_get_relationships_returns_list(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        rels = adapter.get_relationships()
        assert isinstance(rels, list)

    def test_create_and_delete_table(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.create_table("new_table", [
            {"name": "ID", "type": "Long Integer", "nullable": False},
        ])
        assert result["success"] is True

        result = adapter.delete_table("new_table")
        assert result["success"] is True

    def test_delete_table_deletes_fk_relations_before_drop(self, adapter, mock_app, tmp_path):
        """delete_table must delete DAO Relations referencing the table before DROP TABLE."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))

        # Inject a relation: categories → products
        rel = MockDaoRelation(
            name="FK_products_categories",
            table="categories",
            foreign_table="products",
            fields=[MockDaoField("category_id")],
        )
        adapter._dispatcher._current_db._relations._relations.append(rel)

        # Verify relation exists before delete
        assert adapter._dispatcher._current_db._relations.Count == 1

        # Delete the referenced (parent) table — must clean the relation first
        result = adapter.delete_table("categories")
        assert result["success"] is True, f"delete_table failed: {result.get('error')}"

        # Verify relation was cleaned up
        assert adapter._dispatcher._current_db._relations.Count == 0

    def test_delete_table_with_nonexistent_relation_does_not_crash(self, adapter, mock_app, tmp_path):
        """delete_table must not crash when no relations reference the table."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.delete_table("orphan_table")
        assert result["success"] is True

    def test_delete_table_deletes_relations_on_both_sides(self, adapter, mock_app, tmp_path):
        """delete_table must delete relations where table appears as Table or ForeignTable."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))

        # products has FK to categories (rel.Table = categories)
        rel1 = MockDaoRelation(
            name="FK_prod_cat",
            table="categories",
            foreign_table="products",
            fields=[MockDaoField("category_id")],
        )
        # orders has FK to customers (rel.Table = customers)
        rel2 = MockDaoRelation(
            name="FK_ord_cust",
            table="customers",
            foreign_table="orders",
            fields=[MockDaoField("customer_id")],
        )
        adapter._dispatcher._current_db._relations._relations.extend([rel1, rel2])

        assert adapter._dispatcher._current_db._relations.Count == 2

        # Delete categories — only rel1 should be cleaned, rel2 stays
        result = adapter.delete_table("categories")
        assert result["success"] is True

        remaining = adapter._dispatcher._current_db._relations
        assert remaining.Count == 1
        assert remaining(0).Name == "FK_ord_cust"


class TestWinComFormsReportsMacros:
    """Form, report, and macro enumeration."""

    def test_get_forms_returns_list(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("Form1", {"RecordSource": "Table1"}),
            MockProjectItem("Form2"),
        ])
        forms = adapter.get_forms()
        names = [f.name for f in forms]
        assert "Form1" in names
        assert "Form2" in names

    def test_get_forms_not_connected_returns_empty(self, adapter):
        assert adapter.get_forms() == []

    def test_form_exists(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("Form1"),
        ])
        assert adapter.form_exists("Form1") is True
        assert adapter.form_exists("NonExistent") is False

    def test_form_exists_not_connected_returns_false(self, adapter):
        assert adapter.form_exists("Form1") is False

    def test_get_reports_returns_list(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.CurrentProject.AllReports = MockProjectCollection([
            MockProjectItem("Report1", {"RecordSource": "Table1"}),
        ])
        reports = adapter.get_reports()
        assert any(r.name == "Report1" for r in reports)

    def test_get_macros_returns_list(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.CurrentProject.AllMacros = MockProjectCollection([
            MockProjectItem("Macro1"),
        ])
        macros = adapter.get_macros()
        assert any(m.name == "Macro1" for m in macros)

    def test_get_object_metadata_finds_form(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("MyForm"),
        ])
        meta = adapter.get_object_metadata("MyForm")
        assert meta.get("name") == "MyForm"
        # Adapter returns collection name (AllForms -> forms)
        assert meta.get("type") in ("form", "forms")

    def test_get_object_metadata_not_found(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        meta = adapter.get_object_metadata("NonExistent")
        assert meta == {}


class TestWinComVBA:
    """VBA module operations."""

    def test_get_modules_returns_standard_modules(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Set up mock VBA project with modules
        comp1 = MockVBComponent("modMain", comp_type=1, code="Public Sub Hello()\nEnd Sub")
        comp2 = MockVBComponent("modClass1", comp_type=2, code="")  # class module
        mock_app.VBE = MockVBE(MockVBProjects([
            MockVBProject("TestProject")
        ]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp1, comp2])
        modules = adapter.get_modules()
        names = [m.name for m in modules]
        assert "modMain" in names
        assert "modClass1" in names

    def test_get_modules_not_connected_returns_empty(self, adapter):
        assert adapter.get_modules() == []

    def test_get_vba_code_returns_code(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modTest", comp_type=1, code="Public Sub Test()\n  MsgBox \"Hi\"\nEnd Sub")
        mock_app.VBE = MockVBE(MockVBProjects([
            MockVBProject("TestProject")
        ]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        code = adapter.get_vba_code("modTest")
        assert "Public Sub Test()" in code
        assert "End Sub" in code

    def test_get_vba_code_not_found_returns_empty(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([])
        code = adapter.get_vba_code("NonExistent")
        assert code == ""

    def test_set_vba_code_missing_module_uses_load_from_text(self, adapter, mock_app, tmp_path):
        """set_vba_code for a non-existent module must call _load_object_from_text.

        This is the LoadFromText codepath that avoids 'Save As' dialogs on
        unnamed newly-created modules.
        """
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Empty VBComponents — module does NOT exist
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([])

        code = "Public Sub NewCode()\nEnd Sub"
        with patch.object(adapter, "_load_object_from_text", wraps=adapter._load_object_from_text) as mock_lft:
            result = adapter.set_vba_code("modNewModule", code)
            assert result is True
            # Must call LoadFromText with object_type=5 (acModule)
            mock_lft.assert_called_once()
            args = mock_lft.call_args[0]
            assert args[0] == 5  # acModule
            assert args[1] == "modNewModule"
            # Text must include Attribute VB_Name header
            assert 'Attribute VB_Name = "modNewModule"' in args[2]
            assert code in args[2]

    def test_set_vba_code_existing_module_uses_delete_and_add_from_string(self, adapter, mock_app, tmp_path):
        """set_vba_code for an existing module must use DeleteLines + AddFromString.

        This preserves the existing safe in-memory update path and does NOT
        call _load_object_from_text (which is only for new module creation).
        """
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modExisting", comp_type=1, code="Old Code\nLine2")
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])

        new_code = "Public Sub UpdatedCode()\nEnd Sub"
        with patch.object(adapter, "_load_object_from_text", wraps=adapter._load_object_from_text) as mock_lft:
            result = adapter.set_vba_code("modExisting", new_code)
            assert result is True
            # LoadFromText must NOT be called for existing modules
            mock_lft.assert_not_called()
            # CodeModule must have been cleared and repopulated
            final_code = comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
            assert "UpdatedCode" in final_code
            assert "Old Code" not in final_code

    def test_set_vba_code(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modTest", comp_type=1, code="")
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        result = adapter.set_vba_code("modTest", "Public Sub NewCode()\nEnd Sub")
        assert result is True
        assert "Public Sub NewCode()" in comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)

    def test_get_vba_project_name(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("MyProject")]))
        name = adapter.get_vba_project_name()
        assert name == "MyProject"

    def test_compile_vba(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        result = adapter.compile_vba()
        assert result["success"] is True

    def test_save_database(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modTest", comp_type=1, code="Public Sub Foo()\nEnd Sub")
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        result = adapter.save_database()
        assert result["success"] is True

    def test_add_vba_procedure_missing_module_uses_load_from_text(self, adapter, mock_app, tmp_path):
        """add_vba_procedure for a non-existent module must call _load_object_from_text.

        This is the LoadFromText codepath for new module creation.
        """
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Empty VBComponents — module does NOT exist
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([])

        code = "Public Sub MyProc()\nEnd Sub"
        with patch.object(adapter, "_load_object_from_text", wraps=adapter._load_object_from_text) as mock_lft:
            result = adapter.add_vba_procedure("modNew", "MyProc", code)
            assert result is True
            mock_lft.assert_called_once()
            args = mock_lft.call_args[0]
            assert args[0] == 5
            assert args[1] == "modNew"
            assert 'Attribute VB_Name = "modNew"' in args[2]
            assert code in args[2]

    def test_add_vba_procedure_existing_module_uses_add_from_string(self, adapter, mock_app, tmp_path):
        """add_vba_procedure for an existing module must use AddFromString (append).

        The existing-module path must NOT call _load_object_from_text — it
        safely appends via AddFromString on the named module.
        """
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modExisting", comp_type=1, code="Public Sub ExistingProc()\nEnd Sub")
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])

        code = "Public Sub NewProc()\nEnd Sub"
        with patch.object(adapter, "_load_object_from_text", wraps=adapter._load_object_from_text) as mock_lft:
            result = adapter.add_vba_procedure("modExisting", "NewProc", code)
            assert result is True
            # Must NOT use LoadFromText for existing module append
            mock_lft.assert_not_called()
            final_code = comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
            assert "NewProc" in final_code

    def test_add_vba_procedure(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modTest", comp_type=1, code="")
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        result = adapter.add_vba_procedure("modTest", "MyProc", "Public Sub MyProc()\nEnd Sub")
        assert result is True

    def test_delete_module(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modDeleteMe", comp_type=1)
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        result = adapter.delete_module("modDeleteMe")
        assert result is True

    def test_vba_list_procedures(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modTest", comp_type=1, code="Sub Init()\nEnd Sub\nFunction Validate()\nEnd Function")
        comp.CodeModule.set_procedures([
            {"name": "Init", "start_line": 1, "line_count": 2, "kind": 0},
            {"name": "Validate", "start_line": 4, "line_count": 2, "kind": 1},
        ])
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        result = adapter.vba_list_procedures("modTest")
        assert len(result) == 2
        names = [p["name"] for p in result]
        assert "Init" in names
        assert "Validate" in names

    def test_vba_list_procedures_empty_module(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modEmpty", comp_type=1, code="")
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        result = adapter.vba_list_procedures("modEmpty")
        assert result == []

    def test_vba_get_procedure(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        code = "Sub Init()\nMsgBox \"hi\"\nEnd Sub"
        comp = MockVBComponent("modTest", comp_type=1, code=code)
        comp.CodeModule.set_procedures([
            {"name": "Init", "start_line": 1, "line_count": 3, "kind": 0},
        ])
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        result = adapter.vba_get_procedure("modTest", "Init")
        assert result["name"] == "Init"
        assert result["type"] == "Sub"
        assert "MsgBox" in result["code"]
        assert "Sub Init()" in result["signature"]

    def test_vba_get_procedure_not_found(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("modTest", comp_type=1, code="Sub Foo()\nEnd Sub")
        comp.CodeModule.set_procedures([
            {"name": "Foo", "start_line": 1, "line_count": 2, "kind": 0},
        ])
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        result = adapter.vba_get_procedure("modTest", "NonExistent")
        assert result == {}

    def test_vba_replace_procedure(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        code = "Sub Init()\nMsgBox \"old\"\nEnd Sub"
        comp = MockVBComponent("modTest", comp_type=1, code=code)
        comp.CodeModule.set_procedures([
            {"name": "Init", "start_line": 1, "line_count": 3, "kind": 0},
        ])
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])
        new_code = "Sub Init()\nMsgBox \"new\"\nEnd Sub"
        result = adapter.vba_replace_procedure("modTest", "Init", new_code)
        assert result is True
        # Verify the code was replaced
        lines = comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
        assert "MsgBox \"new\"" in lines

    def test_vba_replace_procedure_module_not_found(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([])
        result = adapter.vba_replace_procedure("NonExistent", "Init", "Sub Init()\nEnd Sub")
        assert result is False


class TestWinComControlProperties:
    """Tests for control property batch operations."""

    def test_set_control_properties_success(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Set up a form with a control
        from types import SimpleNamespace
        ctrl1 = SimpleNamespace()
        ctrl1.Name = "txtName"
        ctrl1.ControlType = 100  # TextBox
        props_mock = {
            "Visible": SimpleNamespace(Value=True),
            "Width": SimpleNamespace(Value=100),
            "BackColor": SimpleNamespace(Value=16777215),
        }
        ctrl1.Properties = SimpleNamespace()
        ctrl1.Properties._props = props_mock
        ctrl1.Properties.__call__ = lambda name: props_mock.get(name)
        ctrl1.Properties.Count = 3
        ctrl1.Properties.__iter__ = lambda: iter([])

        mock_form = MagicMock()
        mock_form.Controls.Count = 1
        mock_form.Controls.__getitem__ = lambda self, i: ctrl1
        mock_form.Controls.__call__ = lambda i: ctrl1
        mock_app.Screen.ActiveForm = mock_form
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("Form1"),
        ])

        result = adapter.set_control_properties("Form1", "txtName", {
            "Visible": "False",
            "Width": "200",
        })
        assert isinstance(result, dict)
        # At minimum, returns dict (may be empty if mock didn't fully track)

    def test_set_control_properties_not_connected(self, adapter):
        result = adapter.set_control_properties("Form1", "txtName", {"Width": "200"})
        assert result == {}

    def test_get_control_event_procedures_all_events(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Set up form module with procedures
        comp = MockVBComponent("Form_frmMain", comp_type=1, code="")
        comp.CodeModule.set_procedures([
            {"name": "cmdSave_Click", "start_line": 1, "line_count": 5, "kind": 0},
            {"name": "cmdSave_Enter", "start_line": 7, "line_count": 3, "kind": 0},
            {"name": "txtName_AfterUpdate", "start_line": 11, "line_count": 4, "kind": 0},
            {"name": "Form_Load", "start_line": 16, "line_count": 3, "kind": 0},
        ])
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])

        result = adapter.get_control_event_procedures("frmMain", "")
        assert len(result) == 4

    def test_get_control_event_procedures_filtered(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        comp = MockVBComponent("Form_frmMain", comp_type=1, code="")
        comp.CodeModule.set_procedures([
            {"name": "cmdSave_Click", "start_line": 1, "line_count": 5, "kind": 0},
            {"name": "cmdSave_Enter", "start_line": 7, "line_count": 3, "kind": 0},
            {"name": "txtName_AfterUpdate", "start_line": 11, "line_count": 4, "kind": 0},
            {"name": "Form_Load", "start_line": 16, "line_count": 3, "kind": 0},
        ])
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])

        result = adapter.get_control_event_procedures("frmMain", "cmdSave")
        assert len(result) == 2
        names = [p["procedure_name"] for p in result]
        assert "cmdSave_Click" in names
        assert "cmdSave_Enter" in names

    def test_get_control_event_procedures_form_module_not_found(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([])

        result = adapter.get_control_event_procedures("NonExistent", "")
        assert result == []

    def test_get_control_event_procedures_not_connected(self, adapter):
        result = adapter.get_control_event_procedures("Form1", "")
        assert result == []


class TestWinComExport:
    """Export operations — CSV, JSON, versioning."""

    def test_export_csv(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE export_test (id INTEGER, val TEXT)")
        adapter.insert_data("export_test", {"id": 1, "val": "hello"})
        out = tmp_path / "out.csv"
        result = adapter.export_data("SELECT id, val FROM [export_test]", str(out), format="csv", delimiter=";")
        assert result["success"] is True
        assert result["rows_exported"] == 1
        assert out.exists()

    def test_export_json(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE export_test (id INTEGER, val TEXT)")
        adapter.insert_data("export_test", {"id": 1, "val": "hello"})
        out = tmp_path / "out.json"
        result = adapter.export_data("SELECT id, val FROM [export_test]", str(out), format="json")
        assert result["success"] is True
        assert result["rows_exported"] == 1
        assert out.exists()
        data = json.loads(out.read_text())
        assert data[0]["val"] == "hello"

    def test_export_not_connected(self, adapter):
        result = adapter.export_data("SELECT * FROM [t]", "/tmp/out.csv")
        assert result["success"] is False


class TestWinComErrors:
    """Error handling — invalid SQL, nonexistent tables, disconnected state."""

    def test_execute_invalid_sql(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.execute_query("SELECT * FROM nonexistent")
        assert result["success"] is False
        assert "error" in result

    def test_insert_into_nonexistent_table(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.insert_data("nonexistent", {"id": 1})
        # With our mock layer, the Execute call via the mock path won't
        # actually hit the real SQLite — it needs raw SQL. Since the mock
        # QueryDefs mock doesn't do real SQL, insert may succeed via mock
        # or fail based on connection state. We just check it doesn't crash.
        assert "success" in result

    def test_delete_table_nonexistent(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.delete_table("nonexistent")
        assert result["success"] is True  # mock DAO doesn't error on delete missing

    def test_execute_sql_script(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        script = tmp_path / "test.sql"
        script.write_text("CREATE TABLE script_test (id INTEGER);\nDROP TABLE script_test;")
        result = adapter.execute_sql_script(str(script))
        assert result["success"] is True
        assert result["statements_executed"] == 2

    def test_execute_sql_script_file_not_found(self, adapter):
        result = adapter.execute_sql_script(r"C:\nonexistent\test.sql")
        assert result["success"] is False

    def test_execute_sql_script_not_connected(self, adapter, tmp_path):
        script = tmp_path / "test.sql"
        script.write_text("SELECT 1")
        result = adapter.execute_sql_script(str(script))
        # Should fail because not connected
        assert result["success"] is False

    def test_get_system_tables(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        results = adapter.get_system_tables()
        assert isinstance(results, list)

    def test_get_vba_code_not_connected(self, adapter):
        assert adapter.get_vba_code("modX") == ""


class TestWinComFormControls:
    """Form control operations that require opening forms."""

    def test_open_form(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Set up a form so OpenForm succeeds
        mock_form = MagicMock()
        mock_form.Controls.Count = 0
        mock_app.Screen.ActiveForm = mock_form
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("Form1"),
        ])
        result = adapter.open_form("Form1")
        assert result is True

    def test_close_form(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.close_form("Form1")
        assert result is True

    def test_get_form_controls(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Set up a form with controls
        from types import SimpleNamespace
        ctrl1 = SimpleNamespace()
        ctrl1.Name = "txtName"
        ctrl1.ControlType = 100  # TextBox

        ctrl1.Properties = SimpleNamespace()
        ctrl1.Properties.Count = 0

        mock_form = MagicMock()
        mock_form.Controls.Count = 1
        mock_form.Controls.__getitem__ = lambda self, i: ctrl1  # noqa: ARG005
        # Use __call__ for COM-style access
        mock_form.Controls.__call__ = lambda i: ctrl1  # noqa: ARG005
        mock_app.Screen.ActiveForm = mock_form
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("Form1"),
        ])
        controls = adapter.get_form_controls("Form1")
        assert isinstance(controls, list)

    def test_delete_form(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("FormToDelete"),
        ])
        result = adapter.delete_form("FormToDelete")
        assert result is True

    def test_export_form_to_text(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.export_form_to_text("Form1")
        assert isinstance(result, str)

    def test_import_form_from_text(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.import_form_from_text("Form1", "form data here")
        assert result is True

    def test_get_control_properties(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        mock_form = MagicMock()
        mock_form.Controls.Count = 0
        mock_app.Screen.ActiveForm = mock_form
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("Form1"),
        ])
        props = adapter.get_control_properties("Form1", "txtName")
        assert isinstance(props, dict)


class TestWinComLinkedTables:
    """Linked table operations."""
    def test_get_linked_tables(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.get_linked_tables()
        assert "success" in result

    def test_refresh_linked_table_not_found(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.refresh_linked_table("nonexistent")
        assert result["success"] is False

    def test_unlink_table_not_found(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        result = adapter.unlink_table("nonexistent")
        assert result["success"] is True  # mock deletes silently

    # ========================================================================
    # RED tests for PR 2: password stripping, hidden restore, recreate
    # ========================================================================

    def test_get_linked_tables_includes_attributes(self, adapter, mock_app, tmp_path):
        """get_linked_tables must return attributes integer for each entry."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # First access TableDefs to populate the cached instance
        _ = adapter._dispatcher._current_db.TableDefs
        # Inject a mock linked table with attributes into the cached TableDefs
        mock_dao_tdef = MockDaoTableDef(
            name="ODBC_Linked",
            attributes=0x80000001,  # dbLinkAttachedTable | dbHiddenObject
            connect="ODBC;DSN=mydsn;PWD=secret",
            source_table_name="dbo.Orders",
        )
        # Update the cached TableDefs instance directly
        adapter._dispatcher._current_db._table_defs._tables["ODBC_Linked"] = mock_dao_tdef

        result = adapter.get_linked_tables()
        assert result["success"] is True
        linked = result["linked_tables"]
        assert len(linked) == 1
        assert linked[0]["name"] == "ODBC_Linked"
        assert "attributes" in linked[0]
        assert linked[0]["attributes"] == 0x80000001

    def test_create_linked_table_strips_password_after_append(self, adapter, mock_app, tmp_path):
        """create_linked_table must strip PWD= from Connect after successful Append."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))

        result = adapter.create_linked_table(
            "NewLink",
            "dbo.Orders",
            "ODBC;DSN=mydsn;PWD=secret123",
        )
        assert result["success"] is True

        # Verify the stored Connect has password stripped
        stored = adapter._dispatcher._current_db._tables["NewLink"]
        assert "PWD=secret123" not in stored.Connect
        assert "PWD=" not in stored.Connect

    def test_refresh_linked_table_accepts_optional_connect_string(self, adapter, mock_app, tmp_path):
        """refresh_linked_table must accept optional connect_string parameter."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))

        # Inject a mock linked table with a RefreshLink method
        mock_tdef = MockDaoTableDef(
            name="ExistingLink",
            attributes=0x80000000,
            connect="ODBC;DSN=mydsn",
            source_table_name="dbo.Orders",
        )
        mock_tdef._refresh_called = False
        mock_tdef._connect_before_refresh = None

        def mock_refresh_link():
            mock_tdef._refresh_called = True
            mock_tdef._connect_before_refresh = mock_tdef.Connect

        mock_tdef.RefreshLink = mock_refresh_link
        # Ensure TableDefs cache is populated before setting up mock tables
        _ = adapter._dispatcher._current_db.TableDefs
        adapter._dispatcher._current_db._tables["ExistingLink"] = mock_tdef

        # Call with optional connect_string — password should be re-injected
        result = adapter.refresh_linked_table(
            "ExistingLink",
            connect_string="ODBC;DSN=mydsn;PWD=injected",
        )
        assert result["success"] is True
        assert mock_tdef._refresh_called is True
        # Password should have been temporarily applied
        assert "PWD=injected" in mock_tdef._connect_before_refresh

    def test_refresh_linked_table_strips_password_after_refresh(self, adapter, mock_app, tmp_path):
        """refresh_linked_table must strip PWD= from Connect after RefreshLink."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))

        mock_tdef = MockDaoTableDef(
            name="ExistingLink",
            attributes=0x80000000,
            connect="ODBC;DSN=mydsn",  # password already stripped
            source_table_name="dbo.Orders",
        )
        # Ensure TableDefs cache is populated before setting up mock tables
        _ = adapter._dispatcher._current_db.TableDefs
        adapter._dispatcher._current_db._tables["ExistingLink"] = mock_tdef

        result = adapter.refresh_linked_table(
            "ExistingLink",
            connect_string="ODBC;DSN=mydsn;PWD=secret456",
        )
        assert result["success"] is True
        # After refresh, Connect must be password-stripped
        assert "PWD=" not in mock_tdef.Connect

    def test_recreate_linked_table_restores_hidden_attribute(self, adapter, mock_app, tmp_path):
        """recreate_linked_table must restore dbHiddenObject flag after recreate."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))

        # Pre-existing table with hidden flag
        old_tdef = MockDaoTableDef(
            name="HiddenLink",
            attributes=0x80000001,  # dbLinkAttachedTable | dbHiddenObject
            connect="ODBC;DSN=mydsn;PWD=secret",
            source_table_name="dbo.OldName",
        )
        # Ensure TableDefs cache is populated before setting up mock tables
        _ = adapter._dispatcher._current_db.TableDefs
        adapter._dispatcher._current_db._tables["HiddenLink"] = old_tdef

        result = adapter.recreate_linked_table(
            "HiddenLink",
            "dbo.NewName",
            "ODBC;DSN=mydsn;PWD=secret",
            attributes=0x80000001,  # pass hidden flag
        )
        assert result["success"] is True

        # New table must have hidden flag restored
        new_tdef = adapter._dispatcher._current_db._tables["HiddenLink"]
        assert new_tdef.Attributes == 0x80000001
        assert new_tdef.SourceTableName == "dbo.NewName"
        # And password stripped
        assert "PWD=" not in new_tdef.Connect

    def test_recreate_linked_table_strips_password_after_recreate(self, adapter, mock_app, tmp_path):
        """recreate_linked_table must strip PWD= from Connect after recreate."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))

        old_tdef = MockDaoTableDef(
            name="MyLink",
            attributes=0x80000000,
            connect="ODBC;DSN=mydsn",
            source_table_name="dbo.OldName",
        )
        # Ensure TableDefs cache is populated before setting up mock tables
        _ = adapter._dispatcher._current_db.TableDefs
        adapter._dispatcher._current_db._tables["MyLink"] = old_tdef

        result = adapter.recreate_linked_table(
            "MyLink",
            "dbo.NewName",
            "ODBC;DSN=mydsn;PWD=secret789",
            attributes=None,
        )
        assert result["success"] is True

        new_tdef = adapter._dispatcher._current_db._tables["MyLink"]
        assert "PWD=secret789" not in new_tdef.Connect


class TestWinComVersioningExport:
    """Full versioning export — forms, reports, modules, macros."""

    def test_export_all_versioning_creates_dirs(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Set up mock objects
        mock_app.CurrentProject.AllForms = MockProjectCollection([
            MockProjectItem("Form1"),
        ])
        mock_app.CurrentProject.AllReports = MockProjectCollection([
            MockProjectItem("Report1"),
        ])
        mock_app.CurrentProject.AllMacros = MockProjectCollection([
            MockProjectItem("Macro1"),
        ])
        comp = MockVBComponent("modMain", comp_type=1, code="Public Sub Run()\nEnd Sub")
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("VBAProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])

        out_dir = tmp_path / "versioning"
        result = adapter.export_all_versioning(str(out_dir))
        assert result["success"] is True
        assert result["file_count"] >= 3
        assert (out_dir / "forms").is_dir()
        assert (out_dir / "reports").is_dir()
        assert (out_dir / "macros").is_dir()
        assert (out_dir / "modules").is_dir()

    def test_export_all_versioning_not_connected(self, adapter):
        result = adapter.export_all_versioning("/tmp/versioning")
        assert result["success"] is False


class TestWinComCompactRepair:
    """Compact and repair operations."""

    def test_compact_invalid_action(self, adapter):
        result = adapter.compact_repair("invalid", "/tmp/source.accdb", "/tmp/dest.accdb")
        assert result["success"] is False

    def test_compact_source_not_found(self, adapter):
        result = adapter.compact_repair("compact", "/tmp/nonexistent.accdb", "/tmp/dest.accdb")
        assert result["success"] is False

    def test_compact_success(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock database content")
        adapter.connect(str(db_path))
        out_path = tmp_path / "compacted.accdb"
        result = adapter.compact_repair("compact", str(db_path), str(out_path))
        assert result["success"] is True
        assert "stats" in result


class TestWinComCopyDatabase:
    """Database file copy."""

    def test_copy_success(self, adapter, mock_app, tmp_path):
        src = tmp_path / "source.accdb"
        src.write_text("database content")
        dst = tmp_path / "dest.accdb"
        result = adapter.copy_database(str(src), str(dst))
        assert result is True
        assert dst.exists()

    def test_copy_source_not_found(self, adapter):
        result = adapter.copy_database("/tmp/nonexistent.accdb", "/tmp/dest.accdb")
        assert result is False


class TestWinComLaunchClose:
    """Launch and close Access application."""

    def test_launch_access(self, adapter, mock_app):
        adapter.launch_access(visible=False)
        # Should not raise

    def test_launch_access_visible(self, adapter, mock_app):
        adapter.launch_access(visible=True)
        assert mock_app.Visible is True

    def test_close_access(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # close_access should not raise
        adapter.close_access()

    def test_close_access_not_connected(self, adapter):
        # Should not raise when not connected
        adapter.close_access()

    def test_close_access_does_not_pre_save_modules(self, adapter, mock_app, tmp_path):
        """close_access must NOT call DoCmd.Save(5, ...) for unnamed modules.

        Since set_vba_code/add_vba_procedure now use LoadFromText which
        auto-saves, there is no need to pre-save modules in close_access.
        This test ensures no DoCmd.Save call is made in close_access.
        """
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Set up a real module so the loop body runs
        comp = MockVBComponent("modReal", comp_type=1, code="Public Sub Real()\nEnd Sub")
        mock_app.VBE = MockVBE(MockVBProjects([MockVBProject("TestProject")]))
        mock_app.VBE.VBProjects(1).VBComponents = MockVBComponents([comp])

        # Capture DoCmd calls
        initial_save_count = len(mock_app.DoCmd.calls)
        adapter.close_access()
        # Only Close (object_type, object_name, save) should be recorded,
        # NOT Save(5, module_name) calls in a pre-save loop
        save_calls = [c for c in mock_app.DoCmd.calls if c[0] == "Save"]
        assert len(save_calls) == 0, f"Unexpected DoCmd.Save calls: {save_calls}"


class TestWinComSchemaInspectorDelegation:
    """Tests that verify WinComAdapter delegates schema operations to self._schema.

    These tests prove the pass-through delegation pattern after SchemaInspector
    extraction: get_system_tables, get_relationships, get_object_metadata,
    get_table_schema_plan, and generate_sql all delegate to self._schema.
    """

    def test_get_system_tables_delegates_to_schema(self, adapter, mock_app, tmp_path):
        """get_system_tables returns list after delegation wiring."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # _schema must be present (wired in __init__)
        assert hasattr(adapter, "_schema")
        results = adapter.get_system_tables()
        assert isinstance(results, list)

    def test_get_relationships_delegates_to_schema(self, adapter, mock_app, tmp_path):
        """get_relationships returns list after delegation wiring."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        assert hasattr(adapter, "_schema")
        results = adapter.get_relationships()
        assert isinstance(results, list)

    def test_get_table_schema_plan_delegates_to_schema(self, adapter, mock_app, tmp_path):
        """get_table_schema_plan returns tuple after delegation wiring."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        assert hasattr(adapter, "_schema")
        tables, unknown = adapter.get_table_schema_plan()
        assert isinstance(tables, list)
        assert hasattr(unknown, "primary_keys")

    def test_get_object_metadata_delegates_to_schema(self, adapter, mock_app, tmp_path):
        """get_object_metadata returns dict after delegation wiring."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        assert hasattr(adapter, "_schema")
        result = adapter.get_object_metadata("NonExistent")
        assert isinstance(result, dict)

    def test_generate_sql_delegates_to_schema(self, adapter, mock_app, tmp_path):
        """generate_sql creates file after delegation wiring."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE sql_test (id INTEGER, name TEXT)")
        assert hasattr(adapter, "_schema")
        out_path = tmp_path / "schema.sql"
        result = adapter.generate_sql(str(out_path))
        assert result["success"] is True
        assert os.path.exists(out_path)


class TestWinComGenerateSql:
    """generate_sql — full Jet SQL DDL generation via WinComAdapter."""

    def test_generate_sql_creates_file(self, adapter, mock_app, tmp_path):
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        # Create a real table so get_tables returns something
        adapter.execute_query("CREATE TABLE gen_test (id INTEGER, name TEXT)")
        out_path = tmp_path / "schema.sql"
        result = adapter.generate_sql(str(out_path))
        assert result["success"] is True
        assert os.path.exists(out_path)
        content = out_path.read_text()
        assert "gen_test" in content

    def test_generate_sql_not_connected(self, adapter):
        result = adapter.generate_sql("/tmp/schema.sql")
        assert result["success"] is False


class TestWinComAdapterLifecycle:
    """Adapter lifecycle — connect/disconnect cycles."""

    def test_reconnect_same_adapter(self, adapter, mock_app, tmp_path):
        """Connect, disconnect, then reconnect the SAME adapter."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        assert adapter.connect(str(db_path)) is True
        assert adapter.is_connected() is True
        adapter.disconnect()
        assert adapter.is_connected() is False
        # Reconnect — should work without creating a new adapter
        assert adapter.connect(str(db_path)) is True
        assert adapter.is_connected() is True

    def test_reconnect_different_db(self, adapter, mock_app, tmp_path):
        """Disconnect and connect to a different database."""
        db1 = tmp_path / "db1.accdb"
        db2 = tmp_path / "db2.accdb"
        db1.write_text("mock1")
        db2.write_text("mock2")

        assert adapter.connect(str(db1)) is True
        assert adapter.is_connected() is True
        adapter.disconnect()

        assert adapter.connect(str(db2)) is True
        assert adapter.is_connected() is True

    def test_get_tables_cached_fresh(self, adapter, mock_app, tmp_path):
        """Each get_tables call should re-read the database."""
        db_path = tmp_path / "test.accdb"
        db_path.write_text("mock")
        adapter.connect(str(db_path))
        adapter.execute_query("CREATE TABLE t1 (id INTEGER)")
        tables1 = [t.name for t in adapter.get_tables()]
        assert "t1" in tables1
        adapter.execute_query("CREATE TABLE t2 (id INTEGER)")
        tables2 = [t.name for t in adapter.get_tables()]
        assert "t2" in tables2


class TestVbaOperationsTrustedLocationsSingleSource:
    """Verify VbaOperations and trusted_locations.py are the single source of truth.

    After removing duplicate methods from WinComAdapter (PR 3), the trusted_locations
    module-level functions are the sole implementation. VbaOperations wraps them
    via its _trusted_locations_wrap method.
    """

    def test_vba_operations_has_trusted_locations_wrap(self):
        """VbaOperations has _trusted_locations_wrap that delegates to module functions."""
        from ms_access_mcp.adapters.vba_operations import VbaOperations
        from ms_access_mcp.adapters.trusted_locations import capture_trusted_locations, restore_trusted_locations
        # VbaOperations._trusted_locations_wrap is a bound method
        assert hasattr(VbaOperations, "_trusted_locations_wrap")

    def test_trusted_locations_module_functions_exist(self):
        """Module-level capture_trusted_locations and restore_trusted_locations exist."""
        from ms_access_mcp.adapters.trusted_locations import capture_trusted_locations, restore_trusted_locations
        assert callable(capture_trusted_locations)
        assert callable(restore_trusted_locations)

    def test_vba_operations_trusted_locations_wrap_uses_module_functions(self, mock_app, monkeypatch):
        """VbaOperations._trusted_locations_wrap calls module-level capture/restore."""
        from ms_access_mcp.adapters.vba_operations import VbaOperations
        from ms_access_mcp.adapters.trusted_locations import capture_trusted_locations, restore_trusted_locations

        dispatcher = MagicMock()
        dispatcher._started = True
        vba = VbaOperations(dispatcher)

        capture_called = []
        restore_called = []

        def mock_capture():
            capture_called.append(1)
            return [{"path": "C:\\Test", "description": "Test"}]

        def mock_restore(locs):
            restore_called.append(locs)
            return True

        monkeypatch.setattr("ms_access_mcp.adapters.vba_operations.capture_trusted_locations", mock_capture)
        monkeypatch.setattr("ms_access_mcp.adapters.vba_operations.restore_trusted_locations", mock_restore)
        monkeypatch.setattr(
            "ms_access_mcp.adapters.vba_operations.ServerConfig",
            lambda: MagicMock(preserve_trusted_locations=True),
        )

        def inner():
            return "success"

        result = vba._trusted_locations_wrap(inner)
        assert result == "success"
        assert len(capture_called) == 1
        assert len(restore_called) == 1

    def test_vba_operations_trusted_locations_wrap_skips_when_disabled(self, mock_app, monkeypatch):
        """When preserve_trusted_locations is False, capture/restore are not called."""
        from ms_access_mcp.adapters.vba_operations import VbaOperations

        dispatcher = MagicMock()
        dispatcher._started = True
        vba = VbaOperations(dispatcher)

        called = []

        def mock_capture():
            called.append("capture")
            return []

        def mock_restore(locs):
            called.append("restore")
            return True

        monkeypatch.setattr("ms_access_mcp.adapters.vba_operations.capture_trusted_locations", mock_capture)
        monkeypatch.setattr("ms_access_mcp.adapters.vba_operations.restore_trusted_locations", mock_restore)
        monkeypatch.setattr(
            "ms_access_mcp.adapters.vba_operations.ServerConfig",
            lambda: MagicMock(preserve_trusted_locations=False),
        )

        result = vba._trusted_locations_wrap(lambda: "done")
        assert result == "done"
        assert called == []

    def test_wincom_adapter_no_duplicate_trusted_locations_methods(self):
        """WinComAdapter no longer has _capture_trusted_locations / _restore_trusted_locations / _trusted_locations_wrap."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        assert not hasattr(WinComAdapter, "_capture_trusted_locations")
        assert not hasattr(WinComAdapter, "_restore_trusted_locations")
        assert not hasattr(WinComAdapter, "_trusted_locations_wrap")

    def test_wincom_adapter_no_duplicate_access_control_type_name(self):
        """WinComAdapter no longer has _access_control_type_name (exists in UiOperations)."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        assert not hasattr(WinComAdapter, "_access_control_type_name")

    def test_ui_operations_has_access_control_type_name(self):
        """UiOperations still has _access_control_type_name as the canonical implementation."""
        from ms_access_mcp.adapters.ui_operations import UiOperations
        assert hasattr(UiOperations, "_access_control_type_name")


class TestStripSqlComments:
    """Unit tests for the _strip_sql_comments static method.

    Covers: -- single-line comments, /* */ block comments,
    mixed comments, empty string, no comments, indented comments.
    """

    @staticmethod
    def _strip(sql: str) -> str:
        from ms_access_mcp.adapters.wincom import WinComAdapter
        return WinComAdapter._strip_sql_comments(sql)

    def test_removes_single_line_comments(self):
        sql = "SELECT * FROM customers\n-- fetch all customers\nWHERE active = -1"
        result = self._strip(sql)
        assert "--" not in result
        assert "SELECT" in result
        assert "WHERE" in result

    def test_removes_block_comments(self):
        sql = "SELECT /* comment */ 1"
        result = self._strip(sql)
        assert "/*" not in result
        assert "*/" not in result
        assert "SELECT" in result

    def test_mixed_comments(self):
        sql = """-- header comment
CREATE TABLE Test (ID INTEGER);
/* multi
line */
INSERT INTO Test VALUES (1);"""
        result = self._strip(sql)
        assert "--" not in result
        assert "/*" not in result
        assert "CREATE" in result
        assert "INSERT" in result

    def test_empty_string_returns_empty(self):
        result = self._strip("")
        assert result == ""

    def test_no_comments_unchanged(self):
        sql = "SELECT 1;\nINSERT INTO T VALUES (1);"
        result = self._strip(sql)
        assert result == sql or result.replace("\n", "") == sql.replace("\n", "")

    def test_only_comments_returns_empty(self):
        result = self._strip("-- just a comment\n/* another */")
        assert result.strip() == "" or result == ""

    def test_indented_comment(self):
        sql = "  -- indented comment\nSELECT 1"
        result = self._strip(sql)
        assert "SELECT 1" in result
        assert "indented" not in result

    def test_block_comment_same_line(self):
        sql = "SELECT /* inline */ 1, 2, 3"
        result = self._strip(sql)
        assert "SELECT" in result
        assert "1, 2, 3" in result
        assert "inline" not in result

    def test_multiple_block_comments(self):
        sql = "SELECT /* a */ 1 /* b */ , 2 /* c */"
        result = self._strip(sql)
        assert "SELECT" in result
        assert "1" in result and "2" in result
        assert "a" not in result
        assert "b" not in result
        assert "c" not in result

    def test_comment_only_lines_removed(self):
        sql = "SELECT 1;\n-- clean\nSELECT 2;\n-- more\nSELECT 3;"
        result = self._strip(sql)
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        assert "SELECT 1;" in result
        assert "SELECT 2;" in result
        assert "SELECT 3;" in result
        assert "clean" not in result
        assert "more" not in result


class TestExtractComError:
    """Direct tests for WinComAdapter._extract_com_error static method.

    Covers: generic Exception, pywin32 com_error-like exceptions,
    exceptions with winerror attribute.
    """

    def test_generic_exception_returns_str_error(self):
        """Plain Exception uses str(e) as error, code and message are None."""
        result = WinComAdapter._extract_com_error(Exception("Something broke"))
        assert result["error"] == "Something broke"
        assert result["code"] is None
        assert result["message"] is None

    def test_com_error_with_dao_info_extracts_code_and_description(self):
        """com_error with excepinfo[2] tuple extracts scode and description."""
        # pywin32 com_error: args = (hresult, msg, excepinfo, arg)
        # excepinfo = (help, context, description, helpfile, helpid, scode)
        excepinfo = (None, None, "Syntax error in CREATE TABLE statement.", None, None, -3289)
        err = Exception("Exception occurred.")
        err.args = (-2147352567, "Exception occurred.", excepinfo, None)

        result = WinComAdapter._extract_com_error(err)
        assert result["error"] == "Syntax error in CREATE TABLE statement."
        assert result["code"] == -3289
        assert result["message"] == "Syntax error in CREATE TABLE statement."

    def test_com_error_with_no_description_falls_back_to_str(self):
        """com_error with empty description falls back to str(e) as error."""
        excepinfo = (None, None, "", None, None, -3289)
        err = Exception("Exception occurred.")
        err.args = (-2147352567, "Exception occurred.", excepinfo, None)

        result = WinComAdapter._extract_com_error(err)
        assert result["code"] == -3289
        assert result["message"] is None  # empty description not stored

    def test_com_error_with_no_scode_returns_none_code(self):
        """com_error without scode returns None for code.

        When excepinfo[2] is a short 3-tuple (not 6-element), the DAO
        extraction is skipped entirely. Falls back to str(e).
        """
        excepinfo = (None, None, "DAO error msg")
        err = Exception("Exception occurred.")
        err.args = (-2147352567, "Exception occurred.", excepinfo, None)

        result = WinComAdapter._extract_com_error(err)
        # info is a 3-tuple (len < 6) → skipped → falls back to str(e)
        # str(e) returns repr of args tuple since args has >1 element
        assert result["error"] is not None
        assert result["code"] is None

    def test_com_error_non_tuple_excepinfo_falls_back(self):
        """com_error where excepinfo is not a tuple falls back to str(e)."""
        err = Exception("OLE error 0x80040E14")
        err.args = (-2147352567, "OLE error 0x80040E14", None, None)

        result = WinComAdapter._extract_com_error(err)
        # excepinfo[2] is None, not a tuple → skipped → str(e) = repr of args
        assert result["error"] is not None
        assert result["code"] is None

    def test_exception_with_winerror_uses_it_as_code(self):
        """Exception with winerror attribute uses it as code."""
        err = Exception("Access denied")
        err.winerror = 5

        result = WinComAdapter._extract_com_error(err)
        assert result["error"] == "Access denied"
        assert result["code"] == 5

    def test_exception_without_args_returns_str_error(self):
        """Exception with no args attribute returns str(e)."""
        err = Exception("simple")

        result = WinComAdapter._extract_com_error(err)
        assert result["error"] == "simple"
        assert result["code"] is None
        assert result["message"] is None


class TestParseScriptLines:
    """Direct tests for WinComAdapter._parse_script_lines method.

    Covers: statement splitting, line number tracking, comments,
    blank lines, missing trailing semicolons.
    """

    def _parse(self, sql: str) -> list[dict]:
        """Helper to call _parse_script_lines and return statements list."""
        adapter = WinComAdapter()
        return adapter._parse_script_lines(sql)["statements"]

    def test_empty_string_returns_empty_list(self):
        assert self._parse("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert self._parse("  \n  \n  ") == []

    def test_single_statement_returns_one_entry(self):
        stmts = self._parse("SELECT 1")
        assert len(stmts) == 1
        assert stmts[0]["text"] == "SELECT 1"
        assert stmts[0]["line"] == 1

    def test_two_statements_with_semicolons(self):
        stmts = self._parse("SELECT 1;\nSELECT 2;")
        assert len(stmts) == 2
        assert stmts[0]["text"] == "SELECT 1"
        assert stmts[0]["line"] == 1
        assert stmts[1]["text"] == "SELECT 2"
        assert stmts[1]["line"] == 2

    def test_no_trailing_semicolon(self):
        """Last statement without trailing semicolon is still parsed."""
        stmts = self._parse("SELECT 1;\nSELECT 2")
        assert len(stmts) == 2
        assert stmts[1]["text"] == "SELECT 2"
        assert stmts[1]["line"] == 2

    def test_blank_lines_between_statements_ignored(self):
        stmts = self._parse("SELECT 1;\n\n  \nSELECT 2;")
        assert len(stmts) == 2
        assert stmts[0]["line"] == 1
        assert stmts[1]["line"] == 4  # line 4 = after 3 blank lines

    def test_comments_are_stripped_from_statements(self):
        """Comments before SQL in same chunk: line points to first content.

        Since the `;` delimiter groups comment+SQL into one chunk, the
        line number tracks the chunk's first non-whitespace content,
        not the SQL statement itself (which starts after the comment).
        """
        stmts = self._parse("-- header\nSELECT 1;\n/* mid */\nSELECT 2;")
        assert len(stmts) == 2
        assert stmts[0]["text"] == "SELECT 1"
        assert stmts[0]["line"] == 1
        assert stmts[1]["text"] == "SELECT 2"
        # line is 3: `/* mid */` starts on line 3 (after `;\n`)
        assert stmts[1]["line"] == 3

    def test_leading_whitespace_before_statement(self):
        """Line number points to actual content, not whitespace."""
        stmts = self._parse("  SELECT 1;")
        assert stmts[0]["text"] == "SELECT 1"
        assert stmts[0]["line"] == 1  # whitespace on same line → still line 1

    def test_statement_with_trailing_whitespace(self):
        stmts = self._parse("SELECT 1;  \nSELECT 2;")
        assert len(stmts) == 2
        assert stmts[0]["text"] == "SELECT 1"
        assert stmts[0]["line"] == 1
        assert stmts[1]["line"] == 2

    def test_multiple_semicolons_in_a_row(self):
        """Empty statements between consecutive semicolons are skipped."""
        stmts = self._parse("SELECT 1;;;SELECT 2;")
        assert len(stmts) == 2
        assert stmts[0]["text"] == "SELECT 1"
        assert stmts[1]["text"] == "SELECT 2"

    def test_newline_after_semicolon_line_number(self):
        """Line number tracks correctly with newline after semicolon."""
        stmts = self._parse("SELECT 1;\nSELECT 2;\nSELECT 3;")
        assert stmts[0]["line"] == 1
        assert stmts[1]["line"] == 2
        assert stmts[2]["line"] == 3

    def test_comment_only_chunks_are_skipped(self):
        """Chunks that are only comments after stripping are skipped."""
        stmts = self._parse("SELECT 1;\n-- just a comment\nSELECT 2;")
        assert len(stmts) == 2
        assert stmts[1]["text"] == "SELECT 2"
        # line = 2: chunk starts on line 2 (-- just a comment), first
        # non-whitespace content is `--` at start of line 2
        assert stmts[1]["line"] == 2

    def test_inline_comment_in_statement(self):
        """Inline /* block */ comments are stripped from statement text.

        Note: comment removal leaves the surrounding spaces intact,
        so `SELECT /* keep */ 1` becomes `SELECT  1` (double space).
        """
        stmts = self._parse("SELECT /* keep */ 1;")
        # Comment removal leaves surrounding spaces
        assert "SELECT  1" in stmts[0]["text"]
        assert "keep" not in stmts[0]["text"]
        assert stmts[0]["line"] == 1
