"""Tests for MCP migration tools (extract_schema, upload_schema, get_migration_status)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ms_access_mcp.mcp.server import (
    extract_schema,
    upload_schema,
    get_migration_status,
)
from ms_access_mcp.models.migration import (
    ExtractedSchema,
    TableSchema,
    ColumnSchema,
    TableTransferConfig,
)


# =============================================================================
# Helpers
# =============================================================================

class _FakeAdapter:
    """Minimal adapter for migration MCP tests."""
    def __init__(self):
        self._connected = False

    def connect(self, path):
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self):
        return self._connected


# =============================================================================
# extract_schema
# =============================================================================

class TestExtractSchema:
    """Tests for extract_schema MCP tool."""

    def test_extract_schema_reuses_active_connection_when_path_matches(self, monkeypatch):
        """When adapter is already connected to the same DB, reuse it."""
        fake_adapter = _FakeAdapter()

        mock_conn_svc = MagicMock()
        mock_conn_svc.adapter = fake_adapter
        mock_conn_svc.current_database = "C:/db.accdb"
        mock_conn_svc.is_connected.return_value = True

        mock_migr_svc = MagicMock()
        mock_schema = ExtractedSchema(source="test", version="1.0", tables=[])
        mock_migr_svc.extract_schema.return_value = mock_schema

        monkeypatch.setitem(extract_schema.__globals__, "connection_service", mock_conn_svc)
        monkeypatch.setitem(extract_schema.__globals__, "migration_service", mock_migr_svc)

        result = extract_schema("C:/db.accdb")

        assert result["success"] is True
        assert result["reused_connection"] is True
        mock_migr_svc.extract_schema.assert_called_once_with(fake_adapter, "C:/db.accdb")

    def test_extract_schema_does_not_reuse_when_path_differs(self, monkeypatch):
        """When adapter is connected to a different DB, create new adapter."""
        fake_adapter = _FakeAdapter()

        mock_conn_svc = MagicMock()
        mock_conn_svc.adapter = fake_adapter
        mock_conn_svc.current_database = "C:/old.accdb"
        mock_conn_svc.is_connected.return_value = True

        mock_migr_svc = MagicMock()
        mock_schema = ExtractedSchema(source="test", version="1.0", tables=[])
        mock_migr_svc.extract_schema.return_value = mock_schema

        monkeypatch.setitem(extract_schema.__globals__, "connection_service", mock_conn_svc)
        monkeypatch.setitem(extract_schema.__globals__, "migration_service", mock_migr_svc)
        monkeypatch.setitem(extract_schema.__globals__, "WinComAdapter", lambda: _FakeAdapter())

        result = extract_schema("C:/new.accdb")

        assert result["success"] is True
        assert result["reused_connection"] is False

    def test_extract_schema_returns_error_when_connection_fails(self, monkeypatch):
        """When adapter fails to connect, return error."""
        mock_conn_svc = MagicMock()
        mock_conn_svc.adapter = None
        mock_conn_svc.is_connected.return_value = False

        class _FailingAdapter:
            def connect(self, path):
                return False

        monkeypatch.setitem(extract_schema.__globals__, "connection_service", mock_conn_svc)
        monkeypatch.setitem(extract_schema.__globals__, "WinComAdapter", _FailingAdapter)

        result = extract_schema("C:/db.accdb")

        assert result["success"] is False
        assert "Failed to connect" in result["error"]

    def test_extract_schema_returns_error_when_not_connected(self, monkeypatch):
        """When no adapter is connected and connection_service.is_connected is False."""
        mock_conn_svc = MagicMock()
        mock_conn_svc.adapter = None
        mock_conn_svc.is_connected.return_value = False

        class _FailingAdapter:
            def connect(self, path):
                return False

        monkeypatch.setitem(extract_schema.__globals__, "connection_service", mock_conn_svc)
        monkeypatch.setitem(extract_schema.__globals__, "WinComAdapter", _FailingAdapter)

        result = extract_schema("C:/db.accdb")

        assert result["success"] is False

    def test_extract_schema_case_insensitive_path_match(self, monkeypatch):
        """Path comparison is case-insensitive and normalizes backslashes."""
        fake_adapter = _FakeAdapter()

        mock_conn_svc = MagicMock()
        mock_conn_svc.adapter = fake_adapter
        mock_conn_svc.current_database = "C:/DB.accdb"
        mock_conn_svc.is_connected.return_value = True

        mock_migr_svc = MagicMock()
        mock_schema = ExtractedSchema(source="test", version="1.0", tables=[])
        mock_migr_svc.extract_schema.return_value = mock_schema

        monkeypatch.setitem(extract_schema.__globals__, "connection_service", mock_conn_svc)
        monkeypatch.setitem(extract_schema.__globals__, "migration_service", mock_migr_svc)

        result = extract_schema("c:\\db.accdb")

        assert result["success"] is True
        assert result["reused_connection"] is True


# =============================================================================
# upload_schema
# =============================================================================

class TestUploadSchema:
    """Tests for upload_schema MCP tool."""

    def test_upload_schema_success(self, monkeypatch):
        """upload_schema calls migration_service.upload_schema with parsed schema."""
        mock_migr_svc = MagicMock()
        mock_migr_svc.upload_schema.return_value = {
            "success": True,
            "tables_created": ["customers"],
            "tables_failed": [],
        }

        monkeypatch.setitem(upload_schema.__globals__, "migration_service", mock_migr_svc)

        schema_dict = {
            "source": "test",
            "version": "1.0",
            "tables": [
                {
                    "name": "customers",
                    "columns": [
                        {"name": "ID", "source_type": "Long Integer", "allow_null": False},
                    ],
                }
            ],
        }

        result = upload_schema("sqlite", "/tmp/test.db", schema_dict)

        assert result["success"] is True
        assert result["tables_created"] == ["customers"]
        mock_migr_svc.upload_schema.assert_called_once()
        call_args = mock_migr_svc.upload_schema.call_args
        assert call_args[0][0] == "sqlite"
        assert call_args[0][1] == "/tmp/test.db"
        assert isinstance(call_args[0][2], ExtractedSchema)

    def test_upload_schema_unknown_target_type(self, monkeypatch):
        """upload_schema returns error for unknown target type."""
        mock_migr_svc = MagicMock()
        mock_migr_svc.upload_schema.return_value = {
            "success": False,
            "error": "Unknown target type: oracle",
        }

        monkeypatch.setitem(upload_schema.__globals__, "migration_service", mock_migr_svc)

        schema_dict = {"source": "test", "version": "1.0", "tables": []}

        result = upload_schema("oracle", "/tmp/test.db", schema_dict)

        assert result["success"] is False
        assert "Unknown target type" in result["error"]


# =============================================================================
# get_migration_status
# =============================================================================

class TestGetMigrationStatus:
    """Tests for get_migration_status MCP tool."""

    def test_get_migration_status_returns_job_status(self, monkeypatch):
        """get_migration_status delegates to migration_service.get_job_status."""
        mock_migr_svc = MagicMock()
        mock_migr_svc.get_job_status.return_value = {
            "job_id": "job-123",
            "status": "completed",
            "progress": 1.0,
        }

        monkeypatch.setitem(get_migration_status.__globals__, "migration_service", mock_migr_svc)

        result = get_migration_status("job-123")

        assert result["job_id"] == "job-123"
        assert result["status"] == "completed"
        mock_migr_svc.get_job_status.assert_called_once_with("job-123")

    def test_get_migration_status_returns_failed_status(self, monkeypatch):
        """get_migration_status returns failed job info."""
        mock_migr_svc = MagicMock()
        mock_migr_svc.get_job_status.return_value = {
            "job_id": "job-999",
            "status": "failed",
            "errors": [{"message": "Connection timeout"}],
        }

        monkeypatch.setitem(get_migration_status.__globals__, "migration_service", mock_migr_svc)

        result = get_migration_status("job-999")

        assert result["status"] == "failed"
        assert result["errors"][0]["message"] == "Connection timeout"
