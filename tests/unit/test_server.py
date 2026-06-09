"""Tests for mcp/server.py - server initialization and exports."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


class TestServerInitialization:
    """Tests for server module initialization."""

    def test_services_are_initialized(self):
        """Should initialize all required services."""
        assert server.connection_service is not None
        assert server.com_automation_service is not None
        assert server.migration_service is not None
        assert server.dev_copy_service is not None

    def test_mcp_server_is_initialized(self):
        """Should initialize FastMCP server."""
        assert server.mcp is not None


class TestReExports:
    """Tests for backward-compatible re-exports from submodules."""

    def test_connection_tools_are_exported(self):
        """Should export connection tools."""
        from ms_access_mcp.mcp.server import connect_access, disconnect_access, is_connected
        assert callable(connect_access)
        assert callable(disconnect_access)
        assert callable(is_connected)

    def test_schema_tools_are_exported(self):
        """Should export schema tools."""
        from ms_access_mcp.mcp.server import get_tables, get_table_schema, get_relationships
        assert callable(get_tables)
        assert callable(get_table_schema)
        assert callable(get_relationships)

    def test_crud_tools_are_exported(self):
        """Should export CRUD tools."""
        from ms_access_mcp.mcp.server import get_queries, create_table, query_data
        assert callable(get_queries)
        assert callable(create_table)
        assert callable(query_data)

    def test_export_tools_are_exported(self):
        """Should export export tool."""
        from ms_access_mcp.mcp.server import export_data
        assert callable(export_data)

    def test_com_tools_are_exported(self):
        """Should export COM automation tools."""
        from ms_access_mcp.mcp.server import launch_access, close_access, get_forms
        assert callable(launch_access)
        assert callable(close_access)
        assert callable(get_forms)

    def test_vba_tools_are_exported(self):
        """Should export VBA tools."""
        from ms_access_mcp.mcp.server import get_vba_projects, compile_vba
        assert callable(get_vba_projects)
        assert callable(compile_vba)

    def test_system_tools_are_exported(self):
        """Should export system tools."""
        from ms_access_mcp.mcp.server import get_system_tables, export_form_to_text
        assert callable(get_system_tables)
        assert callable(export_form_to_text)

    def test_migration_tools_are_exported(self):
        """Should export migration tools."""
        from ms_access_mcp.mcp.server import extract_schema, transfer_data
        assert callable(extract_schema)
        assert callable(transfer_data)

    def test_linked_tables_tools_are_exported(self):
        """Should export linked tables tools."""
        from ms_access_mcp.mcp.server import get_linked_tables, create_linked_table, refresh_linked_table, unlink_table, upsert_linked_table
        assert callable(get_linked_tables)
        assert callable(create_linked_table)
        assert callable(refresh_linked_table)
        assert callable(unlink_table)
        assert callable(upsert_linked_table)

    def test_dev_copy_tools_are_exported(self):
        """Should export dev copy tools."""
        from ms_access_mcp.mcp.server import compact_repair, copy_database, create_dev_copy
        assert callable(compact_repair)
        assert callable(copy_database)
        assert callable(create_dev_copy)


class TestHttpConfigInit:
    """Tests for HTTP config initialization."""

    def test_init_http_config_creates_config(self):
        """Should initialize HTTP config from environment."""
        with patch("ms_access_mcp.mcp.server.ServerConfig") as MockConfig, \
             patch("ms_access_mcp.mcp.server.PathGuard") as MockPathGuard, \
             patch("ms_access_mcp.mcp.server.ApiKeyMiddleware") as MockAuth:
            MockConfig.return_value = MagicMock()
            MockConfig.return_value.api_key = "test-key"
            MockConfig.return_value.allowed_dirs = ["/tmp"]

            # Reset global state
            server._config = None
            server._path_guard = None
            server._auth_middleware = None

            server._init_http_config()

            assert server._config is not None
            MockConfig.assert_called_once()
            MockPathGuard.assert_called_once()
            MockAuth.assert_called_once()

    def test_init_http_config_is_idempotent(self):
        """Should only initialize once (idempotent)."""
        with patch("ms_access_mcp.mcp.server.ServerConfig") as MockConfig:
            MockConfig.return_value = MagicMock()
            MockConfig.return_value.api_key = "test-key"
            MockConfig.return_value.allowed_dirs = []

            server._config = None
            server._config = MagicMock()  # Pre-set to simulate already initialized

            server._init_http_config()
            MockConfig.assert_not_called()


class TestNewReExports:
    """Tests for newly added tool re-exports."""

    def test_new_connection_tools_exported(self):
        """Should export list_connections, set_active_connection, get_active_connection."""
        from ms_access_mcp.mcp.server import list_connections, set_active_connection, get_active_connection
        assert callable(list_connections)
        assert callable(set_active_connection)
        assert callable(get_active_connection)

    def test_new_com_tools_exported(self):
        """Should export set_control_properties, get_control_event_procedures."""
        from ms_access_mcp.mcp.server import set_control_properties, get_control_event_procedures
        assert callable(set_control_properties)
        assert callable(get_control_event_procedures)

    def test_new_vba_tools_exported(self):
        """Should export vba_list_procedures, vba_get_procedure, vba_replace_procedure, save_query."""
        from ms_access_mcp.mcp.server import vba_list_procedures, vba_get_procedure, vba_replace_procedure, save_query
        assert callable(vba_list_procedures)
        assert callable(vba_get_procedure)
        assert callable(vba_replace_procedure)
        assert callable(save_query)

    def test_new_system_tools_exported(self):
        """Should export recover_access, diagnose_environment."""
        from ms_access_mcp.mcp.server import recover_access, diagnose_environment
        assert callable(recover_access)
        assert callable(diagnose_environment)

    def test_index_tools_exported(self):
        """Should export get_indexes, create_index, drop_index."""
        from ms_access_mcp.mcp.server import get_indexes, create_index, drop_index
        assert callable(get_indexes)
        assert callable(create_index)
        assert callable(drop_index)


class TestMainGuard:
    """Tests for __main__ guard that enables stdio transport."""

    def test_main_guard_calls_mcp_run(self):
        """The __main__ guard should call mcp.run() for stdio transport."""
        import ms_access_mcp.mcp.server as server_module
        import ast

        # Read the source and parse for __main__ guard
        source = open(server_module.__file__, "r").read()
        tree = ast.parse(source)

        # Find the __main__ guard block
        has_main_guard = False
        has_mcp_run_call = False

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Check for `if __name__ == "__main__":`
                if (isinstance(node.test, ast.Compare) and
                    isinstance(node.test.left, ast.Name) and
                    node.test.left.id == "__name__" and
                    len(node.test.ops) == 1 and
                    isinstance(node.test.ops[0], ast.Eq) and
                    isinstance(node.test.comparators[0], ast.Constant) and
                    node.test.comparators[0].value == "__main__"):
                    has_main_guard = True
                    # Check that mcp.run() is called within this block
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            if (isinstance(child.func, ast.Attribute) and
                                child.func.attr == "run"):
                                has_mcp_run_call = True

        assert has_main_guard, "server.py should have `if __name__ == '__main__':` guard"
        assert has_mcp_run_call, "server.py __main__ guard should call mcp.run()"


class TestRunHttpTLS:
    """Tests for TLS kwargs in run_http()."""

    def test_run_http_accepts_ssl_kwargs(self):
        """run_http should accept ssl_keyfile and ssl_certfile kwargs."""
        from ms_access_mcp.mcp.server import run_http
        import inspect

        sig = inspect.signature(run_http)
        param_names = list(sig.parameters.keys())

        assert "ssl_keyfile" in param_names, "run_http should accept ssl_keyfile parameter"
        assert "ssl_certfile" in param_names, "run_http should accept ssl_certfile parameter"

    def test_run_http_ssl_kwargs_are_optional(self):
        """ssl_keyfile and ssl_certfile should be optional (None defaults)."""
        from ms_access_mcp.mcp.server import run_http
        import inspect

        sig = inspect.signature(run_http)
        ssl_keyfile_param = sig.parameters.get("ssl_keyfile")
        ssl_certfile_param = sig.parameters.get("ssl_certfile")

        assert ssl_keyfile_param is not None, "ssl_keyfile parameter should exist"
        assert ssl_certfile_param is not None, "ssl_certfile parameter should exist"
        assert ssl_keyfile_param.default is None, "ssl_keyfile should default to None"
        assert ssl_certfile_param.default is None, "ssl_certfile should default to None"
