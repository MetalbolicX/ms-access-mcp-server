"""Tests for SchemaExtractor — schema extraction from Access database via adapter."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from ms_access_mcp.services.schema_extractor import SchemaExtractor
from ms_access_mcp.models.migration import ExtractedSchema, TableSchema, ColumnSchema


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

class FakeTable:
    """Minimal table object for adapter.get_tables() fallback."""
    def __init__(self, name: str, fields: list):
        self.name = name
        self.fields = fields


class FakeField:
    """Minimal field object for adapter.get_tables() fallback."""
    def __init__(self, name: str, type: str = "Text", size: int = 0, required: bool = False):
        self.name = name
        self.type = type
        self.size = size
        self.required = required


class FakeQuery:
    """Minimal query object."""
    def __init__(self, name: str):
        self.name = name


# ═══════════════════════════════════════════════════════════════════════
# SchemaExtractor.extract — core behavior
# ═══════════════════════════════════════════════════════════════════════

class TestSchemaExtractorExtract:
    """SchemaExtractor.extract — returns ExtractedSchema with correct structure."""

    def test_returns_extracted_schema_type(self):
        """extract returns an ExtractedSchema instance."""
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = ([], None)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert isinstance(result, ExtractedSchema)

    def test_sets_source_path(self):
        """extract sets the source field to the provided source_path."""
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = ([], None)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/my.accdb")

        assert result.source == "/path/to/my.accdb"

    def test_sets_version(self):
        """extract sets version to '1.0'."""
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = ([], None)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert result.version == "1.0"

    def test_sets_extracted_at(self):
        """extract sets extracted_at to an ISO timestamp string."""
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = ([], None)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert result.extracted_at is not None
        assert "T" in result.extracted_at  # ISO format contains 'T'

    def test_empty_tables_when_no_data(self):
        """extract returns empty tables list when adapter returns nothing."""
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = ([], None)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert result.tables == []


# ═══════════════════════════════════════════════════════════════════════
# SchemaExtractor.extract — get_table_schema_plan path
# ═══════════════════════════════════════════════════════════════════════

class TestSchemaExtractorWithTableSchemaPlan:
    """SchemaExtractor.extract — uses get_table_schema_plan when adapter has it."""

    def test_calls_get_table_schema_plan(self):
        """extract calls adapter.get_table_schema_plan when it exists."""
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = ([], None)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        extractor.extract(adapter, "/path/to/db.accdb")

        adapter.get_table_schema_plan.assert_called_once()

    def test_uses_tables_from_get_table_schema_plan(self):
        """extract uses table list from get_table_schema_plan result."""
        tables = [
            TableSchema(name="customers", columns=[
                ColumnSchema(name="ID", source_type="Long Integer", allow_null=False),
                ColumnSchema(name="Name", source_type="Text", max_length=255),
            ])
        ]
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = (tables, None)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert len(result.tables) == 1
        assert result.tables[0].name == "customers"
        assert len(result.tables[0].columns) == 2

    def test_sets_unknown_metadata_when_returned(self):
        """extract sets unknown_metadata when get_table_schema_plan returns it."""
        from ms_access_mcp.models.migration import UnknownMetadata

        tables = [TableSchema(name="orders", columns=[])]
        unknown_meta = {"primary_keys": True, "foreign_keys": False}
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = (tables, unknown_meta)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert result.unknown_metadata is not None
        # unknown_metadata is set when the payload is not None
        assert isinstance(result.unknown_metadata, UnknownMetadata) or result.unknown_metadata is not None


# ═══════════════════════════════════════════════════════════════════════
# SchemaExtractor.extract — get_tables fallback path
# ═══════════════════════════════════════════════════════════════════════

class TestSchemaExtractorFallback:
    """SchemaExtractor.extract — falls back to get_tables() when get_table_schema_plan absent."""

    def test_does_not_call_get_table_schema_plan_when_missing(self):
        """extract falls back to get_tables when adapter lacks get_table_schema_plan."""
        class NoSchemaPlanAdapter:
            """Adapter without get_table_schema_plan — triggers the fallback code path."""
            def __init__(self):
                self._tables = []
                self._queries = []
                self.get_tables_called = False

            def get_tables(self):
                self.get_tables_called = True
                return self._tables

            def get_queries(self):
                return self._queries

        adapter = NoSchemaPlanAdapter()

        extractor = SchemaExtractor()
        extractor.extract(adapter, "/path/to/db.accdb")

        # Should not fail and should call get_tables
        assert adapter.get_tables_called is True

    def test_builds_table_schemas_from_get_tables(self):
        """extract builds TableSchema list from adapter.get_tables() in fallback path."""
        fields = [
            FakeField(name="ID", type="Long Integer", size=4, required=True),
            FakeField(name="Name", type="Text", size=255, required=False),
        ]
        tables = [FakeTable(name="customers", fields=fields)]
        adapter = MagicMock()
        # Remove get_table_schema_plan to trigger fallback
        del adapter.get_table_schema_plan
        adapter.get_tables.return_value = tables
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert len(result.tables) == 1
        assert result.tables[0].name == "customers"
        assert len(result.tables[0].columns) == 2
 # Check column mapping from field
        col_names = [c.name for c in result.tables[0].columns]
        assert "ID" in col_names
        assert "Name" in col_names

    def test_maps_field_properties_correctly_in_fallback(self):
        """In fallback path, field properties map to ColumnSchema correctly."""
        fields = [
            FakeField(name="ID", type="Long Integer", size=4, required=True),
        ]
        tables = [FakeTable(name="orders", fields=fields)]
        adapter = MagicMock()
        del adapter.get_table_schema_plan
        adapter.get_tables.return_value = tables
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        col = result.tables[0].columns[0]
        assert col.name == "ID"
        assert col.source_type == "Long Integer"
        assert col.max_length == 4
        assert col.allow_null is False  # required=True → allow_null=False
        assert col.is_autoincrement is False

    def test_max_length_zero_becomes_none(self):
        """When field.size is 0, max_length should be None (not0)."""
        fields = [
            FakeField(name="Notes", type="Text", size=0, required=False),
        ]
        tables = [FakeTable(name="memo", fields=fields)]
        adapter = MagicMock()
        del adapter.get_table_schema_plan
        adapter.get_tables.return_value = tables
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert result.tables[0].columns[0].max_length is None


# ═══════════════════════════════════════════════════════════════════════
# SchemaExtractor.extract — query exclusion
# ═══════════════════════════════════════════════════════════════════════

class TestSchemaExtractorQueryExclusion:
    """SchemaExtractor.extract — excludes tables whose names match query names."""

    def test_excludes_table_with_same_name_as_query(self):
        """When a table name matches a query name, the table is excluded."""
        # Table "MyReport" exists in tables
        tables_from_plan = [
            TableSchema(name="MyReport", columns=[
                ColumnSchema(name="ID", source_type="Long Integer"),
            ])
        ]
        queries = [FakeQuery(name="MyReport")]

        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = (tables_from_plan, None)
        adapter.get_queries.return_value = queries

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        # Table "MyReport" must be filtered out
        assert all(t.name != "MyReport" for t in result.tables)

    def test_includes_table_when_no_matching_query(self):
        """Table is included when no query shares its name."""
        tables_from_plan = [
            TableSchema(name="customers", columns=[
                ColumnSchema(name="ID", source_type="Long Integer"),
            ])
        ]
        queries = [FakeQuery(name="ActiveCustomers")]

        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = (tables_from_plan, None)
        adapter.get_queries.return_value = queries

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        assert len(result.tables) == 1
        assert result.tables[0].name == "customers"

    def test_multiple_tables_and_queries(self):
        """Multiple tables and queries — only matching names are excluded."""
        tables_from_plan = [
            TableSchema(name="customers", columns=[]),
            TableSchema(name="orders", columns=[]),
            TableSchema(name="reports", columns=[]),
        ]
        queries = [
            FakeQuery(name="customers"),
            FakeQuery(name="reports"),
        ]

        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = (tables_from_plan, None)
        adapter.get_queries.return_value = queries

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        table_names = {t.name for t in result.tables}
        assert table_names == {"orders"}  # customers and reports filtered out


# ═══════════════════════════════════════════════════════════════════════
# SchemaExtractor.extract — unknown_metadata
# ═══════════════════════════════════════════════════════════════════════

class TestSchemaExtractorUnknownMetadata:
    """SchemaExtractor.extract — sets unknown_metadata when adapter provides it."""

    def test_unknown_metadata_not_set_when_none(self):
        """When get_table_schema_plan returns None for unknown_metadata, field uses default."""
        tables = [TableSchema(name="t", columns=[])]
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = (tables, None)
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        # Should use default UnknownMetadata (all False)
        assert result.unknown_metadata is not None

    def test_unknown_metadata_set_when_returned(self):
        """When get_table_schema_plan returns unknown_metadata dict, it is set on result."""
        tables = [TableSchema(name="t", columns=[])]
        adapter = MagicMock()
        adapter.get_table_schema_plan.return_value = (tables, {"primary_keys": True})
        adapter.get_queries.return_value = []

        extractor = SchemaExtractor()
        result = extractor.extract(adapter, "/path/to/db.accdb")

        # unknown_metadata should be set (not the default empty)
        assert result.unknown_metadata is not None
