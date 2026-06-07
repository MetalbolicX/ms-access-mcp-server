"""Tests for analysis MCP tool — Phase 4.3."""

import pytest
from unittest.mock import MagicMock, patch

# Import server first to resolve circular dependency
from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import _helpers


class TestAnalyzeQueryToolRegistration:
    """Verify analyze_query tool is registered with MCP server."""

    @pytest.mark.anyio
    async def test_analyze_query_tool_registered(self):
        """4.3 RED: analyze_query tool must be registered in MCP server."""
        from ms_access_mcp.mcp.server import mcp
        tool_names = [tool.name for tool in await mcp.list_tools()]
        assert "analyze_query" in tool_names


class TestAnalyzeQueryTool:
    """Test analyze_query MCP tool function — Phase 4.1."""

    def test_analyze_query_returns_dict(self):
        """4.1 RED: analyze_query returns a dict with required keys."""
        from ms_access_mcp.mcp.analysis import analyze_query

        # This will fail because we're not connected, but should still return proper structure
        result = analyze_query(sql="SELECT * FROM Customers")

        assert isinstance(result, dict)

    def test_analyze_query_not_connected(self):
        """4.1 RED: Not connected → returns error dict."""
        from ms_access_mcp.mcp.analysis import analyze_query

        result = analyze_query(sql="SELECT * FROM Customers", connection_name="nonexistent")

        assert result.get("success") is False
        assert "error" in result or "not connected" in result.get("error", "").lower()

    def test_analyze_query_dry_run(self):
        """4.1 RED: dry_run=True → no execution, structure only."""
        from ms_access_mcp.mcp.analysis import analyze_query

        # Mock a connected adapter
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = []
        mock_adapter.get_table_schema_plan.return_value = ([], MagicMock())

        # Set up a connection pool mock
        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter

        with patch.object(_helpers, '_pool', return_value=mock_pool):
            result = analyze_query(
                sql="SELECT * FROM Customers",
                connection_name="test_conn",
                dry_run=True,
            )

        # Dry run should not call execute_query
        mock_adapter.execute_query.assert_not_called()
        assert result.get("success") is True

    def test_analyze_query_with_execution(self):
        """4.1 RED: With connected adapter and dry_run=False → executes query."""
        from ms_access_mcp.mcp.analysis import analyze_query

        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = []
        mock_adapter.get_table_schema_plan.return_value = ([], MagicMock())
        mock_adapter.execute_query.return_value = iter([{"_cnt": 5}])

        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter

        with patch.object(_helpers, '_pool', return_value=mock_pool):
            result = analyze_query(
                sql="SELECT * FROM Customers",
                connection_name="test_conn",
                dry_run=False,
            )

        assert result.get("success") is True
        assert "complexity" in result
        assert "recommendations" in result
        mock_adapter.execute_query.assert_called()

    def test_analyze_query_sample_size(self):
        """4.1 RED: sample_size > 0 → samples data."""
        from ms_access_mcp.mcp.analysis import analyze_query

        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = []
        mock_adapter.get_table_schema_plan.return_value = ([], MagicMock())
        mock_adapter.execute_query.side_effect = [
            iter([{"_cnt": 100}]),
            iter([{"ID": 1}, {"ID": 2}]),
        ]

        mock_pool = MagicMock()
        mock_pool.is_connected.return_value = True
        mock_pool.get_adapter.return_value = mock_adapter

        with patch.object(_helpers, '_pool', return_value=mock_pool):
            result = analyze_query(
                sql="SELECT * FROM Customers",
                connection_name="test_conn",
                dry_run=False,
                sample_size=5,
            )

        assert result.get("execution", {}).get("sample_size") == 5
        assert "sampled_data" in result.get("execution", {})
