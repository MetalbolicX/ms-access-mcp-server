"""Tests for mcp/_helpers.py shared helper functions."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server # noqa: F401
from ms_access_mcp.mcp import _helpers as helpers_module


class TestRequireConnectedDecorator:
    """Tests for the @require_connected() decorator."""

    def test_returns_error_dict_when_disconnected(self):
        """Wrapped function returns error dict when not connected."""
        from ms_access_mcp.mcp._helpers import require_connected

        @require_connected()
        def fake_tool(name: str, connection_name: str = "default") -> dict:
            return {"success": True, "name": name}

        with patch.object(helpers_module, "_check_connected", return_value=False):
            result = fake_tool("foo")
        assert result == {"success": False, "error": "Not connected"}

    def test_passes_through_when_connected(self):
        """Wrapped function executes normally when connected."""
        from ms_access_mcp.mcp._helpers import require_connected

        @require_connected()
        def fake_tool(name: str, connection_name: str = "default") -> dict:
            return {"success": True, "name": name}

        with patch.object(helpers_module, "_check_connected", return_value=True):
            result = fake_tool("foo")
        assert result == {"success": True, "name": "foo"}

    def test_uses_custom_error_return(self):
        """Custom error_return overrides the default error dict."""
        from ms_access_mcp.mcp._helpers import require_connected

        custom = {"success": False, "error": "Custom not connected"}
        decorator = require_connected(error_return=custom)

        @decorator
        def fake_tool(connection_name: str = "default") -> dict:
            return {"success": True}

        with patch.object(helpers_module, "_check_connected", return_value=False):
            result = fake_tool()
        assert result == custom

    def test_uses_default_connection_when_not_specified(self):
        """Decorator checks 'default' connection by default."""
        from ms_access_mcp.mcp._helpers import require_connected

        @require_connected()
        def fake_tool(connection_name: str = "default") -> dict:
            return {"success": True}

        with patch.object(helpers_module, "_check_connected", return_value=True) as mock_check:
            fake_tool()
        mock_check.assert_called_once_with("default")

    def test_uses_provided_connection_name(self):
        """Decorator respects explicit connection_name kwarg."""
        from ms_access_mcp.mcp._helpers import require_connected

        @require_connected()
        def fake_tool(connection_name: str = "default") -> dict:
            return {"success": True}

        with patch.object(helpers_module, "_check_connected", return_value=True) as mock_check:
            fake_tool(connection_name="other_db")
        mock_check.assert_called_once_with("other_db")

    def test_preserves_function_metadata(self):
        """functools.wraps preserves __name__ and __doc__."""
        from ms_access_mcp.mcp._helpers import require_connected

        @require_connected()
        def my_named_tool(connection_name: str = "default") -> dict:
            """My docstring."""
            return {"success": True}

        assert my_named_tool.__name__ == "my_named_tool"
        assert my_named_tool.__doc__ == "My docstring."


class TestDestructiveGuardDecorator:
    """Tests for the @destructive_guard() decorator."""

    def test_blocks_when_confirm_false(self):
        """Wrapped function returns guard error when confirm=False."""
        from ms_access_mcp.mcp._helpers import destructive_guard

        @destructive_guard(action="delete_query")
        def fake_tool(name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
            return {"success": True, "deleted": name}

        with patch.object(helpers_module, "_check_connected", return_value=True):
            result = fake_tool("myquery", confirm=False)
        assert result["success"] is False
        assert "confirm=True required" in result["error"]
        assert "delete_query" in result["error"]

    def test_dry_run_returns_preview(self):
        """Wrapped function returns dry-run preview when dry_run=True."""
        from ms_access_mcp.mcp._helpers import destructive_guard

        @destructive_guard(action="delete_query")
        def fake_tool(name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
            return {"success": True, "deleted": name}

        with patch.object(helpers_module, "_check_connected", return_value=True):
            result = fake_tool("myquery", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "delete_query"
        assert result["name"] == "myquery"

    def test_proceeds_when_confirm_true(self):
        """Wrapped function executes when confirm=True and not dry_run."""
        from ms_access_mcp.mcp._helpers import destructive_guard

        @destructive_guard(action="delete_query")
        def fake_tool(name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
            return {"success": True, "deleted": name}

        with patch.object(helpers_module, "_check_connected", return_value=True):
            result = fake_tool("myquery", confirm=True)
        assert result == {"success": True, "deleted": "myquery"}

    def test_checks_connection_before_guard(self):
        """Decorator checks connection first, then runs guard."""
        from ms_access_mcp.mcp._helpers import destructive_guard

        @destructive_guard(action="delete_query")
        def fake_tool(name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
            return {"success": True, "deleted": name}

        with patch.object(helpers_module, "_check_connected", return_value=False):
            result = fake_tool("myquery", confirm=True)
        assert result == {"success": False, "error": "Not connected"}

    def test_includes_function_args_in_context(self):
        """Non-special kwargs are passed as context to guard_destructive."""
        from ms_access_mcp.mcp._helpers import destructive_guard

        @destructive_guard(action="delete_query")
        def fake_tool(
            name: str,
            table_name: str = "default_table",
            connection_name: str = "default",
            confirm: bool = False,
            dry_run: bool = False,
        ) -> dict:
            return {"success": True}

        with patch.object(helpers_module, "_check_connected", return_value=True):
            result = fake_tool("myquery", table_name="Users", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "delete_query"
        assert result["name"] == "myquery"
        assert result["table_name"] == "Users"

    def test_preserves_function_metadata(self):
        """functools.wraps preserves __name__ and __doc__."""
        from ms_access_mcp.mcp._helpers import destructive_guard

        @destructive_guard(action="delete_query")
        def my_destructive_tool(name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
            """Destructive docstring."""
            return {"success": True}

        assert my_destructive_tool.__name__ == "my_destructive_tool"
        assert my_destructive_tool.__doc__ == "Destructive docstring."


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
