"""Service container — composition root for all MCP server services.

This module provides a single point of wiring for all services used by
MCP tool modules. Use get_container() to access the singleton instance.
Override by setting _container before calling get_container() in tests.
"""

import os
import secrets
from dataclasses import dataclass
from typing import Optional

from ..services.connection import ConnectionPool
from ..services.backend_selector import BackendSelector
from ..services.migration import MigrationService
from ..services.dev_copy_service import DevCopyService
from ..services.session import SessionService
from ..services.rate_limiter import RateLimiter
from ..connectors.registry import ConnectorRegistry, _default_registry
from ..config import ServerConfig
from ..auth import ApiKeyMiddleware
from ..path_guard import PathGuard
from ..orchestrators.credential_vault import CredentialVault


@dataclass
class ServiceContainer:
    """Composition root holding all MCP server service instances."""

    connection_pool: ConnectionPool
    migration: MigrationService
    dev_copy: DevCopyService
    connector_registry: ConnectorRegistry
    config: Optional[ServerConfig] = None
    path_guard: Optional[PathGuard] = None
    auth_middleware: Optional[ApiKeyMiddleware] = None
    credential_vault: Optional[CredentialVault] = None
    session_service: Optional[SessionService] = None
    rate_limiter: Optional[RateLimiter] = None


_container: Optional[ServiceContainer] = None


def _create_session_service(config: ServerConfig) -> SessionService:
    """Create a SessionService from config, generating a secret if needed."""
    secret = config.session_secret
    if not secret:
        # Generate a random secret for this server instance
        secret = secrets.token_urlsafe(32)
    return SessionService(
        secret_key=secret,
        cookie_name=config.session_cookie_name,
        max_age=config.session_max_age,
    )


def _create_rate_limiter(config: ServerConfig) -> RateLimiter:
    """Create a RateLimiter from config."""
    return RateLimiter(
        max_attempts=config.rate_limit_max_attempts,
        window_seconds=config.rate_limit_window_seconds,
    )


def get_container() -> ServiceContainer:
    """Return the singleton ServiceContainer, creating it lazily if needed.

    Override for testing: set _container = mock_container before calling get_container().
    """
    global _container
    if _container is None:
        connection_pool = ConnectionPool(backend_selector=BackendSelector())
        credential_vault = CredentialVault()

        # Try to read config for session and rate limiter services
        session_service = None
        rate_limiter = None
        try:
            config = ServerConfig()
            session_service = _create_session_service(config)
            rate_limiter = _create_rate_limiter(config)
        except ValueError:
            # No ACCESS_MCP_API_KEY — services remain None
            # SSR routes will redirect to login when session_service is None
            pass

        _container = ServiceContainer(
            connection_pool=connection_pool,
            migration=MigrationService(connector_registry=_default_registry, credential_vault=credential_vault),
            dev_copy=DevCopyService(),
            connector_registry=_default_registry,
            credential_vault=credential_vault,
            session_service=session_service,
            rate_limiter=rate_limiter,
        )
    return _container


def _reset_container() -> None:
    """Reset the container singleton (for testing only)."""
    global _container
    _container = None