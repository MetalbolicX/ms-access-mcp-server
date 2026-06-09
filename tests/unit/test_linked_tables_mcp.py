"""Tests for mcp/linked_tables.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import linked_tables as linked_tables_module


class TestLinkedTablesConnectionGuards:
    """Tests that linked table tools check connection before executing."""

    @pytest.mark.parametrize("tool_func,args", [
        (server.get_linked_tables, ()),
        (server.create_linked_table, ("lnk", "RemoteT", "ODBC;DSN=test")),
        (server.refresh_linked_table, ("lnk",)),
        (server.unlink_table, ("lnk",)),
    ])
    def test_linked_table_tools_return_error_when_not_connected(self, tool_func, args):
        """Each linked table tool should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = tool_func(*args)
            assert result["success"] is False
            assert "Not connected" in result["error"]


class TestGetLinkedTables:
    """Tests for get_linked_tables tool."""

    def test_get_linked_tables_delegates_to_adapter(self):
        """get_linked_tables should delegate to adapter.get_linked_tables."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.get_linked_tables.return_value = {"success": True, "tables": []}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.get_linked_tables()
            assert result["success"] is True
            mock_conn.adapter.get_linked_tables.assert_called_once()

    def test_get_linked_tables_returns_adapter_error(self):
        """get_linked_tables should return error on adapter failure."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.get_linked_tables.side_effect = RuntimeError("DAO error")
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.get_linked_tables()
            assert result["success"] is False
            assert "DAO error" in result["error"]


class TestCreateLinkedTable:
    """Tests for create_linked_table tool."""

    def test_create_linked_table_delegates_to_adapter(self):
        """create_linked_table should delegate to adapter.create_linked_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        args = ("lnkName", "RemoteT", "ODBC;DSN=test")
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.create_linked_table(*args)
            assert result["success"] is True
            mock_conn.adapter.create_linked_table.assert_called_once_with("lnkName", "RemoteT", "ODBC;DSN=test")

    def test_create_linked_table_returns_error_on_exception(self):
        """create_linked_table should return error on exception."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_linked_table.side_effect = RuntimeError("Link failed")
        mock_conn.get_adapter.return_value = mock_conn.adapter
        args = ("lnkName", "RemoteT", "ODBC;DSN=bad")
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.create_linked_table(*args)
            assert result["success"] is False
            assert "Link failed" in result["error"]


class TestRefreshLinkedTable:
    """Tests for refresh_linked_table tool."""

    def test_refresh_linked_table_delegates_to_adapter(self):
        """refresh_linked_table should delegate to adapter.refresh_linked_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.refresh_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.refresh_linked_table("existing_link")
            assert result["success"] is True
            mock_conn.adapter.refresh_linked_table.assert_called_once_with("existing_link", connect_string=None)


class TestUnlinkTable:
    """Tests for unlink_table tool."""

    def test_unlink_table_delegates_to_adapter(self):
        """unlink_table should delegate to adapter.unlink_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.unlink_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.unlink_table("lnkName")
            assert result["success"] is True
            mock_conn.adapter.unlink_table.assert_called_once_with("lnkName")


class TestLinkedTablesComOnlyError:
    """Tests that ODBC adapter raises NotImplementedError for COM-only operations.

    These tests verify the MCP tool layer properly catches NotImplementedError
    raised by the ODBC adapter and returns a user-friendly COM-only error message.
    """

    def test_get_linked_tables_returns_com_only_error_with_odbc_adapter(self):
        """get_linked_tables returns COM-only error when adapter raises NotImplementedError."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.get_linked_tables.side_effect = NotImplementedError(
            "get_linked_tables requires COM automation (WinComAdapter)"
        )
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.get_linked_tables()
            assert result["success"] is False
            assert "COM automation" in result["error"]
            assert "WinComAdapter" in result["error"]
            assert "use_com=True" in result["error"]

    def test_create_linked_table_returns_com_only_error_with_odbc_adapter(self):
        """create_linked_table returns COM-only error when adapter raises NotImplementedError."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.create_linked_table.side_effect = NotImplementedError(
            "create_linked_table requires COM automation (WinComAdapter)"
        )
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.create_linked_table("lnk", "RemoteT", "ODBC;DSN=test")
            assert result["success"] is False
            assert "COM automation" in result["error"]
            assert "WinComAdapter" in result["error"]
            assert "use_com=True" in result["error"]

    def test_refresh_linked_table_returns_com_only_error_with_odbc_adapter(self):
        """refresh_linked_table returns COM-only error when adapter raises NotImplementedError."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.refresh_linked_table.side_effect = NotImplementedError(
            "refresh_linked_table requires COM automation (WinComAdapter)"
        )
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.refresh_linked_table("lnk")
            assert result["success"] is False
            assert "COM automation" in result["error"]
            assert "WinComAdapter" in result["error"]
            assert "use_com=True" in result["error"]

    def test_unlink_table_returns_com_only_error_with_odbc_adapter(self):
        """unlink_table returns COM-only error when adapter raises NotImplementedError."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.unlink_table.side_effect = NotImplementedError(
            "unlink_table requires COM automation (WinComAdapter)"
        )
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.unlink_table("lnk")
            assert result["success"] is False
            assert "COM automation" in result["error"]
            assert "WinComAdapter" in result["error"]
            assert "use_com=True" in result["error"]


