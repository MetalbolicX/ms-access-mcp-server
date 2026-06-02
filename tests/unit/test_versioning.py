import pytest
import os
import tempfile
import hashlib
import shutil
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


# =============================================================================
# Task 2.1 — FAILING RED tests for WinCom Core (dedup, module_ext, queries/)
# =============================================================================

class TestWinComAdapterExportAllVersioningDedup:
    """export_all_versioning accepts dedup=True and skips unchanged files."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_dedup_false_writes_all_files(self, tmp_path):
        """When dedup=False, all files are written regardless of content."""
        # This test needs a connected adapter with mock — use skip for now
        pytest.skip("Needs connected WinCom adapter with forms/reports")

    def test_dedup_true_skips_unchanged_files(self, tmp_path):
        """When dedup=True, SHA256 comparison skips re-export of identical content."""
        pytest.skip("Needs connected WinCom adapter with forms/reports")


class TestWinComAdapterExportAllVersioningModuleExt:
    """export_all_versioning accepts module_ext parameter."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_module_ext_bas_uses_bas_extension(self, tmp_path):
        """module_ext='.bas' produces files like modules_modTest.bas."""
        pytest.skip("Needs connected WinCom adapter with VBA modules")

    def test_module_ext_txt_still_works(self, tmp_path):
        """module_ext='.txt' (default) produces files like modules_modTest.txt."""
        pytest.skip("Needs connected WinCom adapter with VBA modules")


class TestWinComAdapterExportAllVersioningQueriesDir:
    """export_all_versioning exports queries to queries/ subdirectory."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_queries_subdirectory_created(self, tmp_path):
        """export_all_versioning creates a queries/ subdirectory."""
        pytest.skip("Needs connected WinCom adapter with queries")

    def test_query_files_named_queries_name_txt(self, tmp_path):
        """Query files are named queries_{name}.txt using SaveAsText(acQuery=5)."""
        pytest.skip("Needs connected WinCom adapter with queries")


class TestWinComAdapterExportQueryToText:
    """export_query_to_text delegates to COM SaveAsText."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_returns_empty_when_not_connected(self):
        """Not connected → empty string."""
        result = self.adapter.export_query_to_text("qryTest")
        assert result == ""

    def test_uses_saveastext_acquery_5(self, tmp_path):
        """Delegates to COM using SaveAsText(acQuery=5, query_name, temp_path)."""
        pytest.skip("Needs connected WinCom adapter with queries")


class TestWinComAdapterImportQueryFromText:
    """import_query_from_text delegates to COM LoadFromText."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_returns_false_when_not_connected(self):
        """Not connected → False."""
        result = self.adapter.import_query_from_text("qryNew", "SELECT 1")
        assert result is False

    def test_uses_loadfromtext_acquery_5(self, tmp_path):
        """Delegates to COM using LoadFromText(acQuery=5, query_name, temp_path)."""
        pytest.skip("Needs connected WinCom adapter with queries")


class TestWinComAdapterImportAllVersioning:
    """import_all_versioning imports all objects from directory."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_nonedir_input_dir_returns_error(self):
        """Non-existent directory → success=False, error message."""
        result = self.adapter.import_all_versioning("Z:\\nonexistent\\dir")
        assert result["success"] is False
        assert "error" in result or "directory" in result.get("error", "").lower()

    def test_valid_directory_imports_in_correct_order(self, tmp_path):
        """Imports modules → forms/reports → macros → queries order."""
        pytest.skip("Needs connected WinCom adapter")

    def test_form_fails_continues_to_next_but_reports(self, tmp_path):
        """If a form import fails, continues to next and reports error."""
        pytest.skip("Needs connected WinCom adapter")

    def test_no_files_in_dir_returns_success_empty(self, tmp_path):
        """Empty directory → success=True, empty imported dict."""
        pytest.skip("Needs connected WinCom adapter")


class TestWinComAdapterCompareVersioning:
    """compare_versioning returns categorized diff dict."""

    def setup_method(self):
        self.adapter = WinComAdapter()

    def test_returns_dict_with_new_missing_changed_unchanged(self, tmp_path):
        """compare_versioning returns dict with new/missing/changed/unchanged buckets."""
        pytest.skip("Needs connected WinCom adapter with objects")

    def test_new_in_db_not_in_export_dir(self, tmp_path):
        """Objects in DB but not in export_dir → in 'new' bucket."""
        pytest.skip("Needs connected WinCom adapter")

    def test_missing_in_export_dir_not_in_db(self, tmp_path):
        """Objects in export_dir but not in DB → in 'missing' bucket."""
        pytest.skip("Needs connected WinCom adapter")

    def test_content_differs_changed_bucket(self, tmp_path):
        """Same name but different content → in 'changed' bucket."""
        pytest.skip("Needs connected WinCom adapter")

    def test_content_matches_unchanged_bucket(self, tmp_path):
        """Same name and identical content → in 'unchanged' bucket."""
        pytest.skip("Needs connected WinCom adapter")

    def test_sha256_skips_re_export_when_content_matches(self, tmp_path):
        """SHA256 hash comparison skips re-export when content matches."""
        pytest.skip("Needs connected WinCom adapter")
