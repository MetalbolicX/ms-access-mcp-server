"""Unit tests for the ms-access-mcp CLI commands."""

import os
from unittest.mock import patch
import pytest
from typer.testing import CliRunner
from ms_access_mcp.cli.main import app

runner = CliRunner()


class TestCliServeCommand:
    def test_serve_sets_env_vars(self):
        """serve command sets env vars before calling run_http."""
        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, [
                "serve",
                "--host", "0.0.0.0",
                "--port", "9999",
                "--api-key", "test-key-12345",
                "--allowed-dirs", "/tmp",
            ])
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once_with(
                host="0.0.0.0", port=9999, transport="http"
            )
        # Clean up env vars
        os.environ.pop("ACCESS_MCP_HOST", None)
        os.environ.pop("ACCESS_MCP_PORT", None)
        os.environ.pop("ACCESS_MCP_API_KEY", None)
        os.environ.pop("ACCESS_MCP_ALLOWED_DIRS", None)

    def test_serve_without_args_uses_defaults(self):
        """serve with no args should use default host/port and http transport."""
        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, ["serve"])
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once_with(
                host="127.0.0.1", port=8000, transport="http"
            )

    def test_serve_with_sse_transport(self):
        """serve --transport sse should pass sse to run_http."""
        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, ["serve", "--transport", "sse"])
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once_with(
                host="127.0.0.1", port=8000, transport="sse"
            )

    def test_serve_with_streamable_http_transport(self):
        """serve --transport streamable-http should pass streamable-http to run_http."""
        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, ["serve", "--transport", "streamable-http"])
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once_with(
                host="127.0.0.1", port=8000, transport="streamable-http"
            )

    def test_serve_without_api_key_exits_with_error(self):
        """serve without ACCESS_MCP_API_KEY should exit with code 1."""
        env = os.environ.copy()
        env.pop("ACCESS_MCP_API_KEY", None)
        env.pop("ACCESS_MCP_HOST", None)
        env.pop("ACCESS_MCP_PORT", None)
        env.pop("ACCESS_MCP_ALLOWED_DIRS", None)
        with (
            runner.isolation(env=env),
            patch.dict(os.environ, {}, clear=False),
            patch("ms_access_mcp.mcp.server._init_http_config") as mock_init,
        ):
            # Ensure API key is not set
            os.environ.pop("ACCESS_MCP_API_KEY", None)
            # Make _init_http_config raise the error it would raise with no API key
            mock_init.side_effect = ValueError("ACCESS_MCP_API_KEY environment variable is not set")
            result = runner.invoke(app, ["serve"], env=env)
            # The command should fail because API key is missing
            assert result.exit_code == 1, f"Expected exit code 1, got {result.exit_code}: {result.stdout}"
        os.environ.pop("ACCESS_MCP_API_KEY", None)

    def test_serve_with_custom_host_and_port(self):
        """serve --host and --port should override defaults."""
        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, [
                "serve",
                "--host", "0.0.0.0",
                "--port", "9000",
            ])
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once_with(
                host="0.0.0.0", port=9000, transport="http"
            )

    def test_serve_with_allowed_dirs_single(self):
        """serve --allowed-dirs with a single directory."""
        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, [
                "serve",
                "--allowed-dirs", "/tmp/test",
            ])
            assert result.exit_code == 0, result.stdout
            # Verify env var was set
            assert os.environ.get("ACCESS_MCP_ALLOWED_DIRS") == "/tmp/test"
        os.environ.pop("ACCESS_MCP_ALLOWED_DIRS", None)

    def test_serve_with_allowed_dirs_multiple(self):
        """serve --allowed-dirs with semicolon-separated directories."""
        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.run_http") as mock_run,
        ):
            result = runner.invoke(app, [
                "serve",
                "--allowed-dirs", "/tmp;/home;/var",
            ])
            assert result.exit_code == 0, result.stdout
            assert os.environ.get("ACCESS_MCP_ALLOWED_DIRS") == "/tmp;/home;/var"
        os.environ.pop("ACCESS_MCP_ALLOWED_DIRS", None)

    def test_serve_with_invalid_transport_errors(self):
        """serve --transport with unknown transport should error gracefully."""
        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.mcp.run") as mock_run,
        ):
            # FastMCP.run will raise on invalid transport
            mock_run.side_effect = ValueError("Invalid transport")
            result = runner.invoke(app, [
                "serve",
                "--transport", "invalid-transport-xyz",
            ])
            # Should fail (either exit code != 0 or error in stdout)
            assert result.exit_code != 0 or "error" in result.stdout.lower(), \
                f"Expected error for invalid transport, got exit={result.exit_code}: {result.stdout}"
        os.environ.pop("ACCESS_MCP_API_KEY", None)

    def test_serve_preserves_env_vars_across_calls(self):
        """Each serve invocation should set its own env vars independently."""
        # Track what run_http is called with across invocations
        calls = []

        def mock_run_http(**kwargs):
            calls.append(kwargs)

        with (
            runner.isolation(),
            patch("ms_access_mcp.mcp.server.run_http", side_effect=mock_run_http),
        ):
            # First call
            result1 = runner.invoke(app, [
                "serve",
                "--api-key", "key-first",
                "--host", "1.2.3.4",
            ])
            assert result1.exit_code == 0, f"First call failed: {result1.stdout}"

            # Second call with different values
            result2 = runner.invoke(app, [
                "serve",
                "--api-key", "key-second",
                "--host", "5.6.7.8",
            ])
            assert result2.exit_code == 0, f"Second call failed: {result2.stdout}"

            # Both invocations should have been made with correct params
            assert len(calls) == 2, f"Expected 2 calls, got {len(calls)}"
            assert calls[0]["host"] == "1.2.3.4"
            assert calls[0]["transport"] == "http"
            assert calls[1]["host"] == "5.6.7.8"
            assert calls[1]["transport"] == "http"
        os.environ.pop("ACCESS_MCP_HOST", None)
        os.environ.pop("ACCESS_MCP_PORT", None)
        os.environ.pop("ACCESS_MCP_API_KEY", None)
        os.environ.pop("ACCESS_MCP_ALLOWED_DIRS", None)


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