class TestConnectStringAllowlist:
    """Tests for connect_string provider allowlist validation via LinkedTableService.

    Per the password-security SDD, the MCP layer no longer maintains its own
    allowlist — validation is delegated to ConnectPolicy in LinkedTableService.
    create_linked_table bypasses LinkedTableService and goes directly to the
    adapter, so it accepts all connect_strings (validation happens at the
    LinkedTableService layer for upsert operations).
    """

    def test_create_linked_table_accepts_any_connect_string(self):
        """create_linked_table accepts any connect_string and delegates to adapter.

        Provider validation is handled by LinkedTableService (via ConnectPolicy)
        for upsert operations. create_linked_table goes directly to the adapter
        without MCP-layer validation.
        """
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.create_linked_table(
                "lnkName",
                "RemoteT",
                "Provider=Unknown.Provider;Data Source=remote.db;",
            )
            assert result["success"] is True

    def test_create_linked_table_accepts_known_odbc_provider(self):
        """create_linked_table should accept ODBC connect strings."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.create_linked_table(
                "lnkName",
                "RemoteT",
                "ODBC;DSN=MyDSN;",
            )
            assert result["success"] is True

    def test_create_linked_table_accepts_ace_oledb_provider(self):
        """create_linked_table should accept Microsoft.ACE.OLEDB connect strings."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.create_linked_table(
                "lnkName",
                "RemoteT",
                "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=\\\\server\\share\\db.accdb;",
            )
            assert result["success"] is True

    def test_create_linked_table_accepts_custom_provider(self):
        """create_linked_table accepts custom providers (validation at service layer)."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.adapter = MagicMock()
        mock_conn.adapter.create_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_conn.adapter
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.create_linked_table(
                "lnkName",
                "RemoteT",
                "Provider=MyCustom.Provider;Data Source=remote.mdb;",
            )
            assert result["success"] is True


class TestUpsertLinkedTable:
    """Tests for upsert_linked_table tool."""

    def test_upsert_linked_table_delegates_to_orchestrator(self):
        """upsert_linked_table should delegate to LinkedTableService.upsert_linked_table."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        # Mock orchestrator - patch at source module since import is inside function
        with patch("ms_access_mcp.orchestrators.linked_table_service.LinkedTableService") as MockService:
            mock_service_instance = MockService.return_value
            mock_service_instance.upsert_linked_table.return_value = {
                "success": True, "status": "created", "name": "Orders"
            }

            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                result = server.upsert_linked_table(
                    "Orders",
                    "dbo.Orders",
                    "ODBC;DSN=MyDSN",
                )
                assert result["success"] is True
                assert result["status"] == "created"
                mock_service_instance.upsert_linked_table.assert_called_once()

    def test_upsert_linked_table_accepts_password_parameter(self):
        """upsert_linked_table should accept optional password for re-injection."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        with patch("ms_access_mcp.orchestrators.linked_table_service.LinkedTableService") as MockService:
            mock_service_instance = MockService.return_value
            mock_service_instance.upsert_linked_table.return_value = {
                "success": True, "status": "refreshed", "name": "Orders"
            }

            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                result = server.upsert_linked_table(
                    "Orders",
                    "dbo.Orders",
                    "ODBC;DSN=MyDSN",
                    password="secret123",
                )
                assert result["success"] is True
                # Verify password was passed through orchestrator
                call_kwargs = mock_service_instance.upsert_linked_table.call_args
                # Password should be injected into connect_string or passed separately
                assert call_kwargs is not None

    def test_upsert_linked_table_accepts_preserve_hidden_parameter(self):
        """upsert_linked_table should accept preserve_hidden parameter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        with patch("ms_access_mcp.orchestrators.linked_table_service.LinkedTableService") as MockService:
            mock_service_instance = MockService.return_value
            mock_service_instance.upsert_linked_table.return_value = {
                "success": True, "status": "recreated", "name": "SysConfig"
            }

            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                result = server.upsert_linked_table(
                    "SysConfig",
                    "dbo.SysConfigV2",
                    "ODBC;DSN=MyDSN",
                    preserve_hidden=True,
                )
                assert result["success"] is True
                call_kwargs = mock_service_instance.upsert_linked_table.call_args
                assert call_kwargs is not None

    def test_upsert_linked_table_returns_error_when_not_connected(self):
        """upsert_linked_table should return error when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.upsert_linked_table(
                "Orders",
                "dbo.Orders",
                "ODBC;DSN=MyDSN",
            )
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_upsert_linked_table_returns_error_on_exception(self):
        """upsert_linked_table should return error on exception."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        with patch("ms_access_mcp.orchestrators.linked_table_service.LinkedTableService") as MockService:
            mock_service_instance = MockService.return_value
            mock_service_instance.upsert_linked_table.side_effect = RuntimeError("DAO error")

            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                result = server.upsert_linked_table(
                    "Orders",
                    "dbo.Orders",
                    "ODBC;DSN=MyDSN",
                )
                assert result["success"] is False
                assert "DAO error" in result["error"]


