"""Tests for PR 5: Data Export (CSV/JSON) capability."""

import pytest
import csv
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestExportTableCsv:
    """Test export_table_csv method on both adapters."""

    def test_export_table_csv_wincom_writes_csv_file(self):
        """WinComAdapter.export_table_csv should write CSV file with correct content."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._started = True

        expected_result = {
            "success": True,
            "rows": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            "count": 2,
            "columns": ["id", "name"],
        }
        adapter._dispatcher.call = MagicMock(return_value=expected_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv("Customers", file_path)

            assert result["success"] is True
            assert result["rows_exported"] == 2
            assert result["file_path"] == file_path

            with open(file_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["id"] == "1"
            assert rows[0]["name"] == "Alice"
            assert rows[1]["id"] == "2"
            assert rows[1]["name"] == "Bob"

    def test_export_table_csv_odbc_writes_csv_file(self):
        """OdbcAdapter.export_table_csv should write CSV file with correct content."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
        adapter._conn.cursor.return_value = mock_cursor

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv("Customers", file_path)

            assert result["success"] is True
            assert result["rows_exported"] == 2
            assert result["file_path"] == file_path

            with open(file_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["id"] == "1"
            assert rows[0]["name"] == "Alice"

    def test_export_table_csv_with_custom_delimiter(self):
        """export_table_csv should use custom delimiter when specified."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "Alice")]
        adapter._conn.cursor.return_value = mock_cursor

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv("Customers", file_path, delimiter=";")

            assert result["success"] is True

            with open(file_path, "r") as f:
                content = f.read()

            assert "1;Alice" in content

    def test_export_table_csv_no_header(self):
        """export_table_csv should skip header row when header=False."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "Alice")]
        adapter._conn.cursor.return_value = mock_cursor

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv("Customers", file_path, header=False)

            assert result["success"] is True

            with open(file_path, "r", newline="") as f:
                reader = csv.reader(f, delimiter=",")
                rows = list(reader)

            assert rows[0][0] == "1"
            assert rows[0][1] == "Alice"
            assert len(rows) == 1

    def test_export_table_csv_returns_error_when_not_connected(self):
        """export_table_csv should return error dict when not connected."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.export_table_csv("Customers", "/tmp/output.csv")

        assert result["success"] is False
        assert "error" in result


class TestExportQueryJson:
    """Test export_query_json method on both adapters."""

    def test_export_query_json_wincom_writes_json_file(self):
        """WinComAdapter.export_query_json should write JSON file with correct content."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._started = True

        expected_result = {
            "success": True,
            "rows": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            "count": 2,
            "columns": ["id", "name"],
        }
        adapter._dispatcher.call = MagicMock(return_value=expected_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.json")

            result = adapter.export_query_json("qryCustomers", file_path)

            assert result["success"] is True
            assert result["rows_exported"] == 2
            assert result["file_path"] == file_path

            with open(file_path, "r") as f:
                data = json.load(f)

            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["id"] == 1
            assert data[0]["name"] == "Alice"

    def test_export_query_json_odbc_writes_json_file(self):
        """OdbcAdapter.export_query_json should write JSON file with correct content."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
        adapter._conn.cursor.return_value = mock_cursor

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.json")

            result = adapter.export_query_json("qryCustomers", file_path)

            assert result["success"] is True
            assert result["rows_exported"] == 2

            with open(file_path, "r") as f:
                data = json.load(f)

            assert isinstance(data, list)
            assert len(data) == 2

    def test_export_query_json_with_pretty_print(self):
        """export_query_json should format JSON with indentation when pretty=True."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]
        adapter._conn.cursor.return_value = mock_cursor

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.json")

            result = adapter.export_query_json("qryTest", file_path, pretty=True)

            assert result["success"] is True

            with open(file_path, "r") as f:
                content = f.read()

            assert "\n" in content
            assert "  " in content

    def test_export_query_json_returns_error_when_not_connected(self):
        """export_query_json should return error dict when not connected."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.export_query_json("qryTest", "/tmp/output.json")

        assert result["success"] is False
        assert "error" in result