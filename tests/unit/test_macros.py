"""Tests for mcp/macros.py tool bindings — PR3 macros-crud."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import macros as macros_module


class TestMacroExists:
    """Tests for macro_exists tool."""

    def test_macro_exists_returns_true_when_exists(self):
        """macro_exists should return exists=True when macro is found."""
        mock_adapter = MagicMock()
        mock_adapter.macro_exists.return_value = True
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.macro_exists("TestMacro")
            assert result["success"] is True
            assert result["exists"] is True
            assert result["macro"] == "TestMacro"

    def test_macro_exists_returns_false_when_not_found(self):
        """macro_exists should return exists=False when macro not found."""
        mock_adapter = MagicMock()
        mock_adapter.macro_exists.return_value = False
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.macro_exists("NonExistent")
            assert result["success"] is True
            assert result["exists"] is False
            assert result["macro"] == "NonExistent"

    def test_macro_exists_returns_error_when_not_connected(self):
        """macro_exists should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.macro_exists("TestMacro")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestGetMacros:
    """Tests for get_macros tool (moved from com.py)."""

    def test_get_macros_returns_macro_list(self):
        """get_macros should return success with macro list."""
        mock_macro = MagicMock()
        mock_macro.model_dump.return_value = {"name": "TestMacro", "type": "Macro"}
        mock_adapter = MagicMock()
        mock_adapter.get_macros.return_value = [mock_macro]
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.get_macros()
            assert result["success"] is True
            assert result["count"] == 1
            assert result["macros"][0]["name"] == "TestMacro"

    def test_get_macros_empty_returns_zero_count(self):
        """get_macros with no macros should return empty list with count 0."""
        mock_adapter = MagicMock()
        mock_adapter.get_macros.return_value = []
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.get_macros()
            assert result["success"] is True
            assert result["count"] == 0
            assert result["macros"] == []

    def test_get_macros_returns_error_when_not_connected(self):
        """get_macros should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.get_macros()
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestGetMacroProperties:
    """Tests for get_macro_properties tool."""

    def test_get_macro_properties_success_returns_dict(self):
        """get_macro_properties should return success with properties dict."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_macro_properties.return_value = {"Name": "TestMacro", "Type": "Macro"}
        with patch.object(macros_module, '_pool', return_value=mock_conn), \
             patch.object(macros_module, '_com', return_value=mock_com):
            result = server.get_macro_properties("TestMacro")
            assert result["success"] is True
            assert result["macro"] == "TestMacro"
            assert result["properties"]["Name"] == "TestMacro"
            mock_com.get_macro_properties.assert_called_once_with("TestMacro")

    def test_get_macro_properties_empty_returns_error(self):
        """get_macro_properties with empty dict should return success=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.get_macro_properties.return_value = {}
        with patch.object(macros_module, '_pool', return_value=mock_conn), \
             patch.object(macros_module, '_com', return_value=mock_com):
            result = server.get_macro_properties("NonExistent")
            assert result["success"] is False
            assert "not found" in result["error"].lower()

    def test_get_macro_properties_returns_error_when_not_connected(self):
        """get_macro_properties should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.get_macro_properties("TestMacro")
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestCreateMacro:
    """Tests for create_macro tool — destructive."""

    def test_create_macro_blocked_without_confirmation(self):
        """create_macro with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.create_macro("NewMacro", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_create_macro_dry_run_returns_preview(self):
        """create_macro with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.create_macro("NewMacro", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "create_macro"
            assert result["macro_name"] == "NewMacro"

    def test_create_macro_success_with_confirmation(self):
        """create_macro with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.create_macro.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn), \
             patch.object(macros_module, '_com', return_value=mock_com):
            result = server.create_macro("NewMacro", confirm=True)
            assert result["success"] is True
            assert result["macro"] == "NewMacro"
            mock_com.create_macro.assert_called_once_with("NewMacro")

    def test_create_macro_returns_error_when_not_connected(self):
        """create_macro should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.create_macro("NewMacro", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestRenameMacro:
    """Tests for rename_macro tool — destructive."""

    def test_rename_macro_blocked_without_confirmation(self):
        """rename_macro with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.rename_macro("OldName", "NewName", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_rename_macro_dry_run_returns_preview(self):
        """rename_macro with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.rename_macro("OldName", "NewName", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "rename_macro"
            assert result["old_name"] == "OldName"
            assert result["new_name"] == "NewName"

    def test_rename_macro_success_with_confirmation(self):
        """rename_macro with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.rename_macro.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn), \
             patch.object(macros_module, '_com', return_value=mock_com):
            result = server.rename_macro("OldName", "NewName", confirm=True)
            assert result["success"] is True
            assert result["old_name"] == "OldName"
            assert result["new_name"] == "NewName"
            mock_com.rename_macro.assert_called_once_with("OldName", "NewName")

    def test_rename_macro_returns_error_when_not_connected(self):
        """rename_macro should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.rename_macro("OldName", "NewName", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestDeleteMacro:
    """Tests for delete_macro tool — destructive."""

    def test_delete_macro_blocked_without_confirmation(self):
        """delete_macro with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.delete_macro("OldMacro", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_delete_macro_dry_run_returns_preview(self):
        """delete_macro with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.delete_macro("OldMacro", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "delete_macro"
            assert result["macro_name"] == "OldMacro"

    def test_delete_macro_success_with_confirmation(self):
        """delete_macro with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.delete_macro.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn), \
             patch.object(macros_module, '_com', return_value=mock_com):
            result = server.delete_macro("OldMacro", confirm=True)
            assert result["success"] is True
            assert result["macro"] == "OldMacro"
            mock_com.delete_macro.assert_called_once_with("OldMacro")

    def test_delete_macro_returns_error_when_not_connected(self):
        """delete_macro should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.delete_macro("OldMacro", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestRunMacro:
    """Tests for run_macro tool — destructive."""

    def test_run_macro_blocked_without_confirmation(self):
        """run_macro with confirm=False should be blocked by guard."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.run_macro("TaskMacro", confirm=False)
            assert result["success"] is False
            assert "confirm=True required" in result["error"]

    def test_run_macro_dry_run_returns_preview(self):
        """run_macro with dry_run=True should return preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.run_macro("TaskMacro", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "run_macro"
            assert result["macro_name"] == "TaskMacro"

    def test_run_macro_success_with_confirmation(self):
        """run_macro with confirm=True should delegate to COM service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_com = MagicMock()
        mock_com.run_macro.return_value = True
        with patch.object(macros_module, '_pool', return_value=mock_conn), \
             patch.object(macros_module, '_com', return_value=mock_com):
            result = server.run_macro("TaskMacro", confirm=True)
            assert result["success"] is True
            assert result["macro"] == "TaskMacro"
            mock_com.run_macro.assert_called_once_with("TaskMacro")

    def test_run_macro_returns_error_when_not_connected(self):
        """run_macro should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(macros_module, '_pool', return_value=mock_conn):
            result = server.run_macro("TaskMacro", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]