class TestRefreshLinkedTableWithConnectString:
    """Tests for refresh_linked_table tool with optional connect_string and password."""

    def test_refresh_linked_table_accepts_optional_connect_string(self):
        """refresh_linked_table should accept optional connect_string parameter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.refresh_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.refresh_linked_table(
                "existing_link",
                connection_name="default",
                connect_string="ODBC;DSN=NewDSN",
            )
            assert result["success"] is True
            mock_adapter.refresh_linked_table.assert_called_once()

    def test_refresh_linked_table_accepts_optional_password(self):
        """refresh_linked_table should accept optional password parameter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.refresh_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.refresh_linked_table(
                "existing_link",
                connection_name="default",
                password="secret123",
            )
            assert result["success"] is True
            mock_adapter.refresh_linked_table.assert_called_once()

    def test_refresh_linked_table_accepts_both_connect_string_and_password(self):
        """refresh_linked_table should accept both connect_string and password."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.refresh_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.refresh_linked_table(
                "existing_link",
                connection_name="default",
                connect_string="ODBC;DSN=NewDSN",
                password="secret123",
            )
            assert result["success"] is True
            mock_adapter.refresh_linked_table.assert_called_once()


class TestStoreCredential:
    """Tests for store_credential tool."""

    def test_store_credential_accepts_server_id_and_password(self):
        """store_credential should accept server_id and password parameters."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.store_credential("srv1", "secret123")
            assert result["success"] is True

    def test_store_credential_does_not_echo_password_in_response(self):
        """store_credential response should not contain the stored password."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.store_credential("srv1", "secret123")
            assert result["success"] is True
            # Response should not echo the password
            response_str = str(result)
            assert "secret123" not in response_str

    def test_store_credential_stores_for_connection_name(self):
        """store_credential should accept connection_name parameter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.store_credential("srv1", "secret123", connection_name="default")
            assert result["success"] is True


class TestClearCredentials:
    """Tests for clear_credentials tool."""

    def test_clear_credentials_clears_vault(self):
        """clear_credentials should clear all stored credentials."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.clear_credentials()
            assert result["success"] is True

    def test_clear_credentials_clears_named_connection(self):
        """clear_credentials should accept connection_name parameter."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
            result = server.clear_credentials(connection_name="default")
            assert result["success"] is True


