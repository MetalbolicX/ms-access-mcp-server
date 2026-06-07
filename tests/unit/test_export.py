"""Tests for mcp/export.py — single export_data tool."""
import pytest
from unittest.mock import patch, MagicMock

# Import server first to resolve circular dependency
from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import export as export_module


class TestExportDataConnectionGuard:
    """Tests that export_data checks connection state."""

    def test_returns_error_when_not_connected(self):
        """export_data should return error when not connected."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = False
        with patch.object(export_module, '_pool', return_value=mock_pool):
            result = server.export_data("SELECT * FROM [T]", "/tmp/out.csv")
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_returns_error_when_no_adapter(self):
        """export_data should return error when no adapter available."""
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.side_effect = KeyError("default")
        with patch.object(export_module, '_pool', return_value=mock_pool):
            result = server.export_data("SELECT * FROM [T]", "/tmp/out.csv")
            assert result["success"] is False
            assert "No adapter" in result["error"]


class TestExportDataCsv:
    """export_data(format='csv') delegates to adapter.export_data."""

    def test_delegates_to_adapter(self):
        """export_data should delegate to adapter.export_data."""
        mock_adapter = MagicMock()
        mock_adapter.export_data.return_value = {
            "success": True, "rows_exported": 42, "file_path": "/tmp/out.csv",
        }
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        with patch.object(export_module, '_pool', return_value=mock_pool):
            result = server.export_data(
                "SELECT * FROM [Customers]", "/tmp/out.csv",
                format="csv", delimiter=",", header=True, encoding="utf-8",
            )
            assert result["success"] is True
            assert result["rows_exported"] == 42

            # Verify adapter.export_data was called with correct args
            mock_adapter.export_data.assert_called_once_with(
                "SELECT * FROM [Customers]", "/tmp/out.csv", "csv",
                delimiter=",", header=True, encoding="utf-8",
            )

    def test_returns_error_on_adapter_failure(self):
        """export_data should return error on adapter failure."""
        mock_adapter = MagicMock()
        mock_adapter.export_data.return_value = {
            "success": False, "error": "File not found",
        }
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        with patch.object(export_module, '_pool', return_value=mock_pool):
            result = server.export_data("SELECT * FROM [Bad]", "/tmp/out.csv")
            assert result["success"] is False
            assert "File not found" in result["error"]


class TestExportDataJson:
    """export_data(format='json') delegates to adapter.export_data."""

    def test_delegates_to_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.export_data.return_value = {
            "success": True, "rows_exported": 10, "file_path": "/tmp/out.json",
        }
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        with patch.object(export_module, '_pool', return_value=mock_pool):
            result = server.export_data(
                "SELECT * FROM [Q]", "/tmp/out.json",
                format="json", pretty=True,
            )
            assert result["success"] is True
            mock_adapter.export_data.assert_called_once_with(
                "SELECT * FROM [Q]", "/tmp/out.json", "json",
                pretty=True,
            )


class TestExportDataExcel:
    """export_data(format='excel') delegates to adapter.export_data."""

    def test_delegates_to_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.export_data.return_value = {
            "success": True, "rows_exported": 5, "file_path": "/tmp/out.xlsx",
        }
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter
        with patch.object(export_module, '_pool', return_value=mock_pool):
            result = server.export_data(
                "SELECT * FROM [Data]", "/tmp/out.xlsx",
                format="excel", sheet_name="Report",
            )
            assert result["success"] is True
            mock_adapter.export_data.assert_called_once_with(
                "SELECT * FROM [Data]", "/tmp/out.xlsx", "excel",
                sheet_name="Report",
            )
