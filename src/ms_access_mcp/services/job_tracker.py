"""JobTracker — JSON-based migration job state persistence."""

from __future__ import annotations

import os
import json
from typing import Optional

from ..models.migration import MigrationJob, TableResult


class JobTracker:
    """Tracks migration job state to JSON file."""

    def __init__(self, state_file: str | None = None):
        self._state_file = state_file or os.path.join(
            os.environ.get("TEMP", "/tmp"), ".migration_jobs.json"
        )
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
                json.dump(
                    {k: v.model_dump() for k, v in self._jobs.items()}, f, indent=2
                )
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