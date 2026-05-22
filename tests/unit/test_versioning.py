import pytest
import os
import tempfile
from ms_access_mcp.adapters.wincom import WinComAdapter


class TestWinComAdapterExportModuleToText:
    """export_module_to_text returns empty string when not connected."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_returns_empty_when_not_connected(self):
        result = self.adapter.export_module_to_text("modTest")
        assert result == ""


class TestWinComAdapterExportMacroToText:
    """export_macro_to_text returns empty string when not connected."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_returns_empty_when_not_connected(self):
        result = self.adapter.export_macro_to_text("mcrTest")
        assert result == ""


class TestWinComAdapterExportAllVersioning:
    """export_all_versioning returns error when not connected."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_returns_error_when_not_connected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.adapter.export_all_versioning(tmpdir)
            assert result["success"] is False
            assert "not connected" in result["error"].lower()

    def test_returns_error_for_invalid_directory(self):
        adapter = WinComAdapter()
        # Non-existent path with non-existent parent
        result = adapter.export_all_versioning("Z:\\nonexistent\\path")
        assert result["success"] is False


class TestOdbcAdapterVersioning:
    """ODBC adapter versioning returns empty/false (COM-only operations)."""

    def setup_method(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter
        self.adapter = OdbcAdapter()

    def test_export_module_to_text_returns_empty(self):
        # ODBC returns empty string for module export (not implemented)
        result = self.adapter.export_module_to_text("mod")
        assert result == ""

    def test_export_macro_to_text_returns_empty(self):
        # ODBC returns empty string for macro export (not implemented)
        result = self.adapter.export_macro_to_text("mcr")
        assert result == ""

    def test_export_all_versioning_raises(self):
        with pytest.raises(NotImplementedError):
            self.adapter.export_all_versioning("/tmp/out")
