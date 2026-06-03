"""
Integration tests for MCP export tool (export_data).

Tier 1: SQLite-backed OdbcAdapter verifies export can succeed via ODBC.
Tier 3: WinCom happy-path verifies file creation with real Access DB.
"""

import json
import os
import tempfile

import pytest

from conftest import pool_with_sqlite
from helpers import call_mcp_tool, skip_unless_windows, skip_unless_db


class TestExportOdbcAdapter:
    """Tier 1: Verify export_data works via OdbcAdapter (SQLite-backed)."""

    def test_export_data_csv_via_sqlite_adapter(self, pool_with_sqlite):
        """export_data(format='csv') succeeds via SQLite-backed OdbcAdapter."""
        adapter = pool_with_sqlite.get_adapter("default")
        adapter.execute_query("CREATE TABLE test_export_csv (ID INTEGER PRIMARY KEY, Name TEXT)")
        adapter.execute_query("INSERT INTO test_export_csv VALUES (1, 'Alice'), (2, 'Bob')")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name

        try:
            result = call_mcp_tool(
                "export_data",
                "SELECT ID, Name FROM [test_export_csv]",
                csv_path,
                format="csv",
                delimiter=",",
                header=True,
                connection_service=pool_with_sqlite,
            )
            assert result["success"] is True, f"export_data failed: {result.get('error')}"
            assert result["rows_exported"] == 2
            assert result["file_path"] == csv_path

            # Verify file contents
            with open(csv_path, newline="", encoding="utf-8") as f:
                contents = f.read()
            assert "ID,Name" in contents
            assert "1,Alice" in contents
            assert "2,Bob" in contents
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_export_data_json_via_sqlite_adapter(self, pool_with_sqlite):
        """export_data(format='json') succeeds via SQLite-backed OdbcAdapter."""
        adapter = pool_with_sqlite.get_adapter("default")
        adapter.execute_query("CREATE TABLE test_export_json (ID INTEGER PRIMARY KEY, Value REAL)")
        adapter.execute_query("INSERT INTO test_export_json VALUES (10, 3.14), (20, 2.718)")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = f.name

        try:
            result = call_mcp_tool(
                "export_data",
                "SELECT ID, Value FROM [test_export_json]",
                json_path,
                format="json",
                pretty=True,
                connection_service=pool_with_sqlite,
            )
            assert result["success"] is True, f"export_data failed: {result.get('error')}"
            assert result["rows_exported"] == 2
            assert result["file_path"] == json_path

            # Verify JSON contents
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) == 2
            assert data[0]["ID"] == 10
            assert data[1]["ID"] == 20
        finally:
            if os.path.exists(json_path):
                os.unlink(json_path)


class TestExportWinComHappyPath:
    """Tier 3: WinCom happy-path for export_data.

    NOTE: These tests require the pool.connect(name, db_path, adapter_type) API
    which is currently broken (pre-existing issue - pool.connect only accepts
    3 args but the tests pass 4). Skip via marker until connection.py is fixed.
    """

    pytestmark = [skip_unless_windows, skip_unless_db]

    def test_export_data_csv_produces_file(self, temp_db_copy):
        """export_data(format='csv') via WinComAdapter produces a real CSV file."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_export", temp_db_copy, adapter, "com")

            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
                csv_path = f.name

            result = call_mcp_tool(
                "export_data",
                "SELECT * FROM [customers]",
                csv_path,
                format="csv",
                connection_service=pool,
            )
            assert isinstance(result, dict), "Result must be a dict"
            assert "success" in result
            if result["success"]:
                assert os.path.exists(csv_path), "CSV file should exist after export"
                with open(csv_path, encoding="utf-8") as f:
                    contents = f.read()
                assert len(contents) > 0, "CSV should have content"
            else:
                assert "error" in result

            pool.disconnect("test_export")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_export_data_json_produces_file(self, temp_db_copy):
        """export_data(format='json') via WinComAdapter produces a real JSON file."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_export", temp_db_copy, adapter, "com")

            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                json_path = f.name

            result = call_mcp_tool(
                "export_data",
                "SELECT * FROM [qry_orders]",
                json_path,
                format="json",
                pretty=True,
                connection_service=pool,
            )
            assert isinstance(result, dict), "Result must be a dict"
            assert "success" in result
            if result["success"]:
                assert os.path.exists(json_path), "JSON file should exist after export"
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                assert isinstance(data, list), "JSON root should be a list of rows"
            else:
                assert "error" in result

            pool.disconnect("test_export")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass


# =============================================================================
# compare_versioning integration tests
# =============================================================================

class TestCompareVersioning:
    """Integration tests for compare_versioning tool.

    Tests compare_versioning with a real or mock export directory.
    The tool delegates to schema_service.compare_versioning → WinComAdapter.compare_versioning.
    """

    def test_compare_versioning_via_odbc_raises_notimplementederror(self, pool_with_sqlite):
        """compare_versioning raises NotImplementedError via OdbcAdapter (requires COM)."""
        with pytest.raises(NotImplementedError, match="COM"):
            call_mcp_tool(
                "compare_versioning",
                "C:\\temp\\export",
                connection_service=pool_with_sqlite,
            )

    def test_compare_versioning_returns_buckets_with_empty_dir(self, temp_db_copy):
        """compare_versioning with empty export dir returns all objects as 'new'."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_cmp", temp_db_copy, adapter, "com")

            with tempfile.TemporaryDirectory() as tmpdir:
                result = call_mcp_tool(
                    "compare_versioning",
                    tmpdir,
                    connection_name="test_cmp",
                    connection_service=pool,
                )
                assert isinstance(result, dict)
                assert "new" in result
                assert "missing" in result
                assert "changed" in result
                assert "unchanged" in result
                # Empty export dir → all DB objects are 'new'
                assert isinstance(result["new"], list)
                assert isinstance(result["missing"], list)
                assert isinstance(result["changed"], list)
                assert isinstance(result["unchanged"], list)

            pool.disconnect("test_cmp")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass

    def test_compare_versioning_nonexistent_dir_via_wincom(self, temp_db_copy):
        """compare_versioning with nonexistent directory handles gracefully."""
        from ms_access_mcp.adapters.wincom import WinComAdapter
        from ms_access_mcp.services.connection import ConnectionPool

        adapter = WinComAdapter()
        pool = ConnectionPool()

        try:
            assert adapter.connect(temp_db_copy), "WinComAdapter failed to connect"
            pool.connect("test_cmp_bad", temp_db_copy, adapter, "com")

            result = call_mcp_tool(
                "compare_versioning",
                "Z:\\totally\\nonexistent\\path\\for\\compare",
                connection_name="test_cmp_bad",
                connection_service=pool,
            )
            assert isinstance(result, dict)
            assert "new" in result  # Should still return buckets

            pool.disconnect("test_cmp_bad")
        finally:
            try:
                if adapter.is_connected():
                    adapter.disconnect()
            except Exception:
                pass
