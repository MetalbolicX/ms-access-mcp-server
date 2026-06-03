"""Tests for PR 5: Data Export (CSV/JSON) capability."""

import pytest
import csv
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

SQL = "SELECT * FROM [Customers]"
SQL_FILTERED = "SELECT * FROM [Customers] WHERE active = 1"


class TestExportTableCsv:
    """Test export_table_csv method on both adapters."""

    # -- Fallback (csv.DictWriter) tests via delimiter != "," ---------------

    def test_export_table_csv_wincom_writes_csv_file(self):
        """WinComAdapter fallback should write CSV with correct content."""
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

            # delimiter=';' forces fallback path
            result = adapter.export_table_csv(SQL, file_path, delimiter=";")

            assert result["success"] is True
            assert result["rows_exported"] == 2
            assert result["file_path"] == file_path

            with open(file_path, "r", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["id"] == "1"
            assert rows[0]["name"] == "Alice"
            assert rows[1]["id"] == "2"
            assert rows[1]["name"] == "Bob"

    def test_export_table_csv_odbc_writes_csv_file(self):
        """OdbcAdapter fallback should write CSV with correct content."""
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

            result = adapter.export_table_csv(SQL, file_path, delimiter=";")

            assert result["success"] is True
            assert result["rows_exported"] == 2
            assert result["file_path"] == file_path

            with open(file_path, "r", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
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

            result = adapter.export_table_csv(SQL, file_path, delimiter=";")

            assert result["success"] is True

            with open(file_path, "r") as f:
                content = f.read()

            assert "1;Alice" in content

    def test_export_table_csv_no_header(self):
        """export_table_csv should skip header row when header=False (fallback)."""
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

            # delimiter=';' forces fallback so we can test header=False without IISAM
            result = adapter.export_table_csv(SQL, file_path, delimiter=";", header=False)

            assert result["success"] is True

            with open(file_path, "r", newline="") as f:
                reader = csv.reader(f, delimiter=";")
                rows = list(reader)

            assert rows[0][0] == "1"
            assert rows[0][1] == "Alice"
            assert len(rows) == 1

    def test_export_table_csv_returns_error_when_not_connected(self):
        """export_table_csv should return error dict when not connected."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = None

        result = adapter.export_table_csv(SQL, "/tmp/output.csv")

        assert result["success"] is False
        assert "error" in result

    # -- IISAM path tests (delimiter = ",") --------------------------------

    def test_export_table_csv_wincom_uses_iisam(self):
        """WinComAdapter should use INSERT INTO [Text;...] with default delimiter."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._started = True
        adapter.db = MagicMock()
        adapter.db.RecordsAffected = 42

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv(SQL, file_path)

            assert result["success"] is True
            assert result["rows_exported"] == 42
            assert result["file_path"] == file_path

            # Verify IISAM SQL was executed
            call_args = adapter.db.Execute.call_args[0][0]
            assert call_args.startswith("INSERT INTO [Text;")
            assert ";CharacterSet=65001;" in call_args
            assert "SELECT * FROM [Customers]" in call_args

    def test_export_table_csv_wincom_iisam_with_custom_sql(self):
        """WinComAdapter IISAM should accept arbitrary SQL with WHERE, GROUP BY, etc."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._started = True
        adapter.db = MagicMock()
        adapter.db.RecordsAffected = 7

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            sql = "SELECT id, name, SUM(amount) AS total FROM [Orders] WHERE status = 'done' GROUP BY id, name HAVING SUM(amount) > 100"
            result = adapter.export_table_csv(sql, file_path)

            assert result["success"] is True
            assert result["rows_exported"] == 7

            call_sql = adapter.db.Execute.call_args[0][0]
            assert "WHERE status = 'done'" in call_sql
            assert "GROUP BY" in call_sql
            assert "HAVING" in call_sql

    def test_export_table_csv_wincom_iisam_no_header(self):
        """WinComAdapter IISAM should set HDR=NO when header=False."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._started = True
        adapter.db = MagicMock()
        adapter.db.RecordsAffected = 5

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv(SQL, file_path, header=False)

            assert result["success"] is True

            call_args = adapter.db.Execute.call_args[0][0]
            assert "HDR=NO" in call_args
            assert "HDR=YES" not in call_args

    def test_export_table_csv_wincom_iisam_fallback_on_custom_delimiter(self):
        """WinComAdapter should fall back when delimiter != ','."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter.__new__(WinComAdapter)
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._started = True

        expected_result = {
            "success": True,
            "rows": [{"id": 1, "name": "Alice"}],
            "count": 1,
            "columns": ["id", "name"],
        }
        adapter._dispatcher.call = MagicMock(return_value=expected_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv(SQL, file_path, delimiter="|")

            assert result["success"] is True
            # db.Execute should NOT be called (fallback used execute_query)
            adapter.db = MagicMock()
            assert adapter.db.Execute.called is False

    def test_export_table_csv_odbc_uses_iisam(self):
        """OdbcAdapter should use INSERT INTO [Text;...] with default delimiter."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 42
        adapter._conn.cursor.return_value = mock_cursor

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv(SQL, file_path)

            assert result["success"] is True
            assert result["rows_exported"] == 42
            assert result["file_path"] == file_path

            # Verify IISAM SQL was executed
            call_sql = mock_cursor.execute.call_args[0][0]
            assert call_sql.startswith("INSERT INTO [Text;")
            assert ";CharacterSet=65001;" in call_sql
            assert "SELECT * FROM [Customers]" in call_sql
            mock_cursor.close.assert_called_once()

    def test_export_table_csv_odbc_iisam_no_header(self):
        """OdbcAdapter IISAM should set HDR=NO when header=False."""
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        adapter = OdbcAdapter.__new__(OdbcAdapter)
        adapter._conn = MagicMock()
        adapter._db_path = "test.accdb"

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        adapter._conn.cursor.return_value = mock_cursor

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.csv")

            result = adapter.export_table_csv(SQL, file_path, header=False)

            assert result["success"] is True

            call_sql = mock_cursor.execute.call_args[0][0]
            assert "HDR=NO" in call_sql
            assert "HDR=YES" not in call_sql

    def test_export_table_csv_iisam_fallback_on_unknown_encoding(self):
        """Both adapters should fall back when encoding is not in the code page map."""
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

            # encoding not in _CODEPAGE_MAP → forces fallback
            result = adapter.export_table_csv(SQL, file_path, encoding="iso-8859-15")

            assert result["success"] is True
            assert result["rows_exported"] == 1
            # verify IISAM INSERT INTO was NOT used
            for call_args in mock_cursor.execute.call_args_list:
                assert not call_args[0][0].startswith("INSERT INTO [Text;"), (
                    "IISAM path should not have been used"
                )


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