"""Unit tests for the export strategy classes (CsvStrategy, JsonStrategy, ExcelStrategy)."""

import csv
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ms_access_mcp.adapters.export.strategies import (
    CsvStrategy,
    ExportContext,
    ExportStrategySelector,
    ExcelStrategy,
    JsonStrategy,
)


# =============================================================================
# Fixtures
# =============================================================================

ROWS = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
COLUMNS = ["id", "name"]
SQL = "SELECT id, name FROM [Users]"


def _make_context(
    *,
    sql: str = SQL,
    file_path: str | None = None,
    options: dict | None = None,
    execute_query_result: dict | None = None,
    execute_raw_raises: bool = False,
) -> ExportContext:
    if file_path is None:
        file_path = os.path.join(tempfile.mkdtemp(), "out")
    if options is None:
        options = {}

    execute_query = MagicMock(return_value=execute_query_result or {
        "success": True,
        "rows": ROWS,
        "columns": COLUMNS,
    })

    execute_raw = MagicMock(side_effect=RuntimeError("no engine")) if execute_raw_raises else MagicMock(return_value=2)

    return ExportContext(
        sql=sql,
        file_path=file_path,
        options=options,
        execute_query=execute_query,
        execute_raw=execute_raw,
    )


# =============================================================================
# CsvStrategy
# =============================================================================


class TestCsvStrategy:
    """CsvStrategy — IISAM path and csv.DictWriter fallback."""

    def test_format_name(self):
        assert CsvStrategy().format_name == "csv"

    def test_iisam_path(self):
        """IISAM path: execute_raw called with INSERT INTO [Text;…]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")
            strategy = CsvStrategy()
            context = _make_context(file_path=file_path, execute_raw_raises=False)

            result = strategy.export(context)

            assert result["success"] is True
            assert result["rows_exported"] == 2
            assert result["file_path"] == file_path

            # Verify execute_raw was called with IISAM-style SQL
            call_sql = context.execute_raw.call_args[0][0]
            assert call_sql.startswith("INSERT INTO [Text;")
            assert "CharacterSet=65001" in call_sql
            assert "SELECT id, name FROM [Users]" in call_sql

    def test_iisam_no_header(self):
        """IISAM path with header=False sets HDR=NO."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")
            strategy = CsvStrategy()
            context = _make_context(file_path=file_path, options={"header": False})

            strategy.export(context)

            call_sql = context.execute_raw.call_args[0][0]
            assert "HDR=NO" in call_sql

    def test_custom_delimiter_triggers_fallback(self):
        """delimiter != ',' should skip IISAM and use csv.DictWriter fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")
            strategy = CsvStrategy()
            context = _make_context(file_path=file_path, options={"delimiter": ";"})

            result = strategy.export(context)

            assert result["success"] is True
            assert result["rows_exported"] == 2
            # execute_raw should NOT have been called
            assert context.execute_raw.call_count == 0
            # File should exist with correct content
            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["id"] == "1"

    def test_iisam_fallback_on_engine_error(self):
        """When IISAM raises, fallback should produce the file via csv.DictWriter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")
            strategy = CsvStrategy()
            context = _make_context(file_path=file_path, execute_raw_raises=True)

            result = strategy.export(context)

            assert result["success"] is True
            assert result["rows_exported"] == 2
            # File should exist
            assert os.path.exists(file_path)

    def test_fallback_no_execute_query(self):
        """Fallback without execute_query returns error."""
        context = ExportContext(
            sql=SQL, file_path="/tmp/nope.csv", options={},
            execute_query=None, execute_raw=None,
        )
        strategy = CsvStrategy()
        # Force fallback by using custom delimiter
        context.options["delimiter"] = ";"

        result = strategy.export(context)

        assert result["success"] is False
        assert "execute_query not available" in result["error"]


# =============================================================================
# JsonStrategy
# =============================================================================


class TestJsonStrategy:
    """JsonStrategy — always uses json.dump."""

    def test_format_name(self):
        assert JsonStrategy().format_name == "json"

    def test_writes_json_file(self):
        """Should write a JSON array of objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.json")
            strategy = JsonStrategy()
            context = _make_context(file_path=file_path)

            result = strategy.export(context)

            assert result["success"] is True
            assert result["rows_exported"] == 2

            with open(file_path) as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["name"] == "Alice"

    def test_pretty_print(self):
        """With pretty=True, output should have indentation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "pretty.json")
            strategy = JsonStrategy()
            context = _make_context(file_path=file_path, options={"pretty": True})

            strategy.export(context)

            with open(file_path) as f:
                content = f.read()
            assert "\n" in content
            assert "  " in content or "\t" in content

    def test_compact_by_default(self):
        """With pretty=False, output should be compact (no extra whitespace)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "compact.json")
            strategy = JsonStrategy()
            context = _make_context(file_path=file_path, options={"pretty": False})

            strategy.export(context)

            with open(file_path) as f:
                content = f.read()
            # Compact JSON has no newlines inside the array
            assert "\n" not in content or content.count("\n") <= 1

    def test_error_on_query_failure(self):
        """Should return error when execute_query fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "fail.json")
            strategy = JsonStrategy()
            context = _make_context(
                file_path=file_path,
                execute_query_result={"success": False, "error": "Table not found"},
            )

            result = strategy.export(context)

            assert result["success"] is False
            assert "Table not found" in result["error"]

    def test_no_execute_query(self):
        """Without execute_query, should return error."""
        context = ExportContext(
            sql=SQL, file_path="/tmp/nope.json", options={},
            execute_query=None, execute_raw=None,
        )
        result = JsonStrategy().export(context)

        assert result["success"] is False


