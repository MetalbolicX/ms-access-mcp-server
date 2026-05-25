import os
import tempfile
import pytest
from ms_access_mcp.adapters.wincom import WinComAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.base import AccessAdapter


class TestProtocolCompliance:
    def test_wincom_adapter_isinstance_access_adapter(self):
        adapter = WinComAdapter()
        assert isinstance(adapter, AccessAdapter)

    def test_odbc_adapter_isinstance_access_adapter(self):
        adapter = OdbcAdapter()
        assert isinstance(adapter, AccessAdapter)


class TestWinComAdapterNotConnected:
    """Test that WinComAdapter returns safe defaults when not connected."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_get_tables_returns_empty_when_not_connected(self):
        assert self.adapter.get_tables() == []

    def test_execute_query_returns_empty_when_not_connected(self):
        assert self.adapter.execute_query("SELECT 1") == []

    def test_get_forms_returns_empty_when_not_connected(self):
        assert self.adapter.get_forms() == []

    def test_get_reports_returns_empty_when_not_connected(self):
        assert self.adapter.get_reports() == []

    def test_get_macros_returns_empty_when_not_connected(self):
        assert self.adapter.get_macros() == []

    def test_get_modules_returns_empty_when_not_connected(self):
        assert self.adapter.get_modules() == []

    def test_get_vba_code_returns_empty_when_not_connected(self):
        assert self.adapter.get_vba_code("mod") == ""

    def test_get_system_tables_returns_empty_when_not_connected(self):
        assert self.adapter.get_system_tables() == []

    def test_form_exists_returns_false_when_not_connected(self):
        assert self.adapter.form_exists("frm") is False

    def test_get_form_controls_returns_empty_when_not_connected(self):
        assert self.adapter.get_form_controls("frm") == []

    def test_export_form_to_text_returns_empty_when_not_connected(self):
        assert self.adapter.export_form_to_text("frm") == ""

    def test_import_form_from_text_returns_false_when_not_connected(self):
        assert self.adapter.import_form_from_text("data") is False

    def test_delete_form_returns_false_when_not_connected(self):
        assert self.adapter.delete_form("frm") is False

    def test_export_report_to_text_returns_empty_when_not_connected(self):
        assert self.adapter.export_report_to_text("rpt") == ""

    def test_import_report_from_text_returns_false_when_not_connected(self):
        assert self.adapter.import_report_from_text("data") is False

    def test_delete_report_returns_false_when_not_connected(self):
        assert self.adapter.delete_report("rpt") is False

    def test_add_vba_procedure_returns_false_when_not_connected(self):
        assert self.adapter.add_vba_procedure("mod", "proc", "code") is False

    def test_compile_vba_returns_false_when_not_connected(self):
        assert self.adapter.compile_vba() is False

    def test_get_object_metadata_returns_empty_when_not_connected(self):
        assert self.adapter.get_object_metadata("obj") == {}


class TestOdbcAdapterStubs:
    """Test that OdbcAdapter returns empty/false for COM-only operations."""

    def setup_method(self):
        self.adapter = OdbcAdapter()

    def test_get_forms_returns_empty(self):
        assert self.adapter.get_forms() == []

    def test_get_reports_returns_empty(self):
        assert self.adapter.get_reports() == []

    def test_get_macros_returns_empty(self):
        assert self.adapter.get_macros() == []

    def test_get_modules_returns_empty(self):
        assert self.adapter.get_modules() == []

    def test_get_vba_code_returns_empty(self):
        assert self.adapter.get_vba_code("mod") == ""

    def test_get_system_tables_returns_empty(self):
        assert self.adapter.get_system_tables() == []

    def test_form_exists_returns_false(self):
        assert self.adapter.form_exists("frm") is False

    def test_get_form_controls_returns_empty(self):
        assert self.adapter.get_form_controls("frm") == []

    def test_export_form_to_text_returns_empty(self):
        assert self.adapter.export_form_to_text("frm") == ""

    def test_import_form_from_text_returns_false(self):
        assert self.adapter.import_form_from_text("data") is False

    def test_delete_form_returns_false(self):
        assert self.adapter.delete_form("frm") is False

    def test_export_report_to_text_returns_empty(self):
        assert self.adapter.export_report_to_text("rpt") == ""

    def test_import_report_from_text_returns_false(self):
        assert self.adapter.import_report_from_text("data") is False

    def test_delete_report_returns_false(self):
        assert self.adapter.delete_report("rpt") is False

    def test_add_vba_procedure_returns_false(self):
        assert self.adapter.add_vba_procedure("mod", "proc", "code") is False

    def test_compile_vba_returns_false(self):
        assert self.adapter.compile_vba() is False

    def test_get_object_metadata_returns_empty(self):
        assert self.adapter.get_object_metadata("obj") == {}

    def test_launch_access_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.adapter.launch_access()

    def test_close_access_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.adapter.close_access()

    def test_set_vba_code_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.adapter.set_vba_code("mod", "code")


class TestOdbcAdapterEdgeCases:
    """Test OdbcAdapter edge case behavior."""

    def setup_method(self):
        self.adapter = OdbcAdapter()

    def test_connect_returns_false_for_nonexistent_path(self):
        assert self.adapter.connect("C:\\nonexistent\\path\\db.accdb") is False

    def test_disconnect_when_not_connected_no_crash(self):
        # Should not raise
        self.adapter.disconnect()

    def test_execute_query_returns_empty_when_not_connected(self):
        assert self.adapter.execute_query("SELECT 1") == []

    def test_get_tables_returns_empty_when_not_connected(self):
        assert self.adapter.get_tables() == []


class TestOdbcAdapterTypeMapping:
    """Test OdbcAdapter._pyodbc_type_name() method."""

    def setup_method(self):
        self.adapter = OdbcAdapter()

    def test_varchar_maps_to_text(self):
        assert self.adapter._pyodbc_type_name("VARCHAR") == "Text"

    def test_char_maps_to_text(self):
        assert self.adapter._pyodbc_type_name("CHAR") == "Text"

    def test_memo_maps_to_memo(self):
        assert self.adapter._pyodbc_type_name("MEMO") == "Memo"

    def test_integer_maps_to_long_integer(self):
        assert self.adapter._pyodbc_type_name("INTEGER") == "Long Integer"

    def test_int_maps_to_long_integer(self):
        assert self.adapter._pyodbc_type_name("INT") == "Long Integer"

    def test_bigint_maps_to_big_integer(self):
        assert self.adapter._pyodbc_type_name("BIGINT") == "Big Integer"

    def test_smallint_maps_to_integer(self):
        assert self.adapter._pyodbc_type_name("SMALLINT") == "Integer"

    def test_tinyint_maps_to_byte(self):
        assert self.adapter._pyodbc_type_name("TINYINT") == "Byte"

    def test_bit_maps_to_boolean(self):
        assert self.adapter._pyodbc_type_name("BIT") == "Boolean"

    def test_datetime_maps_to_datetime(self):
        assert self.adapter._pyodbc_type_name("DATETIME") == "Date/Time"

    def test_decimal_maps_to_decimal(self):
        assert self.adapter._pyodbc_type_name("DECIMAL") == "Decimal"

    def test_money_maps_to_currency(self):
        assert self.adapter._pyodbc_type_name("MONEY") == "Currency"

    def test_float_maps_to_double(self):
        assert self.adapter._pyodbc_type_name("FLOAT") == "Double"

    def test_real_maps_to_single(self):
        assert self.adapter._pyodbc_type_name("REAL") == "Single"

    def test_binary_maps_to_binary(self):
        assert self.adapter._pyodbc_type_name("BINARY") == "Binary"

    def test_varbinary_maps_to_binary(self):
        assert self.adapter._pyodbc_type_name("VARBINARY") == "Binary"

    def test_image_maps_to_binary(self):
        assert self.adapter._pyodbc_type_name("IMAGE") == "Binary"

    def test_guid_maps_to_guid(self):
        assert self.adapter._pyodbc_type_name("GUID") == "GUID"

    def test_unknown_type_returns_as_is(self):
        assert self.adapter._pyodbc_type_name("CUSTOM_TYPE") == "CUSTOM_TYPE"

    def test_lowercase_type_maps_correctly(self):
        assert self.adapter._pyodbc_type_name("varchar") == "Text"


class TestWinComAdapterADOPath:
    """Test ADO path availability for execute_sql_script."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_ado_conn_attribute_exists(self):
        assert hasattr(self.adapter, '_ado_conn')

    def test_ado_conn_is_none_when_not_connected(self):
        assert self.adapter._ado_conn is None


