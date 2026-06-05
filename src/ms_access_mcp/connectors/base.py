from typing import Protocol, Any, runtime_checkable
from pydantic import BaseModel


class ConnectionStatus(BaseModel):
    """Connection state for a target connector."""

    connected: bool
    server_version: str | None = None
    error: str | None = None


class ConnectorCapabilities(BaseModel):
    """Connector capability flags used by target-agnostic orchestration."""

    supports_linked_insert_select: bool
    supports_passthrough_insert_select: bool = False
    supports_checksum: bool
    supports_sampling: bool
    preferred_batch_size: int = 1000


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

    def get_capabilities(self) -> ConnectorCapabilities:
        """Return connector capabilities used by migration strategy selection."""
        ...

    def get_row_count(self, table: str) -> int:
        """Return total rows present in the target table."""
        ...

    def get_checksum(self, table: str, columns: list[str]) -> str | None:
        """Return a deterministic checksum for provided columns when supported."""
        ...

    def sample_rows(self, table: str, columns: list[str], limit: int, offset: int = 0) -> list[dict]:
        """Return deterministic row samples for verification."""
        ...

    def linked_transfer(self, source_adapter: Any, source_table: str, target_table: str) -> int:
        """Execute linked INSERT...SELECT transfer when supported by connector."""
        ...
