from typing import Protocol, Any, runtime_checkable
from pydantic import BaseModel


class ConnectionStatus(BaseModel):
    """Connection state for a target connector."""

    connected: bool
    server_version: str | None = None
    error: str | None = None


@runtime_checkable
class TargetConnector(Protocol):
    """Abstract interface for target database operations during migration."""

    @property
    def target_type(self) -> str:
        """Return the target database type."""
        ...

    def connect(self, connection_string: str) -> bool:
        """Establish connection to target database."""
        ...

    def disconnect(self) -> None:
        """Close the connection."""
        ...

    def is_connected(self) -> bool:
        """Check if currently connected."""
        ...

    def create_table(self, schema: Any) -> bool:
        """Create a table from schema definition. Returns True on success."""
        ...

    def insert_rows(self, table: str, rows: list[dict]) -> int:
        """Insert rows into a table. Returns number of rows inserted."""
        ...

    def rollback_table(self, table: str) -> None:
        """Rollback (delete) a table if partial transfer failed."""
        ...

    def table_exists(self, table_name: str) -> bool:
        """Check if a table already exists in target."""
        ...