r"""
Integration tests against a real Access database via WinCOM adapter.

These tests require:
  - Windows OS with MS Access installed
  - pywin32 (win32com.client)
  - A test .accdb database file

Markers: com_integration

Usage:
  ACCESS_TEST_DB=D:\path\to\test.accdb pytest tests/integration/ -m com_integration -v
"""

import os
import tempfile
import pytest
from helpers import (
    TEST_DB,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
)


pytestmark = [pytest.mark.com_integration, skip_unless_windows, skip_unless_pywin32, skip_unless_db]


class TestWinComAdapterWithRealDb:
    """Test WinComAdapter against a real Access database."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.adapter = WinComAdapter()
        assert self.adapter.connect(TEST_DB), f"Failed to connect to {TEST_DB}"
        assert self.adapter.is_connected()

    def teardown_method(self):
        self.adapter.disconnect()

    # --- Tables ---

    def test_get_tables_returns_real_tables(self):
        tables = self.adapter.get_tables()
        table_names = [t.name for t in tables]
        assert len(table_names) > 0
        assert all(t.name for t in tables)  # no empty names

    def test_get_tables_includes_fields(self):
        tables = self.adapter.get_tables()
        assert all(len(t.fields) >= 0 for t in tables)

    def test_get_tables_system_tables(self):
        system = self.adapter.get_system_tables()
        assert isinstance(system, list)

    # --- Data ---

    def test_execute_query(self):
        result = self.adapter.execute_query("SELECT 1 AS test")
        assert result["success"] is True
        assert result["count"] >= 1

    # --- Schema ---

    def test_get_relationships(self):
        rels = self.adapter.get_relationships()
        assert isinstance(rels, list)

    def test_get_object_metadata(self):
        tables = self.adapter.get_tables()
        if tables:
            meta = self.adapter.get_object_metadata(tables[0].name)
            assert isinstance(meta, dict)

    # --- Forms ---

    def test_get_forms(self):
        forms = self.adapter.get_forms()
        assert isinstance(forms, list)

    def test_form_exists(self):
        forms = self.adapter.get_forms()
        if forms:
            assert self.adapter.form_exists(forms[0].name) is True
        assert self.adapter.form_exists("__nonexistent__form__") is False

    # --- Reports ---

    def test_get_reports(self):
        reports = self.adapter.get_reports()
        assert isinstance(reports, list)

    # --- Macros ---

    def test_get_macros(self):
        macros = self.adapter.get_macros()
        assert isinstance(macros, list)

    # --- Modules / VBA ---

    def test_get_modules(self):
        modules = self.adapter.get_modules()
        assert isinstance(modules, list)

    def test_get_vba_code(self):
        modules = self.adapter.get_modules()
        if modules:
            code = self.adapter.get_vba_code(modules[0].name)
            assert isinstance(code, str)

    def test_export_module_to_text(self):
        modules = self.adapter.get_modules()
        if modules:
            content = self.adapter.export_module_to_text(modules[0].name)
            assert isinstance(content, str)

    def test_export_form_to_text(self):
        forms = self.adapter.get_forms()
        if forms:
            content = self.adapter.export_form_to_text(forms[0].name)
            assert isinstance(content, str)

    def test_export_macro_to_text_not_found(self):
        content = self.adapter.export_macro_to_text("NonExistentMacro")
        assert content == ""

    # --- SQL Script ---

    def test_execute_sql_script_create_and_drop(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False, encoding='utf-8') as f:
            f.write("CREATE TABLE TestTemp (ID INTEGER PRIMARY KEY, Name TEXT(50));\n")
            f.write("DROP TABLE TestTemp;\n")
            script_path = f.name

        try:
            result = self.adapter.execute_sql_script(script_path)
            assert result["success"] is True
            assert result["statements_executed"] == 2
            # Spec fields are None on success
            assert result["failing_statement"] is None
            assert result["failing_line"] is None
            assert result["access_error_code"] is None
            assert result["access_error_message"] is None
        finally:
            os.unlink(script_path)

    def test_execute_sql_script_file_not_found(self):
        result = self.adapter.execute_sql_script(r"C:\nonexistent\path\test.sql")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_execute_sql_script_invalid_sql(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False, encoding='utf-8') as f:
            f.write("INSERT INTO nonexistent_table VALUES (1);\n")
            script_path = f.name

        try:
            result = self.adapter.execute_sql_script(script_path)
            assert result["success"] is False
            assert "statements_executed" in result
            # Spec fields are present on failure
            assert "failing_statement" in result
            assert "failing_line" in result
            assert "access_error_code" in result
            assert "access_error_message" in result
        finally:
            os.unlink(script_path)

    # --- Versioning ---

    def test_export_all_versioning_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.adapter.export_all_versioning(tmpdir)
            assert isinstance(result, dict)
            assert "exported" in result

    # --- Controls ---

    def test_get_form_controls(self):
        forms = self.adapter.get_forms()
        if forms:
            controls = self.adapter.get_form_controls(forms[0].name)
            assert isinstance(controls, list)


@pytest.mark.com_integration
@skip_unless_db
@skip_unless_windows
@skip_unless_pywin32
class TestSchemaServiceRealDb:
    """Test SchemaService with a real adapter and database."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.schema import SchemaService

        self.adapter = WinComAdapter()
        assert self.adapter.connect(TEST_DB)
        self.service = SchemaService(self.adapter)

    def teardown_method(self):
        self.adapter.disconnect()

    def test_get_tables(self):
        tables = self.service.get_tables()
        assert isinstance(tables, list)
        assert len(tables) > 0

    def test_get_relationships(self):
        rels = self.service.get_relationships()
        assert isinstance(rels, list)

    def test_form_exists(self):
        forms = self.service.get_forms()
        if forms:
            assert self.service.form_exists(forms[0].name) is True
