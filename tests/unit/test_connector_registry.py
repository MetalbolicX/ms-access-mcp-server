"""Tests for ConnectorRegistry — OCP-compliant connector factory."""

from __future__ import annotations

import pytest
from ms_access_mcp.connectors.registry import ConnectorRegistry


class TestConnectorRegistry:
    """Basic registry operations."""

    def test_empty_registry_raises_on_unknown(self):
        reg = ConnectorRegistry()
        with pytest.raises(KeyError) as exc:
            reg.get("unknown")
        assert "Unknown connector" in str(exc.value)

    def test_register_and_get(self):
        reg = ConnectorRegistry()
        reg.register("test", dict)  # use built-in as stand-in
        assert reg.get("test") is dict

    def test_create_instantiates(self):
        reg = ConnectorRegistry()
        reg.register("list", list)
        inst = reg.create("list")
        assert isinstance(inst, list)

    def test_list_types(self):
        reg = ConnectorRegistry()
        reg.register("postgres", dict)
        reg.register("mysql", dict)
        types = reg.list_types()
        assert "postgres" in types
        assert "mysql" in types


class TestDefaultRegistry:
    """Default registry has built-in connectors pre-registered."""

    def test_default_registry_has_postgres(self):
        from ms_access_mcp.connectors.registry import get_default_registry
        reg = get_default_registry()
        assert "postgres" in reg.list_types()

    def test_default_registry_can_create_postgres(self):
        from ms_access_mcp.connectors.registry import get_default_registry
        reg = get_default_registry()
        connector = reg.create("postgres")
        assert connector is not None

    def test_mysql_and_mariadb_share_connector(self):
        from ms_access_mcp.connectors.registry import get_default_registry
        reg = get_default_registry()
        # mysql and mariadb map to the same MySqlConnector class
        mysql_cls = reg.get("mysql")
        mariadb_cls = reg.get("mariadb")
        assert mysql_cls is mariadb_cls

    def test_all_builtin_types_creatable(self):
        from ms_access_mcp.connectors.registry import get_default_registry
        reg = get_default_registry()
        for target_type in reg.list_types():
            conn = reg.create(target_type)
            assert conn is not None