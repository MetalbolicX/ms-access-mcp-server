import pytest
from ms_access_mcp.services.schema import SchemaService

def test_schema_service_initialization():
    service = SchemaService()
    assert service is not None

def test_schema_service_can_list_tables():
    service = SchemaService()
    tables = service.get_tables()
    assert isinstance(tables, list)