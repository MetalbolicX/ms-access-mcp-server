"""Unit tests for OdbcAdapter.get_relationships() — delegation to the injected callable.

After the `dao-relationship-extraction` refactor, the adapter stores a
`Callable[[], list[RelationshipInfo]]` in `self._get_relationships_impl`
instead of a full reader object. These tests verify that delegation
contract.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.models.database import RelationshipInfo


class TestOdbcAdapterGetRelationships:
    """Tests that OdbcAdapter.get_relationships() correctly delegates."""

    def setup_method(self):
        self.mock_conn = MagicMock()
        with patch("pyodbc.connect", return_value=self.mock_conn):
            self.adapter = OdbcAdapter()
        self.adapter._conn = self.mock_conn

    # ------------------------------------------------------------------ #
    # No reader (disconnected / not initialized)
    # ------------------------------------------------------------------ #

    def test_get_relationships_returns_empty_when_not_connected(self):
        """Adapter with no connection returns []."""
        adapter = OdbcAdapter()
        assert adapter.get_relationships() == []

    def test_get_relationships_returns_empty_when_impl_not_wired(self):
        """Adapter connected but impl not set returns []."""
        self.adapter._get_relationships_impl = None
        self.adapter._conn = self.mock_conn
        result = self.adapter.get_relationships()
        assert result == []

    # ------------------------------------------------------------------ #
    # Reader delegated
    # ------------------------------------------------------------------ #

    def test_get_relationships_delegates_to_callable(self):
        """When impl is set, get_relationships() returns the callable's result."""
        mock_rel = RelationshipInfo(
            name="FK_Test",
            table="Child",
            foreign_table="Parent",
            columns=["child_id"],
            foreign_columns=["parent_id"],
        )
        mock_impl = MagicMock(return_value=[mock_rel])
        self.adapter._get_relationships_impl = mock_impl

        result = self.adapter.get_relationships()
        assert len(result) == 1
        assert result[0].name == "FK_Test"
        assert result[0].table == "Child"
        mock_impl.assert_called_once()

    def test_get_relationships_delegation_returns_empty(self):
        """When callable returns [], get_relationships() returns []."""
        self.adapter._get_relationships_impl = MagicMock(return_value=[])

        result = self.adapter.get_relationships()
        assert result == []

    # ------------------------------------------------------------------ #
    # Contract compliance — always returns list
    # ------------------------------------------------------------------ #

    def test_get_relationships_returns_list(self):
        """Unconnected adapter still satisfies ISchemaAdapter contract."""
        adapter = OdbcAdapter()
        assert isinstance(adapter.get_relationships(), list)

    def test_get_relationships_propagates_impl_exceptions(self):
        """An exception from the impl is NOT guarded by the adapter layer —
        the reader itself handles degradation (that's the reader's SRP)."""
        mock_impl = MagicMock(side_effect=RuntimeError(
            "This should not happen — reader must catch its own errors"
        ))
        self.adapter._get_relationships_impl = mock_impl

        with pytest.raises(RuntimeError):
            self.adapter.get_relationships()

    # ------------------------------------------------------------------ #
    # _cleanup clears the impl
    # ------------------------------------------------------------------ #

    def test_cleanup_resets_get_relationships_impl(self):
        """After _cleanup(), _get_relationships_impl is None."""
        # Simulate a connected state with impl
        self.adapter._get_relationships_impl = MagicMock()
        self.adapter._conn = self.mock_conn

        self.adapter._cleanup()
        assert self.adapter._get_relationships_impl is None
