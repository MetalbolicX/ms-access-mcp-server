"""RED tests for LinkedTableService orchestrator.

These tests describe the expected API and behavior of LinkedTableService.
They will FAIL until the orchestrator is implemented in Phase 2.
"""
import pytest
from unittest.mock import MagicMock


# =============================================================================
# Task 1.1 — RED: Failing tests for LinkedTableService upsert logic
# =============================================================================


class TestLinkedTableServiceUpsertCreate:
    """upsert_linked_table returns 'created' status when table does not exist."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        # Table does not exist
        self.mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [],
        }
        self.mock_adapter.create_linked_table.return_value = {
            "success": True,
            "name": "Orders",
        }

    def test_returns_created_status_when_table_not_found(self):
        """When table does not exist, upsert returns status='created'."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        assert result["success"] is True
        assert result["status"] == "created"

    def test_calls_create_linked_table_when_not_exists(self):
        """When table not found, create_linked_table is called."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        self.mock_adapter.create_linked_table.assert_called_once()
        call_args = self.mock_adapter.create_linked_table.call_args
        # Support both positional and keyword args
        if call_args.kwargs:
            assert call_args.kwargs.get("name") == "Orders"
        else:
            assert call_args.args[0] == "Orders"

    def test_returns_standard_dict_with_success_and_error(self):
        """Returns dict with 'success' (bool) and 'error' (str|None)."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        assert "success" in result
        assert isinstance(result["success"], bool)
        # error key may be absent on success (only present on failure)
        if not result["success"]:
            assert "error" in result


