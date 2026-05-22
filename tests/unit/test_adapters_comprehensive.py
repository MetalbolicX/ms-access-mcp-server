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