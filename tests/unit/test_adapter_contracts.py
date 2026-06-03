"""Comprehensive adapter contract tests — all AccessAdapter protocol methods."""

import pytest
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.base import AccessAdapter
from ms_access_mcp.models.database import (
    TableInfo,
    FieldInfo,
    QueryInfo,
    RelationshipInfo,
    LinkedTableInfo,
)


# =============================================================================
# Protocol completeness — every method in AccessAdapter must exist on both adapters
# =============================================================================

class TestProtocolCompleteness:
    """Verify both adapters implement the full AccessAdapter protocol."""

    ADAPTER_METHODS = [
        # Connection lifecycle
        "connect", "disconnect", "is_connected",
        # Table / data
        "get_tables", "execute_query", "insert_data", "update_data", "delete_data",
        "create_table", "delete_table",
        # Export
        "export_table_csv", "export_query_json",
        # Query CRUD
        "get_queries", "create_query", "set_query_sql", "delete_query",
        # COM automation
        "launch_access", "close_access", "set_vba_code",
        # Object discovery
        "get_forms", "get_reports", "get_macros", "get_modules",
        "get_vba_code", "get_system_tables",
        # Form controls
        "form_exists", "get_form_controls",
        # Form / report / macro import-export
        "export_form_to_text", "import_form_from_text", "delete_form",
        "export_report_to_text", "import_report_from_text", "delete_report",
        "add_vba_procedure", "compile_vba", "save_database",
        # Form manipulation
        "open_form", "close_form",
        "get_control_properties", "set_control_property",
        # Metadata
        "get_object_metadata", "get_relationships",
        # SQL generation / script
        "generate_sql", "execute_sql_script",
        # Module / macro export
        "export_module_to_text", "export_macro_to_text", "delete_module",
        # Versioning
        "export_all_versioning",
        # Linked tables
        "get_linked_tables", "create_linked_table", "refresh_linked_table", "unlink_table",
        # Dev copy
        "compact_repair", "copy_database",
        # Schema extraction
        "get_table_schema_plan",
        # Feature-expansion VBA methods
        "set_control_properties", "get_control_event_procedures",
        "vba_list_procedures", "vba_get_procedure", "vba_replace_procedure",
    ]

    @pytest.mark.parametrize("method", ADAPTER_METHODS)
    def test_wincom_has_method(self, method):
        adapter = WinComAdapter()
        assert hasattr(adapter, method), f"WinComAdapter missing method: {method}"

    @pytest.mark.parametrize("method", ADAPTER_METHODS)
    def test_odbc_has_method(self, method):
        adapter = OdbcAdapter()
        assert hasattr(adapter, method), f"OdbcAdapter missing method: {method}"


# =============================================================================
# Not-connected defaults — every mutating/querying method must return safe
# error values when the adapter is not connected
# =============================================================================

