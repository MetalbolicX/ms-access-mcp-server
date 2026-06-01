"""Unit tests for the ms-access-mcp CLI commands."""

import os
from unittest.mock import patch
import pytest
from typer.testing import CliRunner
from ms_access_mcp.cli.main import app

runner = CliRunner()


class TestCliServeCommand:
    def test_serve_sets_env_vars(self):
        """serve command sets env vars before importing server."""
        with (
            runner.isolated_filesystem(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, [
                "serve",
                "--host", "0.0.0.0",
                "--port", "9999",
                "--api-key", "test-key-12345",
                "--allowed-dirs", "/tmp",
            ])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                host="0.0.0.0", port=9999, transport="http"
            )
        # Clean up env vars
        os.environ.pop("ACCESS_MCP_HOST", None)
        os.environ.pop("ACCESS_MCP_PORT", None)
        os.environ.pop("ACCESS_MCP_API_KEY", None)
        os.environ.pop("ACCESS_MCP_ALLOWED_DIRS", None)

    def test_serve_without_args_uses_defaults(self):
        """serve with no args should use default host/port."""
        with (
            runner.isolated_filesystem(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, ["serve"])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                host="127.0.0.1", port=8000, transport="http"
            )


class TestCliConnectCommand:
    def test_connect_requires_db_path(self):
        result = runner.invoke(app, ["connect", "/tmp/test.accdb"])
        assert result.exit_code == 0
        assert "Connecting" in result.stdout

    def test_connect_with_com_flag(self):
        result = runner.invoke(app, ["connect", "/tmp/test.accdb", "--com"])
        assert result.exit_code == 0
        assert "COM=True" in result.stdout


class TestCliDisconnectCommand:
    def test_disconnect(self):
        result = runner.invoke(app, ["disconnect"])
        assert result.exit_code == 0
        assert "Disconnecting" in result.stdout


class TestCliStatusCommand:
    def test_status(self):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0


class TestCliListTablesCommand:
    def test_list_tables(self):
        result = runner.invoke(app, ["list-tables"])
        assert result.exit_code == 0
        assert "Tables" in result.stdout


class TestCliListQueriesCommand:
    def test_list_queries(self):
        result = runner.invoke(app, ["list-queries"])
        assert result.exit_code == 0


class TestCliDescribeTableCommand:
    def test_describe_table_requires_name(self):
        result = runner.invoke(app, ["describe-table", "customers"])
        assert result.exit_code == 0
        assert "customers" in result.stdout


class TestCliRunQueryCommand:
    def test_run_query(self):
        result = runner.invoke(app, ["run-query", "SELECT 1"])
        assert result.exit_code == 0
        assert "SELECT 1" in result.stdout

    def test_run_query_with_export(self):
        result = runner.invoke(app, ["run-query", "SELECT 1", "--export", "/tmp/results.csv"])
        assert result.exit_code == 0
        assert "/tmp/results.csv" in result.stdout


class TestCliExportVbaCommand:
    def test_export_vba(self):
        result = runner.invoke(app, ["export-vba", "Module1"])
        assert result.exit_code == 0
        assert "Module1" in result.stdout


class TestCliImportVbaCommand:
    def test_import_vba(self):
        result = runner.invoke(app, ["import-vba", "Module1", os.path.join(os.sep, "tmp", "Module1.bas")])
        assert result.exit_code == 0
        assert "Module1" in result.stdout
        assert os.path.join(os.sep, "tmp", "Module1.bas") in result.stdout


class TestCliHelp:
    def test_help_prints_usage(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Usage" in result.stdout
        assert "Commands" in result.stdout
        assert "serve" in result.stdout
        assert "connect" in result.stdout

    def test_version_flag_not_defined(self):
        """The app does not define a --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code != 0
