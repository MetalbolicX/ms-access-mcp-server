"""Schema extractor — extracts schema from Access database via adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from ..adapters.base import AccessAdapter
from ..models.migration import ExtractedSchema, TableSchema, ColumnSchema


class SchemaExtractor:
    """Extracts schema from an Access database via an adapter.

    Supports two adapter code paths:
    1. get_table_schema_plan() — preferred, returns tables + unknown metadata
    2. get_tables() — fallback, builds TableSchema from raw table/field objects
    """

    def extract(self, adapter: AccessAdapter, source_path: str) -> ExtractedSchema:
        """Extract schema from Access database via adapter.

        Args:
            adapter: AccessAdapter instance (must provide get_queries at minimum)
            source_path: Path to the source Access database

        Returns:
            ExtractedSchema with tables list, source, version, extracted_at,
            and optional unknown_metadata.
        """
        unknown_metadata_payload = None
        if hasattr(adapter, "get_table_schema_plan"):
            schema_tables, unknown_metadata_payload = adapter.get_table_schema_plan()
        else:
            tables = adapter.get_tables()
            schema_tables = []
            for t in tables:
                cols = []
                for f in t.fields:
                    cols.append(ColumnSchema(
                        name=f.name,
                        source_type=f.type,
                        max_length=f.size if f.size > 0 else None,
                        allow_null=not f.required,
                        is_autoincrement=False,
                    ))
                schema_tables.append(TableSchema(name=t.name, columns=cols))
        query_names = {q.name for q in adapter.get_queries()}
        schema_tables = [t for t in schema_tables if t.name not in query_names]

        payload = {
            "source": source_path,
            "version": "1.0",
            "extracted_at": datetime.now(UTC).isoformat(),
            "tables": schema_tables,
        }
        if unknown_metadata_payload is not None:
            payload["unknown_metadata"] = unknown_metadata_payload

        return ExtractedSchema(**payload)
