"""Comprehensive unit tests for ConnectionPool — Phase 1 SDD."""

import pytest
from unittest.mock import MagicMock, patch, call
from ms_access_mcp.services.connection import ConnectionPool, ConnectionState


def make_mock_adapter(name="mock"):
    """Create a mock adapter with configurable behavior."""
    a = MagicMock()
    a.connect.return_value = True
    a.disconnect.return_value = None
    a.is_connected.return_value = True
    a._name = name
    return a


# =============================================================================
# ConnectionState dataclass
# =============================================================================

class TestConnectionState:
    """Tests for ConnectionState structure."""

    def test_connection_state_holds_adapter(self):
        adapter = make_mock_adapter()
        state = ConnectionState(adapter=adapter, db_path="/tmp/db.accdb", adapter_type="odbc")
        assert state.adapter is adapter

    def test_connection_state_holds_db_path(self):
        adapter = make_mock_adapter()
        state = ConnectionState(adapter=adapter, db_path="/tmp/db.accdb", adapter_type="odbc")
        assert state.db_path == "/tmp/db.accdb"

    def test_connection_state_holds_adapter_type(self):
        adapter = make_mock_adapter()
        state = ConnectionState(adapter=adapter, db_path="/tmp/db.accdb", adapter_type="com")
        assert state.adapter_type == "com"


# =============================================================================
# ConnectionPool.initial_state — pool empty, default active context
# =============================================================================

