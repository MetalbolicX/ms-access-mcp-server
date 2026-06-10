"""Com-only adapter mixin — provides NotImplementedError stubs for all COM-only operations.

OdbcAdapter inherits this mixin to satisfy the IUiAdapter protocol without
requiring COM automation. Each stub raises NotImplementedError("requires COM automation").

Methods that OdbcAdapter implements itself (ODBC data operations) are NOT in this mixin:
- execute_query, insert_data, update_data, delete_data (IDataAdapter)
- export_data (IDataAdapter)
- get_tables, get_queries, create_query, set_query_sql, delete_query, create_table, delete_table (ISchemaAdapter)
- get_linked_tables, create_linked_table, refresh_linked_table, unlink_table (ISchemaAdapter)
- export_schema_ddl (ISchemaAdapter)
- compact_repair (returns error dict), copy_database (returns False)

The mixin satisfies the protocol requirement that all IUiAdapter methods exist,
while OdbcAdapter's own implementations override these stubs for the methods it supports
(like copy_database which returns False instead of raising).
"""

from typing import Any


class ComOnlyAdapterMixin:
    """NotImplementedError stubs for COM-only IUiAdapter methods.

    OdbcAdapter inherits from both IDataAdapter/ISchemaAdapter and this mixin.
    The mixin satisfies the protocol requirement that all IUiAdapter methods exist,
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

    def create_module(self, module_name: str, module_type: int = 1) -> bool:
        """Create a VBA module — requires COM automation."""
        raise NotImplementedError("create_module requires COM automation (WinComAdapter)")

    def rename_module(self, old_name: str, new_name: str) -> bool:
        """Rename a VBA module — requires COM automation."""
        raise NotImplementedError("rename_module requires COM automation (WinComAdapter)")

    def module_exists(self, module_name: str) -> bool:
        """Check if a VBA module exists — requires COM automation."""
        raise NotImplementedError("module_exists requires COM automation (WinComAdapter)")

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

    # ========================================================================
    # Macro CRUD operations (COM-only)
    # ========================================================================

    def macro_exists(self, macro_name: str) -> bool:
        """Check if a macro exists — requires COM automation."""
        raise NotImplementedError("macro_exists requires COM automation (WinComAdapter)")

    def create_macro(self, macro_name: str) -> bool:
        """Create an empty macro — requires COM automation."""
        raise NotImplementedError("create_macro requires COM automation (WinComAdapter)")

    def rename_macro(self, old_name: str, new_name: str) -> bool:
        """Rename a macro — requires COM automation."""
        raise NotImplementedError("rename_macro requires COM automation (WinComAdapter)")

    def delete_macro(self, macro_name: str) -> bool:
        """Delete a macro — requires COM automation."""
        raise NotImplementedError("delete_macro requires COM automation (WinComAdapter)")

    # ========================================================================
    # Relation operations (COM-only)
    # ========================================================================

    def create_relationship(self, table_name: str, relationship_name: str, columns: list[str], foreign_table: str, foreign_columns: list[str]) -> dict:
        """Create a foreign key relationship — requires COM automation."""
        raise NotImplementedError("create_relationship requires COM automation (WinComAdapter)")

    def delete_relationship(self, table_name: str, relationship_name: str) -> dict:
        """Delete a foreign key relationship — requires COM automation."""
        raise NotImplementedError("delete_relationship requires COM automation (WinComAdapter)")

    def run_macro(self, macro_name: str) -> bool:
        """Execute a macro — requires COM automation."""
        raise NotImplementedError("run_macro requires COM automation (WinComAdapter)")

    def get_macro_properties(self, macro_name: str) -> dict:
        """Get all properties of a macro — requires COM automation."""
        raise NotImplementedError("get_macro_properties requires COM automation (WinComAdapter)")

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

    def refresh_linked_table(self, name: str, connect_string: str | None = None) -> dict:
        """Refresh a linked table — requires COM automation."""
        raise NotImplementedError("refresh_linked_table requires COM automation (WinComAdapter)")

    def recreate_linked_table(self, name: str, source_table: str, connect_string: str, attributes: int | None = None) -> dict:
        """Recreate a linked table (delete + create) — requires COM automation."""
        raise NotImplementedError("recreate_linked_table requires COM automation (WinComAdapter)")

    def unlink_table(self, name: str) -> dict:
        """Unlink a table — requires COM automation."""
        raise NotImplementedError("unlink_table requires COM automation (WinComAdapter)")

    # ========================================================================
    # Form-level manipulation (COM-only)
    # ========================================================================

    def create_form(self, form_name: str, record_source: str = "", template_name: str = "", properties: dict[str, Any] | None = None) -> bool:
        """Create a new form — requires COM automation."""
        raise NotImplementedError("create_form requires COM automation (WinComAdapter)")

    def rename_form(self, old_name: str, new_name: str) -> bool:
        """Rename a form — requires COM automation."""
        raise NotImplementedError("rename_form requires COM automation (WinComAdapter)")

    def get_form_properties(self, form_name: str) -> dict:
        """Get all properties of a form — requires COM automation."""
        raise NotImplementedError("get_form_properties requires COM automation (WinComAdapter)")

    def set_form_property(self, form_name: str, property_name: str, value: str) -> bool:
        """Set a single form property — requires COM automation."""
        raise NotImplementedError("set_form_property requires COM automation (WinComAdapter)")

    def set_form_properties(self, form_name: str, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple form properties at once — requires COM automation."""
        raise NotImplementedError("set_form_properties requires COM automation (WinComAdapter)")

    def add_control(self, form_name: str, control_type: str, control_name: str, section: int = 0, properties: dict[str, Any] | None = None) -> bool:
        """Add a control to a form — requires COM automation."""
        raise NotImplementedError("add_control requires COM automation (WinComAdapter)")

    def remove_control(self, form_name: str, control_name: str) -> bool:
        """Remove a control from a form — requires COM automation."""
        raise NotImplementedError("remove_control requires COM automation (WinComAdapter)")

    # Form section manipulation (COM-only)
    def get_form_sections(self, form_name: str) -> list:
        """Get all sections of a form — requires COM automation."""
        raise NotImplementedError("get_form_sections requires COM automation (WinComAdapter)")

    def get_form_section_properties(self, form_name: str, section_id: int) -> dict:
        """Get all properties of a form section — requires COM automation."""
        raise NotImplementedError("get_form_section_properties requires COM automation (WinComAdapter)")

    def set_form_section_property(self, form_name: str, section_id: int, property_name: str, value: str) -> bool:
        """Set a single property of a form section — requires COM automation."""
        raise NotImplementedError("set_form_section_property requires COM automation (WinComAdapter)")

    def set_form_section_properties(self, form_name: str, section_id: int, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple properties of a form section at once — requires COM automation."""
        raise NotImplementedError("set_form_section_properties requires COM automation (WinComAdapter)")

    def set_control_event_procedure(self, form_name: str, control_name: str, event_name: str, code: str) -> bool:
        """Set a control's event procedure — requires COM automation."""
        raise NotImplementedError("set_control_event_procedure requires COM automation (WinComAdapter)")

    # ========================================================================
    # Database property operations (COM-only)
    # ========================================================================

    def get_database_properties(self, names=None) -> dict:
        """Get database properties — requires COM automation."""
        raise NotImplementedError("get_database_properties requires COM automation (WinComAdapter)")

    def set_database_property(self, name: str, value: str, type: str | None = None) -> bool:
        """Set a database property — requires COM automation."""
        raise NotImplementedError("set_database_property requires COM automation (WinComAdapter)")
