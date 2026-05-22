from ms_access_mcp.connectors.postgres import PostgresConnector
from ms_access_mcp.models.migration import TableSchema, ColumnSchema

def test_postgres_connector_instantiation():
    conn = PostgresConnector()
    assert conn.target_type == "postgres"

def test_postgres_table_ddl():
    conn = PostgresConnector()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = conn.generate_ddl(table)
    assert "CREATE TABLE" in ddl
    assert '"ID"' in ddl
    assert "BIGSERIAL" in ddl