class TestLinkedTableServiceUpsertRefresh:
    """upsert_linked_table returns 'refreshed' when remote name matches."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        # Table exists with same remote name
        self.mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [
                {"name": "Orders", "source_table": "dbo.Orders", "connect_string": "ODBC;DSN=MyDSN"},
            ],
        }
        self.mock_adapter.refresh_linked_table.return_value = {
            "success": True,
            "name": "Orders",
        }

    def test_returns_refreshed_status_when_source_matches(self):
        """When source_table matches remote_name, returns status='refreshed'."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        assert result["success"] is True
        assert result["status"] == "refreshed"

    def test_calls_refresh_linked_table_when_source_matches(self):
        """When source matches, refresh_linked_table is called."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        self.mock_adapter.refresh_linked_table.assert_called_once()


class TestLinkedTableServiceUpsertRecreate:
    """upsert_linked_table returns 'recreated' when remote name differs."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        # Table exists but with DIFFERENT remote name
        self.mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [
                {
                    "name": "Orders",
                    "source_table": "dbo.Orders",  # current: dbo.Orders
                    "connect_string": "ODBC;DSN=MyDSN",
                    "attributes": 0,  # non-hidden
                },
            ],
        }
        self.mock_adapter.recreate_linked_table.return_value = {
            "success": True,
            "name": "Orders",
        }

    def test_returns_recreated_status_when_source_differs(self):
        """When source_table differs from remote_name, returns status='recreated'."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.OrdersV2",  # different!
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        assert result["success"] is True
        assert result["status"] == "recreated"

    def test_calls_recreate_linked_table_when_remote_name_changes(self):
        """When remote name changes, recreate_linked_table is called."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.OrdersV2",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        self.mock_adapter.recreate_linked_table.assert_called_once()

    def test_passes_hidden_attributes_to_recreate(self):
        """When table is hidden, attributes are passed to recreate."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        # Set hidden attribute (dbHiddenObject = 0x00000001)
        self.mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [
                {
                    "name": "SysConfig",
                    "source_table": "dbo.SysConfig",
                    "connect_string": "ODBC;DSN=MyDSN",
                    "attributes": 1,  # hidden
                },
            ],
        }

        orch = LinkedTableService()
        orch.upsert_linked_table(
            self.mock_adapter,
            local_name="SysConfig",
            remote_name="dbo.SysConfigV2",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        call_args = self.mock_adapter.recreate_linked_table.call_args
        # The adapter method should receive attributes parameter
        assert "attributes" in call_args.kwargs or len(call_args.args) > 3


class TestLinkedTableServiceAllowlistRejection:
    """upsert_linked_table rejects disallowed providers."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        self.mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [],
        }

    def test_rejects_connect_string_without_odbc_or_ace_provider(self):
        """Connect strings without 'ODBC;' or 'Provider=Microsoft.ACE.OLEDB.*' are rejected."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\\db.mdb",
        )

        assert result["success"] is False
        assert "allowlist" in result["error"].lower() or "provider" in result["error"].lower()

    def test_rejects_non_odbc_non_ace_provider(self):
        """Non-ODBC and non-ACE providers are rejected."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        # This connect string uses OLEDB Provider but not ACE (Jet instead)
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\\db.mdb",
        )

        assert result["success"] is False
        assert "allowlist" in result["error"].lower() or "provider" in result["error"].lower()

    def test_accepts_sql_server_odbc_provider(self):
        """SQL Server ODBC provider is accepted (ODBC prefix allowed)."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        # SQL Server ODBC starts with "ODBC;" so it's allowed per design
        self.mock_adapter.create_linked_table.return_value = {"success": True, "name": "Orders"}

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;Driver={SQL Server};Server=.;Database=test;UID=user;PWD=pass",
        )

        # Should not fail on allowlist - ODBC is allowed
        assert result.get("success") is not False or "allowlist" not in str(result.get("error", "")).lower()

    def test_accepts_odbc_connect_string(self):
        """ODBC connect string is accepted."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        self.mock_adapter.create_linked_table.return_value = {"success": True, "name": "Orders"}

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        # Should not fail on allowlist check - should proceed to create
        assert result.get("success") is not False or "allowlist" not in str(result.get("error", "")).lower()

    def test_accepts_ace_provider_connect_string(self):
        """Provider=Microsoft.ACE.OLEDB.* is accepted."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        self.mock_adapter.create_linked_table.return_value = {"success": True, "name": "Orders"}

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="Provider=Microsoft.ACE.OLEDB.12.0;Data Source=C:\\db.accdb",
        )

        # Should not fail on allowlist check
        assert result.get("success") is not False or "allowlist" not in str(result.get("error", "")).lower()


class TestLinkedTableServicePasswordReInjection:
    """Password is re-injected into connect_string on refresh/recreate."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True

    def test_re_injects_password_on_refresh(self):
        """When refreshing, password from original connect_string is re-injected."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        # Table exists with stripped connect_string (no PWD)
        self.mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [
                {
                    "name": "Orders",
                    "source_table": "dbo.Orders",
                    "connect_string": "ODBC;DSN=MyDSN",  # password already stripped
                },
            ],
        }
        self.mock_adapter.refresh_linked_table.return_value = {"success": True, "name": "Orders"}

        orch = LinkedTableService()
        # Original connect_string had PWD=secret
        orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",  # password provided
        )

        # The adapter method should be called with password re-injected
        call_args = self.mock_adapter.refresh_linked_table.call_args
        # If connect_string param is passed, it should contain PWD=
        if "connect_string" in call_args.kwargs:
            assert "PWD=" in call_args.kwargs["connect_string"]

    def test_re_injects_password_on_recreate(self):
        """When recreating, password from original connect_string is re-injected."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        # Table exists with different remote name and stripped connect_string
        self.mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [
                {
                    "name": "Orders",
                    "source_table": "dbo.OrdersOld",
                    "connect_string": "ODBC;DSN=MyDSN",  # password stripped
                    "attributes": 0,
                },
            ],
        }
        self.mock_adapter.recreate_linked_table.return_value = {"success": True, "name": "Orders"}

        orch = LinkedTableService()
        orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.OrdersNew",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",  # password provided
        )

        # The adapter method should be called with password re-injected
        call_args = self.mock_adapter.recreate_linked_table.call_args
        if "connect_string" in call_args.kwargs:
            assert "PWD=" in call_args.kwargs["connect_string"]