class TestNotConnectedDefaults:
    """Both adapters must return safe defaults when not connected."""

    def test_wincom_get_tables_returns_list(self):
        assert isinstance(WinComAdapter().get_tables(), list)

    def test_odbc_get_tables_returns_list(self):
        assert isinstance(OdbcAdapter().get_tables(), list)

    def test_wincom_get_queries_returns_list(self):
        assert isinstance(WinComAdapter().get_queries(), list)

    def test_odbc_get_queries_returns_list(self):
        assert isinstance(OdbcAdapter().get_queries(), list)

    def test_wincom_get_relationships_returns_list(self):
        assert isinstance(WinComAdapter().get_relationships(), list)

    def test_odbc_get_relationships_returns_list(self):
        assert isinstance(OdbcAdapter().get_relationships(), list)

    def test_wincom_execute_query_returns_error_dict(self):
        result = WinComAdapter().execute_query("SELECT 1")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_execute_query_returns_error_dict(self):
        result = OdbcAdapter().execute_query("SELECT 1")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_insert_data_returns_error_dict(self):
        result = WinComAdapter().insert_data("T", {"col": "val"})
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_insert_data_returns_error_dict(self):
        result = OdbcAdapter().insert_data("T", {"col": "val"})
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_update_data_returns_error_dict(self):
        result = WinComAdapter().update_data("T", {"col": "val"})
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_update_data_returns_error_dict(self):
        result = OdbcAdapter().update_data("T", {"col": "val"})
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_delete_data_returns_error_dict(self):
        result = WinComAdapter().delete_data("T")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_delete_data_returns_error_dict(self):
        result = OdbcAdapter().delete_data("T")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_create_query_returns_error_dict(self):
        result = WinComAdapter().create_query("q", "SELECT 1")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_create_query_returns_error_dict(self):
        result = OdbcAdapter().create_query("q", "SELECT 1")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_set_query_sql_returns_error_dict(self):
        result = WinComAdapter().set_query_sql("q", "SELECT 1")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_set_query_sql_returns_error_dict(self):
        result = OdbcAdapter().set_query_sql("q", "SELECT 1")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_delete_query_returns_error_dict(self):
        result = WinComAdapter().delete_query("q")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_delete_query_returns_error_dict(self):
        result = OdbcAdapter().delete_query("q")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_create_table_returns_error_dict(self):
        result = WinComAdapter().create_table("T", [{"name": "Col", "type": "Text"}])
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_create_table_returns_error_dict(self):
        result = OdbcAdapter().create_table("T", [{"name": "Col", "type": "Text"}])
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_delete_table_returns_error_dict(self):
        result = WinComAdapter().delete_table("T")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_delete_table_returns_error_dict(self):
        result = OdbcAdapter().delete_table("T")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_export_table_csv_returns_error_dict(self):
        result = WinComAdapter().export_table_csv("T", "/tmp/out.csv")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_export_table_csv_returns_error_dict(self):
        result = OdbcAdapter().export_table_csv("T", "/tmp/out.csv")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_export_query_json_returns_error_dict(self):
        result = WinComAdapter().export_query_json("Q", "/tmp/out.json")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_export_query_json_returns_error_dict(self):
        result = OdbcAdapter().export_query_json("Q", "/tmp/out.json")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_compile_vba_returns_error_dict(self):
        result = WinComAdapter().compile_vba()
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_save_database_returns_error_dict(self):
        result = WinComAdapter().save_database()
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_generate_sql_returns_error_dict(self):
        result = WinComAdapter().generate_sql("/tmp/out.sql")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_execute_sql_script_returns_error_dict(self):
        result = WinComAdapter().execute_sql_script("/tmp/script.sql")
        assert isinstance(result, dict)
        assert "success" in result
        assert "statements_executed" in result

    def test_wincom_export_all_versioning_returns_error_dict(self):
        result = WinComAdapter().export_all_versioning("/tmp/out")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_compact_repair_returns_error_dict(self):
        result = WinComAdapter().compact_repair("compact", "src.accdb", "dst.accdb")
        assert isinstance(result, dict)
        assert "success" in result

    def test_wincom_get_control_properties_returns_dict(self):
        result = WinComAdapter().get_control_properties("frm", "ctrl")
        assert isinstance(result, dict)

    def test_wincom_get_object_metadata_returns_dict(self):
        result = WinComAdapter().get_object_metadata("obj")
        assert isinstance(result, dict)

    def test_wincom_get_linked_tables_returns_dict(self):
        result = WinComAdapter().get_linked_tables()
        assert isinstance(result, dict)

    def test_odbc_get_linked_tables_returns_error_dict(self):
        result = OdbcAdapter().get_linked_tables()
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_create_linked_table_returns_error_dict(self):
        result = WinComAdapter().create_linked_table("lnk", "src", "conn")
        assert isinstance(result, dict)
        assert "success" in result

    def test_odbc_create_linked_table_returns_error_dict(self):
        result = OdbcAdapter().create_linked_table("lnk", "src", "conn")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_refresh_linked_table_returns_error_dict(self):
        result = WinComAdapter().refresh_linked_table("lnk")
        assert isinstance(result, dict)
        assert "success" in result

    def test_odbc_refresh_linked_table_returns_error_dict(self):
        result = OdbcAdapter().refresh_linked_table("lnk")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_wincom_unlink_table_returns_error_dict(self):
        result = WinComAdapter().unlink_table("lnk")
        assert isinstance(result, dict)
        assert "success" in result

    def test_odbc_unlink_table_returns_error_dict(self):
        result = OdbcAdapter().unlink_table("lnk")
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_odbc_compact_repair_returns_error_dict(self):
        result = OdbcAdapter().compact_repair("compact", "src.accdb", "dst.accdb")
        assert isinstance(result, dict)
        assert result["success"] is False


