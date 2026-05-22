from ms_access_mcp.connectors.sqlite import SqliteConnector
from ms_access_mcp.models.migration import TableSchema, ColumnSchema

def test_sqlite_connector_instantiation():
    conn = SqliteConnector()
    assert conn.target_type == "sqlite"

def test_sqlite_table_ddl():
    conn = SqliteConnector()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = conn.generate_ddl(table)
    assert "CREATE TABLE" in ddl