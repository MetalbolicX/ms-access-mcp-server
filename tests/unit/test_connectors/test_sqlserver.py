from ms_access_mcp.connectors.sqlserver import SqlServerConnector
from ms_access_mcp.models.migration import TableSchema, ColumnSchema

def test_sqlserver_connector_instantiation():
    conn = SqlServerConnector()
    assert conn.target_type == "sqlserver"

def test_sqlserver_table_ddl():
    conn = SqlServerConnector()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = conn.generate_ddl(table)
    assert "CREATE TABLE" in ddl
    assert "INT IDENTITY" in ddl