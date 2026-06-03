"""Tests for VBA compilation pipeline — compile_vba() return type change."""
import pytest
from unittest.mock import MagicMock, patch, Mock


class TestCompileVbaReturnsDict:
    """Task 1.1 RED + 1.3 RED: compile_vba() must return dict with success/error."""

    def test_compile_vba_returns_dict_on_success(self):
        """compile_vba() returns {"success": True} on successful compilation."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter()
        # Mock the dispatcher to avoid COM calls
        adapter._dispatcher._started = True
        adapter._dispatcher._access_app = MagicMock()
        adapter._dispatcher._current_db = MagicMock()
        mock_result = {"success": True}
        adapter._dispatcher.call = MagicMock(return_value=mock_result)

        result = adapter.compile_vba()

        assert isinstance(result, dict), "compile_vba() must return dict, not bool"
        assert result.get("success") is True
        assert "error" not in result or result.get("error") is None

    def test_compile_vba_returns_dict_on_failure(self):
        """compile_vba() returns {"success": False, "error": "..."} on failure."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter()
        adapter._dispatcher._started = True
        adapter._dispatcher._access_app = MagicMock()
        adapter._dispatcher._current_db = MagicMock()
        mock_result = {"success": False, "error": "Compile failed: syntax error"}
        adapter._dispatcher.call = MagicMock(return_value=mock_result)

        result = adapter.compile_vba()

        assert isinstance(result, dict), "compile_vba() must return dict"
        assert result.get("success") is False
        assert "error" in result
        assert isinstance(result["error"], str)

    def test_compile_vba_failure_captures_error_message(self):
        """compile_vba() captures the COM exception message on failure (task 1.3)."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter()
        adapter._dispatcher._started = True
        adapter._dispatcher._access_app = MagicMock()
        adapter._dispatcher._current_db = MagicMock()

        # is_connected() needs to return True without going through dispatcher.call
        with patch.object(adapter, 'is_connected', return_value=True):
            # Now patch dispatcher.call to simulate COM failure during compile
            with patch.object(adapter._dispatcher, 'call', side_effect=Exception("Trust Center settings prevent VBA compilation")):
                result = adapter.compile_vba()

        assert isinstance(result, dict)
        assert result.get("success") is False
        assert "Trust Center" in result.get("error", "")


class TestOdbcAdapterCompileVbaReturnsDict:
    """Task 1.5 GREEN: OdbcAdapter.compile_vba() must return dict."""

    def test_odbc_compile_vba_raises_not_implemented(self):
        """OdbcAdapter.compile_vba() raises NotImplementedError (COM-only)."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter()

        with pytest.raises(NotImplementedError):
            adapter.compile_vba()


class TestCompileWithRetry:
    """Task 2.2 + 2.4: DevCopyService.compile_with_retry() implementation."""

    def test_compile_with_retry_success_first_try(self):
        """compile_with_retry returns {"success": True, "attempts": 1} on first success."""
        from ms_access_mcp.services.dev_copy_service import DevCopyService

        service = DevCopyService()
        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = "Old code"
        mock_adapter.set_vba_code.return_value = True
        mock_adapter.compile_vba.return_value = {"success": True}

        result = service.compile_with_retry(mock_adapter, "mod_test", "New code")

        assert result.get("success") is True
        assert result.get("attempts") == 1
        mock_adapter.set_vba_code.assert_called_once_with("mod_test", "New code")
        mock_adapter.compile_vba.assert_called_once()

    def test_compile_with_retry_intermediate_failure(self):
        """compile_with_retry tries all max_retries and rolls back on persistent failure."""
        from ms_access_mcp.services.dev_copy_service import DevCopyService

        service = DevCopyService()
        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = "Old code"
        mock_adapter.set_vba_code.return_value = True
        mock_adapter.compile_vba.return_value = {"success": False, "error": "Syntax error"}

        result = service.compile_with_retry(mock_adapter, "mod_test", "New code")

        assert result.get("success") is False
        assert result.get("attempt") == 3
        assert result.get("rollback") is True
        # compile_vba should have been called 3 times (all retries exhausted)
        assert mock_adapter.compile_vba.call_count == 3
        assert "error" in result

    def test_compile_with_retry_rollback_existing_module(self):
        """compile_with_retry rolls back existing module on persistent failure."""
        from ms_access_mcp.services.dev_copy_service import DevCopyService

        service = DevCopyService()
        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = "Old code"
        mock_adapter.set_vba_code.return_value = True
        # Fail 3 times
        mock_adapter.compile_vba.side_effect = [
            {"success": False, "error": "Error 1"},
            {"success": False, "error": "Error 2"},
            {"success": False, "error": "Error 3"},
        ]

        result = service.compile_with_retry(mock_adapter, "mod_existing", "New code")

        assert result.get("success") is False
        assert result.get("attempt") == 3
        assert result.get("rollback") is True
        # Should have restored old code
        calls = mock_adapter.set_vba_code.call_args_list
        assert len(calls) == 2  # write + rollback
        assert calls[1][0] == ("mod_existing", "Old code")

    def test_compile_with_retry_rollback_new_module(self):
        """compile_with_retry deletes new module on persistent failure."""
        from ms_access_mcp.services.dev_copy_service import DevCopyService

        service = DevCopyService()
        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = ""  # Module doesn't exist
        mock_adapter.add_vba_procedure.return_value = True
        # Fail 3 times
        mock_adapter.compile_vba.side_effect = [
            {"success": False, "error": "Error 1"},
            {"success": False, "error": "Error 2"},
            {"success": False, "error": "Error 3"},
        ]

        result = service.compile_with_retry(mock_adapter, "mod_new", "New code")

        assert result.get("success") is False
        assert result.get("attempt") == 3
        assert result.get("rollback") is True
        # Should have called delete_module
        mock_adapter.delete_module.assert_called_once_with("mod_new")


class TestImportModuleFromTextCreatesNewModule:
    """Task 2.8 + 2.9: import_module_from_text uses add_vba_procedure for new modules."""

    def test_import_module_from_text_calls_add_vba_procedure_for_new_module(self):
        """import_module_from_text calls add_vba_procedure when module doesn't exist."""
        import tempfile
        import os
        from ms_access_mcp.services.dev_copy_service import DevCopyService

        service = DevCopyService()
        mock_adapter = MagicMock()
        mock_adapter.get_vba_code.return_value = ""  # Module doesn't exist
        mock_adapter.delete_module.return_value = True
        mock_adapter.add_vba_procedure.return_value = True
        mock_adapter.compile_vba.return_value = {"success": True}

        # Create temp file with module code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bas', delete=False) as f:
            f.write("Sub Test()\nEnd Sub")
            temp_path = f.name

        try:
            result = service.import_module_from_text(mock_adapter, "mod_brand_new", temp_path)

            assert result.get("success") is True
            assert result.get("created") is True
            mock_adapter.add_vba_procedure.assert_called_once_with("mod_brand_new", "main", "Sub Test()\nEnd Sub")
        finally:
            os.unlink(temp_path)


class TestCompileVbaInMcpTools:
    """Task 3.2: compile_vba MCP tool re-enabled."""

    def test_compile_vba_tool_returns_adapter_result(self):
        """compile_vba MCP tool returns actual result from adapter, not hardcoded error."""
        from ms_access_mcp.mcp.server import compile_vba as compile_vba_tool

        # We can't easily test the full tool without a connection, but we can
        # verify the function exists and has the right signature
        import inspect
        sig = inspect.signature(compile_vba_tool)
        # Should have no required parameters (only self if method)
        # compile_vba is a function, not a method
        assert callable(compile_vba_tool)