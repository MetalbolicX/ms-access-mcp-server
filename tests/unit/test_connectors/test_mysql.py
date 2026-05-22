from ms_access_mcp.connectors.mysql import MySqlConnector
from ms_access_mcp.models.migration import TableSchema, ColumnSchema

def test_mysql_connector_instantiation():
    conn = MySqlConnector()
    assert conn.target_type == "mysql"

def test_mysql_table_ddl():
    conn = MySqlConnector()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = conn.generate_ddl(table)
    assert "CREATE TABLE" in ddl
    assert "BIGINT AUTO_INCREMENT" in ddl