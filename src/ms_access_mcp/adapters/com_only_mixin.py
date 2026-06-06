"""Com-only adapter mixin — provides NotImplementedError stubs for all COM-only operations.

OdbcAdapter inherits this mixin to satisfy the AccessAdapter protocol without
requiring COM automation. Each stub raises NotImplementedError("requires COM automation").

Methods that OdbcAdapter implements itself (ODBC data operations) are NOT in this mixin:
- execute_query, insert_data, update_data, delete_data
- export_data
- get_tables, get_queries, create_query, set_query_sql, delete_query, create_table, delete_table
- export_schema_ddl
- compact_repair (returns error dict), copy_database (returns False)
"""

from typing import Any


class ComOnlyAdapterMixin:
    """NotImplementedError stubs for COM-only AccessAdapter methods.

    OdbcAdapter inherits from both AccessAdapter (via base.py) and this mixin.
    The mixin satisfies the protocol requirement that all AccessAdapter methods exist,
    while OdbcAdapter's own implementations override these stubs for the methods it supports
    (like copy_database which returns False instead of raising).
    """

    def launch_access(self, visible: bool = False) -> None:
        """Launch Access UI — requires COM automation."""
        raise NotImplementedError("launch_access requires COM automation (WinComAdapter)")

    def close_access(self) -> None:
        """Close Access UI — requires COM automation."""
        raise NotImplementedError("close_access requires COM automation (WinComAdapter)")

    def get_forms(self) -> list:
        """Get all forms — requires COM automation."""
        raise NotImplementedError("get_forms requires COM automation (WinComAdapter)")

    def get_reports(self) -> list:
        """Get all reports — requires COM automation."""
        raise NotImplementedError("get_reports requires COM automation (WinComAdapter)")

    def get_macros(self) -> list:
        """Get all macros — requires COM automation."""
        raise NotImplementedError("get_macros requires COM automation (WinComAdapter)")

    def get_modules(self) -> list:
        """Get all VBA modules — requires COM automation."""
        raise NotImplementedError("get_modules requires COM automation (WinComAdapter)")

    def form_exists(self, form_name: str) -> bool:
        """Check if form exists — requires COM automation."""
        raise NotImplementedError("form_exists requires COM automation (WinComAdapter)")

    def report_exists(self, report_name: str) -> bool:
        """Check if report exists — requires COM automation."""
        raise NotImplementedError("report_exists requires COM automation (WinComAdapter)")

    def delete_form(self, form_name: str) -> bool:
        """Delete a form — requires COM automation."""
        raise NotImplementedError("delete_form requires COM automation (WinComAdapter)")

    def delete_report(self, report_name: str) -> bool:
        """Delete a report — requires COM automation."""
        raise NotImplementedError("delete_report requires COM automation (WinComAdapter)")

    def get_form_controls(self, form_name: str) -> list:
        """Get controls on a form — requires COM automation."""
        raise NotImplementedError("get_form_controls requires COM automation (WinComAdapter)")

    def open_form(self, form_name: str) -> bool:
        """Open a form — requires COM automation."""
        raise NotImplementedError("open_form requires COM automation (WinComAdapter)")

    def close_form(self, form_name: str) -> bool:
        """Close a form — requires COM automation."""
        raise NotImplementedError("close_form requires COM automation (WinComAdapter)")

    def get_control_properties(self, form_name: str, control_name: str) -> dict:
        """Get properties of a control — requires COM automation."""
        raise NotImplementedError("get_control_properties requires COM automation (WinComAdapter)")

    def set_control_property(self, form_name: str, control_name: str, property_name: str, value: str) -> bool:
        """Set a single control property — requires COM automation."""
        raise NotImplementedError("set_control_property requires COM automation (WinComAdapter)")

    def set_control_properties(self, form_name: str, control_name: str, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple control properties at once — requires COM automation."""
        raise NotImplementedError("set_control_properties requires COM automation (WinComAdapter)")

    def get_control_event_procedures(self, form_name: str, control_name: str) -> list[dict]:
        """List event procedures for a control — requires COM automation."""
        raise NotImplementedError("get_control_event_procedures requires COM automation (WinComAdapter)")

    def get_vba_code(self, module_name: str) -> str:
        """Get VBA code from a module — requires COM automation."""
        raise NotImplementedError("get_vba_code requires COM automation (WinComAdapter)")

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Set VBA code in a module — requires COM automation."""
        raise NotImplementedError("set_vba_code requires COM automation (WinComAdapter)")

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        """Add a VBA procedure to a module — requires COM automation."""
        raise NotImplementedError("add_vba_procedure requires COM automation (WinComAdapter)")

    def compile_vba(self) -> dict:
        """Compile all VBA modules — requires COM automation."""
        raise NotImplementedError("compile_vba requires COM automation (WinComAdapter)")

    def save_database(self) -> dict:
        """Save all VBA modules to disk — requires COM automation."""
        raise NotImplementedError("save_database requires COM automation (WinComAdapter)")

    def delete_module(self, module_name: str) -> bool:
        """Delete a VBA module — requires COM automation."""
        raise NotImplementedError("delete_module requires COM automation (WinComAdapter)")

    def vba_list_procedures(self, module_name: str) -> list[dict]:
        """List all procedures in a VBA module — requires COM automation."""
        raise NotImplementedError("vba_list_procedures requires COM automation (WinComAdapter)")

    def vba_get_procedure(self, module_name: str, procedure_name: str) -> dict:
        """Get the source of a specific VBA procedure — requires COM automation."""
        raise NotImplementedError("vba_get_procedure requires COM automation (WinComAdapter)")

    def vba_replace_procedure(self, module_name: str, procedure_name: str, new_code: str) -> bool:
        """Replace a VBA procedure body — requires COM automation."""
        raise NotImplementedError("vba_replace_procedure requires COM automation (WinComAdapter)")

    def export_form_to_text(self, form_name: str) -> str:
        """Export a form definition to text — requires COM automation."""
        raise NotImplementedError("export_form_to_text requires COM automation (WinComAdapter)")

    def import_form_from_text(self, form_name: str, form_data: str) -> bool:
        """Import a form definition from text — requires COM automation."""
        raise NotImplementedError("import_form_from_text requires COM automation (WinComAdapter)")

    def export_report_to_text(self, report_name: str) -> str:
        """Export a report definition to text — requires COM automation."""
        raise NotImplementedError("export_report_to_text requires COM automation (WinComAdapter)")

    def import_report_from_text(self, report_name: str, report_data: str) -> bool:
        """Import a report definition from text — requires COM automation."""
        raise NotImplementedError("import_report_from_text requires COM automation (WinComAdapter)")

    def export_module_to_text(self, module_name: str) -> str:
        """Export a VBA module to text — requires COM automation."""
        raise NotImplementedError("export_module_to_text requires COM automation (WinComAdapter)")

    def export_macro_to_text(self, macro_name: str) -> str:
        """Export a macro to text — requires COM automation."""
        raise NotImplementedError("export_macro_to_text requires COM automation (WinComAdapter)")

    def export_all_versioning(self, output_dir: str) -> dict:
        """Export all versioned objects — requires COM automation."""
        raise NotImplementedError("export_all_versioning requires COM automation (WinComAdapter)")

    def export_query_to_text(self, query_name: str) -> str:
        """Export a query definition to text — requires COM automation."""
        raise NotImplementedError("export_query_to_text requires COM automation (WinComAdapter)")

    def import_query_from_text(self, query_name: str, query_data: str) -> bool:
        """Import a query definition from text — requires COM automation."""
        raise NotImplementedError("import_query_from_text requires COM automation (WinComAdapter)")

    def import_all_versioning(self, input_dir: str) -> dict:
        """Import all versioned objects from directory — requires COM automation."""
        raise NotImplementedError("import_all_versioning requires COM automation (WinComAdapter)")

    def compare_versioning(self, export_dir: str) -> dict:
        """Compare versioned objects — requires COM automation."""
        raise NotImplementedError("compare_versioning requires COM automation (WinComAdapter)")

    def execute_sql_script(self, script_path: str) -> dict:
        """Execute a SQL script file — requires COM automation."""
        raise NotImplementedError("execute_sql_script requires COM automation (WinComAdapter)")

    def execute_raw_sql(self, sql: str) -> int:
        """Execute raw SQL via COM — requires WinComAdapter."""
        raise NotImplementedError("execute_raw_sql requires COM automation (WinComAdapter)")

    # ========================================================================
    # Linked Tables (ISchemaAdapter — COM-only)
    # ========================================================================

    def get_linked_tables(self) -> dict:
        """Get linked tables — requires COM automation."""
        raise NotImplementedError("get_linked_tables requires COM automation (WinComAdapter)")

    def create_linked_table(self, name: str, source_table: str, connect_string: str) -> dict:
        """Create a linked table — requires COM automation."""
        raise NotImplementedError("create_linked_table requires COM automation (WinComAdapter)")

    def refresh_linked_table(self, name: str) -> dict:
        """Refresh a linked table — requires COM automation."""
        raise NotImplementedError("refresh_linked_table requires COM automation (WinComAdapter)")

    def unlink_table(self, name: str) -> dict:
        """Unlink a table — requires COM automation."""
        raise NotImplementedError("unlink_table requires COM automation (WinComAdapter)")