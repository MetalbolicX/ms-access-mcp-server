from ms_access_mcp.models.migration import MigrationJob, TableResult, ExtractedSchema, ColumnSchema, TableSchema

def test_migration_job_defaults():
    job = MigrationJob(id="test-id")
    assert job.id == "test-id"
    assert job.status == "pending"
    assert job.phase == "extract"
    assert job.progress == 0.0
    assert job.results == []
    assert job.errors == []

def test_table_result():
    result = TableResult(table="Customers", source_rows=100, rows_transferred=100, duration_ms=1234, success=True)
    assert result.table == "Customers"
    assert result.rows_transferred == 100

def test_extracted_schema():
    schema = ExtractedSchema(source="C:\\db.accdb", tables=[])
    assert schema.source == "C:\\db.accdb"
    assert schema.version == "1.0"
    assert len(schema.tables) == 0

def test_column_schema():
    col = ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True)
    assert col.name == "ID"
    assert col.is_autoincrement is True