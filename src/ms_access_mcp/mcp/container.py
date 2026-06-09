"""Service container — composition root for all MCP server services.

This module provides a single point of wiring for all services used by
MCP tool modules. Use get_container() to access the singleton instance.
Override by setting _container before calling get_container() in tests.
"""

from dataclasses import dataclass
from typing import Optional

from ..services.connection import ConnectionPool
from ..services.backend_selector import BackendSelector
from ..services.com_automation import COMAutomationService
from ..services.migration import MigrationService
from ..services.dev_copy_service import DevCopyService
from ..connectors.registry import ConnectorRegistry, _default_registry
from ..config import ServerConfig
from ..auth import ApiKeyMiddleware
from ..path_guard import PathGuard
from ..orchestrators.credential_vault import CredentialVault


@dataclass
class ServiceContainer:
    """Composition root holding all MCP server service instances."""

    connection_pool: ConnectionPool
    com_automation: COMAutomationService
    migration: MigrationService
    dev_copy: DevCopyService
    connector_registry: ConnectorRegistry
    config: Optional[ServerConfig] = None
    path_guard: Optional[PathGuard] = None
    auth_middleware: Optional[ApiKeyMiddleware] = None
    credential_vault: Optional[CredentialVault] = None


_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Return the singleton ServiceContainer, creating it lazily if needed.

    Override for testing: set _container = mock_container before calling get_container().
    """
    global _container
    if _container is None:
        connection_pool = ConnectionPool(backend_selector=BackendSelector())
        credential_vault = CredentialVault()
        _container = ServiceContainer(
            connection_pool=connection_pool,
            com_automation=COMAutomationService(connection_pool=connection_pool),
            migration=MigrationService(connector_registry=_default_registry, credential_vault=credential_vault),
            dev_copy=DevCopyService(),
            connector_registry=_default_registry,
            credential_vault=credential_vault,
        )
    return _container


def _reset_container() -> None:
    """Reset the container singleton (for testing only)."""
    global _container
    _container = None