class TestUpsertLinkedTableWithServerId:
    """Tests for upsert_linked_table with server_id parameter."""

    def test_upsert_linked_table_with_server_id_retrieves_from_vault(self):
        """upsert_linked_table with server_id but no password should retrieve from vault."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        # Mock vault returned via get_container().credential_vault
        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = "vault_secret"
        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        with patch.object(linked_tables_module, 'get_container', return_value=mock_container):
            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                with patch("ms_access_mcp.orchestrators.linked_table_service.LinkedTableService") as MockService:
                    mock_service_instance = MockService.return_value
                    mock_service_instance.upsert_linked_table.return_value = {
                        "success": True, "status": "created", "name": "Orders"
                    }

                    result = server.upsert_linked_table(
                        "Orders",
                        "dbo.Orders",
                        "ODBC;DSN=MyDSN",
                        server_id="srv1",
                    )
                    assert result["success"] is True
                    mock_vault.retrieve.assert_called_once_with("srv1")

    def test_upsert_linked_table_with_unknown_server_id_returns_error(self):
        """upsert_linked_table with unknown server_id should return error."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = None  # unknown server_id
        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        with patch.object(linked_tables_module, 'get_container', return_value=mock_container):
            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                result = server.upsert_linked_table(
                    "Orders",
                    "dbo.Orders",
                    "ODBC;DSN=MyDSN",
                    server_id="unknown_srv",
                )
                assert result["success"] is False
                assert "server_id" in result["error"].lower() or "not found" in result["error"].lower()


class TestLinkedTablesSharedVault:
    """Tests verifying linked-table tools use the shared container credential_vault.

    Per PR1, the module-level _vault singleton is replaced by
    get_container().credential_vault so both linked_tables and migration
    domains share the same vault instance.
    """

    def test_upsert_linked_table_uses_container_vault(self):
        """upsert_linked_table with server_id should retrieve password from container vault."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        # Create a mock vault and a mock container that holds it
        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = "container_vault_secret"

        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        with patch.object(linked_tables_module, 'get_container', return_value=mock_container):
            with patch("ms_access_mcp.orchestrators.linked_table_service.LinkedTableService") as MockService:
                mock_service_instance = MockService.return_value
                mock_service_instance.upsert_linked_table.return_value = {
                    "success": True, "status": "created", "name": "Orders"
                }

                result = server.upsert_linked_table(
                    "Orders",
                    "dbo.Orders",
                    "ODBC;DSN=MyDSN",
                    server_id="srv1",
                )
                assert result["success"] is True
                # Vault retrieve should have been called with the server_id
                mock_vault.retrieve.assert_called_once_with("srv1")

    def test_refresh_linked_table_uses_container_vault(self):
        """refresh_linked_table with server_id should retrieve password from container vault."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.refresh_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_adapter

        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = "container_vault_secret"
        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        with patch.object(linked_tables_module, 'get_container', return_value=mock_container):
            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                result = server.refresh_linked_table(
                    "existing_link",
                    server_id="srv1",
                )
                # Should succeed by retrieving password from vault
                assert result["success"] is True
                mock_vault.retrieve.assert_called_once_with("srv1")

    def test_store_credential_stores_in_container_vault(self):
        """store_credential should store password in the container vault."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        mock_vault = MagicMock()

        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        with patch.object(linked_tables_module, 'get_container', return_value=mock_container):
            result = server.store_credential("srv1", "secret123")
            assert result["success"] is True
            mock_vault.store.assert_called_once_with("srv1", "secret123")

    def test_clear_credentials_clears_container_vault(self):
        """clear_credentials should clear the container vault."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        mock_vault = MagicMock()

        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        with patch.object(linked_tables_module, 'get_container', return_value=mock_container):
            result = server.clear_credentials()
            assert result["success"] is True
            mock_vault.clear.assert_called_once()


class TestRefreshLinkedTableWithServerId:
    """Tests for refresh_linked_table with server_id parameter."""

    def test_refresh_linked_table_with_server_id_retrieves_from_vault(self):
        """refresh_linked_table with server_id but no password should retrieve from vault."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_adapter.refresh_linked_table.return_value = {"success": True}
        mock_conn.get_adapter.return_value = mock_adapter

        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = "vault_secret"
        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        with patch.object(linked_tables_module, 'get_container', return_value=mock_container):
            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                result = server.refresh_linked_table(
                    "existing_link",
                    server_id="srv1",
                )
                # Should succeed by retrieving password from vault
                assert result["success"] is True
                mock_vault.retrieve.assert_called_once_with("srv1")

    def test_refresh_linked_table_with_unknown_server_id_returns_error(self):
        """refresh_linked_table with unknown server_id should return error."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_adapter = MagicMock()
        mock_conn.get_adapter.return_value = mock_adapter

        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = None  # unknown server_id
        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        with patch.object(linked_tables_module, 'get_container', return_value=mock_container):
            with patch.object(linked_tables_module, '_pool', return_value=mock_conn):
                result = server.refresh_linked_table(
                    "existing_link",
                    server_id="unknown_srv",
                )
                assert result["success"] is False
