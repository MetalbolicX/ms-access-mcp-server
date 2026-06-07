"""Tests for mcp/container.py - ServiceContainer composition root."""
import pytest

from ms_access_mcp.mcp import container


class TestServiceContainer:
    """Tests for ServiceContainer and get_container()."""

    def setup_method(self):
        """Reset container before each test."""
        container._reset_container()

    def teardown_method(self):
        """Reset container after each test."""
        container._reset_container()

    def test_get_container_returns_service_container(self):
        """get_container() should return a ServiceContainer instance."""
        c = container.get_container()
        assert isinstance(c, container.ServiceContainer)

    def test_get_container_returns_singleton(self):
        """get_container() should return the same instance on repeated calls."""
        c1 = container.get_container()
        c2 = container.get_container()
        assert c1 is c2

    def test_get_container_has_all_services(self):
        """Container should hold all four core service instances."""
        c = container.get_container()
        assert c.connection_pool is not None
        assert c.com_automation is not None
        assert c.migration is not None
        assert c.dev_copy is not None

    def test_container_has_connector_registry(self):
        """Container should hold a connector_registry."""
        c = container.get_container()
        assert c.connector_registry is not None

    def test_container_config_optional(self):
        """config should be None (lazy, set only via HTTP mode)."""
        c = container.get_container()
        assert c.config is None

    def test_container_path_guard_optional(self):
        """path_guard should be None (lazy, set only via HTTP mode)."""
        c = container.get_container()
        assert c.path_guard is None

    def test_container_auth_middleware_optional(self):
        """auth_middleware should be None (lazy, set only via HTTP mode)."""
        c = container.get_container()
        assert c.auth_middleware is None

    def test_connection_pool_uses_backend_selector(self):
        """get_container().connection_pool should be created with a BackendSelector instance."""
        c = container.get_container()
        from ms_access_mcp.services.backend_selector import BackendSelector

        assert isinstance(c.connection_pool._backend_selector, BackendSelector)