"""Tests for mcp/connection.py tool bindings."""
import sys
from unittest.mock import patch, MagicMock
import pytest
# Import server first to resolve circular dependency
from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import connection as conn_module


class TestConnectAccess:
    """Tests for connect_access tool."""

    def test_connect_access_returns_success_when_service_connect_succeeds(self):
        """connect_access should return success when connection_service.connect succeeds."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = True
        mock_conn.current_database = "test.accdb"
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.connect_access("test.accdb")
            assert result["success"] is True
            assert result["connected"] is True
            mock_conn.connect.assert_called_once()

    def test_connect_access_returns_failure_when_service_connect_fails(self):
        """connect_access should return failure when connection_service.connect fails."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = False
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.connect_access("test.accdb")
            assert result["success"] is False
            assert result["connected"] is False


class TestDisconnectAccess:
    """Tests for disconnect_access tool."""

    def test_disconnect_access_returns_true(self):
        """disconnect_access should always return success."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.disconnect_access()
            assert result["success"] is True
            mock_conn.disconnect.assert_called_once()


class TestIsConnected:
    """Tests for is_connected tool."""

    def test_is_connected_returns_true_when_connected(self):
        """is_connected should return True when connection_service is connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.current_database = "/path/to/db.accdb"
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.is_connected()
            assert result["connected"] is True
            assert result["database"] == "/path/to/db.accdb"

    def test_is_connected_returns_false_when_disconnected(self):
        """is_connected should return False when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.current_database = None
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.is_connected()
            assert result["connected"] is False


class TestConnectAccessWithName:
    """Tests for connect_access tool with name parameter."""

    def test_connect_access_with_name_param(self):
        """connect_access with name parameter should include name in response."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = True
        mock_com = MagicMock()
        with (
            patch.object(conn_module, '_pool', return_value=mock_conn),
            patch.object(conn_module, '_com', return_value=mock_com),
        ):
            result = conn_module.connect_access("test.accdb", use_com=False, name="prod")
            assert result["name"] == "prod"

    def test_connect_access_name_in_response(self):
        """connect_access response should contain name key."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = True
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.connect_access("test.accdb", name="prod")
            assert "name" in result


class TestConnectAccessWithPassword:
    """Tests for connect_access tool with password parameter."""

    def test_connect_access_passes_password_to_pool(self):
        """connect_access(database_path, password='...') should pass password to pool.connect()."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = MagicMock()  # New API returns ConnectionState
        with (
            patch.object(conn_module, '_pool', return_value=mock_conn),
            patch.object(conn_module, '_get_path_guard', return_value=None),
        ):
            result = conn_module.connect_access("test.accdb", password="dbsecret")
            call_args = mock_conn.connect.call_args
            assert call_args is not None, "pool.connect() was not called"
            _, kwargs = call_args
            assert kwargs.get("password") == "dbsecret", \
                f"password should be 'dbsecret', got {kwargs}"

    def test_connect_access_with_password_and_use_com(self):
        """connect_access with password and use_com=True should pass both to pool."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = MagicMock()
        with (
            patch.object(conn_module, '_pool', return_value=mock_conn),
            patch.object(conn_module, '_get_path_guard', return_value=None),
        ):
            result = conn_module.connect_access("test.accdb", use_com=True, password="comsecret")
            assert result["success"] is True
            call_args = mock_conn.connect.call_args
            assert call_args is not None
            _, kwargs = call_args
            assert kwargs.get("password") == "comsecret"

    def test_connect_access_without_password_is_backward_compatible(self):
        """connect_access without password should still work (backward compatible)."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = MagicMock()
        with (
            patch.object(conn_module, '_pool', return_value=mock_conn),
            patch.object(conn_module, '_get_path_guard', return_value=None),
        ):
            result = conn_module.connect_access("test.accdb")
            assert result["success"] is True