# =============================================================================
# ExcelStrategy
# =============================================================================


class TestExcelStrategy:
    """ExcelStrategy — IISAM path with openpyxl fallback."""

    def test_format_name(self):
        assert ExcelStrategy().format_name == "excel"

    def test_iisam_path(self):
        """IISAM path: execute_raw called with INSERT INTO [Excel 12.0;…]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.xlsx")
            strategy = ExcelStrategy()
            context = _make_context(file_path=file_path, execute_raw_raises=False)

            result = strategy.export(context)

            assert result["success"] is True
            assert result["rows_exported"] == 2

            # Verify execute_raw was called with Excel IISAM-style SQL
            call_sql = context.execute_raw.call_args[0][0]
            assert call_sql.startswith("INSERT INTO [Excel 12.0;")
            assert f"DATABASE={os.path.join(tmpdir, 'output.xlsx')}" in call_sql
            assert "[Sheet1$]" in call_sql

    def test_openpyxl_fallback(self):
        """When IISAM fails, falls back to openpyxl."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.xlsx")
            strategy = ExcelStrategy()

            execute_raw = MagicMock(side_effect=RuntimeError("no engine"))
            context = _make_context(
                file_path=file_path,
                options={"sheet_name": "MySheet"},
                execute_raw_raises=True,
            )
            context.execute_raw = execute_raw

            with patch("openpyxl.Workbook") as mock_wb_cls:
                mock_wb = MagicMock()
                mock_ws = MagicMock()
                mock_wb.active = mock_ws
                mock_wb_cls.return_value = mock_wb

                result = strategy.export(context)

                assert result["success"] is True
                assert result["rows_exported"] == 2

                # ws.append called for header + 2 data rows
                assert mock_ws.append.call_count == 3
                mock_wb.save.assert_called_once_with(file_path)

    def test_openpyxl_not_installed(self):
        """When openpyxl is missing, return a helpful error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.xlsx")
            strategy = ExcelStrategy()

            # IISAM fails AND openpyxl not available
            execute_raw = MagicMock(side_effect=RuntimeError("no engine"))
            context = _make_context(file_path=file_path, execute_raw_raises=True)
            context.execute_raw = execute_raw

            # Simulate openpyxl ImportError
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "openpyxl" or name.startswith("openpyxl."):
                    raise ImportError("No module named openpyxl")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", mock_import):
                result = strategy.export(context)

            assert result["success"] is False
            assert "openpyxl" in result["error"].lower()

    def test_no_execute_query_fallback(self):
        """Fallback without execute_query returns error."""
        context = ExportContext(
            sql=SQL, file_path="/tmp/nope.xlsx", options={},
            execute_query=None, execute_raw=None,
        )
        strategy = ExcelStrategy()

        result = strategy.export(context)

        assert result["success"] is False
        assert "execute_query not available" in result["error"]


# =============================================================================
# ExportStrategySelector
# =============================================================================


class TestExportStrategySelector:
    """Registry of strategies."""

    def test_get_csv(self):
        selector = ExportStrategySelector()
        strategy = selector.get("csv")
        assert isinstance(strategy, CsvStrategy)

    def test_get_json(self):
        selector = ExportStrategySelector()
        strategy = selector.get("json")
        assert isinstance(strategy, JsonStrategy)

    def test_get_excel(self):
        selector = ExportStrategySelector()
        strategy = selector.get("excel")
        assert isinstance(strategy, ExcelStrategy)

    def test_get_unknown_format(self):
        selector = ExportStrategySelector()
        with pytest.raises(ValueError, match="Unsupported export format"):
            selector.get("parquet")

    def test_register_custom(self):
        selector = ExportStrategySelector()

        class DummyStrategy:
            format_name = "dummy"
            def export(self, context):
                return {"success": True, "rows_exported": 0, "file_path": ""}

        selector.register(DummyStrategy())
        strategy = selector.get("dummy")
        assert strategy.format_name == "dummy"

    def test_supported_formats(self):
        selector = ExportStrategySelector()
        formats = selector.supported_formats()
        assert "csv" in formats
        assert "json" in formats
        assert "excel" in formats

    def test_override_registered(self):
        """Registering same format name overrides the existing strategy."""
        selector = ExportStrategySelector()

        class CustomCsv:
            format_name = "csv"
            def export(self, context):
                return {"success": True, "rows_exported": 999, "file_path": "custom.csv"}

        selector.register(CustomCsv())
        strategy = selector.get("csv")
        assert strategy.export(MagicMock())["rows_exported"] == 999
