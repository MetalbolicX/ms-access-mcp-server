"""Comprehensive unit tests for SchemaService — all 26 methods."""

import pytest
from unittest.mock import MagicMock
from ms_access_mcp.services.schema import SchemaService
from ms_access_mcp.models.database import (
    TableInfo,
    FieldInfo,
    QueryInfo,
    RelationshipInfo,
    FormInfo,
    ReportInfo,
    MacroInfo,
    ModuleInfo,
    ControlInfo,
)


def make_mock_adapter():
    """Fresh mock adapter with all methods returning controlled values."""
    a = MagicMock()
    a.get_tables.return_value = [TableInfo(name="Orders", fields=[], record_count=10)]
    a.get_table_schema = lambda n: TableInfo(name=n, fields=[], record_count=0) if n else None
    a.get_queries.return_value = [QueryInfo(name="q", sql="SELECT 1", type="select")]
    a.get_relationships.return_value = [RelationshipInfo(name="r", table="T", foreign_table="F")]
    a.get_forms.return_value = [FormInfo(name="frm")]
    a.get_reports.return_value = [ReportInfo(name="rpt")]
    a.get_macros.return_value = [MacroInfo(name="mac")]
    a.get_modules.return_value = [ModuleInfo(name="mod")]
    a.get_vba_code.return_value = "Sub Test()\nEnd Sub"
    a.get_system_tables.return_value = [TableInfo(name="USys", fields=[], record_count=0)]
    a.form_exists.return_value = True
    a.get_form_controls.return_value = [ControlInfo(name="ctrl", type="TextBox")]
    a.export_form_to_text.return_value = "FORM DESIGN..."
    a.import_form_from_text.return_value = True
    a.delete_form.return_value = True
    a.export_report_to_text.return_value = "REPORT DESIGN..."
    a.import_report_from_text.return_value = True
    a.delete_report.return_value = True
    a.add_vba_procedure.return_value = True
    a.compile_vba.return_value = {"success": True, "error": None}
    a.get_vba_project_name.return_value = "TestProject"
    a.get_object_metadata.return_value = {"type": "Form"}
    a.execute_sql_script.return_value = {"success": True, "statements_executed": 1, "error": None}
    a.export_module_to_text.return_value = "Sub Test()\nEnd Sub"
    a.export_macro_to_text.return_value = "MACRO DATA"
    a.export_all_versioning.return_value = {"success": True, "exported": {}}
    a.export_query_to_text.return_value = "SELECT * FROM Table1"
    a.import_query_from_text.return_value = True
    a.import_all_versioning.return_value = {"success": True, "imported": {}}
    a.compare_versioning.return_value = {"success": True, "new": [], "missing": [], "changed": []}
    a.export_schema_ddl.return_value = {"success": True, "ddl_tables": "schema/ddl_tables.sql", "ddl_relationships": "schema/ddl_relationships.sql"}
    return a


# =============================================================================
# Adapter delegation — each method must forward to adapter and return its value
# =============================================================================