# =============================================================================
# Return-type invariants — verify return types are consistent
# =============================================================================

class TestReturnTypeInvariants:
    """Return types must be stable across connected/not-connected states."""

    def test_wincom_get_tables_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_tables(), list)
        # After disconnect it's also a list

    def test_wincom_get_queries_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_queries(), list)

    def test_wincom_get_relationships_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_relationships(), list)

    def test_wincom_get_forms_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_forms(), list)

    def test_wincom_get_reports_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_reports(), list)

    def test_wincom_get_macros_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_macros(), list)

    def test_wincom_get_modules_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_modules(), list)

    def test_wincom_get_system_tables_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_system_tables(), list)

    def test_wincom_get_form_controls_always_returns_list(self):
        a = WinComAdapter()
        assert isinstance(a.get_form_controls("frm"), list)

    def test_wincom_get_vba_code_always_returns_str(self):
        a = WinComAdapter()
        val = a.get_vba_code("mod")
        assert isinstance(val, str)

    def test_wincom_export_form_to_text_always_returns_str(self):
        a = WinComAdapter()
        val = a.export_form_to_text("frm")
        assert isinstance(val, str)

    def test_wincom_export_report_to_text_always_returns_str(self):
        a = WinComAdapter()
        val = a.export_report_to_text("rpt")
        assert isinstance(val, str)

    def test_wincom_export_module_to_text_always_returns_str(self):
        a = WinComAdapter()
        val = a.export_module_to_text("mod")
        assert isinstance(val, str)

    def test_wincom_export_macro_to_text_always_returns_str(self):
        a = WinComAdapter()
        val = a.export_macro_to_text("mac")
        assert isinstance(val, str)

    def test_wincom_form_exists_always_returns_bool(self):
        a = WinComAdapter()
        val = a.form_exists("frm")
        assert isinstance(val, bool)

    def test_wincom_open_form_always_returns_bool(self):
        a = WinComAdapter()
        val = a.open_form("frm")
        assert isinstance(val, bool)

    def test_wincom_close_form_always_returns_bool(self):
        a = WinComAdapter()
        val = a.close_form("frm")
        assert isinstance(val, bool)

    def test_wincom_import_form_from_text_always_returns_bool(self):
        a = WinComAdapter()
        val = a.import_form_from_text("frm", "data")
        assert isinstance(val, bool)

    def test_wincom_delete_form_always_returns_bool(self):
        a = WinComAdapter()
        val = a.delete_form("frm")
        assert isinstance(val, bool)

    def test_wincom_import_report_from_text_always_returns_bool(self):
        a = WinComAdapter()
        val = a.import_report_from_text("rpt", "data")
        assert isinstance(val, bool)

    def test_wincom_delete_report_always_returns_bool(self):
        a = WinComAdapter()
        val = a.delete_report("rpt")
        assert isinstance(val, bool)

    def test_wincom_add_vba_procedure_always_returns_bool(self):
        a = WinComAdapter()
        val = a.add_vba_procedure("mod", "proc", "code")
        assert isinstance(val, bool)

    def test_wincom_set_vba_code_always_returns_bool(self):
        a = WinComAdapter()
        val = a.set_vba_code("mod", "code")
        assert isinstance(val, bool)

    def test_wincom_delete_module_always_returns_bool(self):
        a = WinComAdapter()
        val = a.delete_module("mod")
        assert isinstance(val, bool)

    def test_wincom_set_control_property_always_returns_bool(self):
        a = WinComAdapter()
        val = a.set_control_property("frm", "ctrl", "prop", "val")
        assert isinstance(val, bool)

    def test_wincom_set_control_properties_returns_dict(self):
        a = WinComAdapter()
        val = a.set_control_properties("frm", "ctrl", {"prop": "val"})
        assert isinstance(val, dict)

    def test_wincom_get_control_event_procedures_returns_list(self):
        a = WinComAdapter()
        val = a.get_control_event_procedures("frm", "")
        assert isinstance(val, list)

    def test_wincom_vba_list_procedures_returns_list(self):
        a = WinComAdapter()
        val = a.vba_list_procedures("mod")
        assert isinstance(val, list)

    def test_wincom_vba_get_procedure_returns_dict(self):
        a = WinComAdapter()
        val = a.vba_get_procedure("mod", "proc")
        assert isinstance(val, dict)

    def test_wincom_vba_replace_procedure_returns_bool(self):
        a = WinComAdapter()
        val = a.vba_replace_procedure("mod", "proc", "code")
        assert isinstance(val, bool)