class TestWinComAdapterExecuteSqlScript:
    """Test execute_sql_script behavior."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_returns_error_when_not_connected(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("SELECT 1;")
            temp_path = f.name
        try:
            result = self.adapter.execute_sql_script(temp_path)
            assert result["success"] is False
            assert "not connected" in result["error"].lower()
        finally:
            os.unlink(temp_path)

    def test_file_not_found_returns_file_error(self):
        result = self.adapter.execute_sql_script("C:\\nonexistent\\path\\file.sql")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_empty_file_returns_error_when_not_connected(self):
        """Empty file returns error when adapter is not connected (can't validate file content)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("")
            temp_path = f.name
        try:
            result = self.adapter.execute_sql_script(temp_path)
            # Not connected → error before file content is even evaluated
            assert result["success"] is False
            assert "not connected" in result["error"].lower()
        finally:
            os.unlink(temp_path)

    def test_error_dict_contains_required_keys(self):
        """Error dict has required keys when adapter returns error."""
        result = self.adapter.execute_sql_script("C:\\nonexistent\\path\\file.sql")
        # Early return: file not found error dict
        assert "success" in result
        assert "statements_executed" in result
        assert "error" in result


class TestOdbcAdapterDeleteModule:
    """Test that delete_module returns False for OdbcAdapter (COM-only)."""

    def setup_method(self):
        self.adapter = OdbcAdapter()

    def test_delete_module_returns_false(self):
        """OdbcAdapter.delete_module returns False (COM-only operation)."""
        result = self.adapter.delete_module("any_module")
        assert result is False


class TestOdbcAdapterCopyDatabase:
    """Test that copy_database returns False for OdbcAdapter (COM-only)."""

    def setup_method(self):
        self.adapter = OdbcAdapter()

    def test_copy_database_returns_false(self):
        """OdbcAdapter.copy_database returns False (COM-only operation)."""
        result = self.adapter.copy_database("source.accdb", "dest.accdb")
        assert result is False


class TestOdbcAdapterSaveDatabase:
    """Test that save_database returns error dict for OdbcAdapter (COM-only)."""

    def setup_method(self):
        self.adapter = OdbcAdapter()

    def test_save_database_returns_error_dict(self):
        """OdbcAdapter.save_database returns error dict (COM-only operation)."""
        result = self.adapter.save_database()
        assert result["success"] is False
        assert "ODBC" in result["error"] or "not available" in result["error"].lower()


class TestAccessAdapterProtocol:
    """Test that the AccessAdapter protocol includes all expected methods."""

    def test_delete_module_in_protocol(self):
        assert hasattr(AccessAdapter, "delete_module")

    def test_copy_database_in_protocol(self):
        assert hasattr(AccessAdapter, "copy_database")

    def test_save_database_in_protocol(self):
        assert hasattr(AccessAdapter, "save_database")
        # engine is not present in early-return error cases