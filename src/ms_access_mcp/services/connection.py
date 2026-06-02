"""Connection pool management for MS Access databases — Phase 1 SDD.

Implements ConnectionPool with:
- dict[str, ConnectionState] pool
- active connection pointer (defaults to "default")
- connect(name, db_path, adapter_type) → creates named connection
- disconnect(name) → removes from pool
- get(name=None) → returns ConnectionState, uses active or "default"
- list() → returns all connections with status
- set_active(name) → sets active pointer
- get_active() → returns active name
- Backward compatible: "default" name maps to old singleton behavior
"""
from __future__ import annotations
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional, cast

from ..adapters.base import AccessAdapter


@dataclass
class ConnectionState:
    """Holds the state for a single named connection."""
    adapter: AccessAdapter
    db_path: str
    adapter_type: Literal["com", "odbc"]
    created_at: datetime = field(default_factory=datetime.now)


class ConnectionPool:
    """Manages multiple named connections to Access databases.

    Provides connection isolation via named pools with an active context
    pointer. The "default" name preserves backward-compatible singleton
    behavior.
    """

    def __init__(self, adapter: AccessAdapter | None = None) -> None:
        self._pool: dict[str, ConnectionState] = {}
        self._active: str = "default"
        if adapter is not None:
            self._pool["default"] = ConnectionState(
                adapter=adapter,
                db_path="",
                adapter_type="odbc",
            )

    # -------------------------------------------------------------------------
    # Connection lifecycle
    # -------------------------------------------------------------------------

    def connect(
        self,
        name_or_db_path: str,
        db_path_or_adapter: Optional[str | AccessAdapter] = None,
        adapter: str | AccessAdapter | None = "odbc",
        adapter_type: Literal["com", "odbc"] | None = None,
    ) -> ConnectionState | bool:
        """Create or replace a named connection, or backward-compatible connect.

        New API (positional):
            pool.connect("name", "/path/db.accdb", "odbc") -> ConnectionState

        Named connection with pre-created adapter:
            pool.connect("name", "/path/db.accdb", adapter_instance, "com") -> ConnectionState

        Backward-compatible (2 positional args):
            pool.connect("/path/db.accdb", adapter) -> bool

        Args:
            name_or_db_path: Connection name (new API) or db_path (old API)
            db_path_or_adapter: db_path (new API) or adapter instance (old API)
            adapter: Adapter type string ("com"/"odbc") for new API, or pre-created
                     AccessAdapter instance for named connections with an existing adapter.
            adapter_type: Override adapter_type in ConnectionState when using a
                          pre-created adapter (3rd arg). Ignored when adapter is a string.
        """
        # Detect backward-compatible call: 2 positional args, second looks like an adapter
        if db_path_or_adapter is not None and hasattr(db_path_or_adapter, 'connect') and hasattr(db_path_or_adapter, 'disconnect'):
            # Backward-compatible: connect(db_path, adapter)
            db_path = name_or_db_path
            adapter_instance = cast(AccessAdapter, db_path_or_adapter)
            # Remove existing default connection if present
            if "default" in self._pool:
                self._pool["default"].adapter.disconnect()
                del self._pool["default"]
            result = adapter_instance.connect(db_path)
            if result:
                self._pool["default"] = ConnectionState(
                    adapter=adapter_instance,
                    db_path=db_path,
                    adapter_type="com",
                )
                self._active = "default"
            return result

        name = name_or_db_path
        db_path = db_path_or_adapter
        assert isinstance(db_path, str), "db_path must be a string for new API"
        if name in self._pool:
            raise KeyError(f"Connection '{name}' already exists. Use disconnect('{name}') first.")

        from ..adapters.wincom import WinComAdapter
        from ..adapters.odbc import OdbcAdapter

        # 3rd arg is a pre-created adapter instance → named connection with it
        # The caller is responsible for connecting the adapter before registering it.
        if adapter is not None and hasattr(adapter, 'connect') and hasattr(adapter, 'disconnect'):
            adapter_obj = cast(AccessAdapter, adapter)
            actual_adapter_type: Literal["com", "odbc"] = adapter_type or "com"
            state = ConnectionState(
                adapter=adapter_obj,
                db_path=db_path,
                adapter_type=actual_adapter_type,
            )
            self._pool[name] = state
            return state

        # Standard new API: connect(name, db_path, adapter_type_string)
        actual_adapter_type = cast(str, adapter) if isinstance(adapter, str) else (adapter_type or "odbc")
        adapter_obj = WinComAdapter() if actual_adapter_type == "com" else OdbcAdapter()
        result = adapter_obj.connect(db_path)
        if not result:
            raise RuntimeError(f"Failed to connect to {db_path} with {actual_adapter_type} adapter")

        state = ConnectionState(
            adapter=adapter_obj,
            db_path=db_path,
            adapter_type=actual_adapter_type,
        )
        self._pool[name] = state
        return state

    def disconnect(self, name: Optional[str] = None) -> None:
        """Remove a named connection from the pool.

        Args:
            name: Connection identifier to remove. If None, uses "default".
        """
        target = name if name is not None else "default"
        if target not in self._pool:
            if target == "default":
                return
            raise KeyError(f"Connection '{target}' not found")
        state = self._pool[target]
        state.adapter.disconnect()
        if target == "default":
            state.db_path = ""
        else:
            del self._pool[target]

    def get(self, name: Optional[str] = None) -> ConnectionState:
        """Get connection state by name.

        Args:
            name: Connection identifier. If None, uses active connection.

        Returns:
            ConnectionState for the named connection

        Raises:
            KeyError: If name not found or no active connection set
        """
        target = name if name is not None else self._active
        if target not in self._pool:
            raise KeyError(f"Connection '{target}' not found")
        return self._pool[target]

    def list(self) -> dict[str, ConnectionState]:
        """List all connections in the pool.

        Returns:
            Dict mapping connection names to their ConnectionState
        """
        return dict(self._pool)

    # -------------------------------------------------------------------------
    # Active context
    # -------------------------------------------------------------------------

    def set_active(self, name: str) -> None:
        """Set the active connection context.

        Args:
            name: Connection identifier to make active

        Raises:
            KeyError: If name is not in the pool
        """
        if name not in self._pool:
            raise KeyError(f"Connection '{name}' not found")
        self._active = name

    def get_active(self) -> str:
        """Get the name of the currently active connection.

        Returns:
            Name of the active connection
        """
        return self._active

    # -------------------------------------------------------------------------
    # Convenience accessors
    # -------------------------------------------------------------------------

    def get_adapter(self, name: Optional[str] = None) -> AccessAdapter:
        """Get the adapter for a connection.

        Args:
            name: Connection identifier. If None, uses active connection.

        Returns:
            AccessAdapter instance

        Raises:
            KeyError: If connection not found
        """
        return self.get(name).adapter

    def is_connected(self, name: Optional[str] = None) -> bool:
        """Check if a connection is connected.

        Args:
            name: Connection identifier. If None, uses active connection.

        Returns:
            True if the connection exists and adapter is connected
        """
        try:
            state = self.get(name)
            return state.adapter.is_connected()
        except KeyError:
            return False

    # -------------------------------------------------------------------------
    # Recovery
    # -------------------------------------------------------------------------

    def recover_access(self) -> dict:
        """Kill hung MSACCESS.EXE process and reconnect all managed connections.

        Executes taskkill /F /IM MSACCESS.EXE on Windows and attempts to
        reconnect all previously managed connections.

        Returns:
            dict with success status, reconnected connection names, and any errors
        """
        if sys.platform != "win32":
            return {
                "success": False,
                "error": "Not supported on this platform",
            }

        reconnected: list[str] = []
        errors: list[str] = []

        # Kill MSACCESS.EXE
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "MSACCESS.EXE"],
                capture_output=True,
                check=False,
            )
        except Exception as e:
            errors.append(f"Failed to kill MSACCESS.EXE: {e}")

        # Reconnect all managed connections
        for name, state in list(self._pool.items()):
            try:
                state.adapter.connect(state.db_path)
                reconnected.append(name)
            except Exception as e:
                errors.append(f"Failed to reconnect '{name}': {e}")

        return {
            "success": len(reconnected) == len(self._pool),
            "reconnected": reconnected,
            "errors": errors if errors else None,
        }

    # -------------------------------------------------------------------------
    # Backward compatibility properties (for dev_copy_service)
    # -------------------------------------------------------------------------

    @property
    def current_database(self) -> Optional[str]:
        """Get the path of the currently active (or default) database.

        For backward compatibility with code expecting old singleton API.
        """
        try:
            db_path = self.get().db_path
            return db_path or None
        except KeyError:
            return None

    @property
    def adapter(self) -> Optional[AccessAdapter]:
        """Get the adapter of the currently active (or default) connection.

        For backward compatibility with code expecting old singleton API.
        """
        try:
            return self.get().adapter
        except KeyError:
            return None

    def reconnect(self, new_path: str) -> bool:
        """Reconnect to a new database path (backward compatible API).

        Args:
            new_path: Path to the new database file

        Returns:
            True if reconnection succeeded
        """
        if "default" not in self._pool:
            return False
        adapter = self._pool["default"].adapter
        self._pool["default"].adapter.disconnect()
        result = adapter.connect(new_path)
        if result:
            self._pool["default"] = ConnectionState(
                adapter=adapter,
                db_path=new_path,
                adapter_type=self._pool["default"].adapter_type,
            )
        return result


# Alias for backward compatibility
ConnectionService = ConnectionPool