class TestConnectionPoolInitialState:
    """Test initial state of ConnectionPool."""

    def test_pool_empty_by_default(self):
        pool = ConnectionPool()
        assert pool.list() == {}

    def test_active_is_default_by_default(self):
        pool = ConnectionPool()
        assert pool.get_active() == "default"

    def test_get_without_name_returns_default_connection(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["default"] = ConnectionState(adapter=adapter, db_path="/tmp/db.accdb", adapter_type="odbc")
        state = pool.get()
        assert state.db_path == "/tmp/db.accdb"

    def test_get_with_explicit_none_uses_active(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["default"] = ConnectionState(adapter=adapter, db_path="/tmp/db.accdb", adapter_type="odbc")
        pool._active = "default"
        state = pool.get(None)
        assert state.db_path == "/tmp/db.accdb"

    def test_get_without_name_raises_when_default_not_connected(self):
        pool = ConnectionPool()
        with pytest.raises(KeyError, match="'default'"):
            pool.get()


class TestPoolBackendSelectorInjection:
    """Test that ConnectionPool accepts and stores a backend_selector."""

    def test_init_accepts_backend_selector_kwarg(self):
        """ConnectionPool(backend_selector=some_selector) should not raise."""
        mock_selector = MagicMock()
        pool = ConnectionPool(backend_selector=mock_selector)  # type: ignore[arg-type]
        assert pool._backend_selector is mock_selector

    def test_init_creates_default_backend_selector_when_none_provided(self):
        """ConnectionPool() should create a BackendSelector instance by default."""
        pool = ConnectionPool()
        from ms_access_mcp.services.backend_selector import BackendSelector
        assert isinstance(pool._backend_selector, BackendSelector)

    def test_init_does_not_store_pooled_adapter_when_using_backend_selector(self):
        """Passing backend_selector without adapter should leave pool empty."""
        mock_selector = MagicMock()
        pool = ConnectionPool(backend_selector=mock_selector)  # type: ignore[arg-type]
        assert pool.list() == {}


# =============================================================================
# connect() — named connection creation (mocked adapter)
# =============================================================================

class TestPoolConnect:
    """Test ConnectionPool.connect() with named connections."""

    def test_connect_creates_named_connection(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter):
            state = pool.connect("prod", "/tmp/prod.accdb", "odbc")
            assert state is not None
            assert state.db_path == "/tmp/prod.accdb"
            assert state.adapter_type == "odbc"

    def test_connect_stores_adapter_in_pool(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter):
            pool.connect("prod", "/tmp/prod.accdb", "odbc")
            assert "prod" in pool.list()

    def test_connect_calls_adapter_connect(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter):
            pool.connect("prod", "/tmp/prod.accdb", "odbc")
            adapter.connect.assert_called_once_with("/tmp/prod.accdb")

    def test_connect_with_com_adapter_type(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.wincom.WinComAdapter", return_value=adapter):
            state = pool.connect("prod", "/tmp/prod.accdb", "com")
            assert state.adapter_type == "com"

    def test_connect_multiple_different_names(self):
        pool = ConnectionPool()
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter") as mock_odbc:
            mock_odbc.side_effect = [adapter1, adapter2]
            pool.connect("prod", "/tmp/prod.accdb", "odbc")
            pool.connect("dev", "/tmp/dev.accdb", "odbc")
        assert "prod" in pool.list()
        assert "dev" in pool.list()

    def test_connect_same_name_raises_keyerror(self):
        pool = ConnectionPool()
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter") as mock_odbc:
            mock_odbc.side_effect = [adapter1, adapter2]
            pool.connect("prod", "/tmp/prod.accdb", "odbc")
            with pytest.raises(KeyError, match="already exists"):
                pool.connect("prod", "/tmp/other.accdb", "odbc")

    def test_connect_when_adapter_fails_raises_runtimeerror(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        adapter.connect.return_value = False
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter):
            with pytest.raises(RuntimeError, match="Failed to connect"):
                pool.connect("prod", "/tmp/prod.accdb", "odbc")

    def test_connect_auto_mode_calls_backend_selector_get_adapter(self):
        """connect(name, db_path, 'auto') should delegate to BackendSelector."""
        pool = ConnectionPool()
        mock_selector = MagicMock()
        mock_adapter = make_mock_adapter()
        mock_selector.get_adapter.return_value = mock_adapter
        pool._backend_selector = mock_selector  # inject test selector

        with patch.object(mock_adapter, 'connect', return_value=True):
            state = pool.connect("prod", "/tmp/prod.accdb", "auto")

        mock_selector.get_adapter.assert_called_once_with(
            "/tmp/prod.accdb",
            backend="auto",
            capabilities=None,
        )
        assert state is not None

    def test_connect_auto_mode_infers_adapter_type_via_isinstance(self):
        """Auto mode should use isinstance to set adapter_type to 'com' or 'odbc'."""
        pool = ConnectionPool()
        mock_selector = MagicMock()

        # Return a real OdbcAdapter instance so isinstance works
        from ms_access_mcp.adapters.odbc import OdbcAdapter
        real_odbc = OdbcAdapter(db_path="/tmp/prod.accdb")
        mock_selector.get_adapter.return_value = real_odbc
        pool._backend_selector = mock_selector

        with patch.object(real_odbc, 'connect', return_value=True):
            state = pool.connect("prod", "/tmp/prod.accdb", "auto")

        assert state.adapter_type == "odbc"

    def test_connect_explicit_com_does_not_use_backend_selector(self):
        """connect(name, db_path, 'com') should NOT call BackendSelector — direct instantiation."""
        pool = ConnectionPool()
        mock_selector = MagicMock()
        mock_com_adapter = make_mock_adapter()
        pool._backend_selector = mock_selector

        with patch("ms_access_mcp.adapters.wincom.WinComAdapter", return_value=mock_com_adapter):
            state = pool.connect("prod", "/tmp/prod.accdb", "com")

        mock_selector.get_adapter.assert_not_called()
        assert state.adapter_type == "com"

    def test_connect_explicit_odbc_does_not_use_backend_selector(self):
        """connect(name, db_path, 'odbc') should NOT call BackendSelector — direct instantiation."""
        pool = ConnectionPool()
        mock_selector = MagicMock()
        mock_odbc_adapter = make_mock_adapter()
        pool._backend_selector = mock_selector

        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=mock_odbc_adapter):
            state = pool.connect("prod", "/tmp/prod.accdb", "odbc")

        mock_selector.get_adapter.assert_not_called()
        assert state.adapter_type == "odbc"


# =============================================================================
# disconnect() — remove named connection
# =============================================================================

class TestPoolDisconnect:
    """Test ConnectionPool.disconnect() by name."""

    def test_disconnect_removes_from_pool(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool.disconnect("prod")
        assert "prod" not in pool.list()

    def test_disconnect_calls_adapter_disconnect(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool.disconnect("prod")
        adapter.disconnect.assert_called_once()

    def test_disconnect_nonexistent_raises_keyerror(self):
        pool = ConnectionPool()
        with pytest.raises(KeyError, match="not found"):
            pool.disconnect("nonexistent")

    def test_disconnect_one_keeps_other(self):
        pool = ConnectionPool()
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        pool._pool["prod"] = ConnectionState(adapter=adapter1, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool._pool["dev"] = ConnectionState(adapter=adapter2, db_path="/tmp/dev.accdb", adapter_type="odbc")
        pool.disconnect("prod")
        assert "prod" not in pool.list()
        assert "dev" in pool.list()


# =============================================================================
# get() — retrieve connection state
# =============================================================================

class TestPoolGet:
    """Test ConnectionPool.get() by name."""

    def test_get_returns_connection_state(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        state = pool.get("prod")
        assert state.db_path == "/tmp/prod.accdb"

    def test_get_default_returns_default_connection(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["default"] = ConnectionState(adapter=adapter, db_path="/tmp/default.accdb", adapter_type="odbc")
        state = pool.get("default")
        assert state.db_path == "/tmp/default.accdb"

    def test_get_with_none_returns_active(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool._active = "prod"
        state = pool.get(None)
        assert state.db_path == "/tmp/prod.accdb"

    def test_get_nonexistent_raises_keyerror(self):
        pool = ConnectionPool()
        with pytest.raises(KeyError, match="not found"):
            pool.get("nonexistent")


# =============================================================================
# list() — all connections
# =============================================================================

class TestPoolList:
    """Test ConnectionPool.list() returns all connections."""

    def test_list_empty_pool_returns_empty_dict(self):
        pool = ConnectionPool()
        assert pool.list() == {}

    def test_list_returns_all_connections(self):
        pool = ConnectionPool()
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        pool._pool["prod"] = ConnectionState(adapter=adapter1, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool._pool["dev"] = ConnectionState(adapter=adapter2, db_path="/tmp/dev.accdb", adapter_type="odbc")
        connections = pool.list()
        assert "prod" in connections
        assert "dev" in connections


# =============================================================================
# set_active() / get_active() — active context management
# =============================================================================

class TestPoolActiveContext:
    """Test active connection context management."""

    def test_set_active_changes_active_pointer(self):
        pool = ConnectionPool()
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        pool._pool["prod"] = ConnectionState(adapter=adapter1, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool._pool["dev"] = ConnectionState(adapter=adapter2, db_path="/tmp/dev.accdb", adapter_type="odbc")
        pool.set_active("dev")
        assert pool.get_active() == "dev"

    def test_get_active_returns_current_active_name(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool.set_active("prod")
        assert pool.get_active() == "prod"

    def test_set_active_nonexistent_raises_keyerror(self):
        pool = ConnectionPool()
        with pytest.raises(KeyError, match="not found"):
            pool.set_active("nonexistent")

    def test_active_context_affects_get_without_name(self):
        pool = ConnectionPool()
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        pool._pool["prod"] = ConnectionState(adapter=adapter1, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool._pool["dev"] = ConnectionState(adapter=adapter2, db_path="/tmp/dev.accdb", adapter_type="odbc")
        pool.set_active("dev")
        state = pool.get(None)
        assert state.db_path == "/tmp/dev.accdb"


# =============================================================================
# backward compatibility — "default" name preserves old singleton behavior
# =============================================================================

class TestPoolBackwardCompatibility:
    """Ensure 'default' name works as backward-compatible singleton."""

    def test_default_name_works_as_singleton(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter):
            state = pool.connect("default", "/tmp/db.accdb", "odbc")
            assert state.db_path == "/tmp/db.accdb"
            assert pool.get_active() == "default"

    def test_get_without_args_uses_default_when_active_is_default(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter):
            pool.connect("default", "/tmp/db.accdb", "odbc")
            state = pool.get()
            assert state.db_path == "/tmp/db.accdb"


# =============================================================================
# recover_access() — taskkill + reconnect (platform-specific)
# =============================================================================

class TestPoolRecoverAccess:
    """Test recover_access kills MSACCESS.EXE and reconnects all."""

    def test_recover_access_requires_windows(self):
        pool = ConnectionPool()
        with patch("sys.platform", "linux"):
            result = pool.recover_access()
            assert result["success"] is False
            assert "Not supported" in result["error"]

    @patch("sys.platform", "win32")
    @patch("subprocess.run")
    def test_recover_access_kills_msaccess_on_windows(self, mock_run):
        pool = ConnectionPool()
        mock_run.return_value = MagicMock(returncode=0)
        result = pool.recover_access()
        mock_run.assert_called()
        call_args = str(mock_run.call_args)
        assert "taskkill" in call_args.lower() or "msaccess" in call_args.lower()

    @patch("sys.platform", "win32")
    @patch("subprocess.run")
    def test_recover_access_reconnects_all_managed(self, mock_run):
        pool = ConnectionPool()
        mock_run.return_value = MagicMock(returncode=0)
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        pool._pool["prod"] = ConnectionState(adapter=adapter1, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool._pool["dev"] = ConnectionState(adapter=adapter2, db_path="/tmp/dev.accdb", adapter_type="odbc")

        result = pool.recover_access()
        assert adapter1.connect.call_count >= 1
        assert adapter2.connect.call_count >= 1

    @patch("sys.platform", "win32")
    @patch("subprocess.run")
    def test_recover_access_returns_reconnected_names(self, mock_run):
        pool = ConnectionPool()
        mock_run.return_value = MagicMock(returncode=0)
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        pool._pool["prod"] = ConnectionState(adapter=adapter1, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool._pool["dev"] = ConnectionState(adapter=adapter2, db_path="/tmp/dev.accdb", adapter_type="odbc")

        result = pool.recover_access()
        assert "prod" in result.get("reconnected", [])
        assert "dev" in result.get("reconnected", [])


# =============================================================================
# ConnectionPool.get_adapter() — convenience accessor
# =============================================================================

class TestPoolGetAdapter:
    """Test ConnectionPool.get_adapter() convenience method."""

    def test_get_adapter_returns_adapter_from_state(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        retrieved_adapter = pool.get_adapter("prod")
        assert retrieved_adapter is adapter

    def test_get_adapter_none_returns_active(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["default"] = ConnectionState(adapter=adapter, db_path="/tmp/db.accdb", adapter_type="odbc")
        pool.set_active("default")
        retrieved_adapter = pool.get_adapter()
        assert retrieved_adapter is adapter


# =============================================================================
# is_connected() — check connection status
# =============================================================================

class TestPoolIsConnected:
    """Test ConnectionPool.is_connected() method."""

    def test_is_connected_returns_true_when_connected(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        adapter.is_connected.return_value = True
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        assert pool.is_connected("prod") is True

    def test_is_connected_returns_false_when_disconnected(self):
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        adapter.is_connected.return_value = False
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        assert pool.is_connected("prod") is False

    def test_is_connected_returns_false_when_not_in_pool(self):
        pool = ConnectionPool()
        assert pool.is_connected("nonexistent") is False
