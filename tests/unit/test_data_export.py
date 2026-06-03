"""Tests for adapter.export_data — CSV, JSON, Excel via strategy pattern."""

import csv
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ms_access_mcp.adapters.export.strategies import (
    CsvStrategy,
    ExportStrategySelector,
    JsonStrategy,
    ExcelStrategy,
)

SQL = "SELECT * FROM [Customers]"

# =============================================================================
# WinComAdapter — export_data
# =============================================================================


class TestWinComExportData:
    """WinComAdapter.export_data delegates to the strategy selector."""

    def _make_adapter(self, mock_execute_query=None, mock_execute_raw=None):
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.adapters.export.strategies import ExportStrategySelector

        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._strategy_selector = ExportStrategySelector()
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._started = True
        adapter.db = MagicMock()

        # Wire execute_query
        default_query_result = {
            "success": True,
            "rows": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            "count": 2,
            "columns": ["id", "name"],
        }
        adapter.execute_query = mock_execute_query or MagicMock(return_value=default_query_result)

        # Wire _execute_raw
        adapter._execute_raw = mock_execute_raw or MagicMock(return_value=2)

        return adapter

    # -- CSV ------------------------------------------------------------------

    def test_export_data_csv_fallback(self):
        """export_data(format='csv') with custom delimiter uses fallback."""
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")
            result = adapter.export_data(
                SQL, file_path, format="csv",
                delimiter=";", header=True, encoding="utf-8",
            )

            assert result["success"] is True
            assert result["rows_exported"] == 2
            assert result["file_path"] == file_path

            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                rows = list(reader)
            assert len(rows) == 2

    def test_export_data_csv_iisam(self):
        """export_data(format='csv') with defaults uses IISAM path."""
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")
            result = adapter.export_data(SQL, file_path, format="csv")

        assert result["success"] is True
        assert result["rows_exported"] == 2
        # IISAM path called via _execute_raw
        adapter._execute_raw.assert_called_once()
        call_sql = adapter._execute_raw.call_args[0][0]
        assert call_sql.startswith("INSERT INTO [Text;")

    def test_export_data_csv_no_header(self):
        """export_data with header=False passes option through."""
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")
            adapter.export_data(SQL, file_path, format="csv", header=False)

        call_sql = adapter._execute_raw.call_args[0][0]
        assert "HDR=NO" in call_sql

    # -- JSON -----------------------------------------------------------------

    def test_export_data_json(self):
        """export_data(format='json') writes JSON file."""
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.json")
            result = adapter.export_data(SQL, file_path, format="json")

            assert result["success"] is True
            assert result["rows_exported"] == 2

            with open(file_path) as f:
                data = json.load(f)
            assert len(data) == 2
            assert data[0]["name"] == "Alice"

    def test_export_data_json_pretty(self):
        """export_data with pretty=True produces indented JSON."""
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "pretty.json")
            adapter.export_data(SQL, file_path, format="json", pretty=True)

            with open(file_path) as f:
                content = f.read()
            assert "\n" in content
            assert "  " in content

    # -- Excel ----------------------------------------------------------------

    def test_export_data_excel_iisam(self):
        """export_data(format='excel') tries Excel IISAM path."""
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.xlsx")
            result = adapter.export_data(SQL, file_path, format="excel")

            assert result["success"] is True
            assert result["rows_exported"] == 2
        adapter._execute_raw.assert_called_once()
        call_sql = adapter._execute_raw.call_args[0][0]
        assert call_sql.startswith("INSERT INTO [Excel 12.0;")

    def test_export_data_excel_custom_sheet_name(self):
        """export_data passes sheet_name option."""
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.xlsx")
            adapter.export_data(SQL, file_path, format="excel", sheet_name="Report")

        call_sql = adapter._execute_raw.call_args[0][0]
        assert "[Report$]" in call_sql

    # -- Errors ---------------------------------------------------------------

    def test_export_data_not_connected(self):
        """export_data returns error when not connected."""
        adapter = self._make_adapter()
        adapter._dispatcher._started = False

        result = adapter.export_data(SQL, "/tmp/out.csv")
        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_export_data_unsupported_format(self):
        """export_data returns error for unknown format."""
        adapter = self._make_adapter()

        result = adapter.export_data(SQL, "/tmp/out.parquet", format="parquet")
        assert result["success"] is False
        assert "Unsupported export format" in result["error"]


# =============================================================================
# OdbcAdapter — export_data
# =============================================================================


class TestOdbcExportData:
    """OdbcAdapter.export_data delegates to the strategy selector."""

    def _make_adapter(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        default_query_result = {
            "success": True,
            "rows": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            "columns": ["id", "name"],
        }
        adapter.execute_query = MagicMock(return_value=default_query_result)

        adapter._strategy_selector = ExportStrategySelector()

        return adapter

    def test_export_data_csv_fallback(self):
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")
            result = adapter.export_data(SQL, file_path, format="csv", delimiter="|")

            assert result["success"] is True
            assert result["rows_exported"] == 2

            with open(file_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f, delimiter="|"))
            assert len(rows) == 2

    def test_export_data_json(self):
        adapter = self._make_adapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.json")
            result = adapter.export_data(SQL, file_path, format="json")

            assert result["success"] is True
            assert result["rows_exported"] == 2

            with open(file_path) as f:
                data = json.load(f)
            assert len(data) == 2

    def test_export_data_not_connected(self):
        adapter = self._make_adapter()
        adapter._conn = None

        result = adapter.export_data(SQL, "/tmp/out.csv")
        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_export_data_unsupported_format(self):
        adapter = self._make_adapter()

        result = adapter.export_data(SQL, "/tmp/out.parquet", format="parquet")
        assert result["success"] is False
        assert "Unsupported export format" in result["error"]


# =============================================================================
# Strategy selector injection
# =============================================================================


class TestStrategySelectorInjection:
    """Adapters accept an injectable strategy selector."""

    def test_wincom_custom_selector(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        selector = ExportStrategySelector()
        custom = MagicMock()
        custom.format_name = "custom_csv"
        custom.export.return_value = {
            "success": True, "rows_exported": 99, "file_path": "/tmp/out.csv",
        }
        selector.register(custom)
        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._strategy_selector = selector
        adapter._dispatcher = MagicMock()
        adapter._dispatcher._started = True
        adapter._db_path = "test.accdb"
        adapter.execute_query = MagicMock(
            return_value={"success": True, "rows": [], "columns": []}
        )
        adapter._execute_raw = MagicMock(return_value=0)

        # Default selector doesn't have "custom_csv", but ours does
        result = adapter.export_data(SQL, "/tmp/out.csv", format="custom_csv")
        assert result["success"] is True
        assert result["rows_exported"] == 99

    def test_odbc_custom_selector(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        selector = ExportStrategySelector()
        custom = MagicMock()
        custom.format_name = "super_json"
        custom.export.return_value = {
            "success": True, "rows_exported": 50, "file_path": "/tmp/out.json",
        }
        selector.register(custom)
        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._strategy_selector = selector
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"
        adapter.execute_query = MagicMock(
            return_value={"success": True, "rows": [], "columns": []}
        )

        result = adapter.export_data(SQL, "/tmp/out.json", format="super_json")
        assert result["success"] is True
        assert result["rows_exported"] == 50
