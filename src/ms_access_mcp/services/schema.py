from typing import Optional
from ..adapters.base import AccessAdapter
from ..models.database import (
    TableInfo,
    QueryInfo,
    RelationshipInfo,
    FormInfo,
    ReportInfo,
    MacroInfo,
    ModuleInfo,
    ControlInfo,
)


class SchemaService:
    """Provides schema exploration capabilities for Access databases."""

    def __init__(self, adapter: Optional[AccessAdapter] = None):
        self._adapter = adapter

    def set_adapter(self, adapter: AccessAdapter) -> None:
        """Set the adapter for schema operations."""
        self._adapter = adapter

    def get_tables(self) -> list[TableInfo]:
        """Get all user tables from the connected database."""
        if self._adapter is None:
            return []
        return self._adapter.get_tables()

    def get_table_schema(self, table_name: str) -> Optional[TableInfo]:
        """Get detailed schema for a specific table."""
        if self._adapter is None:
            return None
        tables = self._adapter.get_tables()
        for table in tables:
            if table.name == table_name:
                return table
        return None

    def get_queries(self) -> list[QueryInfo]:
        """Get all saved queries from the database."""
        if self._adapter is None:
            return []
        # Stub implementation - requires COM
        return []

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get all foreign key relationships."""
        if self._adapter is None:
            return []
        return self._adapter.get_relationships()

    # COM-only operations (delegate to adapter)

    def get_forms(self) -> list[FormInfo]:
        """Get all forms in the database."""
        if self._adapter is None:
            return []
        return self._adapter.get_forms()

    def get_reports(self) -> list[ReportInfo]:
        """Get all reports in the database."""
        if self._adapter is None:
            return []
        return self._adapter.get_reports()

    def get_macros(self) -> list[MacroInfo]:
        """Get all macros in the database."""
        if self._adapter is None:
            return []
        return self._adapter.get_macros()

    def get_modules(self) -> list[ModuleInfo]:
        """Get all VBA modules in the database."""
        if self._adapter is None:
            return []
        return self._adapter.get_modules()

    def get_vba_code(self, module_name: str) -> str:
        """Get VBA code from a module."""
        if self._adapter is None:
            return ""
        return self._adapter.get_vba_code(module_name)

    def get_system_tables(self) -> list[TableInfo]:
        """Get system tables from the database."""
        if self._adapter is None:
            return []
        return self._adapter.get_system_tables()

    def form_exists(self, form_name: str) -> bool:
        """Check if a form exists."""
        if self._adapter is None:
            return False
        return self._adapter.form_exists(form_name)

    def get_form_controls(self, form_name: str) -> list[ControlInfo]:
        """Get all controls in a form."""
        if self._adapter is None:
            return []
        return self._adapter.get_form_controls(form_name)

    def export_form_to_text(self, form_name: str) -> str:
        """Export a form to text representation."""
        if self._adapter is None:
            return ""
        return self._adapter.export_form_to_text(form_name)

    def import_form_from_text(self, form_data: str) -> bool:
        """Import a form from text representation."""
        if self._adapter is None:
            return False
        return self._adapter.import_form_from_text(form_data)

    def delete_form(self, form_name: str) -> bool:
        """Delete a form from the database."""
        if self._adapter is None:
            return False
        return self._adapter.delete_form(form_name)

    def export_report_to_text(self, report_name: str) -> str:
        """Export a report to text representation."""
        if self._adapter is None:
            return ""
        return self._adapter.export_report_to_text(report_name)

    def import_report_from_text(self, report_data: str) -> bool:
        """Import a report from text representation."""
        if self._adapter is None:
            return False
        return self._adapter.import_report_from_text(report_data)

    def delete_report(self, report_name: str) -> bool:
        """Delete a report from the database."""
        if self._adapter is None:
            return False
        return self._adapter.delete_report(report_name)

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        """Add a VBA procedure to a module."""
        if self._adapter is None:
            return False
        return self._adapter.add_vba_procedure(module_name, procedure_name, code)

    def compile_vba(self) -> bool:
        """Compile VBA code."""
        if self._adapter is None:
            return False
        return self._adapter.compile_vba()

    def get_vba_project_name(self) -> str:
        """Get the VBA project name."""
        if self._adapter is None:
            return ""
        return self._adapter.get_vba_project_name()

    def get_object_metadata(self, object_name: str) -> dict:
        """Get metadata for a database object."""
        if self._adapter is None:
            return {}
        return self._adapter.get_object_metadata(object_name)

    def execute_sql_script(self, script_path: str) -> dict:
        """Execute a Jet SQL script file against the connected database."""
        if self._adapter is None:
            return {"success": False, "error": "No adapter connected", "statements_executed": 0}
        return self._adapter.execute_sql_script(script_path)

    def export_module_to_text(self, module_name: str) -> str:
        """Export VBA module code as plain text."""
        if self._adapter is None:
            return ""
        return self._adapter.export_module_to_text(module_name)

    def export_macro_to_text(self, macro_name: str) -> str:
        """Export macro metadata as plain text."""
        if self._adapter is None:
            return ""
        return self._adapter.export_macro_to_text(macro_name)

    def export_all_versioning(self, output_dir: str) -> dict:
        """Export all forms, reports, modules, and macros to a directory structure."""
        if self._adapter is None:
            return {"success": False, "error": "No adapter connected", "exported": {}}
        return self._adapter.export_all_versioning(output_dir)
