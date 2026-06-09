"""Tests for mcp/_helpers.py shared helper functions."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server # noqa: F401
from ms_access_mcp.mcp import _helpers as helpers_module


class TestGuardDestructive:
    """Tests for guard_destructive() helper."""

    def test_guard_destructive_dry_run_returns_preview_dict(self):
        """guard_destructive with dry_run=True returns preview dict."""
        from ms_access_mcp.mcp._helpers import guard_destructive

        result = guard_destructive(confirm=True, dry_run=True, action="delete_module", module_name="modTest")
        assert result["dry_run"] is True
        assert result["action"] == "delete_module"
        assert result["module_name"] == "modTest"

    def test_guard_destructive_confirm_false_returns_error_dict(self):
        """guard_destructive with confirm=False returns error dict."""
        from ms_access_mcp.mcp._helpers import guard_destructive

        result = guard_destructive(confirm=False, dry_run=False, action="delete_module", module_name="modTest")
        assert result["success"] is False
        assert "confirm=True required" in result["error"]
        assert "delete_module" in result["error"]

    def test_guard_destructive_confirm_true_dry_run_false_returns_none(self):
        """guard_destructive with confirm=True and dry_run=False returns None (proceed)."""
        from ms_access_mcp.mcp._helpers import guard_destructive

        result = guard_destructive(confirm=True, dry_run=False, action="delete_module", module_name="modTest")
        assert result is None

    def test_guard_destructive_passes_through_context_kwargs(self):
        """guard_destructive passes all extra kwargs through in the return dict."""
        from ms_access_mcp.mcp._helpers import guard_destructive

        result = guard_destructive(
            confirm=False, dry_run=False, action="update_data",
            table_name="Users", set_dict={"Name": "Bob"}, where_dict=None
        )
        assert result["success"] is False
        assert result["table_name"] == "Users"
        assert result["set_dict"] == {"Name": "Bob"}
        assert result["where_dict"] is None

    def test_guard_destructive_dry_run_with_extra_context(self):
        """guard_destructive dry_run=True includes all context in preview."""
        from ms_access_mcp.mcp._helpers import guard_destructive

        result = guard_destructive(
            confirm=True, dry_run=True, action="set_vba_code",
            module_name="modTest", code="Sub Test()\nEnd Sub"
        )
        assert result["dry_run"] is True
        assert result["action"] == "set_vba_code"
        assert result["module_name"] == "modTest"
        assert result["code"] == "Sub Test()\nEnd Sub"

    def test_guard_destructive_all_combinations(self):
        """Verify all four confirm/dry_run combinations produce expected results."""
        from ms_access_mcp.mcp._helpers import guard_destructive

        # (confirm, dry_run) -> expected
        combos = [
            (False, False, "error"), # confirm=False, dry_run=False -> error
            (False, True, "dry_run"),  # confirm=False, dry_run=True -> dry_run
            (True, False, "proceed"),  # confirm=True, dry_run=False -> None
            (True, True, "dry_run"), # confirm=True, dry_run=True -> dry_run
        ]
        for confirm, dry_run, expected in combos:
            result = guard_destructive(confirm=confirm, dry_run=dry_run, action="test_action", name="test")
            if expected == "error":
                assert result["success"] is False, f"confirm={confirm}, dry_run={dry_run}"
            elif expected == "dry_run":
                assert result["dry_run"] is True, f"confirm={confirm}, dry_run={dry_run}"
            else:  # proceed
                assert result is None, f"confirm={confirm}, dry_run={dry_run}"
