from typing import Optional
from ..adapters.base import AccessAdapter
from ..models.database import TableInfo, QueryInfo, RelationshipInfo


class SchemaService:
    """Provides schema exploration capabilities for Access databases."""

    def __init__(self, adapter: Optional[AccessAdapter] = None):
        self._adapter = adapter

    def set_adapter(self, adapter: AccessAdapter) -> None:
        """Set the adapter for schema operations."""
        self._adapter = adapter

    def get_tables(self) -> list[TableInfo]:
        """Get all user tables from the connected database."""
        if self._adapter is None:
            return []
        return self._adapter.get_tables()

    def get_table_schema(self, table_name: str) -> Optional[TableInfo]:
        """Get detailed schema for a specific table."""
        if self._adapter is None:
            return None
        tables = self._adapter.get_tables()
        for table in tables:
            if table.name == table_name:
                return table
        return None

    def get_queries(self) -> list[QueryInfo]:
        """Get all saved queries from the database."""
        if self._adapter is None:
            return []
        # Stub implementation
        return []

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get all foreign key relationships."""
        if self._adapter is None:
            return []
        # Stub implementation
        return []
