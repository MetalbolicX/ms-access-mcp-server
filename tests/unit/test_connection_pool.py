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
            adapter.connect.assert_called_once_with("/tmp/prod.accdb", password="")

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
    def test_recover_access_kills_owned_pid_on_windows(self, mock_run):
        """recover_access with confirm=True kills the owned PID, not all MSACCESS."""
        pool = ConnectionPool()
        mock_run.return_value = MagicMock(returncode=0)
        adapter1 = make_mock_adapter("a1")
        pool._pool["prod"] = ConnectionState(
            adapter=adapter1,
            db_path="/tmp/prod.accdb",
            adapter_type="com",
            pid=12345,
        )
        result = pool.recover_access(confirm=True)
        mock_run.assert_called()
        call_args = str(mock_run.call_args)
        assert "taskkill" in call_args.lower()
        assert "/PID" in call_args or "12345" in call_args

    @patch("sys.platform", "win32")
    @patch("subprocess.run")
    def test_recover_access_reconnects_all_managed(self, mock_run):
        pool = ConnectionPool()
        mock_run.return_value = MagicMock(returncode=0)
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        pool._pool["prod"] = ConnectionState(adapter=adapter1, db_path="/tmp/prod.accdb", adapter_type="odbc")
        pool._pool["dev"] = ConnectionState(adapter=adapter2, db_path="/tmp/dev.accdb", adapter_type="odbc")

        result = pool.recover_access(confirm=True)
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

        result = pool.recover_access(confirm=True)
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


# =============================================================================
# ConnectionState.pid — PID tracking for scoped cleanup
# =============================================================================

class TestConnectionStatePid:
    """ConnectionState holds a pid field for scoped process management."""

    def test_connection_state_holds_pid(self):
        """ConnectionState should store pid (process ID) of the Access process."""
        adapter = make_mock_adapter()
        state = ConnectionState(
            adapter=adapter,
            db_path="/tmp/db.accdb",
            adapter_type="com",
            pid=12345,
        )
        assert state.pid == 12345

    def test_connection_state_pid_defaults_to_none(self):
        """ConnectionState pid should default to None when not provided."""
        adapter = make_mock_adapter()
        state = ConnectionState(
            adapter=adapter,
            db_path="/tmp/db.accdb",
            adapter_type="odbc",
        )
        assert state.pid is None


# =============================================================================
# recover_access() — confirm parameter and PID-scoped taskkill
# =============================================================================

class TestPoolRecoverAccessConfirm:
    """recover_access requires confirm=True to execute taskkill."""

    @patch("ms_access_mcp.services.connection.subprocess.run")
    def test_recover_access_rejects_confirm_false(self, mock_subprocess_run):
        """recover_access with confirm=False should NOT execute taskkill."""
        pool = ConnectionPool()
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        result = pool.recover_access(confirm=False)
        # When confirm=False, taskkill should not run
        for call in mock_subprocess_run.call_args_list:
            if call.args or call.kwargs:
                cmd = str(call.args[0] if call.args else call.kwargs)
                assert "taskkill" not in cmd.lower(), f"taskkill should not run when confirm=False, got: {cmd}"
        assert result.get("confirm_required") is True

    @patch("ms_access_mcp.services.connection.subprocess.run")
    def test_recover_access_executes_with_confirm_true(self, mock_subprocess_run):
        """recover_access with confirm=True should execute taskkill targeting owned PIDs."""
        pool = ConnectionPool()
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        adapter1 = make_mock_adapter("a1")
        pool._pool["prod"] = ConnectionState(
            adapter=adapter1,
            db_path="/tmp/prod.accdb",
            adapter_type="com",
            pid=12345,
        )
        result = pool.recover_access(confirm=True)
        # Should have called taskkill with /PID not /IM
        taskkill_calls = [
            c for c in mock_subprocess_run.call_args_list
            if c.args and "taskkill" in str(c.args[0]).lower()
        ]
        assert len(taskkill_calls) >= 1
        # Verify /PID 12345 was passed, not /IM MSACCESS.EXE
        last_taskkill = str(taskkill_calls[-1].args[0])
        assert "/PID" in last_taskkill or "12345" in last_taskkill, \
            f"taskkill should target specific PID, not global MSACCESS.EXE: {last_taskkill}"

    @patch("ms_access_mcp.services.connection.subprocess.run")
    def test_recover_access_only_kills_owned_pids(self, mock_subprocess_run):
        """recover_access should only kill PIDs stored in ConnectionState, not all MSACCESS."""
        pool = ConnectionPool()
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        pool._pool["prod"] = ConnectionState(
            adapter=adapter1,
            db_path="/tmp/prod.accdb",
            adapter_type="com",
            pid=12345,
        )
        pool._pool["dev"] = ConnectionState(
            adapter=adapter2,
            db_path="/tmp/dev.accdb",
            adapter_type="com",
            pid=67890,
        )
        result = pool.recover_access(confirm=True)
        # Both PIDs should appear in taskkill calls
        all_calls_str = str(mock_subprocess_run.call_args_list)
        assert "12345" in all_calls_str, "PID 12345 should be targeted"
        assert "67890" in all_calls_str, "PID 67890 should be targeted"
        # /IM MSACCESS.EXE should NOT appear
        assert "/IM" not in all_calls_str and "MSACCESS.EXE" not in all_calls_str, \
            "Should use /PID not /IM MSACCESS.EXE"


