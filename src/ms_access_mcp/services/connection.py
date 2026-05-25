from typing import Optional
from ..adapters.base import AccessAdapter


class ConnectionService:
    """Manages connection state and lifecycle for Access databases."""

    def __init__(self, adapter: Optional[AccessAdapter] = None):
        self._adapter = adapter
        self._current_database: Optional[str] = None

    def connect(self, db_path: str, adapter: AccessAdapter) -> bool:
        """Connect to an Access database using the provided adapter."""
        self._adapter = adapter
        result = self._adapter.connect(db_path)
        if result:
            self._current_database = db_path
        return result

    def disconnect(self) -> None:
        """Disconnect from the current database."""
        if self._adapter:
            self._adapter.disconnect()
            self._current_database = None

    def is_connected(self) -> bool:
        """Check if currently connected to a database."""
        if self._adapter is None:
            return False
        return self._adapter.is_connected()

    @property
    def current_database(self) -> Optional[str]:
        """Get the path of the currently connected database."""
        return self._current_database

    @property
    def adapter(self) -> Optional[AccessAdapter]:
        """Get the currently configured adapter instance."""
        return self._adapter

    def reconnect(self, new_path: str) -> bool:
        """Disconnect and reconnect to a new database path.

        Preserves the current adapter instance but reconnects to a different
        database file (e.g., after deploying dev copy back to production).

        Args:
            new_path: Path to the new database file

        Returns:
            True if reconnection succeeded, False otherwise
        """
        if self._adapter is None:
            return False
        self.disconnect()
        return self.connect(new_path, self._adapter)
