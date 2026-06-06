import os
import json
import uuid
import hashlib
from datetime import UTC, datetime
from typing import Optional

from ..models.migration import MigrationJob, ExtractedSchema, TableResult, TableSchema, ColumnSchema, TableTransferConfig
from ..adapters.base import AccessAdapter
from .job_tracker import JobTracker
from .schema_mapper import SchemaMapper
from .verification import VerificationService
from ..connectors.base import ConnectorCapabilities
from .transfer_strategy import TransferContext, TransferStrategySelector
from ..connectors.registry import ConnectorRegistry, _default_registry
from .sql_builder import build_select, resolve_override, validate_columns, extract_rows
from .topological_sorter import sort_tables_by_fk
from .schema_extractor import SchemaExtractor


class MigrationService:
    """Orchestrates schema extraction, upload, and data transfer."""

    def __init__(self, connector_registry: ConnectorRegistry | None = None, job_tracker: JobTracker | None = None):
        self._tracker = job_tracker or JobTracker()
        self._schema_extractor = SchemaExtractor()
        self._schema_mapper = SchemaMapper()
        self._transfer_selector = TransferStrategySelector()
        self._verification = VerificationService()
        self._connector_registry = connector_registry or _default_registry

    def extract_schema(self, adapter: AccessAdapter, source_path: str) -> ExtractedSchema:
        """Extract schema from Access database via adapter."""
        return self._schema_extractor.extract(adapter, source_path)

    @staticmethod
    def _normalize_value(value) -> str:
        """Normalize a value for checksum computation (delegates to sql_builder)."""
        from .sql_builder import normalize_value
        return normalize_value(value)

    def _build_source_snapshot_connector(
        self,
        *,
        rows: list[dict],
        supports_checksum: bool,
        supports_sampling: bool,
    ):
        class _SourceSnapshotConnector:
            def __init__(self, snapshot_rows: list[dict], parent: "MigrationService"):
                self._rows = [dict(row) for row in snapshot_rows]
                self._parent = parent

            def get_capabilities(self) -> ConnectorCapabilities:
                return ConnectorCapabilities(
                    supports_linked_insert_select=False,
                    supports_passthrough_insert_select=False,
                    supports_checksum=supports_checksum,
                    supports_sampling=supports_sampling,
                    preferred_batch_size=1000,
                )

            def get_row_count(self, table: str) -> int:
                _ = table
                return len(self._rows)

            def get_checksum(self, table: str, columns: list[str]) -> str | None:
                _ = table
                ordered_rows = self.sample_rows(table, columns, len(self._rows), 0)
                payload = "||".join(
                    "|".join(self._parent._normalize_value(row.get(column)) for column in columns)
                    for row in ordered_rows
                )
                return hashlib.md5(payload.encode("utf-8")).hexdigest()

            def sample_rows(self, table: str, columns: list[str], limit: int, offset: int = 0) -> list[dict]:
                _ = table
                sorted_rows = sorted(
                    self._rows,
                    key=lambda row: tuple(self._parent._normalize_value(row.get(column)) for column in columns),
                )
                sampled_rows = sorted_rows[offset : offset + limit]
                return [{column: row.get(column) for column in columns} for row in sampled_rows]

        return _SourceSnapshotConnector(rows, self)

    def _verify_table_result(
        self,
        *,
        target_connector,
        table_name: str,
        columns: list[str],
        source_rows: list[dict],
        verification_mode: str,
    ):
        supports_detailed = verification_mode == "full"
        source_snapshot = self._build_source_snapshot_connector(
            rows=source_rows,
            supports_checksum=supports_detailed,
            supports_sampling=supports_detailed,
        )
        verification = self._verification.verify_table(
            source_snapshot,
            target_connector,
            table_name,
            columns,
        )

        if verification_mode == "count-only":
            count_signal = next(signal for signal in verification.signals if signal.signal_type == "count")
            verification.signals = [count_signal]
            verification.status = "passed" if count_signal.passed else "failed"

        return verification

    def upload_schema(self, target_type: str, connection_string: str, schema: ExtractedSchema) -> dict:
        """Create tables in target database.

        Tables are topologically sorted so parent tables (referenced by FK)
        are created before children. FK constraints are generated inline
        in the CREATE TABLE statement — no separate ALTER TABLE phase needed.
        """
        try:
            connector_cls = self._connector_registry.get(target_type)
        except KeyError:
            return {"success": False, "error": f"Unknown target type: {target_type}"}

        connector = connector_cls()
        if not connector.connect(connection_string):
            return {"success": False, "error": "Failed to connect to target database", "tables_created": [], "tables_failed": []}

        created = []
        failed = []

        tables_sorted = sort_tables_by_fk(schema.tables)
        for table in tables_sorted:
            if connector.table_exists(table.name):
                failed.append(table.name)
                continue
            if connector.create_table(table):
                created.append(table.name)
            else:
                failed.append(table.name)

        connector.disconnect()
        return {"success": True, "tables_created": created, "tables_failed": failed}

    def transfer_data(
        self,
        target_type: str,
        connection_string: str,
        schema: ExtractedSchema,
        adapter: AccessAdapter,
        job_id: str | None = None,
        *,
        transfer_mode: str = "auto",
        verification_mode: str = "full",
        table_overrides: dict[str, TableTransferConfig] | None = None,
        odbc_connection_string: str | None = None,
    ) -> dict:
        """Transfer data from Access to target database.

        Args:
            odbc_connection_string: Optional ODBC connection string override for passthrough.
                When provided, this is used instead of calling connector.get_odbc_connection_string().
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        self._tracker.create_job(job_id, target_type)
        self._tracker.update_job(job_id, status="running", phase="transfer")

        try:
            connector_cls = self._connector_registry.get(target_type)
        except KeyError:
            return {"success": False, "job_id": job_id, "error": f"Unknown target type: {target_type}"}

        connector = connector_cls()
        if not connector.connect(connection_string):
            return {"success": False, "job_id": job_id, "error": "Failed to connect to target database"}

        total_tables = len(schema.tables)
        for i, table in enumerate(schema.tables):
            self._tracker.update_job(job_id, current_table=table.name, progress=i / total_tables)

            try:
                table_columns = [column.name for column in table.columns]
                effective_columns, where, order_by = resolve_override(
                    table.name, table_overrides, table_columns
                )
                if effective_columns is not None:
                    validate_columns(effective_columns, table_columns)
                select_sql = build_select(table.name, effective_columns, where, order_by)
                query_result = adapter.execute_query(select_sql)
                rows = extract_rows(query_result)
                source_count = len(rows)

                columns_for_verification = effective_columns if effective_columns is not None else table_columns
                if effective_columns and effective_columns != table_columns:
                    rows = [{k: row.get(k) for k in effective_columns} for row in rows]

                if rows:
                    transfer_outcome = self._transfer_selector.transfer(
                        TransferContext(
                            table_name=table.name,
                            source_adapter=adapter,
                            target_connector=connector,
                            source_rows=rows,
                            allow_linked=transfer_mode != "batch",
                            columns=effective_columns,
                            where_clause=where,
                            order_by_columns=order_by,
                            odbc_connection_string=odbc_connection_string,
                        )
                    )
                    verification = self._verify_table_result(
                        target_connector=connector,
                        table_name=table.name,
                        columns=columns_for_verification,
                        source_rows=rows,
                        verification_mode=verification_mode,
                    )
                    result = TableResult(
                        table=table.name,
                        source_rows=source_count,
                        rows_transferred=transfer_outcome.rows_transferred,
                        duration_ms=0,
                        success=True,
                        strategy_used=transfer_outcome.strategy_used,
                        strategy_fallback_reason=transfer_outcome.fallback_reason,
                        verification=verification,
                    )
                else:
                    verification = self._verify_table_result(
                        target_connector=connector,
                        table_name=table.name,
                        columns=effective_columns,
                        source_rows=rows,
                        verification_mode=verification_mode,
                    )
                    result = TableResult(
                        table=table.name,
                        source_rows=0,
                        rows_transferred=0,
                        duration_ms=0,
                        success=True,
                        strategy_used="batch",
                        verification=verification,
                    )
                self._tracker.add_result(job_id, result)
            except Exception as e:
                connector.rollback_table(table.name)
                result = TableResult(table=table.name, source_rows=0, rows_transferred=0, duration_ms=0, success=False, error=str(e))
                self._tracker.add_result(job_id, result)

        connector.disconnect()
        self._tracker.update_job(job_id, status="completed", progress=1.0, completed_at=datetime.now(UTC).isoformat())

        return {"success": True, "job_id": job_id}

    def get_job_status(self, job_id: str) -> dict:
        job = self._tracker.get_job(job_id)
        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}
        return {"success": True, "job": job.model_dump()}

    def execute_raw_sql(self, sql: str, adapter: AccessAdapter) -> dict:
        """Execute a raw SQL statement via the adapter (passthrough path).

        Args:
            sql: Raw SQL string (e.g., INSERT INTO [ODBC;...].[table] SELECT ...)
            adapter: Source adapter (must have execute_raw_sql method)

        Returns:
            dict with success=True and rows_affected (int), or success=False and error.
        """
        if not sql or sql.strip() == "":
            return {"success": False, "error": "SQL string cannot be empty"}
        if not hasattr(adapter, "execute_raw_sql"):
            return {"success": False, "error": "Adapter does not implement execute_raw_sql (requires WinComAdapter)"}
        try:
            rows_affected = adapter.execute_raw_sql(sql)
            return {"success": True, "rows_affected": rows_affected}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