class TestConnectAccessBackendParam:
    """connect_access accepts an optional ``backend=`` selector arg (slice 2).

    The legacy ``use_com`` parameter is preserved for backward
    compatibility. When ``backend`` is set it wins over ``use_com``.
    """

    def test_connect_access_backend_odbc_routes_to_pool(self):
        """``backend='odbc'`` is forwarded to pool.connect(..., adapter_type='odbc')."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = MagicMock()
        with (
            patch.object(conn_module, "_pool", return_value=mock_conn),
            patch.object(conn_module, "_get_path_guard", return_value=None),
        ):
            result = conn_module.connect_access("test.accdb", backend="odbc")
            assert result["success"] is True
            call_args = mock_conn.connect.call_args
            assert call_args is not None
            # 3rd positional arg or `adapter` kwarg is the adapter_type string
            adapter_arg = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("adapter")
            assert adapter_arg == "odbc"

    def test_connect_access_backend_dao_routes_to_pool(self):
        """``backend='dao'`` is forwarded to pool.connect(..., adapter_type='dao')."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = MagicMock()
        with (
            patch.object(conn_module, "_pool", return_value=mock_conn),
            patch.object(conn_module, "_get_path_guard", return_value=None),
        ):
            result = conn_module.connect_access("test.accdb", backend="dao")
            assert result["success"] is True
            call_args = mock_conn.connect.call_args
            assert call_args is not None
            adapter_arg = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("adapter")
            assert adapter_arg == "dao"

    def test_connect_access_backend_wins_over_use_com(self):
        """``backend='odbc'`` overrides ``use_com=True`` (the new param takes precedence)."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.connect.return_value = MagicMock()
        with (
            patch.object(conn_module, "_pool", return_value=mock_conn),
            patch.object(conn_module, "_get_path_guard", return_value=None),
        ):
            result = conn_module.connect_access(
                "test.accdb", use_com=True, backend="odbc"
            )
            assert result["success"] is True
            call_args = mock_conn.connect.call_args
            adapter_arg = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("adapter")
            assert adapter_arg == "odbc"


class TestDisconnectAccessWithName:
    """Tests for disconnect_access tool with name parameter."""

    def test_disconnect_access_with_name_param(self):
        """disconnect_access should call disconnect with the given name."""
        mock_conn = MagicMock()
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.disconnect_access("prod")
            mock_conn.disconnect.assert_called_once_with("prod")
            assert result["success"] is True

    def test_disconnect_access_unknown_name_returns_error(self):
        """disconnect_access with unknown name should return error."""
        mock_conn = MagicMock()
        mock_conn.disconnect.side_effect = KeyError("not found")
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.disconnect_access("unknown")
            assert result["success"] is False


class TestNewConnectionTools:
    """Tests for new connection management tools."""

    def test_list_connections_returns_structure(self):
        """list_connections should return dict with connections key."""
        mock_conn = MagicMock()
        mock_state = MagicMock()
        mock_state.db_path = "/path/to/db.accdb"
        mock_state.adapter_type = "odbc"
        mock_state.adapter.is_connected.return_value = True
        mock_conn.list.return_value = {"default": mock_state}
        mock_conn.get_active.return_value = "default"
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.list_connections()
            assert "connections" in result
            assert "success" in result

    def test_set_active_connection_calls_service(self):
        """set_active_connection should call connection_service.set_active."""
        mock_conn = MagicMock()
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.set_active_connection("prod")
            mock_conn.set_active.assert_called_once_with("prod")
            assert result["success"] is True

    def test_set_active_connection_unknown_returns_error(self):
        """set_active_connection with unknown name should return error."""
        mock_conn = MagicMock()
        mock_conn.set_active.side_effect = KeyError("not found")
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.set_active_connection("unknown")
            assert result["success"] is False

    def test_get_active_connection_returns_name(self):
        """get_active_connection should return the active connection name."""
        mock_conn = MagicMock()
        mock_conn.get_active.return_value = "default"
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.get_active_connection()
            assert result["active"] == "default"

    def test_is_connected_with_connection_name(self):
        """is_connected should pass connection_name to connection_service."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.current_database = "/path/to/db.accdb"
        with patch.object(conn_module, '_pool', return_value=mock_conn):
            result = conn_module.is_connected(connection_name="prod")
            mock_conn.is_connected.assert_called_once_with("prod")
            assert result["connected"] is True


# =============================================================================
# _format_connect_response — shared response helper (PR 2 refactor)
# =============================================================================


