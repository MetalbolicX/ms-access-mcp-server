from ms_access_mcp.models.migration import (
    MigrationJob,
    TableResult,
    ExtractedSchema,
    ColumnSchema,
    TableSchema,
    ForeignKeySchema,
    IndexSchema,
    UnknownMetadata,
    VerificationSignal,
    VerificationResult,
)

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


def test_table_schema_supports_fk_default_index_metadata():
    table = TableSchema(
        name="Orders",
        columns=[
            ColumnSchema(
                name="OrderID",
                source_type="Long Integer",
                allow_null=False,
                is_autoincrement=True,
            ),
            ColumnSchema(
                name="Status",
                source_type="Text",
                max_length=20,
                default_value="PENDING",
            ),
        ],
        primary_key=["OrderID"],
        foreign_keys=[
            ForeignKeySchema(
                name="fk_orders_customer",
                columns=["CustomerID"],
                referenced_table="Customers",
                referenced_columns=["ID"],
            )
        ],
        indexes=[IndexSchema(name="idx_orders_status", columns=["Status"], is_unique=False)],
    )

    assert table.foreign_keys[0].referenced_table == "Customers"
    assert table.columns[1].default_value == "PENDING"
    assert table.indexes[0].columns == ["Status"]


def test_unknown_metadata_is_explicit_in_schema_plan():
    schema = ExtractedSchema(
        source="C:\\db.accdb",
        tables=[],
        unknown_metadata=UnknownMetadata(
            primary_keys=True,
            foreign_keys=False,
            defaults=True,
            indexes=False,
            autoincrement=True,
        ),
    )

    assert schema.unknown_metadata.primary_keys is True
    assert schema.unknown_metadata.indexes is False


def test_verification_result_records_structured_signals():
    verification = VerificationResult(
        table="Orders",
        status="failed",
        signals=[
            VerificationSignal(
                signal_type="count",
                passed=False,
                expected="250",
                actual="249",
            )
        ],
    )

    assert verification.table == "Orders"
    assert verification.status == "failed"
    assert verification.signals[0].signal_type == "count"
    assert verification.signals[0].passed is False


def test_normalizes_table_and_column_fields_during_model_validation():
    table = TableSchema(
        name="  Customers  ",
        columns=[
            ColumnSchema(
                name="  Name  ",
                source_type="  Text  ",
                default_value="   ",
            )
        ],
    )

    assert table.name == "Customers"
    assert table.columns[0].name == "Name"
    assert table.columns[0].source_type == "Text"
    assert table.columns[0].default_value is None