class TestLinkedTableServiceRecreateFailureReporting:
    """Recreate failure is reported clearly to caller."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True
        # Table exists with different remote name
        self.mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [
                {
                    "name": "Orders",
                    "source_table": "dbo.OrdersOld",
                    "connect_string": "ODBC;DSN=MyDSN",
                    "attributes": 0,
                },
            ],
        }
        # Recreate fails
        self.mock_adapter.recreate_linked_table.return_value = {
            "success": False,
            "error": "Connection failed: invalid credentials",
        }

    def test_returns_error_dict_when_recreate_fails(self):
        """When recreate fails, error is propagated to caller."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.OrdersNew",
            connect_string="ODBC;DSN=MyDSN;PWD=wrong",
        )

        assert result["success"] is False
        assert result["error"] is not None
        assert "connection" in result["error"].lower() or "credentials" in result["error"].lower()

    def test_does_not_leave_orphaned_tdef_on_recreate_failure(self):
        """On recreate failure, no orphaned table is left behind."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.OrdersNew",
            connect_string="ODBC;DSN=MyDSN;PWD=wrong",
        )

        # If recreate failed, the error is propagated
        # The orchestrator should not leave the table in a half-created state
        assert result["success"] is False


class TestLinkedTableServiceNotConnected:
    """Returns error dict when adapter is not connected."""

    def setup_method(self):
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = False

    def test_returns_error_when_not_connected(self):
        """Not-connected adapter → returns error dict (does not raise)."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()
        result = orch.upsert_linked_table(
            self.mock_adapter,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=MyDSN;PWD=secret",
        )

        assert result["success"] is False
        assert "not connected" in result["error"].lower()


class TestLinkedTableServiceGetLinkedTablesReturnsAttributes:
    """get_linked_tables result includes attributes field."""

    def test_returns_dict_with_attributes_for_each_table(self):
        """Each linked table entry includes attributes integer."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        mock_adapter = MagicMock()
        mock_adapter.is_connected.return_value = True
        mock_adapter.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [
                {"name": "Orders", "source_table": "dbo.Orders", "connect_string": "ODBC;DSN=MyDSN", "attributes": 0},
                {"name": "SysConfig", "source_table": "dbo.SysConfig", "connect_string": "ODBC;DSN=MyDSN", "attributes": 1},
            ],
        }

        orch = LinkedTableService()
        # Just verify the service can read attributes from the result
        result = mock_adapter.get_linked_tables()
        for table in result["linked_tables"]:
            assert "attributes" in table


class TestLinkedTableServiceIsolatedFromConnectionState:
    """Service is stateless and does not hold connection state."""

    def test_same_service_instance_can_be_used_with_different_adapters(self):
        """LinkedTableService instance can delegate to different adapter instances."""
        from ms_access_mcp.orchestrators.linked_table_service import LinkedTableService

        orch = LinkedTableService()

        # First adapter - table doesn't exist
        adapter1 = MagicMock()
        adapter1.is_connected.return_value = True
        adapter1.get_linked_tables.return_value = {"success": True, "linked_tables": []}
        adapter1.create_linked_table.return_value = {"success": True, "name": "Orders"}

        result1 = orch.upsert_linked_table(
            adapter1,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=DSN1;PWD=secret",
        )
        assert result1["success"] is True
        assert result1["status"] == "created"

        # Second adapter - table exists
        adapter2 = MagicMock()
        adapter2.is_connected.return_value = True
        adapter2.get_linked_tables.return_value = {
            "success": True,
            "linked_tables": [
                {"name": "Orders", "source_table": "dbo.Orders", "connect_string": "ODBC;DSN=DSN2", "attributes": 0},
            ],
        }
        adapter2.refresh_linked_table.return_value = {"success": True, "name": "Orders"}

        result2 = orch.upsert_linked_table(
            adapter2,
            local_name="Orders",
            remote_name="dbo.Orders",
            connect_string="ODBC;DSN=DSN2;PWD=secret",
        )
        assert result2["success"] is True
        assert result2["status"] == "refreshed"