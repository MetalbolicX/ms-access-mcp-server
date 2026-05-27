"""Tests for mcp/migration.py tool bindings."""
import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server


class TestMigrationToolsConnectionGuards:
    """Tests for migration tools that reuse active connection check."""

    def test_extract_schema_reuses_active_connection_when_same_db(self):
        """extract_schema should reuse active connection when paths match."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.current_database = "/path/to/db.accdb"
        mock_conn.adapter = MagicMock()
        mock_svc = MagicMock()
        mock_svc.extract_schema.return_value = MagicMock(model_dump=MagicMock(return_value={"source": "/path/to/db.accdb", "tables": []}))
        with patch.dict(server.extract_schema.__globals__, connection_service=mock_conn, migration_service=mock_svc):
            result = server.extract_schema("/path/to/db.accdb")
            assert result["success"] is True
            assert result["reused_connection"] is True

    def test_extract_schema_creates_new_adapter_when_not_connected(self):
        """extract_schema should create new adapter and disconnect when no active connection."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_conn.adapter = None
        mock_svc = MagicMock()
        mock_svc.extract_schema.return_value = MagicMock(model_dump=MagicMock(return_value={"source": "/path/to/db.accdb", "tables": []}))
        mock_adapter = MagicMock()
        mock_adapter.connect.return_value = True
        with patch.dict(server.extract_schema.__globals__, connection_service=mock_conn, migration_service=mock_svc, WinComAdapter=MagicMock(return_value=mock_adapter)):
            result = server.extract_schema("/path/to/db.accdb")
            assert result["success"] is True
            assert result["reused_connection"] is False
            mock_adapter.disconnect.assert_called_once()


class TestUploadSchema:
    """Tests for upload_schema tool."""

    def test_upload_schema_deserializes_and_calls_service(self):
        """upload_schema should deserialize schema_json and call migration service."""
        mock_svc = MagicMock()
        mock_svc.upload_schema.return_value = {"success": True}
        schema_dict = {"source": "/src.accdb", "tables": [], "version": "1.0"}
        with patch.dict(server.upload_schema.__globals__, migration_service=mock_svc):
            result = server.upload_schema("postgres", "conn-string", schema_dict)
            assert result["success"] is True
            mock_svc.upload_schema.assert_called_once()


class TestTransferData:
    """Tests for transfer_data tool."""

    def test_transfer_data_connects_extracts_and_transfers(self):
        """transfer_data should connect, extract schema (if not provided), and transfer."""
        mock_svc = MagicMock()
        mock_svc.extract_schema.return_value = MagicMock(model_dump=MagicMock(return_value={"source": "/src.accdb", "tables": []}))
        mock_svc.transfer_data.return_value = {"success": True, "job_id": "job-123"}
        mock_adapter = MagicMock()
        mock_adapter.connect.return_value = True
        with patch.dict(server.transfer_data.__globals__, migration_service=mock_svc, WinComAdapter=MagicMock(return_value=mock_adapter)):
            result = server.transfer_data("postgres", "conn-string", "/src.accdb")
            assert result["success"] is True
            mock_adapter.connect.assert_called_once_with("/src.accdb")
            mock_svc.transfer_data.assert_called_once()
            mock_adapter.disconnect.assert_called_once()

    def test_transfer_data_with_schema_json_skips_extraction(self):
        """transfer_data with schema_json should use provided schema without extraction."""
        mock_svc = MagicMock()
        mock_svc.transfer_data.return_value = {"success": True}
        mock_adapter = MagicMock()
        mock_adapter.connect.return_value = True
        schema_json = {"source": "/src.accdb", "tables": [], "version": "1.0"}
        with patch.dict(server.transfer_data.__globals__, migration_service=mock_svc, WinComAdapter=MagicMock(return_value=mock_adapter)):
            result = server.transfer_data("postgres", "conn-string", "/src.accdb", schema_json=schema_json)
            assert result["success"] is True
            mock_svc.extract_schema.assert_not_called()


class TestGetMigrationStatus:
    """Tests for get_migration_status tool."""

    def test_get_migration_status_delegates_to_service(self):
        """get_migration_status should delegate to migration_service.get_job_status."""
        mock_svc = MagicMock()
        mock_svc.get_job_status.return_value = {"success": True, "job": {}}
        with patch.dict(server.get_migration_status.__globals__, migration_service=mock_svc):
            result = server.get_migration_status("job-123")
            assert result["success"] is True
            mock_svc.get_job_status.assert_called_once_with("job-123")