class TestFormatConnectResponseHelper:
    """``_format_connect_response`` is the shared response builder used by
    both ``connect_access`` and ``create_access_database``. Both success
    and failure paths must be pinned to one shape.
    """

    def test_helper_success_returns_connected_true(self):
        """Truthy state yields success=True, connected=True, with path/name."""
        result = conn_module._format_connect_response(
            state=MagicMock(), database_path="C:/x.accdb", name="prod"
        )
        assert result == {
            "success": True,
            "connected": True,
            "database": "C:/x.accdb",
            "name": "prod",
        }

    def test_helper_failure_returns_connected_false(self):
        """Falsy state yields success=False, connected=False, plus an error."""
        result = conn_module._format_connect_response(
            state=None, database_path="C:/x.accdb", name="prod"
        )
        assert result["success"] is False
        assert result["connected"] is False
        assert result["database"] == "C:/x.accdb"
        assert result["name"] == "prod"
        assert "error" in result
        assert "prod" in result["error"]


# =============================================================================
# create_access_database — PR 2 (tool wiring + safety)
# =============================================================================


class TestCreateAccessDatabaseHappyPath:
    """``create_access_database`` happy path: file is bootstrapped and
    (by default) connected via the COM adapter. The response is the
    shared connect shape with ``connected=True``.
    """

    def test_create_access_database_returns_success_when_bootstrap_succeeds(self, monkeypatch):
        """Happy path: bootstrap OK + connect OK → success=True, connected=True."""
        monkeypatch.setattr(sys, "platform", "win32")
        mock_conn = MagicMock()
        mock_conn.list.return_value = {}  # No name collisions
        mock_conn.connect.return_value = MagicMock()  # Truthy state

        mock_bootstrap = MagicMock()
        mock_bootstrap.success = True
        mock_bootstrap.path = r"C:\fake\new.accdb"
        mock_bootstrap.error = None

        with (
            patch.object(conn_module, "_pool", return_value=mock_conn),
            patch.object(conn_module, "_get_path_guard", return_value=None),
            patch("os.path.exists", return_value=False),
            patch.object(conn_module, "create_blank_database", return_value=mock_bootstrap),
        ):
            result = conn_module.create_access_database(r"C:\fake\new.accdb")

        assert result["success"] is True
        assert result["connected"] is True
        assert result["database"] == r"C:\fake\new.accdb"
        assert result["name"] == "default"
        mock_conn.connect.assert_called_once_with(
            "default", r"C:\fake\new.accdb", "com", password=""
        )

    def test_create_access_database_uses_custom_name(self, monkeypatch):
        """Custom ``name`` flows through to the pool connect call."""
        monkeypatch.setattr(sys, "platform", "win32")
        mock_conn = MagicMock()
        mock_conn.list.return_value = {}
        mock_conn.connect.return_value = MagicMock()
        mock_bootstrap = MagicMock(success=True, path=r"C:\fake\new.accdb", error=None)

        with (
            patch.object(conn_module, "_pool", return_value=mock_conn),
            patch.object(conn_module, "_get_path_guard", return_value=None),
            patch("os.path.exists", return_value=False),
            patch.object(conn_module, "create_blank_database", return_value=mock_bootstrap),
        ):
            result = conn_module.create_access_database(r"C:\fake\new.accdb", name="myapp")

        assert result["name"] == "myapp"
        mock_conn.connect.assert_called_once_with(
            "myapp", r"C:\fake\new.accdb", "com", password=""
        )


class TestCreateAccessDatabaseConnectFalse:
    """``create_access_database(connect=False)`` creates the file only
    and does NOT register a connection. The response has
    ``connected=False``.
    """

    def test_connect_false_does_not_call_pool_connect(self, monkeypatch):
        """connect=False must skip the pool.connect() call entirely."""
        monkeypatch.setattr(sys, "platform", "win32")
        mock_conn = MagicMock()
        mock_bootstrap = MagicMock(success=True, path=r"C:\fake\new.accdb", error=None)

        with (
            patch.object(conn_module, "_pool", return_value=mock_conn),
            patch.object(conn_module, "_get_path_guard", return_value=None),
            patch("os.path.exists", return_value=False),
            patch.object(conn_module, "create_blank_database", return_value=mock_bootstrap),
        ):
            result = conn_module.create_access_database(
                r"C:\fake\new.accdb", connect=False
            )

        assert result["success"] is True
        assert result["connected"] is False
        assert result["database"] == r"C:\fake\new.accdb"
        assert result["name"] == "default"
        mock_conn.connect.assert_not_called()


