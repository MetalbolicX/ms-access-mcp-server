"""Tests for JobTracker — JSON-based migration job state persistence."""

from __future__ import annotations

import pytest
from ms_access_mcp.services.job_tracker import JobTracker
from ms_access_mcp.models.migration import MigrationJob, TableResult


class TestJobTracker:
    """JobTracker persistence to JSON file."""

    def test_create_job_creates_entry(self, tmp_path):
        """create_job should create a MigrationJob with pending/extract status."""
        state = tmp_path / "jobs.json"
        tracker = JobTracker(str(state))
        job = tracker.create_job("job-1", "postgres")
        assert job.id == "job-1"
        assert job.status == "pending"
        assert job.phase == "extract"

    def test_get_job_returns_none_for_missing(self, tmp_path):
        """get_job returns None when no job with that ID exists."""
        tracker = JobTracker(str(tmp_path / "nonexistent.json"))
        assert tracker.get_job("nonexistent") is None

    def test_update_job_modifies_fields(self, tmp_path):
        """update_job should modify arbitrary fields on an existing job."""
        tracker = JobTracker(str(tmp_path / "jobs.json"))
        tracker.create_job("job-1", "postgres")
        tracker.update_job("job-1", status="running", progress=0.5)
        job = tracker.get_job("job-1")
        assert job.status == "running"
        assert job.progress == 0.5

    def test_add_result_appends_to_results(self, tmp_path):
        """add_result should append a TableResult to the job's results list."""
        tracker = JobTracker(str(tmp_path / "jobs.json"))
        tracker.create_job("job-1", "postgres")
        result = TableResult(
            table="t1", source_rows=10, rows_transferred=10,
            duration_ms=100, success=True,
        )
        tracker.add_result("job-1", result)
        job = tracker.get_job("job-1")
        assert len(job.results) == 1
        assert job.results[0].table == "t1"

    def test_update_progress_sets_progress(self, tmp_path):
        """update_progress should set progress and current_table fields."""
        tracker = JobTracker(str(tmp_path / "jobs.json"))
        tracker.create_job("job-1", "postgres")
        tracker.update_progress("job-1", 0.75, current_table="customers")
        job = tracker.get_job("job-1")
        assert job.progress == 0.75
        assert job.current_table == "customers"

    def test_persistence_across_instances(self, tmp_path):
        """A second JobTracker instance reading the same file should see prior jobs."""
        state = tmp_path / "jobs.json"
        t1 = JobTracker(str(state))
        t1.create_job("job-1", "mysql")
        t2 = JobTracker(str(state))
        assert t2.get_job("job-1") is not None