class TestSchemaServiceDelegation:
    """Every SchemaService method must delegate to the adapter and return adapter's result."""

    def setup_method(self):
        self.service = SchemaService()
        self.mock_adapter = make_mock_adapter()
        self.service.set_adapter(self.mock_adapter)

    def test_get_tables_delegates(self):
        assert self.service.get_tables() == [TableInfo(name="Orders", fields=[], record_count=10)]
        self.mock_adapter.get_tables.assert_called_once()

    def test_get_queries_delegates(self):
        assert self.service.get_queries() == [QueryInfo(name="q", sql="SELECT 1", type="select")]
        self.mock_adapter.get_queries.assert_called_once()

    def test_get_relationships_delegates(self):
        rels = self.service.get_relationships()
        assert len(rels) == 1
        assert rels[0].name == "r"
        self.mock_adapter.get_relationships.assert_called_once()

    def test_get_forms_delegates(self):
        assert self.service.get_forms() == [FormInfo(name="frm")]
        self.mock_adapter.get_forms.assert_called_once()

    def test_get_reports_delegates(self):
        assert self.service.get_reports() == [ReportInfo(name="rpt")]
        self.mock_adapter.get_reports.assert_called_once()

    def test_get_macros_delegates(self):
        assert self.service.get_macros() == [MacroInfo(name="mac")]
        self.mock_adapter.get_macros.assert_called_once()

    def test_get_modules_delegates(self):
        assert self.service.get_modules() == [ModuleInfo(name="mod")]
        self.mock_adapter.get_modules.assert_called_once()

    def test_get_vba_code_delegates(self):
        assert self.service.get_vba_code("mod") == "Sub Test()\nEnd Sub"
        self.mock_adapter.get_vba_code.assert_called_once_with("mod")

    def test_get_system_tables_delegates(self):
        tables = self.service.get_system_tables()
        assert tables[0].name == "USys"
        self.mock_adapter.get_system_tables.assert_called_once()

    def test_form_exists_delegates(self):
        assert self.service.form_exists("frm") is True
        self.mock_adapter.form_exists.assert_called_once_with("frm")

    def test_get_form_controls_delegates(self):
        ctrls = self.service.get_form_controls("frm")
        assert ctrls[0].name == "ctrl"
        self.mock_adapter.get_form_controls.assert_called_once_with("frm")

    def test_export_form_to_text_delegates(self):
        assert self.service.export_form_to_text("frm") == "FORM DESIGN..."
        self.mock_adapter.export_form_to_text.assert_called_once_with("frm")

    def test_import_form_from_text_delegates(self):
        assert self.service.import_form_from_text("frm", "data") is True
        self.mock_adapter.import_form_from_text.assert_called_once_with("frm", "data")

    def test_delete_form_delegates(self):
        assert self.service.delete_form("frm") is True
        self.mock_adapter.delete_form.assert_called_once_with("frm")

    def test_export_report_to_text_delegates(self):
        assert self.service.export_report_to_text("rpt") == "REPORT DESIGN..."
        self.mock_adapter.export_report_to_text.assert_called_once_with("rpt")

    def test_import_report_from_text_delegates(self):
        assert self.service.import_report_from_text("rpt", "data") is True
        self.mock_adapter.import_report_from_text.assert_called_once_with("rpt", "data")

    def test_delete_report_delegates(self):
        assert self.service.delete_report("rpt") is True
        self.mock_adapter.delete_report.assert_called_once_with("rpt")

    def test_add_vba_procedure_delegates(self):
        assert self.service.add_vba_procedure("mod", "proc", "code") is True
        self.mock_adapter.add_vba_procedure.assert_called_once_with("mod", "proc", "code")

    def test_compile_vba_delegates(self):
        result = self.service.compile_vba()
        assert result["success"] is True
        self.mock_adapter.compile_vba.assert_called_once()

    def test_get_vba_project_name_delegates(self):
        assert self.service.get_vba_project_name() == "TestProject"
        self.mock_adapter.get_vba_project_name.assert_called_once()

    def test_get_object_metadata_delegates(self):
        assert self.service.get_object_metadata("obj") == {"type": "Form"}
        self.mock_adapter.get_object_metadata.assert_called_once_with("obj")

    def test_execute_sql_script_delegates(self):
        result = self.service.execute_sql_script("/tmp/script.sql")
        assert result["success"] is True
        assert result["statements_executed"] == 1
        self.mock_adapter.execute_sql_script.assert_called_once_with("/tmp/script.sql")

    def test_export_module_to_text_delegates(self):
        assert self.service.export_module_to_text("mod") == "Sub Test()\nEnd Sub"
        self.mock_adapter.export_module_to_text.assert_called_once_with("mod")

    def test_export_macro_to_text_delegates(self):
        assert self.service.export_macro_to_text("mac") == "MACRO DATA"
        self.mock_adapter.export_macro_to_text.assert_called_once_with("mac")

    def test_export_all_versioning_delegates(self):
        result = self.service.export_all_versioning("/tmp/out")
        assert result["success"] is True
        self.mock_adapter.export_all_versioning.assert_called_once_with("/tmp/out")

    def test_export_query_to_text_delegates(self):
        assert self.service.export_query_to_text("q1") == "SELECT * FROM Table1"
        self.mock_adapter.export_query_to_text.assert_called_once_with("q1")

    def test_import_query_from_text_delegates(self):
        assert self.service.import_query_from_text("q1", "SELECT 1") is True
        self.mock_adapter.import_query_from_text.assert_called_once_with("q1", "SELECT 1")

    def test_import_all_versioning_delegates(self):
        result = self.service.import_all_versioning("/tmp/in")
        assert result["success"] is True
        self.mock_adapter.import_all_versioning.assert_called_once_with("/tmp/in")

    def test_compare_versioning_delegates(self):
        result = self.service.compare_versioning("/tmp/compare")
        assert result["success"] is True
        self.mock_adapter.compare_versioning.assert_called_once_with("/tmp/compare")

    def test_export_schema_ddl_delegates(self):
        result = self.service.export_schema_ddl("/tmp/ddl")
        assert result["success"] is True
        self.mock_adapter.export_schema_ddl.assert_called_once_with("/tmp/ddl")