class TestCreateAccessDatabasePathGuard:
    """PathGuard rejection short-circuits the tool before any work
    happens. Mirrors ``connect_access``'s path validation.
    """

    def test_path_guard_rejection_returns_error(self):
        """PathGuard ValueError → success=False, error contains the message."""
        mock_guard = MagicMock()
        mock_guard.validate.side_effect = ValueError("path not allowed")

        with patch.object(conn_module, "_get_path_guard", return_value=mock_guard):
            result = conn_module.create_access_database(r"C:\outside\new.accdb")

        assert result["success"] is False
        assert "not allowed" in result["error"]


class TestCreateAccessDatabaseFileExists:
    """REQ-3: refuse to overwrite an existing file.
    Short-circuits BEFORE the bootstrap runs.
    """

    def test_file_exists_returns_error_without_bootstrap(self, monkeypatch):
        """If the file exists on disk, return error and do not call bootstrap."""
        monkeypatch.setattr(sys, "platform", "win32")

        with (
            patch.object(conn_module, "_get_path_guard", return_value=None),
            patch("os.path.exists", return_value=True),
            patch.object(conn_module, "create_blank_database") as mock_bootstrap,
        ):
            result = conn_module.create_access_database(r"C:\fake\exists.accdb")

        assert result["success"] is False
        assert "already exists" in result["error"]
        assert result["database"] == r"C:\fake\exists.accdb"
        mock_bootstrap.assert_not_called()


class TestCreateAccessDatabaseNameCollision:
    """Name-collision short-circuit: if a connection with the same
    name is already in the pool, refuse and return a clean error
    (avoids the bootstrap round-trip on a doomed call).
    """

    def test_existing_connection_name_returns_error(self, monkeypatch):
        """Pre-existing name in pool → success=False, error mentions name."""
        monkeypatch.setattr(sys, "platform", "win32")
        mock_conn = MagicMock()
        # Pool already has a connection named "default"
        mock_conn.list.return_value = {"default": MagicMock()}

        with (
            patch.object(conn_module, "_pool", return_value=mock_conn),
            patch.object(conn_module, "_get_path_guard", return_value=None),
            patch("os.path.exists", return_value=False),
            patch.object(conn_module, "create_blank_database") as mock_bootstrap,
        ):
            result = conn_module.create_access_database(r"C:\fake\new.accdb", name="default")

        assert result["success"] is False
        assert "default" in result["error"]
        assert "already exists" in result["error"]
        mock_bootstrap.assert_not_called()
        mock_conn.connect.assert_not_called()


class TestCreateAccessDatabaseBootstrapFailure:
    """When the bootstrap service returns a failure, the tool propagates it."""

    def test_bootstrap_failure_returns_error(self, monkeypatch):
        """Bootstrap success=False → tool returns success=False with the error."""
        monkeypatch.setattr(sys, "platform", "win32")
        mock_conn = MagicMock()
        mock_conn.list.return_value = {}
        mock_bootstrap = MagicMock(
            success=False, path=r"C:\fake\new.accdb", error="DAO boom"
        )

        with (
            patch.object(conn_module, "_pool", return_value=mock_conn),
            patch.object(conn_module, "_get_path_guard", return_value=None),
            patch("os.path.exists", return_value=False),
            patch.object(conn_module, "create_blank_database", return_value=mock_bootstrap),
        ):
            result = conn_module.create_access_database(r"C:\fake\new.accdb")

        assert result["success"] is False
        assert result["error"] == "DAO boom"
        assert result["database"] == r"C:\fake\new.accdb"
        mock_conn.connect.assert_not_called()


class TestCreateAccessDatabaseNonWindows:
    """REQ-8: non-Windows hosts are refused BEFORE the bootstrap runs
    (so we never touch pywin32 even through the service's guard).
    """

    @pytest.mark.parametrize("platform_name", ["linux", "darwin"])
    def test_non_windows_returns_requires_windows_error(
        self, monkeypatch, platform_name
    ):
        """Non-Windows host → success=False, error mentions Windows requirement."""
        monkeypatch.setattr(sys, "platform", platform_name)

        with (
            patch.object(conn_module, "_get_path_guard", return_value=None),
            patch.object(conn_module, "create_blank_database") as mock_bootstrap,
        ):
            result = conn_module.create_access_database("/tmp/x.accdb")

        assert result["success"] is False
        assert "Windows" in result["error"]
        mock_bootstrap.assert_not_called()
