from ms_access_mcp.services.migration import MigrationService, JobTracker
from ms_access_mcp.models.migration import MigrationJob, ExtractedSchema, TableSchema, ColumnSchema
import uuid
import os
import tempfile


def test_job_tracker_creates_job():
    """JobTracker should create a job with pending status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, ".test_jobs.json")
        tracker = JobTracker(state_file=state_file)
        job_id = str(uuid.uuid4())
        tracker.create_job(job_id, "postgres")
        job = tracker.get_job(job_id)
        assert job is not None
        assert job.id == job_id
        assert job.status == "pending"
        assert job.phase == "extract"


def test_job_tracker_updates_progress():
    """JobTracker should update job progress and current_table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, ".test_jobs.json")
        tracker = JobTracker(state_file=state_file)
        job_id = str(uuid.uuid4())
        tracker.create_job(job_id, "postgres")
        tracker.update_progress(job_id, 0.5, current_table="Customers")
        job = tracker.get_job(job_id)
        assert job.progress == 0.5
        assert job.current_table == "Customers"


def test_job_tracker_persists_to_file():
    """JobTracker should persist job state to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, ".test_jobs.json")
        tracker = JobTracker(state_file=state_file)
        job_id = str(uuid.uuid4())
        tracker.create_job(job_id, "mysql")
        tracker.update_progress(job_id, 0.75, current_table="Orders")

        # Create new tracker instance to verify persistence
        tracker2 = JobTracker(state_file=state_file)
        job = tracker2.get_job(job_id)
        assert job is not None
        assert job.progress == 0.75
        assert job.current_table == "Orders"
        assert job.status == "pending"


def test_job_tracker_add_result():
    """JobTracker should store table results."""
    from ms_access_mcp.models.migration import TableResult
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, ".test_jobs.json")
        tracker = JobTracker(state_file=state_file)
        job_id = str(uuid.uuid4())
        tracker.create_job(job_id, "sqlite")
        result = TableResult(table="Products", source_rows=50, rows_transferred=50, duration_ms=100, success=True)
        tracker.add_result(job_id, result)
        job = tracker.get_job(job_id)
        assert len(job.results) == 1
        assert job.results[0].table == "Products"
        assert job.results[0].source_rows == 50


def test_migration_service_has_extract_schema():
    """MigrationService should have extract_schema method."""
    service = MigrationService()
    assert hasattr(service, 'extract_schema')
    assert callable(service.extract_schema)


def test_migration_service_has_upload_schema():
    """MigrationService should have upload_schema method."""
    service = MigrationService()
    assert hasattr(service, 'upload_schema')
    assert callable(service.upload_schema)


def test_migration_service_has_transfer_data():
    """MigrationService should have transfer_data method."""
    service = MigrationService()
    assert hasattr(service, 'transfer_data')
    assert callable(service.transfer_data)


def test_migration_service_has_get_job_status():
    """MigrationService should have get_job_status method."""
    service = MigrationService()
    assert hasattr(service, 'get_job_status')
    assert callable(service.get_job_status)