"""Tests that all MCP tools correctly route connection_name to the pool."""
import pytest
from unittest.mock import patch, MagicMock
from ms_access_mcp.mcp import server


class TestConnectionNameThroughTools:
    """connection_name param propagates to connection_service for all tools."""

    @pytest.mark.parametrize("tool_name,tool_args,tool_kwargs", [
        ("get_tables", (), {}),
        ("get_queries", (), {}),
        ("export_data", ("SELECT * FROM [table]", "/tmp/out.csv", "csv"), {}),
        ("get_linked_tables", (), {}),
        ("get_forms", (), {}),
        ("get_vba_projects", (), {}),
        ("compact_repair", ("compact", "s.accdb", "d.accdb"), {}),
        ("get_control_event_procedures", ("Form1",), {}),
    ])
    def test_tool_uses_connection_name(self, tool_name, tool_args, tool_kwargs):
        tool_func = getattr(server, tool_name)
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = MagicMock()
        with patch.dict(tool_func.__globals__, connection_service=mock_conn):
            tool_func(*tool_args, connection_name="prod", **tool_kwargs)
            mock_conn.is_connected.assert_called_with("prod")