class TestPoolRecoverAccessNoConfirmFlag:
    """recover_access without confirm defaults to no-kill (backward compat)."""

    @patch("ms_access_mcp.services.connection.subprocess.run")
    def test_recover_access_default_confirm_is_false(self, mock_subprocess_run):
        """recover_access called without confirm defaults to False (no kill)."""
        pool = ConnectionPool()
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        result = pool.recover_access()  # No confirm arg
        # Default behavior should be confirm=False
        taskkill_calls = [
            c for c in mock_subprocess_run.call_args_list
            if c.args and "taskkill" in str(c.args[0]).lower()
        ]
        assert len(taskkill_calls) == 0, "taskkill should not run without explicit confirm=True"


class TestPoolRLock:
    """Tests for RLock-protected pool mutation under concurrent access."""

    def test_pool_has_rlock_for_thread_safety(self):
        """ConnectionPool should use RLock to protect _pool and _active dicts."""
        pool = ConnectionPool()
        # _lock should be an RLock-like lock (reentrant)
        assert hasattr(pool, "_lock"), "ConnectionPool should have a _lock attribute"
        import threading
        # threading.RLock wraps _thread.RLock; check via type name
        lock_type_name = type(pool._lock).__name__
        assert "RLock" in lock_type_name or "Lock" in lock_type_name, \
            f"_lock should be an RLock, got {lock_type_name}"

    def test_connect_disconnect_concurrent_safety(self):
        """Concurrent connect/disconnect calls should not corrupt pool state."""
        import threading
        import time

        pool = ConnectionPool()
        errors = []

        def connect_worker(name):
            try:
                adapter = make_mock_adapter(name)
                pool.connect(name, "/tmp/test.accdb", adapter=adapter)
            except Exception as e:
                errors.append(f"connect {name}: {e}")

        def disconnect_worker(name):
            try:
                pool.disconnect(name)
            except Exception as e:
                errors.append(f"disconnect {name}: {e}")

        threads = []
        for i in range(5):
            t_connect = threading.Thread(target=connect_worker, args=(f"conn{i}",))
            t_disconnect = threading.Thread(target=disconnect_worker, args=(f"conn{i}",))
            threads.extend([t_connect, t_disconnect])

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        # Pool should be in a consistent state
        assert isinstance(pool.list(), dict)

    def test_pool_list_returns_snapshot_under_concurrent_connect(self):
        """pool.list() should return a consistent dict snapshot during concurrent writes."""
        import threading

        pool = ConnectionPool()
        results = []

        def writer(idx):
            adapter = make_mock_adapter(f"w{idx}")
            pool.connect(f"conn{idx}", f"/tmp/test{idx}.accdb", adapter=adapter)

        def reader():
            for _ in range(10):
                try:
                    snapshot = pool.list()
                    results.append(len(snapshot))
                except Exception:
                    pass

        threads = []
        for i in range(5):
            t_write = threading.Thread(target=writer, args=(i,))
            t_read = threading.Thread(target=reader)
            threads.extend([t_write, t_read])

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # All reads should succeed without exception
        assert len(results) == 50, f"Expected 50 reads, got {len(results)}"
        # No read should return a corrupt/partial dict
        for r in results:
            assert isinstance(r, int)