# =============================================================================
# No-adapter defaults — every method must return a safe default when adapter is None
# =============================================================================

class TestSchemaServiceNoAdapterDefaults:
    """Each method returns the correct safe default when no adapter is set."""

    def setup_method(self):
        self.service = SchemaService()

    def test_get_tables_returns_empty_list(self):
        assert self.service.get_tables() == []

    def test_get_queries_returns_empty_list(self):
        assert self.service.get_queries() == []

    def test_get_relationships_returns_empty_list(self):
        assert self.service.get_relationships() == []

    def test_get_forms_returns_empty_list(self):
        assert self.service.get_forms() == []

    def test_get_reports_returns_empty_list(self):
        assert self.service.get_reports() == []

    def test_get_macros_returns_empty_list(self):
        assert self.service.get_macros() == []

    def test_get_modules_returns_empty_list(self):
        assert self.service.get_modules() == []

    def test_get_vba_code_returns_empty_string(self):
        assert self.service.get_vba_code("mod") == ""

    def test_get_system_tables_returns_empty_list(self):
        assert self.service.get_system_tables() == []

    def test_form_exists_returns_false(self):
        assert self.service.form_exists("frm") is False

    def test_get_form_controls_returns_empty_list(self):
        assert self.service.get_form_controls("frm") == []

    def test_export_form_to_text_returns_empty_string(self):
        assert self.service.export_form_to_text("frm") == ""

    def test_import_form_from_text_returns_false(self):
        assert self.service.import_form_from_text("frm", "data") is False

    def test_delete_form_returns_false(self):
        assert self.service.delete_form("frm") is False

    def test_export_report_to_text_returns_empty_string(self):
        assert self.service.export_report_to_text("rpt") == ""

    def test_import_report_from_text_returns_false(self):
        assert self.service.import_report_from_text("rpt", "data") is False

    def test_delete_report_returns_false(self):
        assert self.service.delete_report("rpt") is False

    def test_add_vba_procedure_returns_false(self):
        assert self.service.add_vba_procedure("mod", "proc", "code") is False

    def test_compile_vba_returns_false(self):
        assert self.service.compile_vba() is False

    def test_get_vba_project_name_returns_empty_string(self):
        assert self.service.get_vba_project_name() == ""

    def test_get_object_metadata_returns_empty_dict(self):
        assert self.service.get_object_metadata("obj") == {}

    def test_execute_sql_script_returns_error_dict(self):
        result = self.service.execute_sql_script("/tmp/script.sql")
        assert result["success"] is False
        assert "No adapter connected" in result["error"]
        assert result["statements_executed"] == 0

    def test_export_module_to_text_returns_empty_string(self):
        assert self.service.export_module_to_text("mod") == ""

    def test_export_macro_to_text_returns_empty_string(self):
        assert self.service.export_macro_to_text("mac") == ""

    def test_export_all_versioning_returns_error_dict(self):
        result = self.service.export_all_versioning("/tmp/out")
        assert result["success"] is False
        assert "No adapter connected" in result["error"]
        assert result["exported"] == {}

    def test_export_query_to_text_returns_empty_string(self):
        assert self.service.export_query_to_text("q1") == ""

    def test_import_query_from_text_returns_false(self):
        assert self.service.import_query_from_text("q1", "SELECT 1") is False

    def test_import_all_versioning_returns_error_dict(self):
        result = self.service.import_all_versioning("/tmp/in")
        assert result["success"] is False
        assert "No adapter connected" in result["error"]

    def test_compare_versioning_returns_error_dict(self):
        result = self.service.compare_versioning("/tmp/compare")
        assert result["success"] is False
        assert "No adapter connected" in result["error"]

    def test_export_schema_ddl_returns_error_dict(self):
        result = self.service.export_schema_ddl("/tmp/ddl")
        assert result["success"] is False
        assert "No adapter connected" in result["error"]


# =============================================================================
# get_table_schema — lookup by name with correct not-found behavior
# =============================================================================
# set_adapter — wiring and overwriting
# =============================================================================

class TestSetAdapter:
    """set_adapter wires the adapter and supports overwriting."""

    def test_set_adapter_stores_it(self):
        service = SchemaService()
        adapter = make_mock_adapter()
        service.set_adapter(adapter)
        assert service._adapter is adapter

    def test_set_adapter_overwrites_previous(self):
        service = SchemaService()
        a1 = make_mock_adapter()
        a2 = make_mock_adapter()
        service.set_adapter(a1)
        service.set_adapter(a2)
        assert service._adapter is a2

    def test_constructor_accepts_adapter(self):
        adapter = make_mock_adapter()
        service = SchemaService(adapter)
        assert service._adapter is adapter