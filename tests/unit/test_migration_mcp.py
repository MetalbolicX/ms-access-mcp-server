"""Tests for MCP migration tools (extract_schema, upload_schema, get_migration_status)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ms_access_mcp.mcp.server import (
    extract_schema,
    upload_schema,
    get_migration_status,
)
from ms_access_mcp.mcp import migration as migration_module
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

    def test_upload_schema_with_server_id_resolves_password_from_vault(self, monkeypatch):
        """upload_schema with server_id retrieves password from vault and injects PWD."""
        from unittest.mock import patch

        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = "vault_secret"

        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        mock_migr_svc = MagicMock()
        mock_migr_svc.upload_schema.return_value = {
            "success": True,
            "tables_created": ["customers"],
            "tables_failed": [],
        }

        def fake_get_container():
            return mock_container

        schema_dict = {
            "source": "test",
            "version": "1.0",
            "tables": [
                {"name": "customers", "columns": [{"name": "ID", "source_type": "Long Integer", "allow_null": False}]},
            ],
        }

        with patch.object(upload_schema.__globals__["get_container"], '__wrapped__', fake_get_container, create=True):
            pass  # patch at module level below

        # Patch get_container in the migration module
        with patch('ms_access_mcp.mcp.migration.get_container', return_value=mock_container):
            with patch('ms_access_mcp.mcp.migration._migration', return_value=mock_migr_svc):
                result = upload_schema(
                    "postgres",
                    "DRIVER={PostgreSQL};SERVER=localhost;DATABASE=test",
                    schema_dict,
                    server_id="srv1",
                )

        assert result["success"] is True
        mock_vault.retrieve.assert_called_once_with("srv1")
        # Verify PWD was injected into the connection string passed to the service
        call_args = mock_migr_svc.upload_schema.call_args
        conn_str_with_pwd = call_args[0][1]
        assert "PWD=vault_secret" in conn_str_with_pwd

    def test_upload_schema_with_unknown_server_id_returns_error_without_calling_connector(self, monkeypatch):
        """upload_schema with unknown server_id returns error before connector is called."""
        from unittest.mock import patch

        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = None  # vault miss

        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        mock_migr_svc = MagicMock()

        schema_dict = {
            "source": "test",
            "version": "1.0",
            "tables": [
                {"name": "customers", "columns": [{"name": "ID", "source_type": "Long Integer", "allow_null": False}]},
            ],
        }

        with patch('ms_access_mcp.mcp.migration.get_container', return_value=mock_container):
            with patch('ms_access_mcp.mcp.migration._migration', return_value=mock_migr_svc):
                result = upload_schema(
                    "postgres",
                    "DRIVER={PostgreSQL};SERVER=localhost;DATABASE=test",
                    schema_dict,
                    server_id="unknown_srv",
                )

        assert result["success"] is False
        assert "server_id" in result["error"].lower() or "not found" in result["error"].lower()
        # Connector should NOT have been called
        mock_migr_svc.upload_schema.assert_not_called()


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


# =============================================================================
# transfer_data
# =============================================================================

class TestTransferData:
    """Tests for transfer_data MCP tool."""

    def test_transfer_data_with_server_id_injects_pwd_into_both_connection_strings(self):
        """transfer_data with server_id retrieves password from vault and injects PWD into
        both connection_string and odbc_connection_string before calling the service."""
        from unittest.mock import patch

        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = "vault_secret"

        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        mock_migr_svc = MagicMock()
        mock_migr_svc.transfer_data.return_value = {
            "success": True,
            "job_id": "job-123",
        }

        mock_pool = MagicMock()
        mock_pool.list.return_value = {}

        mock_adapter = MagicMock()
        mock_adapter.connect.return_value = True

        schema_dict = {
            "source": "test",
            "version": "1.0",
            "tables": [
                {"name": "customers", "columns": [{"name": "ID", "source_type": "Long Integer", "allow_null": False}]},
            ],
        }

        with patch('ms_access_mcp.mcp.migration.get_container', return_value=mock_container):
            with patch('ms_access_mcp.mcp.migration._migration', return_value=mock_migr_svc):
                with patch('ms_access_mcp.mcp.migration._pool', return_value=mock_pool):
                    with patch('ms_access_mcp.mcp.migration.BackendSelector.get_adapter', return_value=mock_adapter):
                        result = migration_module.transfer_data(
                            "postgres",
                            "DRIVER={PostgreSQL};SERVER=localhost;DATABASE=test",
                            "C:/Users/MetalbolicX/db.accdb",
                            schema_json=schema_dict,
                            server_id="srv1",
                            odbc_connection_string="DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=myuser",
                        )

        assert result["success"] is True, f"Expected success but got: {result}"
        mock_vault.retrieve.assert_called_once_with("srv1")

        # Verify PWD was injected into BOTH connection strings
        call_args = mock_migr_svc.transfer_data.call_args
        _, kwargs = call_args
        conn_str_with_pwd = kwargs.get("connection_string") or call_args[0][1]
        odbc_str_with_pwd = kwargs.get("odbc_connection_string") or call_args[0][-1]
        assert "PWD=vault_secret" in conn_str_with_pwd
        assert "PWD=vault_secret" in odbc_str_with_pwd

    def test_transfer_data_with_unknown_server_id_returns_error_without_calling_connector(self):
        """transfer_data with unknown server_id returns error before connector is called."""
        from unittest.mock import patch

        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = None  # vault miss

        mock_container = MagicMock()
        mock_container.credential_vault = mock_vault

        mock_migr_svc = MagicMock()

        mock_pool = MagicMock()
        mock_pool.list.return_value = {}

        mock_adapter = MagicMock()
        mock_adapter.connect.return_value = True

        schema_dict = {
            "source": "test",
            "version": "1.0",
            "tables": [
                {"name": "customers", "columns": [{"name": "ID", "source_type": "Long Integer", "allow_null": False}]},
            ],
        }

        with patch('ms_access_mcp.mcp.migration.get_container', return_value=mock_container):
            with patch('ms_access_mcp.mcp.migration._migration', return_value=mock_migr_svc):
                with patch('ms_access_mcp.mcp.migration._pool', return_value=mock_pool):
                    with patch('ms_access_mcp.mcp.migration.BackendSelector.get_adapter', return_value=mock_adapter):
                        result = migration_module.transfer_data(
                            "postgres",
                            "DRIVER={PostgreSQL};SERVER=localhost;DATABASE=test",
                            "C:/Users/MetalbolicX/db.accdb",
                            schema_json=schema_dict,
                            server_id="unknown_srv",
                            odbc_connection_string="DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=myuser",
                        )

        assert result["success"] is False
        assert "server_id" in result["error"].lower() or "not found" in result["error"].lower()
        # Connector should NOT have been called
        mock_migr_svc.transfer_data.assert_not_called()

    def test_transfer_data_without_server_id_passes_connection_strings_as_provided(self):
        """transfer_data without server_id passes connection strings unchanged to the service."""
        from unittest.mock import patch

        mock_container = MagicMock()
        mock_container.credential_vault = MagicMock()
        mock_container.credential_vault.retrieve.return_value = None  # no server_id means no lookup

        mock_migr_svc = MagicMock()
        mock_migr_svc.transfer_data.return_value = {
            "success": True,
            "job_id": "job-456",
        }

        mock_pool = MagicMock()
        mock_pool.list.return_value = {}

        mock_adapter = MagicMock()
        mock_adapter.connect.return_value = True

        schema_dict = {
            "source": "test",
            "version": "1.0",
            "tables": [
                {"name": "customers", "columns": [{"name": "ID", "source_type": "Long Integer", "allow_null": False}]},
            ],
        }

        with patch('ms_access_mcp.mcp.migration.get_container', return_value=mock_container):
            with patch('ms_access_mcp.mcp.migration._migration', return_value=mock_migr_svc):
                with patch('ms_access_mcp.mcp.migration._pool', return_value=mock_pool):
                    with patch('ms_access_mcp.mcp.migration.BackendSelector.get_adapter', return_value=mock_adapter):
                        result = migration_module.transfer_data(
                            "postgres",
                            "DRIVER={PostgreSQL};SERVER=localhost;DATABASE=test;PWD=plaintext",
                            "C:/Users/MetalbolicX/db.accdb",
                            schema_json=schema_dict,
                            odbc_connection_string="DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=myuser;PWD=plaintext2",
                        )

        assert result["success"] is True
        # Without server_id, vault should NOT be consulted
        mock_container.credential_vault.retrieve.assert_not_called()
        call_args = mock_migr_svc.transfer_data.call_args
        _, kwargs = call_args
        odbc_str = kwargs.get("odbc_connection_string") or call_args[0][-1]
        # Passwords should remain as provided (not overwritten)
        assert "PWD=plaintext" in odbc_str or "PWD=plaintext2" in odbc_str
