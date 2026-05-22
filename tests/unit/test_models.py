import pytest
from ms_access_mcp.models.database import TableInfo, FieldInfo, QueryInfo
from ms_access_mcp.models.vba import VBAProjectInfo, VBAModuleInfo

def test_field_info_creation():
    field = FieldInfo(name="ID", type="Long Integer", size=4, required=True)
    assert field.name == "ID"
    assert field.type == "Long Integer"
    assert field.size == 4
    assert field.required is True

def test_table_info_creation():
    fields = [FieldInfo(name="ID", type="Long Integer", size=4, required=True)]
    table = TableInfo(name="Customers", fields=fields, record_count=10)
    assert table.name == "Customers"
    assert len(table.fields) == 1
    assert table.fields[0].name == "ID"
    assert table.record_count == 10

def test_query_info_creation():
    query = QueryInfo(name="qryActiveCustomers", sql="SELECT * FROM Customers WHERE Active=1", type="Select")
    assert query.name == "qryActiveCustomers"
    assert "Active=1" in query.sql
    assert query.type == "Select"

def test_vba_models_creation():
    module = VBAModuleInfo(name="modUtils", type="Standard", has_code=True)
    project = VBAProjectInfo(name="CurrentProject", description="Main DB", modules=[module])
    assert project.name == "CurrentProject"
    assert len(project.modules) == 1
    assert project.modules[0].name == "modUtils"
    assert project.modules[0].has_code is True