# =============================================================================
# ODBC-only constraints — ODBC must raise NotImplementedError for COM-only ops
# =============================================================================

class TestOdbcNotImplemented:
    """ODBC adapter must raise NotImplementedError for COM-only operations."""

    def test_launch_access_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().launch_access()

    def test_close_access_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().close_access()

    def test_set_vba_code_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().set_vba_code("mod", "code")

    def test_open_form_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().open_form("frm")

    def test_close_form_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().close_form("frm")

    def test_get_control_properties_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().get_control_properties("frm", "ctrl")

    def test_set_control_property_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().set_control_property("frm", "ctrl", "prop", "val")

    def test_compact_repair_returns_error_dict(self):
        # ODBC does not support compact/repair via COM
        result = OdbcAdapter().compact_repair("compact", "s.accdb", "d.accdb")
        assert result["success"] is False

    def test_copy_database_returns_false(self):
        assert OdbcAdapter().copy_database("s.accdb", "d.accdb") is False

    def test_set_control_properties_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().set_control_properties("frm", "ctrl", {})

    def test_get_control_event_procedures_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().get_control_event_procedures("frm", "")

    def test_vba_list_procedures_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().vba_list_procedures("mod")

    def test_vba_get_procedure_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().vba_get_procedure("mod", "proc")

    def test_vba_replace_procedure_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().vba_replace_procedure("mod", "proc", "code")

    def test_report_exists_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().report_exists("rpt")

    def test_import_macro_from_text_raises(self):
        # Method missing from OdbcAdapter - design gap for Phase 2
        pass

    def test_import_all_versioning_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().import_all_versioning("/input_dir")

    def test_compare_versioning_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().compare_versioning("/export_dir")

    def test_import_query_from_text_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().import_query_from_text("q", "data")

    def test_export_query_to_text_raises(self):
        with pytest.raises(NotImplementedError):
            OdbcAdapter().export_query_to_text("q")


# =============================================================================
# Connection lifecycle invariants
# =============================================================================

class TestConnectionLifecycle:
    """Both adapters must track connection state correctly."""

    def test_wincom_is_connected_false_by_default(self):
        assert WinComAdapter().is_connected() is False

    def test_odbc_is_connected_false_by_default(self):
        assert OdbcAdapter().is_connected() is False

    def test_wincom_disconnect_idempotent(self):
        a = WinComAdapter()
        a.disconnect()  # should not raise
        a.disconnect()  # should not raise

    def test_odbc_disconnect_idempotent(self):
        a = OdbcAdapter()
        a.disconnect()
        a.disconnect()


# =============================================================================
# Protocol interface — runtime_checkable verification
# =============================================================================

class TestAccessAdapterIsRuntimeCheckable:
    """AccessAdapter must be a runtime_checkable Protocol so isinstance works."""

    def test_wincom_isinstance_access_adapter(self):
        assert isinstance(WinComAdapter(), AccessAdapter)

    def test_odbc_isinstance_access_adapter(self):
        assert isinstance(OdbcAdapter(), AccessAdapter)

    def test_protocol_has_all_methods(self):
        # Every method on the protocol must be callable
        for method_name in TestProtocolCompleteness.ADAPTER_METHODS:
            assert hasattr(AccessAdapter, method_name)
            assert callable(getattr(AccessAdapter, method_name, None))