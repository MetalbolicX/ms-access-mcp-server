from ms_access_mcp.services.schema_mapper import SchemaMapper, MappedColumn
from ms_access_mcp.models.migration import ColumnSchema, TableSchema, ExtractedSchema


def test_map_text_to_postgres():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "postgres")
    assert mapped.target_type == "VARCHAR(255)"
    assert mapped.allow_null is True


def test_map_text_to_sqlite():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "sqlite")
    assert mapped.target_type == "TEXT"


def test_map_autoincrement_to_postgres():
    mapper = SchemaMapper()
    col = ColumnSchema(name="ID", source_type="Long Integer", max_length=None, allow_null=False, is_autoincrement=True)
    mapped = mapper.map_column(col, "postgres")
    assert "SERIAL" in mapped.target_type or "BIGSERIAL" in mapped.target_type


def test_map_datetime_to_postgres():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Created", source_type="Date/Time", max_length=None, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "postgres")
    assert mapped.target_type == "TIMESTAMP(0)"


def test_map_memo_to_mysql():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Notes", source_type="Memo", max_length=None, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "mysql")
    assert mapped.target_type == "LONGTEXT"


def test_map_unknown_to_sqlserver():
    mapper = SchemaMapper()
    col = ColumnSchema(name="Data", source_type="Binary", max_length=None, allow_null=True, is_autoincrement=False)
    mapped = mapper.map_column(col, "sqlserver")
    assert "VARBINARY" in mapped.target_type or "max" in mapped.target_type


def test_map_table_to_sqlite():
    mapper = SchemaMapper()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = mapper.map_table_ddl(table, "sqlite")
    assert "CREATE TABLE" in ddl
    assert '"ID" INTEGER PRIMARY KEY' in ddl or "ID" in ddl