import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.migration import MigrationJob, ExtractedSchema, TableResult, TableSchema, ColumnSchema
from ..adapters.base import AccessAdapter
from .schema_mapper import SchemaMapper
from ..connectors.postgres import PostgresConnector
from ..connectors.mysql import MySqlConnector
from ..connectors.sqlite import SqliteConnector
from ..connectors.sqlserver import SqlServerConnector

CONNECTORS = {
    "postgres": PostgresConnector,
    "mysql": MySqlConnector,
    "mariadb": MySqlConnector,
    "sqlite": SqliteConnector,
    "sqlserver": SqlServerConnector,
}


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

    def __init__(self):
        self._tracker = JobTracker()
        self._schema_mapper = SchemaMapper()

    def extract_schema(self, adapter: AccessAdapter, source_path: str) -> ExtractedSchema:
        """Extract schema from Access database via adapter."""
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

        return ExtractedSchema(
            source=source_path,
            version="1.0",
            extracted_at=datetime.utcnow().isoformat(),
            tables=schema_tables,
        )

    def upload_schema(self, target_type: str, connection_string: str, schema: ExtractedSchema) -> dict:
        """Create tables in target database."""
        connector_cls = CONNECTORS.get(target_type)
        if not connector_cls:
            return {"success": False, "error": f"Unknown target type: {target_type}"}

        connector = connector_cls()
        if not connector.connect(connection_string):
            return {"success": False, "error": "Failed to connect to target database"}

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
    ) -> dict:
        """Transfer data from Access to target database."""
        if job_id is None:
            job_id = str(uuid.uuid4())

        self._tracker.create_job(job_id, target_type)
        self._tracker.update_job(job_id, status="running", phase="transfer")

        connector_cls = CONNECTORS.get(target_type)
        if not connector_cls:
            return {"success": False, "job_id": job_id, "error": f"Unknown target type: {target_type}"}

        connector = connector_cls()
        if not connector.connect(connection_string):
            return {"success": False, "job_id": job_id, "error": "Failed to connect to target database"}

        total_tables = len(schema.tables)
        for i, table in enumerate(schema.tables):
            self._tracker.update_job(job_id, current_table=table.name, progress=i / total_tables)

            try:
                rows = adapter.execute_query(f"SELECT * FROM [{table.name}]")
                if rows:
                    inserted = connector.insert_rows(table.name, rows)
                    result = TableResult(
                        table=table.name,
                        source_rows=inserted,
                        rows_transferred=inserted,
                        duration_ms=0,
                        success=True,
                    )
                else:
                    result = TableResult(table=table.name, source_rows=0, rows_transferred=0, duration_ms=0, success=True)
                self._tracker.add_result(job_id, result)
            except Exception as e:
                connector.rollback_table(table.name)
                result = TableResult(table=table.name, source_rows=0, rows_transferred=0, duration_ms=0, success=False, error=str(e))
                self._tracker.add_result(job_id, result)

        connector.disconnect()
        self._tracker.update_job(job_id, status="completed", progress=1.0, completed_at=datetime.utcnow().isoformat())

        return {"success": True, "job_id": job_id}

    def get_job_status(self, job_id: str) -> dict:
        job = self._tracker.get_job(job_id)
        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}
        return {"success": True, "job": job.model_dump()}