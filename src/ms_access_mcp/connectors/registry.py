"""Connector registry — OCP-compliant connector factory.

Register connectors at startup. MigrationService receives the registry
via constructor injection and never needs modification for new connectors.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connectors.base import TargetConnector


class ConnectorRegistry:
    """Registry of TargetConnector classes by target type name."""

    def __init__(self) -> None:
        self._entries: dict[str, type] = {}

    def register(self, name: str, connector_cls: type["TargetConnector"]) -> None:
        self._entries[name] = connector_cls

    def get(self, name: str) -> type["TargetConnector"]:
        cls = self._entries.get(name)
        if cls is None:
            raise KeyError(f"Unknown connector: {name}")
        return cls

    def create(self, name: str) -> "TargetConnector":
        return self.get(name)()

    def list_types(self) -> list[str]:
        return list(self._entries.keys())


# Default registry with built-in connectors
_default_registry = ConnectorRegistry()

# Register lazily at import time to avoid circular imports
def _init_default_registry() -> None:
    from ..connectors.postgres import PostgresConnector
    from ..connectors.mysql import MySqlConnector
    from ..connectors.sqlite import SqliteConnector
    from ..connectors.sqlserver import SqlServerConnector

    _default_registry.register("postgres", PostgresConnector)
    _default_registry.register("mysql", MySqlConnector)
    _default_registry.register("mariadb", MySqlConnector)
    _default_registry.register("sqlite", SqliteConnector)
    _default_registry.register("sqlserver", SqlServerConnector)

_init_default_registry()


def get_default_registry() -> ConnectorRegistry:
    """Return the default registry instance."""
    return _default_registry