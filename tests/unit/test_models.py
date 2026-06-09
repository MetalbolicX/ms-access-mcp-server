import pytest
from ms_access_mcp.models.database import TableInfo, FieldInfo, QueryInfo, IndexInfo
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


# =============================================================================
# IndexInfo tests — index-management-tools PR1 Task 1.1
# =============================================================================

def test_index_info_minimal_instantiation():
    """IndexInfo with only name — all other fields use defaults."""
    idx = IndexInfo(name="IX_Example")
    assert idx.name == "IX_Example"
    assert idx.columns == []
    assert idx.is_unique is False
    assert idx.is_primary is False
    assert idx.ignore_nulls is False


def test_index_info_all_fields():
    """IndexInfo with all fields explicitly set."""
    idx = IndexInfo(
        name="PK_Customers",
        columns=["CustomerID"],
        is_unique=True,
        is_primary=True,
        ignore_nulls=False,
    )
    assert idx.name == "PK_Customers"
    assert idx.columns == ["CustomerID"]
    assert idx.is_unique is True
    assert idx.is_primary is True
    assert idx.ignore_nulls is False


def test_index_info_composite_columns():
    """IndexInfo with multiple columns for composite index."""
    idx = IndexInfo(name="IX_Orders_CustomerDate", columns=["CustomerID", "OrderDate"])
    assert idx.name == "IX_Orders_CustomerDate"
    assert len(idx.columns) == 2
    assert "CustomerID" in idx.columns
    assert "OrderDate" in idx.columns


def test_index_info_ignore_nulls_true():
    """IndexInfo with ignore_nulls=True for Jet WITH IGNORE NULL clause."""
    idx = IndexInfo(name="IX_Name", columns=["LastName"], ignore_nulls=True)
    assert idx.ignore_nulls is True


def test_index_info_non_primary_non_unique():
    """IndexInfo for a secondary non-unique index."""
    idx = IndexInfo(name="IX_LastName", columns=["LastName"], is_unique=False, is_primary=False)
    assert idx.is_unique is False
    assert idx.is_primary is False
