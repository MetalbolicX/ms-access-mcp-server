import os
import json
import uuid
import hashlib
from datetime import UTC, datetime
from typing import Optional

from ..models.migration import MigrationJob, ExtractedSchema, TableResult, TableSchema, ColumnSchema, TableTransferConfig
from ..adapters.base import AccessAdapter
from .schema_mapper import SchemaMapper
from .verification import VerificationService
from ..connectors.base import ConnectorCapabilities
from .transfer_strategy import TransferContext, TransferStrategySelector
from ..connectors.registry import ConnectorRegistry, _default_registry


class JobTracker:
    """Tracks migration job state to JSON file."""

    def __init__(self, state_file: str | None = None):
        self._state_file = state_file or os.path.join(os.environ.get("TEMP", "/tmp"), ".migration_jobs.json")
        self._jobs: dict[str, MigrationJob] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, "r") as f:
                    data = json.load(f)
                    for job_data in data.values():
                        self._jobs[job_data["id"]] = MigrationJob(**job_data)
            except Exception:
                pass

    def _save(self) -> None:
        try:
            with open(self._state_file, "w") as f:
                json.dump({k: v.model_dump() for k, v in self._jobs.items()}, f, indent=2)
        except Exception:
            pass

    def create_job(self, job_id: str, target_type: str) -> MigrationJob:
        job = MigrationJob(id=job_id, status="pending", phase="extract")
        self._jobs[job_id] = job
        self._save()
        return job

    def get_job(self, job_id: str) -> Optional[MigrationJob]:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs) -> None:
        if job_id in self._jobs:
            for k, v in kwargs.items():
                setattr(self._jobs[job_id], k, v)
            self._save()

    def add_result(self, job_id: str, result: TableResult) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].results.append(result)
            self._save()

    def update_progress(self, job_id: str, progress: float, current_table: str | None = None) -> None:
        self.update_job(job_id, progress=progress, current_table=current_table)


class MigrationService:
    """Orchestrates schema extraction, upload, and data transfer."""

    def __init__(self, connector_registry: ConnectorRegistry | None = None):
        self._tracker = JobTracker()
        self._schema_mapper = SchemaMapper()
        self._transfer_selector = TransferStrategySelector()
        self._verification = VerificationService()
        self._connector_registry = connector_registry or _default_registry

    @staticmethod
    def _build_select(
        table_name: str,
        columns: list[str] | None,
        where: str | None,
        order_by: list[str] | None,
    ) -> str:
        """Build SELECT statement with optional column list, WHERE, ORDER BY.

        columns=None → SELECT *
        columns=[] → invalid (should not reach here)
        columns=[...] → SELECT col, col, ...
        """
        cols = "*" if columns is None else ", ".join(columns)
        sql = f"SELECT {cols} FROM [{table_name}]"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {', '.join(order_by)}"
        return sql

    @staticmethod
    def _resolve_override(
        table_name: str,
        overrides: dict[str, "TableTransferConfig"] | None,
        schema_columns: list[str],
    ) -> tuple[list[str] | None, str | None, list[str] | None]:
        """Return (effective_columns, where, order_by) for a table.

        Returns (None, None, None) when table has no override entry or all override
        fields are None — signaling to _build_select to use SELECT *.
        Returns (list, str, list) when at least one override field is set.
        """
        if overrides is None:
            return None, None, None
        cfg = overrides.get(table_name)
        if cfg is None:
            return None, None, None
        effective_cols = cfg.columns if cfg.columns else None
        return effective_cols, cfg.where, cfg.order_by

    @staticmethod
    def _validate_columns(requested: list[str], available: list[str]) -> None:
        """Raise ValueError if any requested column not in available."""
        available_set = set(available)
        for col in requested:
            if col not in available_set:
                raise ValueError(f"Invalid column '{col}' not found in table schema")

    @staticmethod
    def _extract_rows_from_query_result(query_result: dict | list) -> list[dict]:
        if isinstance(query_result, dict):
            return query_result.get("rows", []) if query_result.get("success", False) else []
        return query_result

    def extract_schema(self, adapter: AccessAdapter, source_path: str) -> ExtractedSchema:
        """Extract schema from Access database via adapter."""
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

    @staticmethod
    def _normalize_value(value) -> str:
        return "<NULL>" if value is None else str(value)

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
        """Create tables in target database."""
        try:
            connector_cls = self._connector_registry.get(target_type)
        except KeyError:
            return {"success": False, "error": f"Unknown target type: {target_type}"}

        connector = connector_cls()
        if not connector.connect(connection_string):
            return {"success": False, "error": "Failed to connect to target database", "tables_created": [], "tables_failed": []}

        created = []
        failed = []

        for table in schema.tables:
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
    ) -> dict:
        """Transfer data from Access to target database."""
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
                effective_columns, where, order_by = self._resolve_override(
                    table.name, table_overrides, table_columns
                )
                if effective_columns is not None:
                    self._validate_columns(effective_columns, table_columns)
                select_sql = self._build_select(table.name, effective_columns, where, order_by)
                query_result = adapter.execute_query(select_sql)
                rows = self._extract_rows_from_query_result(query_result)
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