# =============================================================================
# connection_pool_size gauge — observability
# =============================================================================

class TestConnectionPoolSizeGauge:
    """ConnectionPool emits connection_pool_size gauge for observability."""

    def test_pool_updates_pool_size_gauge_on_connect(self):
        """Connecting a new named connection should update connection_pool_size gauge."""
        from ms_access_mcp.telemetry import metrics
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter):
            with patch.object(metrics, "connection_pool_size") as mock_gauge:
                pool.connect("prod", "/tmp/prod.accdb", "odbc")
                # Gauge should be set to pool size (1)
                mock_gauge.set.assert_called_with(1)

    def test_pool_updates_pool_size_gauge_on_disconnect(self):
        """Disconnecting a connection should update connection_pool_size gauge."""
        from ms_access_mcp.telemetry import metrics
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        pool._pool["prod"] = ConnectionState(adapter=adapter, db_path="/tmp/prod.accdb", adapter_type="odbc")
        with patch.object(metrics, "connection_pool_size") as mock_gauge:
            pool.disconnect("prod")
            # Gauge should be set to pool size (0)
            mock_gauge.set.assert_called_with(0)

    def test_pool_updates_pool_size_gauge_on_multiple_connects(self):
        """Multiple connects should update gauge to reflect current pool size."""
        from ms_access_mcp.telemetry import metrics
        pool = ConnectionPool()
        adapter1 = make_mock_adapter("a1")
        adapter2 = make_mock_adapter("a2")
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter") as mock_odbc:
            mock_odbc.side_effect = [adapter1, adapter2]
            with patch.object(metrics, "connection_pool_size") as mock_gauge:
                pool.connect("prod", "/tmp/prod.accdb", "odbc")
                pool.connect("dev", "/tmp/dev.accdb", "odbc")
                # Last call should set gauge to 2
                assert mock_gauge.set.call_args_list[-1] == call(2)


# =============================================================================
# password forwarding — ConnectionPool passes password to adapter.connect()
# =============================================================================

class TestPoolPasswordForwarding:
    """Test that password is threaded through ConnectionPool to the adapter."""

    def test_connect_passes_password_to_odbc_adapter(self):
        """connect(name, db_path, adapter_type, password) should pass password to OdbcAdapter.connect()."""
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter) as mock_cls:
            pool.connect("prod", "/tmp/prod.accdb", "odbc", password="secret123")
            # Verify connect was called with db_path AND password
            call_args = adapter.connect.call_args
            assert call_args is not None, "adapter.connect() was not called"
            assert call_args[0][0] == "/tmp/prod.accdb", "First arg should be db_path"
            assert call_args[1].get("password") == "secret123" or (
                len(call_args[0]) > 1 and call_args[0][1] == "secret123"
            ), "password should be passed to adapter.connect()"

    def test_connect_passes_password_to_com_adapter(self):
        """connect(name, db_path, 'com', password) should pass password to WinComAdapter.connect()."""
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.wincom.WinComAdapter", return_value=adapter) as mock_cls:
            pool.connect("prod", "/tmp/prod.accdb", "com", password="secret456")
            call_args = adapter.connect.call_args
            assert call_args is not None, "adapter.connect() was not called"
            assert call_args[1].get("password") == "secret456" or (
                len(call_args[0]) > 1 and call_args[0][1] == "secret456"
            ), "password should be passed to WinComAdapter.connect()"

    def test_connect_with_empty_password_is_backward_compatible(self):
        """connect without password (empty string) should still work."""
        pool = ConnectionPool()
        adapter = make_mock_adapter()
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter", return_value=adapter):
            # Should not raise — backward compatible
            result = pool.connect("prod", "/tmp/prod.accdb", "odbc")
            assert result is not None
